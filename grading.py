"""Gear ACEScct grading with explicit wide-gamut float input/output.

Math derived from ComfyUI_Gear (MIT; vendor/GEAR-LICENSE). The upstream
Rec.709 wrapper is intentionally bypassed: our working buffer is ACEScg.
Display transforms never enter this processing path.
"""
import copy
import math
import numpy as np
import torch
from .vendor import gear_grading as gear
from .hdr_master import TO_REC2020

GEAR_REVISION = 'cee4806315e99c8adadc4710d03650146f55f5af'
SCALARS = {
    'exposure': (-10, 10, 0), 'temperature': (-1, 1, 0), 'tint': (-1, 1, 0),
    'contrast': (0, 4, 1), 'pivot': (.001, 1, .18), 'shadows': (-2, 2, 0),
    'highlights': (-2, 2, 0), 'saturation': (0, 3, 1), 'vibrance': (-2, 2, 0),
}
VECTORS = {'lift': (-1, 1, 0), 'gamma': (.1, 4, 1), 'gain': (0, 4, 1), 'offset': (-1, 1, 0)}
P3_TO_2020 = np.array([[.753833035,.198597369,.047569596],[.045743849,.941777220,.012478931],[-.001210340,.017601717,.983608623]], dtype=np.float64)
TO_2020 = {**TO_REC2020, 'linear-p3': P3_TO_2020}


def neutral_grade():
    return {**{k:v[2] for k,v in SCALARS.items()}, **{k:[v[2]]*3 for k,v in VECTORS.items()}}


def validate_grading(value=None):
    if value is None: value = {}
    if not isinstance(value, dict) or set(value)-{'balance','finish'}:
        raise ValueError('Grading must contain balance and finish settings.')
    result = {}
    for stage in ('balance','finish'):
        incoming=value.get(stage,{})
        if not isinstance(incoming,dict) or set(incoming)-set(SCALARS)-set(VECTORS):
            raise ValueError('Unknown Gear grading control.')
        result[stage]=neutral_grade()
        for key, val in incoming.items():
            schema=SCALARS.get(key) or VECTORS[key]
            values=val if key in VECTORS else [val]
            if not isinstance(values,list) or len(values)!=(3 if key in VECTORS else 1):
                raise ValueError('Color wheel values require three channels.')
            if any(type(x) not in (int,float) or not math.isfinite(x) or not schema[0]<=x<=schema[1] for x in values):
                raise ValueError(f'Invalid {stage} {key}.')
            result[stage][key]=copy.deepcopy(val)
    return result


def convert(rgb, source, destination):
    if source == destination: return rgb
    matrix=np.linalg.solve(np.asarray(TO_2020[destination],dtype=np.float64), np.asarray(TO_2020[source],dtype=np.float64))
    if isinstance(rgb,torch.Tensor):
        return rgb @ torch.as_tensor(matrix.T,dtype=rgb.dtype,device=rgb.device)
    return (rgb @ matrix.T).astype(np.float32)


def apply_grade(rgb, settings, space):
    if settings == neutral_grade(): return rgb
    numpy_input=isinstance(rgb,np.ndarray)
    tensor=torch.from_numpy(np.ascontiguousarray(rgb)) if numpy_input else rgb
    c=convert(tensor.float(),space,'linear-acescg')
    p=gear.RenderParams(**settings)
    c=c*(2.0**p.exposure)
    wb=torch.tensor([1+p.temperature*.45,1+p.tint*.35,1-p.temperature*.45],device=c.device)
    cct=gear._cct_encode(c*wb)
    luma=lambda x:gear._luma(x,gear._AP1_LUMA)
    vec=lambda x:torch.tensor(x,dtype=c.dtype,device=c.device)
    cct=cct+vec(p.offset)
    cct=cct+vec(p.lift)*(1-luma(cct)*2).clamp(0,1)
    cct=cct*vec(p.gain)
    # The log toe can be negative; identity gamma must not clip those values.
    cct=torch.sign(cct)*torch.pow(torch.abs(cct),1/vec(p.gamma))
    pivot=gear._cct_encode(torch.tensor(p.pivot,device=c.device))
    cct=(cct-pivot)*p.contrast+pivot
    luminance=luma(cct)
    cct=cct+p.shadows*torch.sigmoid(-12*(luminance-.3))*.15+p.highlights*torch.sigmoid(12*(luminance-.6))*.15
    if abs(p.vibrance)>.001:
        luminance=luma(cct)
        chroma=cct.max(dim=-1,keepdim=True).values-cct.min(dim=-1,keepdim=True).values
        cct=luminance+(cct-luminance)*(1+(1-chroma*2)*p.vibrance)
    luminance=luma(cct)
    cct=luminance+(cct-luminance)*p.saturation
    output=convert(gear._cct_decode(cct),'linear-acescg',space)
    if not torch.isfinite(output).all(): raise ValueError('Grade produced non-finite pixels.')
    return output.cpu().numpy() if numpy_input else output

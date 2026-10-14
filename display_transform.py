"""Terminal SDR viewing transform shared by live, still and SDR delivery.

Inputs remain linear float in an explicit gamut. Only the returned display
pixels are compressed/clipped; this module never edits the source or recipe.
"""
import numpy as np
import torch
from .grading import convert


def sdr_knee(recipe, hdr_eligible=False):
    mode = recipe.get('sdr_output', 'legacy')
    if mode == 'rolloff': return .7
    if mode == 'clip': return 1.
    if mode == 'legacy': return .7 if hdr_eligible else 1.
    raise ValueError('Unknown SDR output transform.')


def validate_view(value=None):
    value = {} if value is None else value
    if not isinstance(value, dict) or set(value)-{'mode','exposure','stage','comparison'}:
        raise ValueError('Invalid viewer settings.')
    result = dict(mode=value.get('mode','output'), exposure=value.get('exposure',0),
                  stage=value.get('stage','finish'), comparison=value.get('comparison','source'))
    if result['mode'] not in ('output','rolloff','clip') or result['stage'] not in ('source','film','finish') or result['comparison'] not in ('source','film'):
        raise ValueError('Unknown viewer mode or processing stage.')
    ev=result['exposure']
    if type(ev) not in (int,float) or not np.isfinite(ev) or not -10<=ev<=10:
        raise ValueError('Viewer exposure must be between -10 and 10 EV.')
    return result


def encode_sdr(rgb, source_space='linear-p3', knee=.7, exposure=0):
    """Return sRGB display codes [0,1], preserving input storage and precision."""
    light = convert(rgb.float() if isinstance(rgb,torch.Tensor) else np.asarray(rgb,dtype=np.float32),source_space,'linear-rec709') * (2.**exposure)
    if isinstance(light,torch.Tensor):
        if 0<=knee<1:
            over=(light-knee).clamp_min(0)
            light=torch.where(light>knee,knee+(1-knee)*over/(over+1-knee),light)
        light=light.clamp(0,1)
        return torch.where(light<=.0031308,light*12.92,1.055*light.pow(1/2.4)-.055).clamp(0,1)
    if 0<=knee<1:
        over=np.maximum(light-knee,0)
        light=np.where(light>knee,knee+(1-knee)*over/(over+1-knee),light)
    light=np.clip(light,0,1)
    return np.clip(np.where(light<=.0031308,light*12.92,1.055*light**(1/2.4)-.055),0,1)


def view_knee(view, recipe, eligible=False):
    return sdr_knee(recipe,eligible) if view['mode']=='output' else .7 if view['mode']=='rolloff' else 1.

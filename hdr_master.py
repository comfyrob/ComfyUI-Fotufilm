"""Lossless HDR source bundle and bounded browser float proxies."""
import json
import math
import tempfile
import zipfile
from pathlib import Path

import numpy as np
import OpenEXR

FORMAT = 'film-finish-hdr-v1'
PRIMARIES = {
    'linear-rec709': (0.64, 0.33, 0.30, 0.60, 0.15, 0.06, 0.3127, 0.3290),
    'linear-rec2020': (0.708, 0.292, 0.170, 0.797, 0.131, 0.046, 0.3127, 0.3290),
    'linear-acescg': (0.713, 0.293, 0.165, 0.830, 0.128, 0.044, 0.32168, 0.33767),
}
# D60 ACEScg to D65 Rec.2020 includes Bradford adaptation.
TO_REC2020 = {
    'linear-rec709': np.array([[.627403896, .329283038, .043313066], [.069097289, .919540395, .011362316], [.016391439, .088013308, .895595253]], dtype=np.float32),
    'linear-rec2020': np.eye(3, dtype=np.float32),
    'linear-acescg': np.array([[1.02582475, -.02005319, -.00577156], [-.00223437, 1.00458650, -.00235213], [-.00501335, -.02529007, 1.03030342]], dtype=np.float32),
}


def validate_manifest(value):
    if not isinstance(value, dict) or value.get('format') != FORMAT or value.get('colorSpace') not in PRIMARIES:
        raise ValueError('Unsupported float HDR master.')
    for name, limit in (('width', 8192), ('height', 8192), ('frames', 1200), ('proxyWidth', 1280), ('proxyHeight', 1280)):
        number = value.get(name)
        if type(number) is not int or not 1 <= number <= limit:
            raise ValueError(f'Invalid HDR master {name}.')
    if value['width'] * value['height'] > 40_000_000 or value['proxyWidth'] > value['width'] or value['proxyHeight'] > value['height']:
        raise ValueError('Invalid HDR frame dimensions.')
    fps = value.get('fps')
    if isinstance(fps, bool) or not isinstance(fps, (int, float)) or not math.isfinite(fps) or not 1 <= fps <= 120:
        raise ValueError('Invalid HDR frame rate.')
    if value.get('proxyColorSpace') != 'linear-rec2020' or value.get('proxyFormat') != 'rgba32float-le':
        raise ValueError('Unsupported HDR preview encoding.')
    if value.get('playback') not in ('playback.mp4', 'playback.mov', 'playback.webm', 'playback.m4v'):
        raise ValueError('Invalid HDR playback asset.')
    return value


def read_manifest(path):
    with zipfile.ZipFile(path) as bundle:
        info = bundle.getinfo('manifest.json')
        if info.file_size > 16384:
            raise ValueError('Invalid HDR manifest size.')
        return validate_manifest(json.loads(bundle.read(info)))


def read_member(path, name, max_size):
    with zipfile.ZipFile(path) as bundle:
        info = bundle.getinfo(name)
        if info.file_size > max_size:
            raise ValueError('HDR bundle member exceeds its expected size.')
        return bundle.read(info)


def write_master(images, fps, color_space, playback, destination, interrupt=lambda: None, proxy_edge=1280):
    import torch
    import torch.nn.functional as F
    if images.ndim != 4 or images.shape[-1] != 3 or not torch.isfinite(images).all():
        raise ValueError('Expected finite scene-linear RGB video frames.')
    count, height, width, _ = images.shape
    scale = min(1, proxy_edge / max(width, height))
    pw, ph = max(1, round(width * scale)), max(1, round(height * scale))
    suffix = Path(playback).suffix.lower()
    manifest = validate_manifest({'format': FORMAT, 'colorSpace': color_space, 'width': width, 'height': height,
        'frames': count, 'fps': float(fps), 'referenceWhite': 1, 'masterFormat': 'exr-rgb32float',
        'proxyColorSpace': 'linear-rec2020', 'proxyFormat': 'rgba32float-le', 'proxyWidth': pw, 'proxyHeight': ph,
        'playback': 'playback' + suffix})
    temporary = Path(destination).with_suffix('.part')
    try:
        with tempfile.TemporaryDirectory(prefix='film-hdr-master-') as directory, zipfile.ZipFile(temporary, 'w', allowZip64=True) as bundle:
            for index, image in enumerate(images):
                interrupt()
                rgb = image.detach().cpu().float().numpy()
                path = Path(directory) / 'frame.exr'
                OpenEXR.File({'chromaticities': PRIMARIES[color_space], 'compression': OpenEXR.ZIP_COMPRESSION},
                    {c: np.ascontiguousarray(rgb[:, :, i]) for i, c in enumerate('RGB')}).write(str(path))
                bundle.write(path, f'master/{index:06d}.exr')
                reduced = F.interpolate(torch.from_numpy(rgb).permute(2, 0, 1)[None], size=(ph, pw), mode='area')[0].permute(1, 2, 0).numpy()
                proxy = np.ones((ph, pw, 4), dtype='<f4')
                proxy[:, :, :3] = reduced @ TO_REC2020[color_space].T
                bundle.writestr(f'preview/{index:06d}.rgba32f', proxy.tobytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=1)
            bundle.write(playback, manifest['playback'])
            bundle.writestr('manifest.json', json.dumps(manifest))
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)
    return manifest

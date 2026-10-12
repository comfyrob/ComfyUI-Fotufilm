"""Full-resolution frame inspection, separate from display previews and video jobs."""
import inspect
import io
import json
import logging
import os
import tempfile
import uuid
from pathlib import Path

import numpy as np
import OpenEXR
from PIL import Image

from .grading import apply_grade, convert, validate_grading
from .hdr_master import PRIMARIES
from .preview_runtime import SourceCursor, render_stats
from .recipe import validate_recipe

STAGES = ('source', 'balance', 'film', 'finish')


def inspection_frame(source, recipe, index, stage, *, runtime=None, fingerprint=None):
    """Return one unclipped RGB32F Rec.2020 frame, always at source resolution."""
    if stage not in STAGES:
        raise ValueError('Choose source, balance, film or finish.')
    if type(index) is not int or not 0 <= index < source.info['frames']:
        raise ValueError('Frame number is outside the source.')
    recipe = validate_recipe(recipe)
    stats = render_stats()
    cursor = SourceCursor(source, None)
    try:
        if stage in ('source', 'balance'):
            rgb = (runtime.source_frame(cursor, fingerprint, index, stats)
                   if runtime else cursor.read(index))
            if stage == 'balance':
                rgb = apply_grade(rgb, validate_grading(recipe.get('grading'))['balance'], 'linear-rec2020')
        else:
            from .finish_pipeline import Finisher
            with tempfile.TemporaryDirectory(prefix='fotufilm-inspect-') as directory:
                finisher = Finisher(recipe, directory, runtime)
                try:
                    if runtime:
                        rgb = runtime.developed_frame(cursor, fingerprint, index, finisher, stats)
                    else:
                        rgb = finisher.develop(cursor.read(index), index)
                    if stage == 'finish':
                        rgb = finisher.finish(rgb)
                    # The core inspector understands Rec.2020, not Fotufilm's linear P3.
                    # This is a gamut conversion of an inspection copy, never a clamp.
                    rgb = convert(rgb, 'linear-p3', 'linear-rec2020')
                finally:
                    finisher.close()
    finally:
        cursor.close()
    return np.ascontiguousarray(rgb, dtype=np.float32), stats


def write_inspection(rgb, destination, metadata):
    """Publish an EXR atomically; the PNG is only a labelled SDR browsing thumbnail."""
    from .finish_pipeline import resize_float
    from .master_export import delivery
    rgb = np.asarray(rgb, dtype=np.float32)
    if rgb.ndim != 3 or rgb.shape[-1] != 3 or min(rgb.shape[:2]) < 1 or not np.isfinite(rgb).all():
        raise ValueError('Expected finite RGB float pixels.')
    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.part')
    metadata = {**metadata, 'colorSpace': 'linear-rec2020', 'precision': 'float32',
                'width': rgb.shape[1], 'height': rgb.shape[0], 'displayTransformBaked': False}
    try:
        OpenEXR.File({'chromaticities': PRIMARIES['linear-rec2020'], 'compression': OpenEXR.ZIP_COMPRESSION},
                    {c: np.ascontiguousarray(rgb[:, :, i]) for i, c in enumerate('RGB')}).write(str(temporary))
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    poster = path.with_suffix('.png')
    reduced = resize_float(rgb, 960)
    pixels = (delivery(convert(reduced, 'linear-rec2020', 'linear-p3'), False, .7) / 257).round().astype('uint8')
    Image.fromarray(pixels).save(poster, compress_level=1)
    path.with_suffix('.json').write_text(json.dumps(metadata, indent=2))
    return metadata


def asset_preview(path):
    """Opt into #16898's save-output protocol only when that protocol is present."""
    import folder_paths
    from server import PromptServer
    manager = getattr(getattr(PromptServer, 'instance', None), 'asset_manager', None)
    directory = getattr(folder_paths, 'get_previews_directory', None)
    register = getattr(manager, 'register_executed_output', None)
    if not (getattr(manager, 'enabled', False) and directory and callable(register)):
        return None
    if 'preview_ref' not in inspect.signature(register).parameters:
        return None
    poster = Path(path).with_suffix('.png')
    from blake3 import blake3  # Installed by ComfyUI's optional Assets dependencies.
    with Image.open(poster) as image:
        width, height = image.size
        buffer = io.BytesIO()
        image.convert('RGB').save(buffer, format='JPEG', quality=85)
    data = buffer.getvalue()
    # Core trusts this content hash and accepts only <blake3>.jpg / .webp.
    filename = blake3(data).hexdigest() + '.jpg'
    root = Path(directory())
    root.mkdir(parents=True, exist_ok=True)
    target = root / filename
    if not target.exists():
        temporary = target.with_name(target.name + '.' + uuid.uuid4().hex + '.part')
        try:
            temporary.write_bytes(data)
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)
    return {'filename': filename, 'width': width, 'height': height}


def publish_inspection(path, *, register=False):
    """Standard Comfy outputs; registration failure never hides a saved EXR."""
    from .studio_server import descriptor
    path = Path(path)
    entry = descriptor(path)
    poster = descriptor(path.with_suffix('.png'))
    warning = None
    preview = None
    asset_id = None
    try:
        preview = asset_preview(path)
        if register:
            from server import PromptServer
            manager = getattr(getattr(PromptServer, 'instance', None), 'asset_manager', None)
            if getattr(manager, 'enabled', False):
                kwargs = {'preview_ref': preview} if preview else {}
                asset = manager.register_executed_output(str(path), None, **kwargs)
                asset_id = getattr(asset, 'id', None)
            if not asset_id:
                warning = 'Saved EXR. Assets are unavailable; download it or use the inspection node in History.'
    except Exception:
        logging.warning('Fotufilm EXR saved but asset preview registration failed', exc_info=True)
        warning = 'Saved EXR. Asset registration failed; download remains available.'
    if preview:
        entry['asset_preview'] = preview
    return {'exr': entry, 'poster': poster, 'assetId': asset_id, 'warning': warning}

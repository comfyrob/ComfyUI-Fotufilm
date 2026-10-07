"""Check the Linux native ABI; actual rendering requires a GPU worker."""
import ctypes
import importlib.util
import os
import sys
import types
from pathlib import Path

root = Path(__file__).resolve().parents[1]
if sys.platform == 'linux' and (root / 'linux-runtime').is_dir():
    if '--render' not in sys.argv:
        os.environ['FOTUFILM_GPU_DEVICE'] = 'cpu'
    package = types.ModuleType('film_finish_native_check')
    package.__path__ = [str(root)]
    sys.modules[package.__name__] = package
    spec = importlib.util.spec_from_file_location('film_finish_native_check.native', root / 'native.py')
    native = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(native)
    engine = None
    try:
        try:
            engine = native.Engine()
        except RuntimeError as error:
            # The pinned Linux AOT library deliberately has no CPU developer.
            # Building without a GPU verifies loading, not engine execution.
            if '--render' in sys.argv or str(error) != 'The Halide engine is not linked into this build.':
                raise
        stocks = Path(os.environ.get('FOTUFILM_STOCKS', '/nonexistent'))
        if not (stocks / 'ektachromee100.json').is_file() or not (stocks / 'vision250d.json').is_file():
            raise RuntimeError('The pinned film-stock catalogue is not configured.')
        for name in ('libavutil.so.58', 'libswresample.so.4', 'libswscale.so.7', 'libavcodec.so.60', 'libavformat.so.60'):
            ctypes.CDLL(name)
        if engine:
            descriptor, _ = engine.call('importPath', {'path': str(root / 'tests/codec-smoke.mp4')})
            if 'video' not in descriptor:
                raise RuntimeError('Fotufilm did not recognize the codec fixture as video')
            if '--render' in sys.argv:
                import json
                import tempfile
                import numpy as np
                import OpenEXR
                from film_finish_native_check.recipe import render_request
                recipe = json.loads((root / 'examples/vision250d-clean.recipe.json').read_text())
                with tempfile.TemporaryDirectory() as directory:
                    path = str(Path(directory) / 'smoke.exr')
                    rgb = np.full((32, 32), .18, dtype=np.float32)
                    OpenEXR.File({'chromaticities': (.64, .33, .30, .60, .15, .06, .3127, .3290)},
                                 {c: rgb.copy() for c in 'RGB'}).write(path)
                    result = engine.render_float(path, 32, 32, render_request(recipe, 1, edge=None))
                    if result.shape != (32, 32, 3) or not np.isfinite(result).all() or result.max() <= 0:
                        raise RuntimeError('Invalid native render output.')
                print('GPU render passed: finite 32x32 linear Display P3 float frame.')
        print('ComfyUI-Fotufilm native libraries and FFmpeg ABI loaded.')
    finally:
        if engine:
            engine.close()
else:
    raise SystemExit('This check requires the installed Linux runtime.')

"""Stream a float HDR source through Fotufilm; encode only at final delivery."""
import json
import subprocess
import tempfile
import zipfile
from fractions import Fraction
from pathlib import Path

import imageio_ffmpeg
import numpy as np
import OpenEXR

from .hdr_master import read_manifest
from .native import Engine
from .recipe import render_request, validate_recipe

P3_TO_709 = np.array([[1.2249401, -.2249404, 0], [-.0420569, 1.0420571, 0], [-.0196376, -.0786361, 1.0982735]], dtype=np.float32)
P3_TO_2020 = np.array([[.753833035, .198597369, .047569596], [.045743849, .941777220, .012478931], [-.001210340, .017601717, .983608623]], dtype=np.float32)
HLG_WHITE = (np.exp((.75 - .55991073) / .17883277) + .28466892) / 12
HDR_CEILING = (1 / HLG_WHITE) ** 1.2


def delivery(linear_p3, hdr, knee):
    # Port of Fotufilm PrintEncoding / HLGTransfer (Apache-2.0), matching browser delivery.
    if hdr:
        positive = np.maximum(linear_p3, 0)
        peak = np.max(positive, axis=-1, keepdims=True)
        over = np.maximum(peak - .9, 0)
        rolled = np.where(peak <= .9, peak, .9 + (HDR_CEILING - .9) * over / (over + HDR_CEILING - .9))
        wide = np.maximum((positive * np.divide(rolled, peak, out=np.zeros_like(peak), where=peak > 1e-6)) @ P3_TO_2020.T, 0)
        y = wide @ np.array([.2627, .6780, .0593], dtype=np.float32)
        light = wide * np.where(y > 1e-6, np.maximum(y, 1e-6) ** (-1 / 6), 0)[..., None] * HLG_WHITE
        light = np.clip(light, 0, 1)
        encoded = np.where(light <= 1 / 12, np.sqrt(3 * light), .17883277 * np.log(np.maximum(12 * light - .28466892, 1e-8)) + .55991073)
    else:
        light = linear_p3 @ P3_TO_709.T
        if 0 <= knee < 1:
            over = np.maximum(light - knee, 0)
            light = np.where(light > knee, knee + (1 - knee) * over / (over + 1 - knee), light)
        light = np.clip(light, 0, 1)
        encoded = np.where(light <= .0031308, light * 12.92, 1.055 * light ** (1 / 2.4) - .055)
    return np.rint(np.clip(encoded, 0, 1) * 65535).astype('<u2')


def export_master(bundle_path, recipe, format_id, destination, interrupt=lambda: None):
    recipe = validate_recipe(recipe)
    manifest = read_manifest(bundle_path)
    engine = Engine()
    process = None
    try:
        with tempfile.TemporaryDirectory(prefix='film-master-export-') as directory, zipfile.ZipFile(bundle_path) as bundle:
            directory = Path(directory)
            playback = directory / manifest['playback']
            info = bundle.getinfo(manifest['playback'])
            if info.file_size > 2 * 1024 ** 3:
                raise ValueError('Invalid playback asset size.')
            with bundle.open(info) as source, playback.open('wb') as target:
                import shutil
                shutil.copyfileobj(source, target)
            frame_path = directory / 'frame.exr'
            request = render_request(recipe, recipe['seed'] or 0, edge=None)
            first = bundle.getinfo('master/000000.exr')
            if first.file_size > 256 * 1024 ** 2:
                raise ValueError('Invalid EXR frame size.')
            frame_path.write_bytes(bundle.read(first))
            descriptor, _ = engine.call('importPath', {'path': str(frame_path)})
            # The native profile owns HDR eligibility. Linux's still-encoder availability is irrelevant.
            profiles, _ = engine.call('prepare')
            stock = next((item for item in profiles['catalogue'] if item['id'] == recipe['stock']), None)
            if stock is None:
                raise ValueError('Film stock unavailable.')
            # Stock records are bundled with the pinned native engine for Linux and macOS.
            from .runtime_paths import stocks_path
            stocks_root = stocks_path()
            stock_data = json.loads((stocks_root / (recipe['stock'] + '.json')).read_text())
            carries_hdr = (stock_data.get('isReversal', False) and not stock_data.get('isReflectionPrint', False)
                and recipe['medium'] == 'screen' and recipe['digitalReference'] == 'reference-exposure')
            if format_id == 'hlg' and not carries_hdr:
                raise ValueError('HDR delivery needs a direct-view slide-film finish with Reference exposure.')
            engine.call('release', {'handle': descriptor['handle']})
            knee = .7 if carries_hdr else 1
            width, height = manifest['width'], manifest['height']
            fps = Fraction(manifest['fps']).limit_denominator(100000)
            hdr = format_id == 'hlg'
            matrix = 'bt2020' if hdr else 'bt709'
            args = [imageio_ffmpeg.get_ffmpeg_exe(), '-hide_banner', '-loglevel', 'error', '-y',
                '-f', 'rawvideo', '-pixel_format', 'rgb48le', '-video_size', f'{width + width % 2}x{height + height % 2}', '-framerate', str(fps), '-i', 'pipe:0',
                '-i', str(playback), '-map', '0:v:0', '-map', '1:a?', '-vf', f'scale=in_color_matrix={matrix}:out_color_matrix={matrix}',
                '-c:a', 'aac', '-af', 'apad', '-shortest']
            if format_id == 'prores422hq':
                args += ['-c:v', 'prores_ks', '-profile:v', '3', '-pix_fmt', 'yuv422p10le']
            elif hdr:
                args += ['-c:v', 'libx265', '-preset', 'medium', '-crf', '12', '-pix_fmt', 'yuv420p10le', '-tag:v', 'hvc1',
                         '-x265-params', 'colorprim=bt2020:transfer=arib-std-b67:colormatrix=bt2020nc:range=limited']
            else:
                args += ['-c:v', 'libx264', '-preset', 'medium', '-crf', '16', '-pix_fmt', 'yuv420p']
            args += ['-color_primaries', 'bt2020' if hdr else 'bt709', '-color_trc', 'arib-std-b67' if hdr else 'iec61966-2-1',
                '-colorspace', 'bt2020nc' if hdr else 'bt709', '-movflags', '+faststart', str(destination)]
            with (directory / 'encoder.log').open('w+b') as log:
                process = subprocess.Popen(args, stdin=subprocess.PIPE, stderr=log, stdout=subprocess.DEVNULL)
                for index in range(manifest['frames']):
                    interrupt()
                    info = bundle.getinfo(f'master/{index:06d}.exr')
                    if info.file_size > 256 * 1024 ** 2:
                        raise ValueError('Invalid EXR frame size.')
                    frame_path.write_bytes(bundle.read(info))
                    with OpenEXR.File(str(frame_path), header_only=True) as image:
                        low, high = image.header()['dataWindow']
                        if tuple(high - low + 1) != (width, height):
                            raise ValueError('EXR dimensions do not match the master manifest.')
                    request['edit']['seed'] = ((recipe['seed'] or 0) + index * 0x7f4a7c15) & 0xffffffff
                    rgb = engine.render_float(str(frame_path), width, height, request)
                    if not np.isfinite(rgb).all():
                        raise ValueError('Fotufilm produced non-finite output.')
                    if width % 2 or height % 2:
                        rgb = np.pad(rgb, ((0, height % 2), (0, width % 2), (0, 0)), mode='edge')
                    process.stdin.write(delivery(rgb, hdr, knee).tobytes())
                process.stdin.close()
                if process.wait(timeout=300):
                    log.seek(0)
                    raise ValueError('Video encoding failed: ' + log.read(1600).decode(errors='replace'))
            Path(destination).with_suffix('.recipe.json').write_text(json.dumps(recipe, indent=2))
    except Exception:
        if process and process.poll() is None:
            process.kill()
            process.wait()
        Path(destination).unlink(missing_ok=True)
        raise
    finally:
        engine.close()

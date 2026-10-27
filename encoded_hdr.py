"""Tagged BT.2020 HLG/PQ to linear BT.2020 relative to HDR diffuse white.

HLG: BT.2100 reference display (1000 nits, gamma 1.2, zero black), 75% white.
PQ: ST 2084 absolute luminance / 203 nits. This interprets a finished HDR
signal; it cannot reconstruct scene radiance discarded during mastering.
"""
from fractions import Fraction
from pathlib import Path
import os
import subprocess
import tempfile

import av
import imageio_ffmpeg
import numpy as np

HLG_A, HLG_B, HLG_C = .17883277, .28466892, .55991073
HLG_WHITE = float((np.exp((.75 - HLG_C) / HLG_A) + HLG_B) / 12)


def linearize_hdr(encoded, transfer):
    value = np.maximum(np.asarray(encoded, dtype=np.float32), 0)
    if transfer == 18:
        scene = np.where(value <= .5, value * value / 3,
                         (np.exp((value - HLG_C) / HLG_A) + HLG_B) / 12)
        luminance = scene @ np.array([.2627, .6780, .0593], dtype=np.float32)
        return scene * np.maximum(luminance, 0)[..., None] ** .2 / HLG_WHITE ** 1.2
    if transfer == 16:
        power = value ** (1 / (2523 / 32))
        light = (np.maximum(power - 3424 / 4096, 0) /
                 np.maximum(2413 / 128 - (2392 / 128) * power, 1e-8)) ** (1 / (2610 / 16384))
        return light * (10000 / 203)
    raise ValueError('Expected tagged HLG or PQ video.')


def decode_rgb(frame, transfer, *, width=None, height=None):
    """Explicit YUV matrix/range; 16-bit RGB codes before transfer decoding."""
    rgb = frame.reformat(width=width, height=height, format='rgb48le',
                         src_colorspace=9, dst_colorspace=9,
                         src_color_range=int(frame.color_range) or 1,
                         dst_color_range=2).to_ndarray()
    return linearize_hdr(rgb.astype(np.float32) / 65535, transfer)


def linearize_hdr_tensor(encoded, transfer):
    """The reference HLG/PQ math in float32, without returning to the CPU."""
    import torch
    value = encoded.to(dtype=torch.float32).clamp_min(0)
    if transfer == 18:
        scene = torch.where(value <= .5, value * value / 3,
                            (torch.exp((value - HLG_C) / HLG_A) + HLG_B) / 12)
        luminance = scene[..., 0] * .2627 + scene[..., 1] * .6780 + scene[..., 2] * .0593
        return scene * luminance.clamp_min(0).unsqueeze(-1).pow(.2) / HLG_WHITE ** 1.2
    if transfer == 16:
        power = value.pow(1 / (2523 / 32))
        light = ((power - 3424 / 4096).clamp_min(0) /
                 (2413 / 128 - (2392 / 128) * power).clamp_min(1e-8)).pow(1 / (2610 / 16384))
        return light * (10000 / 203)
    raise ValueError('Expected tagged HLG or PQ video.')


def processing_rgb(frame, transfer, edge=None):
    """Linearize at source resolution; resize linear light on CUDA when present.

    Upload the compact uint16 RGB codes once. Only the selected-size float
    result returns to the host for Fotufilm's current memory-input ABI. This
    preserves the existing decode matrix, area filter, dimensions and range.
    The playback proxy is never a processing input.
    """
    import torch
    from .finish_pipeline import resize_float
    if not torch.cuda.is_available():
        return resize_float(decode_rgb(frame, transfer), edge)
    encoded = frame.reformat(format='rgb48le', src_colorspace=9, dst_colorspace=9,
                             src_color_range=int(frame.color_range) or 1,
                             dst_color_range=2).to_ndarray()
    with torch.inference_mode():
        codes = torch.from_numpy(encoded).to(device='cuda').to(dtype=torch.float32) / 65535
        rgb = linearize_hdr_tensor(codes, transfer)
        height, width = rgb.shape[:2]
        if edge and max(width, height) > edge:
            scale = edge / max(width, height)
            rgb = torch.nn.functional.interpolate(rgb.permute(2, 0, 1)[None],
                size=(max(1, round(height * scale)), max(1, round(width * scale))),
                mode='area')[0].permute(1, 2, 0)
        return rgb.contiguous().cpu().numpy()


def playback_proxy(source, destination, edge=768):
    """SDR transport/audio copy only; never used as a processing source.

    Only this proxy resizes before linearization. Source.frames() linearizes
    at original resolution before resizing for film processing.
    """
    from .display_transform import encode_sdr
    destination = Path(destination)
    scale = min(1, edge / max(source.info['width'], source.info['height']))
    width, height = [max(2, round(source.info[k] * scale / 2) * 2) for k in ('width', 'height')]
    fps = Fraction(source.info['fps']).limit_denominator(100000)
    with tempfile.TemporaryDirectory(dir=destination.parent, prefix='hdr-playback-') as directory:
        output = Path(directory) / 'preview.mp4'
        command = [imageio_ffmpeg.get_ffmpeg_exe(), '-hide_banner', '-loglevel', 'error', '-y',
                   '-f', 'rawvideo', '-pixel_format', 'rgb24', '-video_size', f'{width}x{height}',
                   '-framerate', str(fps), '-i', 'pipe:0', '-i', str(source.path),
                   '-map', '0:v:0', '-map', '1:a?', '-map_metadata', '-1',
                   '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '18', '-pix_fmt', 'yuv420p',
                   '-vf', 'scale=in_color_matrix=bt709:out_color_matrix=bt709',
                   '-color_primaries', 'bt709', '-color_trc', 'iec61966-2-1', '-colorspace', 'bt709',
                   '-bsf:v', 'h264_metadata=colour_primaries=1:transfer_characteristics=13:matrix_coefficients=1',
                   '-c:a', 'aac', '-af', 'apad', '-t', str(source.info['duration']),
                   '-movflags', '+faststart+write_colr', str(output)]
        with (Path(directory) / 'encode.log').open('w+b') as log:
            process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=log)
            try:
                with av.open(str(source.path)) as container:
                    stream = container.streams.video[0]
                    stream.thread_type = 'AUTO'
                    for frame in container.decode(stream):
                        rgb = decode_rgb(frame, source.transfer, width=width, height=height)
                        display = encode_sdr(rgb, 'linear-rec2020')
                        process.stdin.write(np.rint(display * 255).astype('uint8').tobytes())
                process.stdin.close()
                if process.wait(timeout=120):
                    log.seek(0)
                    raise RuntimeError('HDR playback preparation failed: ' + log.read(1000).decode(errors='replace'))
                from .video_delivery import repair_h264_color
                repair_h264_color(output)
                os.replace(output, destination)
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait()
                if process.stdin and not process.stdin.closed:
                    try:process.stdin.close()
                    except BrokenPipeError:pass

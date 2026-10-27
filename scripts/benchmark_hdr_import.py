"""Compare HDR source processing on one CUDA worker, without AI inference.

Run inside Comfy's Python environment:
  python scripts/benchmark_hdr_import.py /path/to/hdr.mp4 --comfy /comfyui \
    --full-clip --output /tmp/hdr-performance.json

Reports server throughput, NOT browser playback FPS. The reference keeps the
previous CPU HDR conversion; CUDA film, grading and encoding are unchanged.
"""
import argparse
import json
import statistics
import struct
import sys
import tempfile
import time
import types
from pathlib import Path
from unittest.mock import patch


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('video', type=Path)
    parser.add_argument('--comfy', type=Path, default=Path('/comfyui'))
    parser.add_argument('--frames', type=int, default=32)
    parser.add_argument('--full-clip', action='store_true')
    parser.add_argument('--output', type=Path, required=True)
    options = parser.parse_args()
    sys.path.insert(0, str(options.comfy))
    sys.argv = ['benchmark', '--cpu']  # No Comfy model initialization.
    import comfy.options
    comfy.options.enable_args_parsing()
    root = Path(__file__).resolve().parents[1]
    pack = types.ModuleType('film_finish'); pack.__path__ = [str(root)]
    sys.modules['film_finish'] = pack
    import av
    import numpy as np
    import torch
    from film_finish import encoded_hdr
    from film_finish.finish_pipeline import Source, resize_float
    from film_finish.preview_runtime import PreviewRuntime
    from film_finish.live_preview import LiveRenderer
    if not torch.cuda.is_available():
        raise RuntimeError('Run on the target CUDA worker, not a local CPU-only install.')
    source = Source(options.video)
    if not source.info.get('encodedHDR'):
        raise ValueError('Choose a tagged HLG/PQ movie.')
    if source.info['frames'] < 3:
        raise ValueError('Use at least three frames to separate initialization from steady playback.')
    options.output.parent.mkdir(parents=True, exist_ok=True)
    recipe = json.loads((root/'examples/vision250d-clean.recipe.json').read_text())
    report = dict(gpu=torch.cuda.get_device_name(), source=source.info,
                  engine=json.loads((root/'runtime/float-engine-lock.json').read_text())['upstreamCommit'],
                  recipe=recipe, torchThreads=torch.get_num_threads(), memoryCacheMiB=4096, runs=[], parity=[])
    accelerated = encoded_hdr.processing_rgb

    def reference(frame, transfer, edge=None):
        return resize_float(encoded_hdr.decode_rgb(frame, transfer), edge)

    # Check actual clip colors before measuring speed. GPU float32 math need
    # not be bit-identical to NumPy, but must retain range and numerical parity.
    with av.open(str(source.path)) as container:
        stream = container.streams.video[0]; stream.thread_type = 'AUTO'
        for index, frame in enumerate(container.decode(stream)):
            if index not in (0, 8, 16):
                continue
            for edge in (960, 1280):
                expected = reference(frame, source.transfer, edge)
                actual = accelerated(frame, source.transfer, edge)
                np.testing.assert_allclose(actual, expected, rtol=1e-4, atol=2e-5)
                report['parity'].append(dict(frame=index, edge=edge,
                    maxAbsError=float(np.max(np.abs(actual-expected))), peak=float(actual.max())))
            if index == 16:
                break

    count = min(max(3, options.frames), source.info['frames'])
    cases = [('cpu-reference', reference, count), ('cuda', accelerated, count)]
    if options.full_clip:
        cases.append(('cuda-full-clip', accelerated, source.info['frames']))
    for name, process, length in cases:
        for edge in (1280, 960):
            with patch.object(encoded_hdr, 'processing_rgb', process), tempfile.TemporaryDirectory() as directory:
                runtime = PreviewRuntime(Path(directory)/'cache', name, disk_limit=0, memory_limit=4*1024**3)
                renderer = LiveRenderer({'source':source, 'fingerprint':'benchmark'}, edge, runtime)
                try:
                    for pass_name in ('first-pass', 'replay'):
                        rows, elapsed = [], []
                        first_ms = None
                        for index in range(length):
                            start = time.perf_counter()
                            packet = renderer.render(recipe, index, False, 1)
                            duration = time.perf_counter()-start
                            n = struct.unpack('!I', packet[:4])[0]
                            meta = json.loads(packet[4:4+n])
                            assert meta['frame'] == index
                            if index == 0:
                                first_ms = round(duration*1000, 2)
                            if index > 1:
                                rows.append(meta); elapsed.append(duration)
                        result = dict(path=name, edge=edge, passName=pass_name,
                            framesVerified=length, timedFrames=len(rows), firstFrameMs=first_ms,
                            serverFPS=round(len(elapsed)/sum(elapsed), 2),
                            medianMs={k:round(statistics.median(row['ms'][k] for row in rows), 2) for k in rows[0]['ms']},
                            p95Ms=round(float(np.percentile([row['ms']['total'] for row in rows], 95)), 2),
                            encoder=rows[0]['encoder'], memoryInput=rows[0]['memoryInput'])
                        report['runs'].append(result)
                        options.output.write_text(json.dumps(report, indent=2))
                        print(json.dumps(result), flush=True)
                finally:
                    renderer.close(); runtime.close()


if __name__ == '__main__':
    main()

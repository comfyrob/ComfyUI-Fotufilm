# HDR import performance — 27 October 2026

The encoded HLG/PQ import added in `eb62d68` (merged into main at `a1b4448`) performed full-resolution HDR transfer conversion in NumPy on the CPU. SDR already used CUDA. Changing the preview from 1280px to 960px barely helped because both sizes first paid for that full-resolution CPU conversion.

The fix uploads RGB16 decoded samples to CUDA, performs the same float32 HLG/PQ conversion at source resolution, and resizes in linear light using the existing area filter. Only the selected-size float result returns to host memory for Fotufilm's current ABI. Film, grading, encoding, engine revision and selected preview size are unchanged. CPU-only hosts retain the previous path. Export still processes the original resolution.

## Controlled measurements

Isolated Modal RTX PRO 6000 Blackwell Server Edition, 16 CPUs, 32 GiB host RAM. No AI inference or active user session was involved. Engine `9242d189`, CUDA StrictFloat float-memory input, Vision3 250D clean recipe with grain 0.55, NVENC H.264, 4 GiB preview cache and disk cache disabled.

Input: the reported 3840×2176 H.264 High 10 HLG clip, 48 fps, 409 frames. These are **server processing and encoding measurements**, not delivered browser FPS. They exclude WebSocket delivery, browser decoding and presentation. First two frames are excluded from steady-state throughput; initialization is recorded separately.

Same worker, same first 32 frames, empty frame caches per path/size:

| Preview | Previous HDR path | CUDA HDR path | Median processing before → after |
| --- | ---: | ---: | ---: |
| 1280px | 5.05 fps | 42.43 fps | 200.93 → 20.44 ms |
| 960px | 5.11 fps | 61.37 fps | 193.34 → 14.37 ms |

On an earlier worker the old path took approximately 403 ms at 1280px, consistent with the reported ~400 ms. CPU throughput varied between workers, so that number is **not** used as the paired speedup claim.

Full-clip validation of the fix, all 409 frame indices verified in order:

| Preview | First-pass server throughput | Median processing | 95th percentile |
| --- | ---: | ---: | ---: |
| 1280px | 50.15 fps | 19.50 ms | 21.93 ms |
| 960px | 66.73 fps | 14.14 ms | 18.73 ms |

The full clip exceeds the cache budget. Replay remained 51.75 / 78.57 server fps at 1280 / 960px; it was not a wholly cached replay. A short 32-frame replay fits in cache and is much faster, but those numbers should not be advertised as uncached rendering performance.

Cold native-engine initialization remains: the first render in the process took 9.4 seconds. Later first-frame setup in the already-warm process took roughly 0.6–1 second. The fix improves sustained HDR playback; it does not eliminate cold startup or source playback-copy preparation.

## Quality and regression checks

- Original resolution is linearized before preview resizing; no pre-linearization downscale, reduced precision, replacement LUT or skipped video frames.
- Actual HDR source frames 0, 8 and 16 match the CPU reference at 960 and 1280px. Worst absolute channel difference: **2.63×10⁻⁶**, with HDR values above 4 retained. GPU/CPU float math is numerically equivalent within tolerance, not bit-identical.
- HLG and PQ tests cover full-size and resized CUDA output, colored highlights, reference white, timing, audio, and seek behavior.
- **40 focused tests passed on CUDA, zero skipped**: encoded HDR, grading, EXR masters, export ranges, native video output, preview caching, frame order, and live encoding. OpenImageIO emitted a binding-reference warning at interpreter shutdown after the successful run; no test failed.

The SDR code path is unchanged. A 1280×726 SDR control derived from the same clip was tested against the previous `Source` implementation. Sampled source pixels are bit-identical. An initial short 960px run had an inconsistent timing result, so the control was repeated three times with alternating before/after order and 128 frames per pass. Median first-pass server throughput was 28.19 → 29.75 fps at 1280px and 41.19 → 44.44 fps at 960px. These checks showed no consistent SDR regression; the small differences are not claimed as an SDR optimization. This control used a separate worker from the HDR benchmark, so absolute times are not comparable across the two tables.

Recorded reports: [HDR paired and full-clip measurements](benchmarks/2026-10-27-hdr-import.json), [repeated SDR control](benchmarks/2026-10-27-sdr-control.json). No source media is included.

## Reproduce

Inside the target CUDA ComfyUI Python environment, using the installed pack's native runtime:

```sh
python scripts/benchmark_hdr_import.py /path/to/tagged-hdr.mp4 \
  --comfy /comfyui --full-clip --output /tmp/hdr-performance.json
```

This compares the previous CPU source conversion with the new CUDA path on the same worker. The engine and all later stages stay identical. It performs actual source-color parity assertions before timing, uses a fresh cache for each case, and reports initialization, first-pass, replay, frame counts, encoder and stage timings.

Next user-facing verification is the node's **delivered FPS** and slider response on the normal remote connection after pulling the fix. Faster server throughput creates room for real-time delivery; it is not a guarantee of a particular displayed frame rate for every stock, video, network or simultaneous workload.

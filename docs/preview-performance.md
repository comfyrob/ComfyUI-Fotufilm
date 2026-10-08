# Studio preview optimization

## Behavior

- Reuse one native Fotufilm engine on the Studio worker. Graph nodes retain independent lifetimes.
- Cache source frames and developed, pre-finish **float32 linear P3** pixels. No SDR display transform or quantization enters these caches.
- A finish-grade edit runs only the new finishing grade and output conversion for cached frames. Balance/film changes rerun Fotufilm. Keys include the pipeline source signature, source fingerprint, frame, effective preview size, full native render request, balance grade and grain seed.
- Keep 192 MiB of float pixels in RAM and up to 4 GiB of uncompressed NPY on temporary disk. Oversized frames bypass the relevant cache; eviction only costs a recomputation. Encoded previews retain their separate 2 GiB budget. This does not include engine allocations or working buffers.
- Interactive current-frame work has priority over playback, exports and thumbnails. Video encoders and decoders stay open while their generator yields between frames. Work resumes at the following frame; cancellation closes the process and removes partial video output.
- Wait 100 ms to coalesce slider edits. Once a still is ready, allow another 400 ms for changes to settle before starting the playback update. Current-frame polling uses 80 ms intervals. Newer edits supersede old work; aborted playback requests can be retried.
- Share before-frame PNGs when only finishing controls change. PNG compression level 1 encodes faster than the previous default level 6, with identical decoded pixels. Files can be larger.

## Measured comparison

Isolated Modal L4, 4 CPU cores, native backend reports CUDA. Source: **960×540 / 24 fps**, Vision3 250D, grain **0.55**, balance exposure **+0.25 EV**, finishing saturation varied. Same frame sizes, frame indices, seeds, float pipeline and encoder settings in both paths. Baseline: `finish_pipeline.py` from commit `296a4ed`. Timings include server rendering and file creation, **not browser/network latency**.

| Operation | Previous path | Optimized path | Ratio |
|---|---:|---:|---:|
| Finish-grade still, median of three changes | 1.060 s | 0.188 s | 5.65× faster |
| Balance-grade still, one change | 1.067 s | 0.346 s | 3.08× faster |
| Finish-grade playback update, all 24 frames | 9.640 s | 2.136 s | 4.51× faster |

The 24-frame update had 24 film-cache hits. Still PNGs and every decoded video frame matched baseline pixels exactly, with grain enabled. The float HDR cache also has a pre-display native parity regression test. The preview PNG grew from approximately 625 KB to 725 KB for the measured finishing grades. The unchanged before image can now be reused.

These are warm-edit measurements. The baseline's first cold native render took 14.19 s; initial kernel compilation is still required after a fresh process starts. Preparing the optimized playback cache took 8.08 s for 24 frames. This is not a claim of 24 fps continuous film recalculation, or a guarantee for other stocks, resolutions or workers.

Run `python scripts/benchmark_previews.py /path/to/video.mp4` on a render worker. Optional `--baseline /path/to/previous_finish_pipeline.py` compares with the previous implementation. The script asserts exact output parity and leaves no persistent outputs. It does not load AI models.

## Remaining work

The native input bridge still uses a float EXR handoff when film must be recomputed. Gear grading remains on CPU, and playback swaps after the complete clip is encoded. A direct float input ABI, GPU grading and progressive playback are separate follow-up work; they are not implied by these measurements. The viewer continues to use the existing SDR display conversion of HDR float processing.

## Integration checks

The isolated Nodes 2.0 browser test loaded the source without executing the graph, updated a finishing grade, recovered from rapid change/revert edits, and played a 960×540 rendered clip at playback rate 1 with before/after enabled. A paused frame reported `film reused`. This checks functioning playback, not measured display FPS.

A concurrent API check submitted a current-frame request while a 120-frame playback render was running. The frame waited 0.152 s in the queue and completed while playback was at 5%; cancellation then stopped the clip. A separate synthetic HDR-master request reused its native float film output and the exact same before-image URL after a finishing-grade edit. Tests used isolated workers without AI models or persistent user volumes; the main ComfyUI worker was not restarted.

Final regression run: **26 tests passed** on the isolated native CPU runtime. Coverage includes exact cached/uncached still and clip pixels with grain, float-HDR parity before display conversion, invalidation, source/frame/seed changes, memory/disk bounds, cancellation cleanup, priority/resume order, existing audio/timing and HLG/ProRes tags, and workflow graph contracts.

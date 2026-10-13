# Continuous Studio preview

For the 0.3.1 numeric controls, correction-preserving looks, coalesced gesture
transport, timing measurements and short exports, see
[Studio interaction upgrade](interaction-upgrade.md). The underlying native
engine and float-memory ABI below remain pinned to v1.11.

Studio is a ComfyUI DOM widget: inline with Nodes 2.0 or opened in a larger
ComfyUI dialog. It does not launch a separate application or inference server.

## Processing and graph

```
Load Video ── LTX reconstruction ── linear ACEScg IMAGE ── Studio
      │                                  │                 │
      └──────── source/audio ─────────────┤                 recipe
                                         ├── optional HDR archive
                                         └── optional final export
```

The source video supplies original comparison, transport and audio. Studio holds
a reference to the generated float frames; it does not write/read an EXR archive
to accept them. They become available after the graph executes LTX once. Existing
SDR Load Video files can be opened before execution. Frames expire on server
restart/eviction; the optional archive is the durable version.

Within Studio: **Gear balance → Fotufilm → Gear finish → monitor conversion**.
Balance changes what exposes the film. Finish changes the developed result and
can reuse the expensive film computation. Export reads original float frames and
the saved recipe, independently of the monitor encoding.

## Interactive transport

- One same-origin WebSocket, one warm native engine, one sequential decoder.
- Decode one frame ahead while the current frame is developed. No automatic
  source-frame skipping, quality reduction or reduced texture settings.
- CUDA float32 Gear math; native Fotufilm CUDA development with its pinned
  spectral profiles, film response, grain and spatial effects.
- H.264 NVENC monitor packets go directly to WebCodecs in the custom node.
  Software H.264 encoding is a compatibility fallback on the **server**.
- The acknowledgement window adapts to measured round-trip latency (3–12 frames). New slider revisions supersede older
  revisions; stale frames are decoded if needed for dependencies but not shown.
- Before/after is encoded together from the same source frame. Pausing sends a
  lossless PNG of the SDR display pixels. There is no full MP4 job per edit.
- Look thumbnails run while paused, below interactive frames in worker priority.
- Preview choice is 1280 or 1920 pixels on the long edge, capped at source size.
  The status shows actual dimensions, delivered fps and per-frame processing ms.

The moving preview is compressed 8-bit SDR with a display transform, **not native
HDR monitoring**. HDR processing stays float and retains above-white values.
An HDR-capable display alone does not make this SDR transport an HDR monitor.
Use full-resolution EXR inspection or eligible HLG export to assess HDR output.

## Runtime and precision

`install.py` installs both the original runtime and the checksum-pinned
`libfotufilm-float.so` from this pack's release. CUDA hosts select the extension;
Vulkan/CPU hosts retain the upstream runtime. `FOTUFILM_LIBRARY` overrides this
selection. Restart/rebuild the Comfy server after installing.

The additive memory entry point is implemented in `runtime/ComfyFloatInput.swift`.
It accepts linear Rec.2020 RGBA32F and invokes the normal Fotufilm render function.
The CUDA-only AOT build keeps upstream StrictFloat schedules and all 38 feature
variants; it does not use the engine's approximate realtime mode.

The older file-input fallback writes FLOAT EXR, but upstream v1.11's
`Sources/CFotufilmCodecs/DecodeEXR.cpp` reads via `Imf::RgbaInputFile`/`Imf::Rgba`,
which quantizes to half before converting back to float. The memory extension
avoids that quantization as well as disk/codec work. Parity tests compare
half-representable HDR values so that the comparison tests color/film behavior,
not that known precision difference. Direct input remains float32.

Rebuild sources: Fotufilm commit `f602857a031a6a9c9b0966284ff989eb3046c323`,
Swift 6.2 on Ubuntu Noble, Halide 21.0.0 Linux x86-64 SDK, upstream codec development
packages. With a clean checkout and `HALIDE_ROOT` configured, run
`bash scripts/build_linux_float.sh /path/to/fotufilm`. The patch is deliberately
version-locked; it must not be applied to arbitrary newer engine revisions.
The release bundle includes the additive sources and upstream notices. Engine
and stock attribution remain in `upstream/`; SDK/runtime components retain their
licenses. Binary digests and build provenance are in `runtime/float-engine-lock.json`.

## Resource limits

Float caches are lossless and bounded: Studio uses up to 4 GiB RAM by default,
allocated only as frames are visited. Set `FOTUFILM_PREVIEW_CACHE_MB` (64–16384) to
fit the worker. File-based inspection/export can also use the existing 4 GiB
float disk cache. Live playback does not write each frame to disk. Upstream
IMAGE references have a separate 8 GiB aggregate registry budget. Native engine,
active frames and inference memory are additional; run one Studio editor while
benchmarking. Large clips exceeding the cache are recomputed on replay.

## Validation status

Prepared: streaming protocol, direct HDR graph, optional outputs, native memory
extension and installer. The tests verify frame order, cache invalidation,
float/color parity, graph connections, encoder delivery, exports and cancellation.
See the release notes for measured remote execution and deployed test status.

Cold engine/driver initialization and first use of a film can still be slow.
A fresh film pass, cached replay and finish-only grading have different costs;
none should be presented as the other's frame-rate result. Network latency,
comparison mode, resolution and recipe also affect delivery. LTX inference is
not part of the interactive loop and is not expected to run in real time.

### Executed on 2026-10-12

Remote RTX PRO 6000, 16 requested CPU cores, ComfyUI 0.39.0/frontend 1.55.14,
Fotufilm v1.11 with the float extension. A five-second 24fps demo was upscaled to
1280×720 **as a workload fixture**, not as evidence of image-quality improvement.
Vision3 250D with grain, +0.25 EV input grade and 0.85 finishing saturation:

| Measured path | Result |
|---|---:|
| First 120-frame pass, network client, after first-frame initialization | 23.82 fps |
| Cached 120-frame replay, network client | 24.48 fps |
| First-pass median server processing | 30.98 ms/frame |
| Cached median server processing | 4.27 ms/frame |
| First frame following finish-grade change, server processing | 5.83 ms |

The client checked all 120 frame indices in sequence on both passes. The slight
replay excess over 24 is measurement/network burst timing, not a higher source
rate. Initial native/driver startup in separate tests took about 17–26 seconds;
container startup is additional. These results do not establish 24fps for every
film, 1080p, dual-source comparison, or all networks.

43 Python tests passed on the RTX worker and five JavaScript tests passed locally.
Nodes 2.0 was enabled in the actual ComfyUI interface; live playback, finishing
saturation, timeline seeking, lossless pause and pointer dragging of the
before/after divider were checked. HDR float input and native parity were tested;
LTX inference itself was not rerun for this release. The isolated finishing test
instance contains a sample clip, not the user's model volume.

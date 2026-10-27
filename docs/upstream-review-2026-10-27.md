# Fotufilm upstream review — 27 October 2026

Scope: the ComfyUI node pack's Linux CUDA engine, continuous video preview and separate Film / Color editors. Reviewed upstream from our pinned `9242d189b6f8321a27c6f6a345aeb4e5991da569` through `4e663ad2c758` on main. No engine version change is included in the HDR import performance fix.

## What addresses the reported slowdown?

Our HLG/PQ importer decoded the full-resolution transfer function on the CPU before resizing. That work sits **outside Fotufilm**. SDR already used CUDA. This explains why the same server could approach real-time with SDR while HDR stayed slow at both 960px and 1280px.

Moving that existing HDR math and linear-light resize to CUDA fixes this bottleneck without changing the film engine, preview dimensions or frame count. See [measurements](hdr-import-performance.md). Updating upstream alone would not remove the Python/NumPy source conversion.

## Useful upstream changes

| Change | Value for this node pack | Integration decision |
| --- | --- | --- |
| [#316: faster 4K Resolve rendering](https://github.com/DhaliwalX/fotufilm-engine/pull/316), `e7b0b2c1c65c` | Compiled variants for exact combinations of stages, larger row windows and fewer intermediate buffers are useful ideas for reducing film-stage work. | Investigate a **CUDA port** after the import fix. The reported M4 Pro results do not establish an RTX speedup. |
| [#321: Shadow Detail / Highlight Detail](https://github.com/DhaliwalX/fotufilm-engine/pull/321), `9b572cf2e920` | Adjusts the film/print response to reveal dark and bright detail while retaining its color characteristics. More film-specific than lifting the final image's shadows. | Good candidates for two understandable Film controls. Require engine rebuild, request mapping and CUDA parity/performance checks. Not a playback optimization. |
| [#286: print descriptors](https://github.com/DhaliwalX/fotufilm-engine/pull/286), [#287: three more cinema prints](https://github.com/DhaliwalX/fotufilm-engine/pull/287) | Adds Kodak EXR 5386, Agfa CP30 and Fujifilm ETERNA-CP 3521XD print choices. Allows more genuinely distinct recipes rather than many presets of the same output. | Useful next catalogue upgrade. Keep capture stock, print choice and complete Look distinguishable. 3521XD borrows 3513DI spectra; do not advertise every profile as a complete independent measurement. |
| [#313](https://github.com/DhaliwalX/fotufilm-engine/pull/313), [#314](https://github.com/DhaliwalX/fotufilm-engine/pull/314), [#315](https://github.com/DhaliwalX/fotufilm-engine/pull/315): Cineon Log | Offers developed-negative density encoded for subsequent grading/printing. Fits an advanced node-based film → grade/print workflow. | Defer from the default preview. Cineon code values are **not linear Display P3** and cannot go through our present float output contract unchanged. Need explicit encoding metadata, matching viewer and export treatment. |
| [#312: revised Vision3 250D / CineStill 400D curves](https://github.com/DhaliwalX/fotufilm-engine/pull/312) | Improves agreement with the source characteristic curves. | Worth adopting as a versioned visual change, with updated thumbnails and recipe checks. Our benchmark uses Vision3 250D: changing this simultaneously would confound the comparison. |
| [#295: HDR browser decoding](https://github.com/DhaliwalX/fotufilm-engine/pull/295) | Useful HLG/PQ metadata and decode test cases; adds HEIC/HEVC browser support. | Our server uses PyAV and already recognizes numeric HLG/PQ tags. This browser-specific patch is not the solution to our server slowdown. |
| [#318: Linux Swift build fixes](https://github.com/DhaliwalX/fotufilm-engine/pull/318), [#322: generated constants and WebGPU updates](https://github.com/DhaliwalX/fotufilm-engine/pull/322) | Required compatibility work when taking current upstream. | Upgrade the host, kernels, generated constants and stock resources together. Never mix newer constants or profiles into an older native binary. |

## Why #316 is not a drop-in RTX optimization

Source inspection, beyond the PR's benchmark headline:

- [`tools/generate_halide_ios.cpp`](https://github.com/DhaliwalX/fotufilm-engine/blob/e7b0b2c1c65c/tools/generate_halide_ios.cpp) explicitly skips row-window variants for Linux. The new exact-stage variants belong to that windowed family.
- [`GpuBackend.h`](https://github.com/DhaliwalX/fotufilm-engine/blob/e7b0b2c1c65c/Sources/FotufilmHalide/Pipeline/GpuBackend.h) enables register-stage fusion only for windowed Metal. The new measured-curve table shortcut is also gated to realtime Metal.
- [`Schedule/Gpu.h`](https://github.com/DhaliwalX/fotufilm-engine/blob/e7b0b2c1c65c/Sources/FotufilmHalide/Schedule/Gpu.h) gates the additional blur/decimation optimizations to Metal windows or WebGPU.
- The new Metal allocation pool addresses a missing Metal facility. The [Linux backend](https://github.com/DhaliwalX/fotufilm-engine/blob/e7b0b2c1c65c/Sources/FotufilmHalide/FotufilmHalideLinux.cpp) already enables Halide device-allocation reuse; copying the pool is not automatically an improvement.
- Fused decode scans may benefit paths that actually use that GPU decoder. Our custom float-memory bridge supplies already-linear pixels, so this is not the current source conversion path. Upstream's new camera-log GPU decoding still excludes HLG.

The transferable engineering idea is to compute less intermediate data and reuse allocations, while retaining the same output. A CUDA port needs its own compiled kernels and image-parity checks; simply changing the upstream SHA will not activate Metal schedules on NVIDIA.

## Recommended order

1. Ship the independently measured HDR import fix. Keep the existing engine and look rendering stable.
2. Measure actual delivered playback and slider response on the user's ComfyUI session. Inspect source, film, grade, encode and delivery timings separately if it is still slow.
3. Upgrade the engine in a separate change: adapt the additive float-memory ABI and build scripts to the new desktop host layout (upstream removed the old CEF host), rebuild Linux CUDA, package matching resources, and verify existing recipes and exports.
4. Add the new print choices and optional detail controls once that runtime is validated.
5. Profile the remaining film-stage cost before porting the Metal scheduling techniques to CUDA. Keep strict float quality as the baseline; do not silently enable an approximate realtime mode or reduce preview resolution to meet a frame-rate claim.

This work stays inside ComfyUI custom nodes. Upstream's Flutter UI migration is not a reason to replace the node interface or revive a standalone browser application.

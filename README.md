# ComfyUI-Fotufilm

Film simulation and HDR video finishing nodes for ComfyUI, extracted from Film Finish. Uses the real [Fotufilm engine](https://github.com/DhaliwalX/fotufilm-engine), pinned to **v1.11** (`f602857a031a6a9c9b0966284ff989eb3046c323`). This is an independent integration, not an official Fotufilm product.

## Install

In your ComfyUI environment, using its Python interpreter:

```sh
git clone https://github.com/comfyrob/ComfyUI-Fotufilm.git custom_nodes/ComfyUI-Fotufilm
python -m pip install -r custom_nodes/ComfyUI-Fotufilm/requirements.txt
python custom_nodes/ComfyUI-Fotufilm/install.py
```

Restart ComfyUI after installation. Do not install this alongside the original local `film_finish` pack: their node IDs overlap.

**Linux:** x86-64, Ubuntu 24.04 / compatible glibc 2.39 environment. The installer downloads checksum-pinned Fotufilm, FFmpeg and system libraries, extracts the required runtime and film profiles, and verifies the native dependency closure. It does not download model weights or install a desktop application. CUDA hosts use this pack’s additive float-memory engine; Vulkan/CPU hosts retain the upstream engine. The build-time check validates loading without rendering; test execution on the GPU worker too.

**macOS:** install Halide 21 and the upstream Swift build prerequisites, then run `bash scripts/build_macos.sh`. Alternatively point `FOTUFILM_LIBRARY` and `FOTUFILM_STOCKS` at an existing pinned build. These can also be keys in a local, gitignored `runtime.local.json`. macOS is suitable for inspection and small CPU checks; use your remote GPU environment for heavy video work.

**Windows / Linux ARM:** no packaged runtime supported yet.

## Nodes

| Node ID | Purpose |
|---|---|
| `FotufilmStudio` | Expand a video/recipe editor inside a Nodes 2.0 node, or open the larger Studio. |
| `FotufilmStudioReview` | Return a downstream render to its originating Studio without a graph cycle. |
| `FotufilmDevelopVideo` | Optional final export of VIDEO or connected linear IMAGE frames; MP4, ProRes or eligible HLG. |
| `FotufilmDevelopFrames` | Develop IMAGE frame batches; returns **linear Display P3 float** frames. |
| `FilmFinishHDRPad` | Pad video to LTX spatial / temporal alignment. |
| `FilmFinishHDRRestore` | Crop reconstruction back to the original dimensions and frame count. |
| `FilmFinishSaveHDRVideo` | Save linear frames as Rec.2020 HLG HEVC 10-bit with audio. |
| `FilmFinishSaveHDRMaster` | Optional RGB32F EXR archive for reuse across sessions; no longer required by Studio. |
| `FotufilmLoadHDRMaster` | Reopen an existing float master without running LTX. |
| `FotufilmDevelopHDRMaster` | Develop a saved float master into MP4, ProRes or eligible HLG. |

Category: **Film Finish**. IDs intentionally match existing workflows.

### Nodes 2.0 Studio

Enable **Settings → Comfy → Modern Node Design (Nodes 2.0)**. Open `Fotufilm - Studio.json`, upload a video, and use **Edit in node** or **Open studio**. The editor uses ComfyUI's DOM-widget support, node sizing, advanced-input disclosure and official extension hooks; it also works with the legacy canvas. It is not a private Vue renderer replacement.

An existing **Load Video** file appears immediately, without executing the graph. A connected **Load HDR Master** can also be previewed before execution. Newly generated HDR must finish once before it can be viewed. Studio resolves source-file widgets and cached outputs, including subgraph outputs; it never presents an unexecuted processing node as a completed result.

Editing **Looks**, **Film** or **Grade** updates a continuous server-rendered stream, independent of the graph queue. No MP4 is regenerated per edit, and no LTX job is submitted by moving a slider. Preview sizes are explicitly **1280px / 1920px long edge**, capped at source resolution. The viewer reports measured delivery fps and processing time; it never silently reduces resolution or skips source frames to advertise a higher rate.

The server keeps Fotufilm warm, uses float32 Gear grading on CUDA when available, and delivers H.264 monitor frames through a same-origin WebSocket to WebCodecs inside the node. NVIDIA NVENC is preferred; a CPU encoder is available on the server. The acknowledgement window adapts to network latency, capped at 12 frames. New control revisions supersede stale work, and before/after comes from the same source frame. Paused previews use lossless PNG display pixels. The moving monitor stream is compressed SDR, **not a lossless float or calibrated HDR viewer**. Export and EXR inspection always read the original float source, never the monitor stream.

The additive `fotufilm_image_from_rgba32f` extension accepts linear Rec.2020 float memory directly. It uses the pinned Fotufilm render engine and profiles. The existing upstream runtime remains compatible, using an uncompressed temporary EXR when the extension is absent; the monitor tooltip identifies this slower path. See [live preview notes](docs/live-preview.md) for runtime setup and validation status.

**Grade → Balance input** grades the float source before Fotufilm. **Grade → Finish look** refines Fotufilm's linear P3 output. The controls use pinned Gear ACEScct math, adapted for wide-gamut float buffers: exposure, warmth/tint, contrast, highlights/shadows, saturation/vibrance, and lift/gamma/gain/offset wheels. There is one terminal display conversion, not a tone map before film simulation. See [Gear attribution and adaptation](vendor/README.md).

Looks are complete recipes. Choosing a different film keeps the look name and marks it **Modified**. Look cards are actual first-frame film renders, generated while playback is paused. Playback supports looping, frame steps, scrubbing, zoom/pan and a draggable before/after divider. The enlarged Studio and inline node share one editor implementation.

**Original / Enhanced HDR** selects the source for interactive finishing and Studio's **Export video**. **Before / after** compares that same source before and after grading plus film. HDR processing reads connected linear frames or a saved float EXR master; browser stills and playback use an explicitly labelled SDR display conversion. This is not a calibrated HDR monitor. Export provides MP4, ProRes 422 HQ, and eligible HLG.

**Save to node** persists the recipe. **Run workflow** saves and queues the connected graph, including any uncached upstream stages; the graph follows its wired source/master, regardless of the interactive comparison source. **Export video** directly renders the current Studio source and recipe at full resolution without rerunning LTX. The optional **Develop Video** branch can connect its `studio` input to Studio to return a graph render without an extra Return node. Existing Return to Studio workflows remain compatible.

The same float film and grading operations serve previews and final exports. Film texture can differ with preview resolution; inspect at source resolution when assessing grain. Real-time performance depends on the recipe, hardware and network; cold engine initialization remains separate from warm playback.

### Full-resolution EXR inspection

Open **Inspect full-resolution frame** below the recipe controls in Studio. Choose **Source**, **After balance grade**, **After Fotufilm**, or **After finishing grade**, then **Save EXR frame**. This captures the playhead and current recipe, processes only that frame at source resolution, and saves an unclipped RGB32F EXR in `output/fotufilm-inspections/`. No LTX job or video render is submitted. Where possible, inspection reuses the full-resolution source/film caches. The saved frame is a snapshot; subsequent slider edits do not change it.

The new **Fotufilm · Inspect Frame** output node provides the same stages in a graph. Connect exactly one HDR master, VIDEO, or IMAGE batch. For IMAGE, explicitly choose the input color space; use **linear Display P3** for Develop Frames output. Stage **source** inspects the connected pixels without applying the recipe. Connecting an already-developed image and selecting film/finish would apply the film again. The node returns one IMAGE in **linear Rec.2020** and its color-space label. Ordinary graph execution may run uncached upstream nodes; use the Studio button or the saved-master example to avoid an LTX dependency.

[`Fotufilm - Inspect HDR frame.json`](examples/Fotufilm%20-%20Inspect%20HDR%20frame.json) opens an existing master with no LTX nodes. Frame numbering starts at zero.

On compatible ComfyUI backend/frontend builds with Assets enabled ([backend #16898](https://github.com/Comfy-Org/ComfyUI/pull/16898), [frontend #20839](https://github.com/Comfy-Org/ComfyUI_frontend/pull/20839)), open the EXR from **Assets → Outputs** or the inspection node's **History** result. Studio's independent frame jobs appear in Assets, not workflow History. The pack supplies its own color-converted SDR thumbnail through the new preview protocol; the original EXR remains separate. Older builds receive an SDR PNG thumbnail plus the saved EXR for download. Updating this pack alone does not install those core changes.

Inspection copies are explicitly converted to Rec.2020, including Fotufilm's linear-P3 output, and include EXR chromaticities plus a JSON recipe/frame sidecar. No display transform is baked into the EXR. Core's current inspector reads float pixels but displays SDR; its exposure control changes the view, not the grade. There is no private frontend import or automatic opening of core's dialog. This feature does not change video playback speed or resolution.

See [Nodes 2.0 integration notes](docs/nodes-2-studio.md).

The pack does **not** perform neural SDR-to-HDR conversion by itself. The included LTX 2.5 workflow requires [ComfyUI-LTXVideo](https://github.com/Lightricks/ComfyUI-LTXVideo) at `3bf3ca62595f1764c47d01c35c8e5dfe47e1a88f`, the model files named in that workflow, and `colour-science==0.4.7`. Install model weights on your remote models volume, not in this repository or the container image.

## Workflows and color

Start with **[Film Finish - Studio + LTX 2.5 HDR.json](examples/Film%20Finish%20-%20Studio%20%2B%20LTX%202.5%20HDR.json)** for one connected workflow:

`Load Video → LTX 2.5 subgraph → Studio (linear HDR frames → Gear → Fotufilm → Gear)`

The root has three main nodes plus two optional output branches: **Archive HDR source** and **Export finished video**. Both output branches start with `enabled=false`. Studio's `images` input receives the LTX `hdr_linear` IMAGE output in **linear ACEScg**, with frame rate connected separately. A master archive is not needed for preview. Open the LTX subgraph to inspect its reconstruction stages.

Enable the archive branch to retain float EXRs and source audio for later sessions. Enable the export branch after saving your Studio recipe, or use Studio's Export video button. LTX depends on the original video, not the film recipe. Keep its seed fixed to reuse cached reconstruction; a restart or eviction can require reconstruction again. Direct frame references are bounded to 8 GiB across Studio assets and expire with the server.

Use **Film Finish - Studio + LTX 2.5 HDR - Modal INT8.json** for the INT8 transformer and `ltx25/` LoRA paths already installed on Rob's Modal volume. The BF16 reference remains separate; the INT8 variant has not been inference-tested by this change.

`Fotufilm - Finish saved HDR master.json` opens a durable master without any LTX nodes. Enter `folder/name.ffhdr.zip [output]` for an existing server output, or an input-folder path. `Fotufilm - Studio.json` is the smaller connected SDR-finishing workflow. The older grouped LTX lab and saved-master workflows remain available. For a durable handoff after a restart, upload a saved `.ffhdr.zip` to ComfyUI's input folder and set the Develop HDR Master `file` field under advanced inputs. A connected `master` takes precedence over `file`.

Recipes in `examples/*.recipe.json` select film, print/scan, exposure and texture. HDR delivery currently requires a direct-view slide-film recipe with **Reference exposure**, such as the supplied Ektachrome recipe. Negative/print recipes produce an SDR finish even when the input is HDR. An SDR node thumbnail does not display the full float range; use the HLG video or EXR master in a color-managed HDR viewer.

The pack includes same-origin `/fotufilm/` preview/export routes on your existing ComfyUI server. It does not launch another server or install the standalone Film Finish app or deployment credentials. Routes inherit the host's access boundary. Preview jobs are serialized, prioritized and cancellable. Encoded previews have a 2 GiB temporary cache; lossless float intermediates have a separate 4 GiB disk / up to 4 GiB RAM budget (`FOTUFILM_PREVIEW_CACHE_MB` adjusts RAM), excluding native-engine buffers and active renders. Evicted frames are recomputed. Exports are saved in the normal output directory.

## Container image integration

Clone a **commit SHA**, install `requirements.txt`, then execute `install.py` during image build. Installing only Python dependencies is insufficient: Fotufilm needs its native libraries and stock resources. The files live beside the pack in `linux-runtime/`; downloads are cached in `.runtime/`. Both directories are gitignored. The installer performs no model inference.

Run `python scripts/check_runtime.py` for a build-time ABI check. On a GPU worker, `python scripts/check_runtime.py --render` also verifies engine initialization and video decoding. Run `python -m unittest discover -s tests` with ComfyUI's Python (plus `colour-science`) for float-master checks.

## License and attribution

The ComfyUI adapter is **GPL-3.0-only**, retaining the Film Finish source license. Fotufilm engine code is **Apache-2.0**; its film profiles are **CC BY-SA 4.0**, attributed to **Fotufilm — https://fotufilm.com**, copyright MUAStudio Inc. Profiles are unmodified. Upstream notices are retained in [`upstream/`](upstream/); the runtime installer preserves bundled notices and records source URLs/checksums. Rendered videos do not inherit the profile license.

Gear grading code is MIT, copyright 2026 Mohamed Oumoumad, with its license retained in `vendor/GEAR-LICENSE`.

Native binaries are downloaded directly from upstream distributions during installation, not redistributed in this Git repository. FFmpeg and its codecs retain their own licenses; the installer changes only FFmpeg dynamic-library name references to match Fotufilm's ABI. See [`runtime/README.md`](runtime/README.md).

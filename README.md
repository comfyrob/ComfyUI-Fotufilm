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

**Linux:** x86-64, Ubuntu 24.04 / compatible glibc 2.39 environment. The installer downloads checksum-pinned Fotufilm, FFmpeg and system libraries, extracts the required runtime and film profiles, and verifies the native dependency closure. It does not download model weights or install a desktop application. CUDA/Vulkan accelerates the native Linux renderer; the packaged Halide fallback also passes small CPU render tests. The build-time check validates loading without rendering; test execution on the GPU worker too.

**macOS:** install Halide 21 and the upstream Swift build prerequisites, then run `bash scripts/build_macos.sh`. Alternatively point `FOTUFILM_LIBRARY` and `FOTUFILM_STOCKS` at an existing pinned build. These can also be keys in a local, gitignored `runtime.local.json`. macOS is suitable for inspection and small CPU checks; use your remote GPU environment for heavy video work.

**Windows / Linux ARM:** no packaged runtime supported yet.

## Nodes

| Node ID | Purpose |
|---|---|
| `FotufilmStudio` | Expand a video/recipe editor inside a Nodes 2.0 node, or open the larger Studio. |
| `FotufilmStudioReview` | Return a downstream render to its originating Studio without a graph cycle. |
| `FotufilmDevelopVideo` | Develop a VIDEO through Fotufilm; MP4, ProRes 422 HQ or eligible HLG output. |
| `FotufilmDevelopFrames` | Develop IMAGE frame batches; returns **linear Display P3 float** frames. |
| `FilmFinishHDRPad` | Pad video to LTX spatial / temporal alignment. |
| `FilmFinishHDRRestore` | Crop reconstruction back to the original dimensions and frame count. |
| `FilmFinishSaveHDRVideo` | Save linear frames as Rec.2020 HLG HEVC 10-bit with audio. |
| `FilmFinishSaveHDRMaster` | Save RGB32F EXR frames and return a typed master connection to the next node. |
| `FotufilmLoadHDRMaster` | Reopen an existing float master without running LTX. |
| `FotufilmDevelopHDRMaster` | Develop a saved float master into MP4, ProRes or eligible HLG. |

Category: **Film Finish**. IDs intentionally match existing workflows.

### Nodes 2.0 Studio

Enable **Settings → Comfy → Modern Node Design (Nodes 2.0)**. Open `Fotufilm - Studio.json`, upload a video, and use **Edit in node** or **Open studio**. The editor uses ComfyUI's DOM-widget support, node sizing, advanced-input disclosure and official extension hooks; it also works with the legacy canvas. It is not a private Vue renderer replacement.

An existing **Load Video** file appears immediately, without executing the graph. A connected **Load HDR Master** can also be previewed before execution. Newly generated HDR must finish once before it can be viewed. Studio resolves source-file widgets and cached outputs, including subgraph outputs; it never presents an unexecuted processing node as a completed result.

Editing **Looks**, **Film** or **Grade** automatically requests a native frame preview, then renders a cached playback clip. This uses the real Fotufilm engine on the ComfyUI server, independent of the graph queue. New edits cancel outdated work between frames. No LTX job is submitted by changing a slider. Preview quality is **960px / 1440px long edge**, capped at source resolution; automatic clips cover the first 20 seconds. Final exports cover the full source.

Studio keeps a native engine warm and saves developed float32 frames before the finishing grade. **Finish look** changes reuse those frames; balance, stock, texture, grain seed, source, frame or resolution changes invalidate the affected film results. A single worker lets interactive frames interrupt playback/export work at frame boundaries and resumes without skipping frames. PNG previews use faster lossless compression. Resolution, grain, float precision and video encoding quality are unchanged. See [preview performance measurements](docs/preview-performance.md).

**Grade → Balance input** grades the float source before Fotufilm. **Grade → Finish look** refines Fotufilm's linear P3 output. The controls use pinned Gear ACEScct math, adapted for wide-gamut float buffers: exposure, warmth/tint, contrast, highlights/shadows, saturation/vibrance, and lift/gamma/gain/offset wheels. There is one terminal display conversion, not a tone map before film simulation. See [Gear attribution and adaptation](vendor/README.md).

Looks are complete recipes. Choosing a different film keeps the look name and marks it **Modified**. Look cards are actual first-frame film renders, generated in the background. Playback supports looping, frame steps, scrubbing, zoom/pan and a draggable before/after divider. The enlarged Studio and inline node share one editor implementation.

**Original / Enhanced HDR** selects the source for interactive finishing and Studio's **Export video**. **Before / after** compares that same source before and after grading plus film. HDR processing reads the float EXR master; browser stills and playback use an explicitly labelled SDR display conversion. This is not a calibrated HDR monitor. Export provides MP4, ProRes 422 HQ, and eligible HLG.

**Save to node** persists the recipe. **Run workflow** saves and queues the connected graph, including any uncached upstream stages; the graph follows its wired source/master, regardless of the interactive comparison source. **Export video** directly renders the current Studio source and recipe at full resolution without rerunning LTX. The **Return to Studio** node sends a graph render back to the viewer without a backward wire.

The same float pipeline serves native frame previews, playback renders, frame-batch nodes and final exports. Film texture can differ with preview resolution; compare at full resolution when assessing grain. Rendering is asynchronous, not instantaneous: cached video plays at its normal frame rate after it is ready.

See [Nodes 2.0 integration notes](docs/nodes-2-studio.md).

The pack does **not** perform neural SDR-to-HDR conversion by itself. The included LTX 2.5 workflow requires [ComfyUI-LTXVideo](https://github.com/Lightricks/ComfyUI-LTXVideo) at `3bf3ca62595f1764c47d01c35c8e5dfe47e1a88f`, the model files named in that workflow, and `colour-science==0.4.7`. Install model weights on your remote models volume, not in this repository or the container image.

## Workflows and color

Start with **[Film Finish - Studio + LTX 2.5 HDR.json](examples/Film%20Finish%20-%20Studio%20%2B%20LTX%202.5%20HDR.json)** for one connected workflow:

`Load Video → LTX 2.5 subgraph → float EXR master → Studio (Gear → Fotufilm → Gear) → Develop HDR Master → Return to Studio`

The Studio feeds the film recipe into Fotufilm separately. Open the LTX subgraph to inspect the 25 internal nodes and their groups. The root contains six functional nodes and a note. Save HDR Master passes through Studio to Develop HDR Master; no download/reupload is needed. LTX depends on the original video, not the film recipe, so recipe-only edits can reuse its cached result. Keep the reconstruction seed fixed. Cache reuse is not guaranteed across server restarts, graph changes or cache eviction.

Use **Film Finish - Studio + LTX 2.5 HDR - Modal INT8.json** for the INT8 transformer and `ltx25/` LoRA paths already installed on Rob's Modal volume. The BF16 reference remains separate; the INT8 variant has not been inference-tested by this change.

`Fotufilm - Finish saved HDR master.json` opens a durable master without any LTX nodes. Enter `folder/name.ffhdr.zip [output]` for an existing server output, or an input-folder path. `Fotufilm - Studio.json` is the smaller connected SDR-finishing workflow. The older grouped LTX lab and saved-master workflows remain available. For a durable handoff after a restart, upload a saved `.ffhdr.zip` to ComfyUI's input folder and set the Develop HDR Master `file` field under advanced inputs. A connected `master` takes precedence over `file`.

Recipes in `examples/*.recipe.json` select film, print/scan, exposure and texture. HDR delivery currently requires a direct-view slide-film recipe with **Reference exposure**, such as the supplied Ektachrome recipe. Negative/print recipes produce an SDR finish even when the input is HDR. An SDR node thumbnail does not display the full float range; use the HLG video or EXR master in a color-managed HDR viewer.

The pack includes same-origin `/fotufilm/` preview/export routes on your existing ComfyUI server. It does not launch another server or install the standalone Film Finish app or deployment credentials. Routes inherit the host's access boundary. Preview jobs are serialized, prioritized and cancellable. Encoded previews have a 2 GiB temporary cache; lossless float intermediates have a separate 4 GiB disk / 192 MiB RAM budget, excluding native-engine buffers and active renders. Evicted frames are recomputed. Exports are saved in the normal output directory.

## Container image integration

Clone a **commit SHA**, install `requirements.txt`, then execute `install.py` during image build. Installing only Python dependencies is insufficient: Fotufilm needs its native libraries and stock resources. The files live beside the pack in `linux-runtime/`; downloads are cached in `.runtime/`. Both directories are gitignored. The installer performs no model inference.

Run `python scripts/check_runtime.py` for a build-time ABI check. On a GPU worker, `python scripts/check_runtime.py --render` also verifies engine initialization and video decoding. Run `python -m unittest discover -s tests` with ComfyUI's Python (plus `colour-science`) for float-master checks.

## License and attribution

The ComfyUI adapter is **GPL-3.0-only**, retaining the Film Finish source license. Fotufilm engine code is **Apache-2.0**; its film profiles are **CC BY-SA 4.0**, attributed to **Fotufilm — https://fotufilm.com**, copyright MUAStudio Inc. Profiles are unmodified. Upstream notices are retained in [`upstream/`](upstream/); the runtime installer preserves bundled notices and records source URLs/checksums. Rendered videos do not inherit the profile license.

Gear grading code is MIT, copyright 2026 Mohamed Oumoumad, with its license retained in `vendor/GEAR-LICENSE`.

Native binaries are downloaded directly from upstream distributions during installation, not redistributed in this Git repository. FFmpeg and its codecs retain their own licenses; the installer changes only FFmpeg dynamic-library name references to match Fotufilm's ABI. See [`runtime/README.md`](runtime/README.md).

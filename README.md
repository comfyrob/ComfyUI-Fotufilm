# ComfyUI-Fotufilm

## Start with one graph

Open **[SDR / NVIDIA / LTX HDR → Film + Color](examples/Fotufilm%20-%20SDR%20or%20NVIDIA%20or%20LTX%20HDR%20-%20Film%20%2B%20Grade.json)**. Core's **Use HDR?** switch selects SDR or HDR; **Use LTX?** selects NVIDIA (Off) or the unchanged LTX 2.5 reconstruction (On). Only the selected source branch executes. The graph includes optional native **Create Video → Save Video**, native EXR saves and a beginner guide. **[SDR / NVIDIA only](examples/Fotufilm%20-%20SDR%20or%20NVIDIA%20HDR%20-%20Film%20%2B%20Grade.json)** avoids requiring LTX models. Requires core with `ComfySwitchNode`, `ImageColorSpace` and the current native video nodes (validated at `98cc0bf`). [Read the workflow guide](docs/hdr-choice-workflow.md).

Film and Color expose only their settings outputs. The shared live renderer applies them to the same source; the optional export renders full-resolution pixels. Existing Studio and split-editor workflows remain supported.

Film opens expanded by default. Browse **54 curated recipes** by category or customize one of **28 stock profiles**. The look library opens on **All**. The selected look remains visible above the library; selecting another category does not change it. Grading wheels remain in the separate Color node. Native video saving uses the same SDR transform as the normal preview; EXRs retain linear float values. Native batch output uses more memory than the legacy frame-by-frame exporter.

Film simulation and HDR video finishing custom nodes using the real [Fotufilm engine](https://github.com/DhaliwalX/fotufilm-engine). Linux CUDA is pinned to **`9242d189`** with matching profiles; the CPU/Vulkan/macOS fallback remains **v1.11 (`f602857a`)**. This is an independent integration, not an official Fotufilm product. [Engine upgrade and validation](docs/engine-9242d189.md).

## Install

In your ComfyUI environment, using its Python interpreter:

```sh
git clone https://github.com/comfyrob/ComfyUI-Fotufilm.git custom_nodes/ComfyUI-Fotufilm
python -m pip install -r custom_nodes/ComfyUI-Fotufilm/requirements.txt
python custom_nodes/ComfyUI-Fotufilm/install.py
```

After updating an existing checkout, rerun `python custom_nodes/ComfyUI-Fotufilm/install.py` to update the native engine and profiles. Restart ComfyUI after installation. Do not install this alongside the original local `film_finish` pack: their node IDs overlap.

**Linux:** x86-64, Ubuntu 24.04 / compatible glibc 2.39 environment. The installer downloads checksum-pinned Fotufilm, FFmpeg and system libraries, extracts the required runtime and film profiles, and verifies the native dependency closure. It does not download model weights or install a desktop application. CUDA hosts use this pack’s additive float-memory engine; Vulkan/CPU hosts retain the upstream engine. The build-time check validates loading without rendering; test execution on the GPU worker too.

**macOS:** install Halide 21 and the upstream Swift build prerequisites, then run `bash scripts/build_macos.sh`. Alternatively point `FOTUFILM_LIBRARY` and `FOTUFILM_STOCKS` at an existing pinned build. These can also be keys in a local, gitignored `runtime.local.json`. macOS is suitable for inspection and small CPU checks; use your remote GPU environment for heavy video work.

**Windows / Linux ARM:** no packaged runtime supported yet.

## Nodes

| Node ID | Purpose |
|---|---|
| `FotufilmSelectSource` | Legacy three-way selector; new workflows use core If/Else Switch nodes. |
| `FotufilmLTXHDRDecode` | Upstream LTX HDR decode without an independent output/save trigger; enables lazy branch selection. |
| `FotufilmLinearToRec709` | Explicit unclipped linear gamut conversion for shared processing and native EXR saving. |
| `FotufilmFilmEditor` | Film/look editor with one `film_settings` output. |
| `FotufilmGradeEditor` | Separate color editor with one `finished_settings` output. |
| `FotufilmStudio` | Expand a video/recipe editor inside a Nodes 2.0 node, or open the larger Studio. |
| `FotufilmBalanceFrames` | Optional Gear source correction; preserves float range, outputs linear ACEScg. |
| `FotufilmInspectFrame` | Save Still (EXR): optional full-resolution frame output, outside Studio. |
| `FotufilmStudioReview` | Return a downstream render to its originating Studio without a graph cycle. |
| `FotufilmDevelopVideo` | Optional final export of VIDEO or connected linear IMAGE frames; MP4, ProRes or eligible HLG. |
| `FotufilmDevelopFrames` | Develop once; returns **linear Display P3 float** frames and separate **sRGB SDR** frames for native Create Video. |
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

Editing **Looks**, **Film** or **Color & texture** updates a continuous server-rendered stream, independent of the graph queue. No MP4 is regenerated per edit, and no LTX job is submitted by moving a slider. Preview sizes are explicitly **640 / 960 / 1280 / 1920px long edge**, capped at source resolution. The viewer reports measured delivery fps and processing time; it never silently reduces resolution or skips source frames to advertise a higher rate.

The server keeps Fotufilm warm, uses float32 Gear grading on CUDA when available, and delivers H.264 monitor frames through a same-origin WebSocket to WebCodecs inside the node. NVIDIA NVENC is preferred; a CPU encoder is available on the server. The acknowledgement window adapts to network latency, capped at 12 frames. New control revisions supersede stale work, and before/after comes from the same source frame. Paused previews use lossless PNG display pixels. The moving monitor stream is compressed SDR, **not a lossless float or calibrated HDR viewer**. Export and EXR inspection always read the original float source, never the monitor stream.

The additive `fotufilm_image_from_rgba32f` extension accepts linear Rec.2020 float memory directly. It uses the pinned Fotufilm render engine and profiles. The existing upstream runtime remains compatible, using an uncompressed temporary EXR when the extension is absent; the monitor tooltip identifies this slower path. See [live preview notes](docs/live-preview.md) for runtime setup and validation status.

**Balance Source** is an optional graph node that corrects the float source before Fotufilm. Studio's **Color & texture** tab refines the finished look, with visible color wheels. The controls use pinned Gear ACEScct math, adapted for wide-gamut float buffers: exposure, warmth/tint, contrast, highlights/shadows, saturation/vibrance, and lift/gamma/gain/offset wheels. There is one terminal display conversion, not a tone map before film simulation. See [Gear attribution and adaptation](vendor/README.md).

Looks are complete recipes. Choosing a different film keeps the look name and marks it **Modified**. Look cards are actual first-frame film renders, loaded independently of playback, with cached results and retry on failure. Only on-screen cards and the pinned selection request thumbnails; playback keeps priority. The installed server catalogue disables missing stocks with an explanation instead of substituting a different profile. Playback supports looping, frame steps, scrubbing, zoom/pan and a draggable before/after divider. The enlarged Studio and inline node share one editor implementation.

**54 default looks** are grouped into Cinema, Portrait, Slide, Vintage, B&W and Experimental. Search by look or stock name, and star favorites to keep a personal shortlist. All remain editable; filtering does not change the active look. See [look catalogue and optional output nodes](docs/looks-and-outputs.md) for the new defaults, external profile research, and native ComfyUI save-node alternatives.

**Original / Enhanced HDR** selects the source for interactive finishing and Studio's **Export video**. **Before / after** compares that same source before and after grading plus film. HDR processing reads connected linear frames, a saved float EXR master, or a tagged HLG/PQ video; browser stills and playback use an explicitly labelled SDR display conversion. This is not a calibrated HDR monitor. Export provides MP4, ProRes 422 HQ, and eligible HLG.

**Save to node** persists the recipe. Use ComfyUI’s **Run** control to queue the connected graph, including uncached upstream stages; the graph follows its wired source/master, regardless of the interactive comparison source. **Export video** directly renders the current Studio source and recipe at full resolution without rerunning LTX. The optional **Develop Video** branch can connect its `studio` input to Studio to return a graph render without an extra Return node. Existing Return to Studio workflows remain compatible.

The same float film and grading operations serve previews and final exports. Film texture can differ with preview resolution; inspect at source resolution when assessing grain. Real-time performance depends on the recipe, hardware and network; cold engine initialization remains separate from warm playback.

### Full-resolution EXR inspection

Stills live in the **Fotufilm · Save Still (EXR)** graph node (`FotufilmInspectFrame`). Connect exactly one HDR master, VIDEO or IMAGE batch, and Studio's `recipe_json` output. Choose a frame, enable the output and run the graph. It writes one full-resolution RGB32F EXR under `output/fotufilm-inspections/`. The example starts this optional save branch disabled.

Advanced `stage=finish` applies the full recipe; `source` saves connected pixels unchanged apart from explicit color conversion. Select the actual IMAGE input space. Already-developed frames require `source` and **linear Display P3** to avoid applying film twice. Output is linear Rec.2020 plus its color-space label. Ordinary graph execution can run uncached upstream nodes. Studio no longer contains a histogram, still-saving panel or graph-run button.

[`Fotufilm - Inspect HDR frame.json`](examples/Fotufilm%20-%20Inspect%20HDR%20frame.json) opens an existing master with no LTX nodes. Frame numbering starts at zero.

On compatible ComfyUI backend/frontend builds with Assets enabled ([backend #16898](https://github.com/Comfy-Org/ComfyUI/pull/16898), [frontend #20839](https://github.com/Comfy-Org/ComfyUI_frontend/pull/20839)), open the EXR from **Assets → Outputs** or the inspection node's **History** result. The pack supplies its own color-converted SDR thumbnail through the new preview protocol; the original EXR remains separate. Older builds receive an SDR PNG thumbnail plus the saved EXR for download. Updating this pack alone does not install those core changes.

Inspection copies are explicitly converted to Rec.2020, including Fotufilm's linear-P3 output, and include EXR chromaticities plus a JSON recipe/frame sidecar. No display transform is baked into the EXR. Core's current inspector reads float pixels but displays SDR; its exposure control changes the view, not the grade. There is no private frontend import or automatic opening of core's dialog. This feature does not change video playback speed or resolution.

See [Nodes 2.0 integration notes](docs/nodes-2-studio.md).

The pack does **not** perform neural SDR-to-HDR conversion by itself. The included LTX 2.5 workflow requires [ComfyUI-LTXVideo](https://github.com/Lightricks/ComfyUI-LTXVideo) at `3bf3ca62595f1764c47d01c35c8e5dfe47e1a88f`, the model files named in that workflow, and `colour-science==0.4.7`. Install model weights on your remote models volume, not in this repository or the container image.

## Existing HDR movies

Use [Fotufilm - Open HDR video.json](examples/Fotufilm%20-%20Open%20HDR%20video.json) for an already-HDR MP4/MOV. Tagged BT.2020 HLG/PQ is decoded to float for film and grading; a compatible SDR copy supplies playback/audio without replacing the processing source. No LTX pass or EXR archive is required. See [import details and limitations](docs/encoded-hdr-video.md).

## Older workflows and color

For the earlier combined Studio layout, use **[Film Finish - Studio + LTX 2.5 HDR.json](examples/Film%20Finish%20-%20Studio%20%2B%20LTX%202.5%20HDR.json)** for one connected workflow:

`Load Video → LTX 2.5 subgraph → optional Balance Source → Studio (film + finishing color)`

The root has three main nodes plus two optional output branches: **Archive HDR source** and **Export finished video**. Both output branches start with `enabled=false`. Studio's `images` input receives the LTX `hdr_linear` IMAGE output in **linear ACEScg**, with frame rate connected separately. A master archive is not needed for preview. Open the LTX subgraph to inspect its reconstruction stages.

Enable the archive branch to retain float EXRs and source audio for later sessions. Enable the export branch after saving your Studio recipe, or use Studio's Export video button. LTX depends on the original video, not the film recipe. Keep its seed fixed to reuse cached reconstruction; a restart or eviction can require reconstruction again. Direct frame references are bounded to 8 GiB across Studio assets and expire with the server.

For explicit graph-based correction and saving, open **[Fotufilm - Balance + Studio + optional still - Modal.json](examples/Fotufilm%20-%20Balance%20%2B%20Studio%20%2B%20optional%20still%20-%20Modal.json)**. Balance Source applies Gear correction on linear frames before Studio. Changing this graph node requires Run; live finishing adjustments stay in Studio. Save final still is disabled by default and reads the same corrected source and Studio recipe. See [grading controls](docs/grading-controls.md) for wiring and saved-recipe compatibility.

Use **Film Finish - Studio + LTX 2.5 HDR - Modal INT8.json** for the INT8 transformer and `ltx25/` LoRA paths already installed on Rob's Modal volume. The BF16 reference remains separate. The current combined graph's INT8 LTX branch passed a 97-frame, 1280×720 sampling/decode run after correcting the container's CUDA library search order; see [validation details](docs/cuda-runtime-troubleshooting.md).

`Fotufilm - Finish saved HDR master.json` opens a durable master without any LTX nodes. Enter `folder/name.ffhdr.zip [output]` for an existing server output, or an input-folder path. `Fotufilm - Studio.json` is the smaller connected SDR-finishing workflow. The older grouped LTX lab and saved-master workflows remain available. For a durable handoff after a restart, upload a saved `.ffhdr.zip` to ComfyUI's input folder and set the Develop HDR Master `file` field under advanced inputs. A connected `master` takes precedence over `file`.

Recipes in `examples/*.recipe.json` select film, print/scan, exposure and texture. HDR delivery currently requires a direct-view slide-film recipe with **Reference exposure**, such as the supplied Ektachrome recipe. Negative/print recipes produce an SDR finish even when the input is HDR. An SDR node thumbnail does not display the full float range; use the HLG video or EXR master in a color-managed HDR viewer.

The pack includes same-origin `/fotufilm/` preview/export routes on your existing ComfyUI server. It does not launch another server or install the standalone Film Finish app or deployment credentials. Routes inherit the host's access boundary. Preview jobs are serialized, prioritized and cancellable. Encoded previews have a 2 GiB temporary cache; lossless float intermediates have a separate 4 GiB disk / up to 4 GiB RAM budget (`FOTUFILM_PREVIEW_CACHE_MB` adjusts RAM), excluding native-engine buffers and active renders. Evicted frames are recomputed. Exports are saved in the normal output directory.

## Container image integration

Clone a **commit SHA**, install `requirements.txt`, then execute `install.py` during image build. Installing only Python dependencies is insufficient: Fotufilm needs its native libraries and stock resources. The files live beside the pack in `linux-runtime/`; downloads are cached in `.runtime/`. Both directories are gitignored. The installer performs no model inference.

Run `python scripts/check_runtime.py` for a build-time ABI check. On a GPU worker, `python scripts/check_runtime.py --render` also verifies engine initialization and video decoding. Run `python -m unittest discover -s tests` with ComfyUI's Python (plus `colour-science`) for float-master checks.

If LTX fails before its first step with `CUBLAS_STATUS_NOT_INITIALIZED`, check for mixed CUDA libraries in the container image. See [CUDA runtime troubleshooting](docs/cuda-runtime-troubleshooting.md), which also distinguishes incomplete model downloads from sampling failures.

## License and attribution

The ComfyUI adapter is **GPL-3.0-only**, retaining the Film Finish source license. Fotufilm engine code is **Apache-2.0**; its film profiles are **CC BY-SA 4.0**, attributed to **Fotufilm — https://fotufilm.com**, copyright MUAStudio Inc. Profiles are unmodified. Upstream notices are retained in [`upstream/`](upstream/); the runtime installer preserves bundled notices and records source URLs/checksums. Rendered videos do not inherit the profile license.

Gear grading code is MIT, copyright 2026 Mohamed Oumoumad, with its license retained in `vendor/GEAR-LICENSE`.

The additive CUDA engine is distributed as a checksum-pinned GitHub release asset; other runtime binaries are downloaded from their upstream distributions. Binary files are not committed to this Git repository. FFmpeg and its codecs retain their own licenses; the installer changes only FFmpeg dynamic-library name references to match Fotufilm's ABI. See [`runtime/README.md`](runtime/README.md).

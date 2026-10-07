# ComfyUI-Fotufilm

Film simulation and HDR video finishing nodes for ComfyUI, extracted from Film Finish. Uses the real [Fotufilm engine](https://github.com/DhaliwalX/fotufilm-engine), pinned to **v1.11** (`f602857a031a6a9c9b0966284ff989eb3046c323`). This is an independent integration, not an official Fotufilm product.

## Install

In your ComfyUI environment, using its Python interpreter:

```sh
git clone https://github.com/comfyrob/ComfyUI-Fotufilm.git custom_nodes/ComfyUI-Fotufilm
python -m pip install -r custom_nodes/ComfyUI-Fotufilm/requirements.txt
python custom_nodes/ComfyUI-Fotufilm/install.py
```

Restart ComfyUI after installation. Do not install this alongside the original local `film_finish` pack: they register the same seven node IDs.

**Linux:** x86-64, Ubuntu 24.04 / compatible glibc 2.39 environment. The installer downloads checksum-pinned Fotufilm, FFmpeg and system libraries, extracts the required runtime and film profiles, and verifies the native dependency closure. It does not download model weights or install a desktop application. The native Linux renderer requires a supported CUDA/Vulkan GPU. The build-time check validates loading without rendering; test execution on the GPU worker too.

**macOS:** install Halide 21 and the upstream Swift build prerequisites, then run `bash scripts/build_macos.sh`. Alternatively point `FOTUFILM_LIBRARY` and `FOTUFILM_STOCKS` at an existing pinned build. These can also be keys in a local, gitignored `runtime.local.json`. macOS is suitable for inspection and small CPU checks; use your remote GPU environment for heavy video work.

**Windows / Linux ARM:** no packaged runtime supported yet.

## Nodes

| Node ID | Purpose |
|---|---|
| `FotufilmDevelopVideo` | Develop a VIDEO through Fotufilm; MP4, ProRes 422 HQ or eligible HLG output. |
| `FotufilmDevelopFrames` | Develop IMAGE frame batches; returns **linear Display P3 float** frames. |
| `FilmFinishHDRPad` | Pad video to LTX spatial / temporal alignment. |
| `FilmFinishHDRRestore` | Crop reconstruction back to the original dimensions and frame count. |
| `FilmFinishSaveHDRVideo` | Save linear frames as Rec.2020 HLG HEVC 10-bit with audio. |
| `FilmFinishSaveHDRMaster` | Save RGB32F EXR frames, float preview data and the source playback/audio in an `.ffhdr.zip` bundle. |
| `FotufilmDevelopHDRMaster` | Develop a saved float master into MP4, ProRes or eligible HLG. |

Category: **Film Finish**. IDs intentionally match existing workflows.

The pack does **not** perform neural SDR-to-HDR conversion by itself. The included LTX 2.5 workflow requires [ComfyUI-LTXVideo](https://github.com/Lightricks/ComfyUI-LTXVideo) at `3bf3ca62595f1764c47d01c35c8e5dfe47e1a88f`, the model files named in that workflow, and `colour-science==0.4.7`. Install model weights on your remote models volume, not in this repository or the container image.

## Workflows and color

Drag a grouped workflow from [`examples/`](examples/) into ComfyUI. The full graph separates input, LTX 2.5 reconstruction, restoration, float master, HLG delivery, Fotufilm finishing and an SDR control. A smaller saved-master graph lets you iterate on film recipes without re-running LTX.

The saved-master handoff is a **file boundary**: copy/upload the resulting `.ffhdr.zip` into ComfyUI's input folder and enter its relative filename in `FotufilmDevelopHDRMaster`. The workflow notes explain which output nodes to enable at each step. JSON files ending in `.api.json` are API graphs; the two `Film Finish - … .json` files are editable UI graphs.

Recipes in `examples/*.recipe.json` select film, print/scan, exposure and texture. HDR delivery currently requires a direct-view slide-film recipe with **Reference exposure**, such as the supplied Ektachrome recipe. Negative/print recipes produce an SDR finish even when the input is HDR. An SDR node thumbnail does not display the full float range; use the HLG video or EXR master in a color-managed HDR viewer.

This repository contains nodes only. It does not install the Film Finish browser app, web routes, deployment authentication or a job service.

## Container image integration

Clone a **commit SHA**, install `requirements.txt`, then execute `install.py` during image build. Installing only Python dependencies is insufficient: Fotufilm needs its native libraries and stock resources. The files live beside the pack in `linux-runtime/`; downloads are cached in `.runtime/`. Both directories are gitignored. The installer performs no model inference.

Run `python scripts/check_runtime.py` for a build-time ABI check. On a GPU worker, `python scripts/check_runtime.py --render` also verifies engine initialization and video decoding. Run `python -m unittest discover -s tests` with ComfyUI's Python (plus `colour-science`) for float-master checks.

## License and attribution

The ComfyUI adapter is **GPL-3.0-only**, retaining the Film Finish source license. Fotufilm engine code is **Apache-2.0**; its film profiles are **CC BY-SA 4.0**, attributed to **Fotufilm — https://fotufilm.com**, copyright MUAStudio Inc. Profiles are unmodified. Upstream notices are retained in [`upstream/`](upstream/); the runtime installer preserves bundled notices and records source URLs/checksums. Rendered videos do not inherit the profile license.

Native binaries are downloaded directly from upstream distributions during installation, not redistributed in this Git repository. FFmpeg and its codecs retain their own licenses; the installer changes only FFmpeg dynamic-library name references to match Fotufilm's ABI. See [`runtime/README.md`](runtime/README.md).

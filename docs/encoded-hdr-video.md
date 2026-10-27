# Opening an existing HDR video

Use **Fotufilm - Open HDR video.json**: Load Video → Film → Color. Both editors share the original VIDEO; Film passes its settings to Color. Choose your file and the preview starts without queuing a graph. No reconstruction or archive is needed.

The importer now accepts tagged BT.2020 **HLG** and **PQ** MP4/MOV files, including 10-bit H.264 and HEVC supported by the server's PyAV decoder. Untagged or conflicting HDR color metadata is rejected rather than guessed. HDR10+ and Dolby Vision dynamic metadata are not applied; this path interprets tagged HLG/PQ pixels only.

The server expands YUV video range, uses the BT.2020 non-constant-luminance matrix, then removes the HLG/PQ transfer curve. Film and grading receive float32 linear Rec.2020, including values above 1. HLG uses a reference 1000-nit display, system gamma 1.2 and 75% signal diffuse white; PQ is normalized to 203-nit diffuse white. These are documented interpretations of a finished HDR signal, not a recovery of the original scene exposure. See the [BBC/W3C reference-white explanation](https://www.w3.org/Graphics/Color/Workshop/slides/talk/cotton2) and [PyAV's reformatter API](https://pyav.basswood.io/docs/develop/api/video.html).

For HDR movies, the node prepares a cached 768px SDR H.264 copy at the original frame rate, with audio. It drives the timeline and sound only. The native film renderer reads the **original HDR file**, linearizes at full resolution, then resizes to the chosen preview size. Export reads the original resolution. The source label reports original dimensions; preview status reports rendered dimensions. The monitor stream remains SDR; this change does not add calibrated HDR display output.

Constant-frame-rate videos seek to a preceding keyframe when a new frame reader starts away from frame zero. This avoids decoding the entire earlier clip on backwards scrubs. Source frames are streamed, not collected into one giant IMAGE batch. At 3840×2176, a 409-frame RGB float32 batch alone is roughly 38 GiB; keep file input connected for interactive finishing.

## Local validation — 2026-10-27

Tested with the supplied 3840×2176, 48 fps, 409-frame H.264 High 10 HLG movie. Import metadata, headroom, compatible playback preparation, native film preview and the separate Color editor are checked locally in Comfy Desktop. No AI model inference is needed. A 640px source-frame read took about one second on the Mac; one-time playback preparation took about nine seconds. The expanded editor correctly uses the 48 fps source timeline instead of its 24 fps widget default. A brief moving 640px preview reached about 8 fps on this Mac; this is a local check, not an RTX benchmark or a real-time guarantee.

Validation: 32 UI tests and 29 focused processing/export tests passed. Regression tests cover HLG/PQ reference values, float32 headroom, incorrect metadata rejection, exact CFR frame seeking, playback frame count/rate/audio, and the original-HDR UI state. The existing LTX reconstruction, NVIDIA conversion, float archive and native export branches remain available for their respective inputs.

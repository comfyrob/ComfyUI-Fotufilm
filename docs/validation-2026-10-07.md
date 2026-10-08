# Native Studio verification — 2026-10-07

## Implemented

- Existing Load Video input plays before graph execution; existing float master can be reopened without LTX.
- Native Gear balance → Fotufilm → Gear finish pipeline shared by frame previews, playback, frame nodes and export.
- Original/HDR source controls separated from the same-source before/after finishing divider.
- Automatic cancellable previews, 960/1440px quality choices, real first-frame Look cards, modified look state, color wheels, undo and explicit export.
- Six functional nodes in the consolidated HDR graph; separate BF16 reference, Modal INT8 paths and saved-master workflow.

## Runtime checks

ComfyUI 0.39.0, frontend 1.53.10; real pinned Fotufilm v1.11 Linux runtime. **18 tests passed**, including float/negative preservation, explicit gamut conversion, real preview/export processing parity, video frame count, frame rate, audio retention, ProRes/HLG delivery tags, safe file resolution, cancelled-job behavior and acyclic graph/master handoff.

HTTP tests rendered a 960×540, 120-frame / 24fps demo clip. No AI models were loaded. On a four-core CPU test worker the cold still took 16.7s and the five-second playback render took 73.7s. A separate L4 test measured a cold still at 20.6s, warm still at 1.18s, and 24 frames at 8.69s (960px, grain off, exposure +0.25 and finish saturation 0.85). These are measured render times, not playback frame rates or guarantees for other recipes/hardware. Film texture and resolution affect cost.

## Browser checks

Nodes 2.0 was enabled in the isolated test instance. Confirmed existing video loaded without queue execution, pointer dragging moved the divider (51% to approximately 78%), keyboard movement worked, and Grade changes started native previews. Enlarging Studio exposed the same grading controls and color wheels. All 12 native Look thumbnails loaded. A synthetic 384×216 float master (24 frames, 24fps; explicitly a test fixture, not an LTX result) opened before graph execution. Switching to Original and back to Enhanced HDR worked. Studio exported it to a finished MP4, and the connected saved-master graph completed successfully, returning the video and the exact saved grade (balance exposure −0.05 EV) to Studio. Browser playback advanced at 1× with a fully buffered clip. Browser dropped-frame counters were not available through the test API, so no measured 24fps display guarantee is claimed.

## Deployment boundaries

The changes were exercised in an isolated Modal test app without model/output volumes. The existing `comfyui-rtxpro6000-a` app was not stopped or redeployed. Local Mac work was limited to source edits and UI control; native rendering ran remotely.

LTX inference and the Modal INT8 reconstruction variant were not rerun by this change. Model filenames match the inspected Modal volume, but this does not constitute inference validation. Native HDR generation/upscaling remain deferred.

## Limits

The current player is an **SDR display conversion of float processing**, not a calibrated browser HDR monitor. HLG exports require an eligible direct-view slide-film recipe. Native frame updates are asynchronous; playback becomes a normal browser-decoded clip once rendered. Automatic playback is limited to the first 20 seconds; exports process the whole clip. VFR conforming, dedicated HDR luminance scopes, LUT export and instantaneous continuous slider rendering are not implemented.

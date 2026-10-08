# Native Studio in Nodes 2.0

Studio uses public extension hooks (`nodeCreated`, `loadedGraphNode`, `executed`, `onNodeOutputsUpdated`) and `addDOMWidget`. The outer node retains ComfyUI's ports, resize handles, selection and subgraph behavior. No private Vue renderer is replaced. Modern Node Design is a user setting; the pack does not force it on.

## Source discovery and HDR order

The connected Load Video file widget is resolved without executing its producer, following the core video editor's file/output resolution pattern. Cached VIDEO outputs and subgraph output links are supported. A processing node with no cached output is not treated as a source file. Lightweight connection checks discover a changed file and clear old source/preview state.

A Load HDR Master file can be registered without execution. Save HDR Master's completed output is discovered after reconstruction. The source bundle retains RGB32F EXRs with explicit primaries. The embedded original video is used for timing and audio; it is never used as the HDR image input to Fotufilm.

The consolidated workflow has six functional root nodes and an instruction note:

`Load Video → LTX 2.5 subgraph → Save HDR Master → Studio → Develop HDR Master → Return to Studio`

The original VIDEO also feeds Studio and Save HDR Master. Studio passes the typed master through and supplies its edited recipe. LTX receives no recipe connection, allowing fixed-seed reconstruction cache reuse. The 25-node LTX subgraph remains editable. Use the saved-master example after a restart to avoid relying on the execution cache.

## Processing

`float source → Gear balance (ACEScct/AP1) → Fotufilm → Gear finish → display/delivery conversion`

Input spaces are explicit; the adapter avoids Gear's Rec.709 input clamp. Neutral grading preserves the float buffer exactly. PNG previews and H.264 playback are SDR display conversions. A display histogram is labelled SDR; it is not an HDR luminance scope. HLG export remains limited to direct-view slide film / Reference exposure.

The Gear math is pinned and attributed in `vendor/`. Final video exports and frame-batch nodes use the same `Finisher` as interactive previews, including deterministic per-frame grain seeds. Preview downsampling can change texture, so it is not a substitute for full-resolution grain inspection.

## Interactive rendering

Edits debounce for 250 ms, cancel superseded frame/playback work, request a current-frame native render, and then prepare a browser-decodable playback clip. Stale responses cannot replace newer recipes. Frame seeking uses a separate request channel from playback. Opening the enlarged Studio disposes the inline editor's jobs; closing it restores the node editor.

Jobs use the existing ComfyUI HTTP server. They do not submit the execution graph, load AI models, or call Developer Platform implicitly. The file resolver restricts reads to Comfy input/output/temp directories. The serialized worker bounds rendering concurrency; source registration and job status remain responsive. Queue cancellation removes pending futures. Cache keys include the source fingerprint, renderer code signature, recipe, frame and resolution. Preview cache is capped at 2 GiB; it is not durable storage.

Look thumbnails are native renders of the active source's first frame, generated after the main playback render. They resume from cached thumbnails after edits. A complete Look includes film, color and texture; changing components preserves its name with a Modified badge. Save to node persists the recipe, including grading.

## Export and graph execution

Studio Export uses the active Original/HDR source and the current recipe, at source resolution. The graph's Run workflow follows its actual wired inputs and may execute uncached LTX stages. These are separate explicit actions. Return to Studio correlates a downstream render with an opaque execution token and exact recipe, so there is no graph cycle.

Automatic previews render the first 20 seconds at a selected 960px or 1440px long edge, never upscaling. Exports render the complete source, with audio and frame rate retained. Source clips are treated as constant-frame-rate sequences; VFR conforming and calibrated browser HDR output are not part of this release.

## Verification

See `validation-2026-10-07.md` for the tested environment, timings and limits. Tests cover float headroom, explicit color conversion, real still/export math parity, video frame count/timing/audio, cancellation, file containment and graph connectivity. There is no LTX inference in these finishing tests.

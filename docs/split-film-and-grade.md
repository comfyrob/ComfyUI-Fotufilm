# Film, grade and viewer

Open **Fotufilm - Film + Color Grade.json** for an existing SDR clip, or **Fotufilm - LTX HDR + Film + Color Grade - Modal.json** for the pinned LTX 2.5 workflow. Existing Studio workflows remain compatible.

The graph has two editable control nodes:

- **Film Emulation** chooses a Look (film, texture and default colors), film stock, print and texture. Look defaults remain part of the recipe.
- **Color Grade** edits finishing colors with Gear math. Its visible wheels and sliders start at the selected look's defaults. Reset restores those defaults. Changing a look updates untouched controls and retains explicitly changed controls.

Both nodes preview the same source through the shared renderer. Their `recipe_json` connection describes the processing order; it does **not** contain processed pixels. Their `source_video` output is the original video. Connect the same linear IMAGE batch and its declared color space to both nodes and to the optional export. Color Grade's combined recipe feeds the export node. This avoids eagerly developing an entire video simply to open another viewer.

Film edits propagate to a directly connected Color Grade editor without queueing. Save to node in Color Grade also saves the connected Film node's current recipe. The optional queued export uses those saved controls. Unsaved controls are session drafts; a saved workflow stores the saved widget values. Arbitrary nodes inserted into the recipe connection require their normal Comfy execution; the extension does not pretend to evaluate an arbitrary graph live.

## Color contract

LTX's `acescct` decode produces linear **ACEScg**. Remove Padding crops excess spatial/frame padding without changing those values. The source adapter explicitly converts ACEScg to linear Rec.2020 for Fotufilm. Fotufilm produces linear Display P3. Gear operates in ACEScg internally and returns to the declared input gamut. These are float processing buffers, not display video.

The new examples select a fixed SDR highlight roll-off, independent of film selection (`sdr_output: rolloff`). Live frames, still previews and SDR exports use one implementation: declared input gamut → linear Rec.709 → highlight roll-off → sRGB display encoding. The roll-off is a simple per-channel shoulder starting at 0.7, **not** an ACES or AgX output transform. Saturated out-of-gamut colors still clip at the final SDR boundary. Older recipes without `sdr_output` retain their previous output curve.

The viewer offers:

- **SDR output**: the recipe's SDR output transform. At 0 viewing EV and Finished result, it matches SDR export before codec quantization.
- **HDR range → SDR**: a highlight-compressing inspection view.
- **Uncompressed → SDR**: no highlight compression; values outside the display range clip. This does not turn the screen into an HDR monitor.
- **View EV**: temporary exposure to examine bright or dark areas. It never changes the grade or export.
- **Show**: connected source, film before color grading, or finished result. Color Grade's before/after compares film before finishing color against the final grade. Film's comparison uses the connected source.

Both comparison halves use the same view settings, gamut conversion and frame index. Preview frames use an SDR PNG or H.264 transport. They never become the EXR/HDR master or the input to final export. True HDR display output, perceptual gamut mapping and a calibrated output transform remain separate work.

## Performance

Film and Grade reuse registered float frames and the server's developed-film cache. Finishing controls do not enter the film cache key. Changing viewing exposure or the monitor stage does not invalidate film processing. The source-only live view can skip the film engine entirely. Cache misses, initial native compilation, network transit and 8-bit monitor encoding still cost time; this change makes no universal real-time guarantee.

Optional archives and still saves stay outside the interactive path. The LTX model pins, generative HDR process and float output remain unchanged. No new weights are required.

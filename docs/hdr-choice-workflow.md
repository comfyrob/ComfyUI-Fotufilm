# Start here: finish your video

## 1. Choose your source

Load your video, then choose **Original SDR**, **NVIDIA HDR**, or **LTX 2.5 HDR** in **Choose HDR Method**. Run the workflow once to prepare the selected source for both editors.

- **Original SDR:** no HDR generation. Start here for ordinary film finishing.
- **NVIDIA HDR:** enhances SDR with RTX Video HDR. Its contrast/saturation controls shape the source; the later Color Grade node shapes your finished look.
- **LTX 2.5 HDR:** our generative reconstruction workflow. It can infer new highlight detail and can also change details. Its existing models, sampling and HDR decode remain intact.

Only the selected image branch is requested. Do not add active save/preview outputs directly to an unselected branch: output nodes can independently make that branch execute. Keep LTX seeds fixed to reuse cached results. Selecting a different method is a source-processing decision, not an instant display toggle. A cache hit can reuse previously processed frames; a restart or cache eviction cannot.

The combined example requires both NVIDIA and LTX packs and the LTX model files. Use the SDR/NVIDIA-only example if you do not have LTX installed. The HDR method selector does not hide missing-node or missing-model validation errors. Heavy processing belongs on your remote GPU environment, not your Mac.

## 2. Choose a look, then adjust color

Open **Film Emulation** and choose a Look. A Look is a complete starting recipe: film stock, print response, texture and default colors. Film stock is one ingredient, not another competing preset.

Open **Color Grade** to adjust the finished result. Exposure changes brightness, warmth/tint balance color, and the wheels tint shadows, midtones and highlights. Small changes are usually enough. Reset restores the selected look's defaults.

Film and Grade receive the **same prepared image frames**. The wire between them carries **settings**, not rendered video. The shared renderer combines those settings for preview and export; this avoids developing a whole video just to open the next node. Film edits update a directly connected Grade editor. Click **Save to node** before a queued export or saving the workflow so the graph uses your latest choices.

The new Film node exposes only `film_settings`; Color exposes only `finished_settings`. Both are saved settings (Comfy STRING), not video or pixel buffers. Older Studio/Film Emulation/Color Grade nodes remain available for saved workflows, with their original ports. The new workflow needs neither a session wire nor a custom HDR master type.

## 3. Understand what the viewer shows

Choose **640 Fast** or **960 Balanced** for a smaller preview. **1280 Detailed** and **1920 Inspect** help judge texture. These sizes are the longest edge, capped at the source size. They do not change your saved resolution or source frame rate. Smaller previews make fine grain harder to judge; they do not promise a fixed playback speed.

The current player displays an **SDR representation**, even when the source contains HDR. HDR data remains in the processing pipeline; a brighter HDR-capable monitor alone does not make this transport HDR.

**Before / after** compares the same source frame. In Color Grade, Before is the film result before finishing adjustments; After is your grade. In Film Emulation, Before is the prepared source. This is not a comparison between NVIDIA and LTX.

**Inspect HDR** contains optional viewing tools. **Processing stage** selects source, film or final result. **Preview brightness** temporarily reveals bright/dark detail without changing your grade or export. **Display mapping** chooses how bright values fit onto the SDR screen. For the ordinary finished preview, use **SDR output**, **Finished result**, and **0 EV**. Actual Exposure in Color Grade does affect the export.

## 4. Save only what you need

- **Export finished video:** enable its `enabled` control and run. It renders the original-resolution selected source with the saved film and grade, retaining the original audio and frame rate. Disable it again when you only want to prepare/edit a source. MP4 is the ordinary SDR choice. HDR HLG currently requires a supported direct-view slide-film finish; an HDR source alone does not guarantee an HDR output.
- **Save source EXR sequence:** unmute this native Save Image (Advanced) node and run. It saves the selected source before film and grade. It does not archive every HDR method. In Original SDR mode, float EXR does not invent extra highlight detail.
- **Save finished EXR sequence:** unmute its native save node and run. The render branch applies film and grade at original resolution, then saves linear frames before the SDR display transform. This batch render can use substantial memory on long clips.

The two EXR save nodes start **muted**. Use the node's mode/menu to enable one, then mute it again afterward. Do not use bypass as an output toggle. EXRs are separate numbered frames, not a playable movie: retain the workflow, original video/audio and frame rate for later reassembly.

Both native savers are set to **EXR / 32-bit float / linear**. The preceding nodes explicitly convert to linear Rec.709, preserving negative and above-white values. Here Rec.709 describes RGB coordinates; it does not clamp the frames to SDR. Do not change the saver to `HDR`: in this core node that means HLG-encoded input, which these wires are not. NVIDIA uses PQ → linear through core; LTX uses ACEScg → linear Rec.709 after padding removal. Their different brightness models can produce different film responses.

The legacy **Archive HDR source** node bundles float frames, timing and the original video in a custom `.ffhdr.zip`. It remains available for existing workflows, but is unnecessary in this native EXR workflow.

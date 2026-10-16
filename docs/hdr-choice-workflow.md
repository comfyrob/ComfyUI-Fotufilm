# Start here: finish your video

## 1. Choose your source

Load your video, then use core's **If/Else Switch** nodes. Run once to prepare the selected source for both editors.

| Source | Use HDR? | Use LTX? |
| --- | --- | --- |
| Original SDR | Off | Ignored |
| NVIDIA HDR | On | Off |
| LTX 2.5 HDR | On | On |

The SDR/NVIDIA example has just the first switch. `on_false` means Off; `on_true` means On. These are native, lazy switches: they request only the selected input. The old custom Choose HDR Method node remains compatible with older graphs but is no longer used here.

- **Original SDR:** no HDR generation. Start here for ordinary film finishing.
- **NVIDIA HDR:** enhances SDR with RTX Video HDR. Its contrast/saturation controls shape the source; the later Color Grade node shapes your finished look.
- **LTX 2.5 HDR:** our generative reconstruction workflow. It can infer new highlight detail and can also change details. Its models and sampling remain intact. A small on-demand adapter calls the same upstream HDR decoder without its independent save/output trigger, so selecting another source does not run LTX.

Only the selected image branch is requested. Do not add active save/preview outputs directly to an unselected branch: output nodes can independently make that branch execute. Keep LTX seeds fixed to reuse cached results. Selecting a different method is a source-processing decision, not an instant display toggle. A cache hit can reuse previously processed frames; a restart or cache eviction cannot.

The combined example requires both NVIDIA and LTX packs and the LTX model files. Use the SDR/NVIDIA-only example if you do not have LTX installed. The HDR method selector does not hide missing-node or missing-model validation errors. Heavy processing belongs on your remote GPU environment, not your Mac.

## 2. Choose a look, then adjust color

**Film Emulation opens expanded.** Choose a Look from **Start here**, then explore the categories or **All**. There are 36 starting looks and 16 directly selectable stocks. These are independently authored Fotufilm recipes, not copies of Osmo presets or camera-manufacturer profiles. First-frame thumbnails are illustrative; use the playing viewer to judge your clip.

A Look is a complete starting recipe: film stock, print response, texture and default colors. Film stock is one ingredient, not another competing preset. The pinned header keeps the selected look visible when you browse another category. **Modified** means you changed its recipe. The reset arrow returns to that look's defaults.

Open **Color Grade** to adjust the finished result. Exposure changes brightness, warmth/tint balance color, and the wheels tint shadows, midtones and highlights. Small changes are usually enough. Reset restores the selected look's defaults.

Film and Grade receive the **same prepared image frames**. The wire between them carries **settings**, not rendered video. The shared renderer combines those settings for preview and export; this avoids developing a whole video just to open the next node. Film edits update a directly connected Grade editor. Click **Save to node** before a queued export or saving the workflow so the graph uses your latest choices.

The new Film node exposes only `film_settings`; Color exposes only `finished_settings`. Both are saved settings (Comfy STRING), not video or pixel buffers. Older Studio/Film Emulation/Color Grade nodes remain available for saved workflows, with their original ports. The new workflow needs neither a session wire nor a custom HDR master type.

## 3. Understand what the viewer shows

Choose **640 Fast** or **960 Balanced** for a smaller preview. **1280 Detailed** and **1920 Inspect** help judge texture. These sizes are the longest edge, capped at the source size. They do not change your saved resolution or source frame rate. Smaller previews make fine grain harder to judge; they do not promise a fixed playback speed.

The current player displays an **SDR representation**, even when the source contains HDR. HDR data remains in the processing pipeline; a brighter HDR-capable monitor alone does not make this transport HDR.

**Before / after** compares the same source frame. In Color Grade, Before is the film result before finishing adjustments; After is your grade. In Film Emulation, Before is the prepared source. This is not a comparison between NVIDIA and LTX.

**Inspect HDR** contains optional viewing tools. **Processing stage** selects source, film or final result. **Preview brightness** temporarily reveals bright/dark detail without changing your grade or export. **Display mapping** chooses how bright values fit onto the SDR screen. For the ordinary finished preview, use **SDR output**, **Finished result**, and **0 EV**. Actual Exposure in Color Grade does affect the export.

## 4. Save only what you need

- **Save finished video:** unmute the native **Save Video** node and run. **Render film + color at full resolution** applies your saved recipe, then its `sdr_images` output feeds native **Create Video → Save Video**. The original audio and frame rate are connected. Create Video is set to **sRGB** because these frames already use the same SDR display transform as the normal editor preview. Do not relabel them HDR. This is an SDR delivery, including when you started with HDR.
- **Save source EXR sequence:** unmute this native Save Image (Advanced) node and run. It saves the selected source before film and grade. It does not archive every HDR method. In Original SDR mode, float EXR does not invent extra highlight detail.
- **Save finished EXR sequence:** unmute its native save node and run. The render branch applies film and grade at original resolution, then saves linear frames before the SDR display transform. This batch render can use substantial memory on long clips.

All three native save nodes start **muted**. Enable only the output you need, then mute it again afterward. Muted output branches do not render a final video while you are editing. Do not use bypass as an output toggle. EXRs are separate numbered frames, not a playable movie: retain the workflow, original video/audio and frame rate for later reassembly.

Native video assembly holds the finished frame batch in memory, including linear and SDR copies. For long/high-resolution clips, the legacy **Fotufilm Develop Video** node remains a more memory-efficient frame-by-frame exporter and retains its ProRes/eligible HLG options. It is not required in this graph. Choosing native saving simplifies integration; it does not remove the cost of rendering the final frames.

Both native savers are set to **EXR / 32-bit float / linear**. The preceding nodes explicitly convert to linear Rec.709, preserving negative and above-white values. Here Rec.709 describes RGB coordinates; it does not clamp the frames to SDR. Do not change the saver to `HDR`: in this core node that means HLG-encoded input, which these wires are not. NVIDIA uses PQ → linear through core; LTX uses ACEScg → linear Rec.709 after padding removal. Their different brightness models can produce different film responses.

The legacy **Archive HDR source** node bundles float frames, timing and the original video in a custom `.ffhdr.zip`. It remains available for existing workflows, but is unnecessary in this native EXR workflow.

## 5. Why the small color conversion remains

“Linear” describes how brightness is encoded; it does not specify which red, green and blue coordinates are used. LTX's ACEScct decoder returns **linear ACEScg**. Core's `linear` means **linear Rec.709**. Our conversion changes those coordinates without clipping the highlight range. Current core accepts encoded ACEScct but does not offer raw linear ACEScg or linear Display P3 as input choices. Selecting ACEScct for an already-decoded linear image would decode it twice and produce wrong colors.

The [official LTX 2.5 Tiled Fusion HDR example](https://github.com/Lightricks/ComfyUI-LTXVideo/blob/master/example_workflows/2.5/HDR_workflows/LTX-2.5_V2V_TiledFusion_SDR_to_HDR.json) uses SDR → ACEScct preprocessing, generative sampling, LTX HDR decoding, EXR/HLG output and native Save Video for its preview. It does not contain a dedicated artistic color-grade or film-emulation stage. Its decoding is the basis for our HDR source, not a replacement for Fotufilm or the Color node. Our existing model and sampling settings are preserved; this update changes routing, editing and saving.

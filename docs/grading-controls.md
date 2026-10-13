# Studio and the node graph

Studio is for choosing a look and adjusting its finished color and texture.
It has one set of color controls: Exposure, Warmth, Tint, Contrast, Saturation,
Grain and Halation. Shadows, Midtones and Highlights wheels stay visible in
Color & texture. Highlights/shadows sliders, Vibrance and the Overall wheel
remain under More color controls.

Gear's lift/gamma/gain wheels affect overlapping tonal ranges, not isolated
masks. Click or drag toward a color, use arrow keys to fine-tune, or Home to
center the tint. Numeric fields accept exact slider values. Undo restores the
recipe and look selection. Changing film marks a preset Modified.

## Source correction belongs before Studio

The optional **Fotufilm · Balance Source** node applies the same float Gear math
to IMAGE frames before film. Select the actual input space: LTX HDR restoration
is linear ACEScg; decoded ordinary SDR frames from Get Video Components are
sRGB. Its output is always linear ACEScg, including when correction is disabled.
No HDR highlight reconstruction, film simulation or display transform occurs
in this node. Values above one and negative linear values stay available.

Connect its output to Studio's `images` input and the optional Develop Video
`images` input; keep both set to `linear-acescg`. Connect the original VIDEO for
audio/timing. Queue after changing Balance Source. Comfy reuses cached upstream
LTX output when its inputs and seed are unchanged. Studio's Before/after then
shows **the corrected source versus the finished film look**; it is not an
uncorrected/corrected-source comparison. Branch raw and corrected frames to
separate inspection nodes if you need that comparison.

This advanced graph correction is not a live Studio control. Everyday finishing
color is still interactive and does not rerun LTX. The Studio source selector's
legacy “Enhanced HDR” label currently identifies the connected linear-frame
branch; it does not prove that a model reconstructed those frames.

Older recipes may contain a `grading.balance` correction. Studio preserves it
and shows **Saved input correction is active**. Clear correction removes it and
Undo restores it. If moving those values to Balance Source, clear the embedded
correction to avoid applying it twice. No automatic migration changes saved looks.

## Stills belong on an optional output branch

Use **Fotufilm · Save Still (EXR)** (`FotufilmInspectFrame`, same stable node ID).
Connect one source (IMAGE, VIDEO or master) and Studio's `recipe_json` output.
Choose a frame and enable the branch when you want a still. The new example
starts it disabled. Advanced `stage=finish` saves the final look; `source` saves
connected pixels without reapplying film. Do not apply `finish` to already
finished frames. Choose their correct input space (linear Display P3 for
Develop Frames). The node writes full-resolution RGB32F EXR with Rec.2020
chromaticities and returns linear Rec.2020 IMAGE pixels.

Studio no longer contains a still-save dropdown, histogram or graph-run button.
Save to node stores the recipe; use Comfy's Run control for the graph. Studio's
Export video action still provides a direct full-resolution export of its active
source; graph exports remain available separately.

## Look previews

Native first-frame thumbnails now use a separate cancellable batch. Playback,
seeking and finishing edits that do not alter preset previews cannot restart it.
Thumbnails render sequentially at 384px, behind interactive frames in the server
queue. Completed results are cached. Source or relevant recipe changes invalidate
them; failed job/image loads expose Retry previews. Images are decoded before
being shown. There is no ungraded-image substitute masquerading as a film preview.

## Monitor limitations

The monitor is SDR. Processing retains float HDR range, but the display cannot
show all its brightness. EXR preserves values that already exist; it does not
create detail. Native engine initialization, the network and server load still
limit first-frame latency. This UI update does not promise real-time playback
for every film/resolution.

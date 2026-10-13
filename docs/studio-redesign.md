# Studio UI update · 0.3.2

Scope: Fotufilm's ComfyUI DOM widget, enlarged Studio, thumbnail loading and
optional graph branches. No standalone web app, engine upgrade, model change
or LTX inference is included in this pass.

## What changed

| Problem | Resolution |
|---|---|
| Two grading stages without a corrected-source monitoring view | Studio exposes finishing color only. Optional Balance Source applies float Gear correction upstream in the graph. |
| Still-saving controls interrupt the editing flow | Save Still (EXR) is a separate output node with an enable switch; its existing node ID is preserved. |
| Histogram adds noise to a casual finishing editor | Removed from Studio, including its canvas readback work. |
| Look thumbnails depend on paused live-frame callbacks | Independent sequential jobs, stable request keys, decoded images, bounded node-session cache and visible retry. |
| Green-tinted chrome and lengthy control panels | Neutral dark editing surfaces, restrained blue accent, segmented tabs, visible wheels first, concise copy. |

Studio deliberately keeps neutral dark chrome even if the surrounding ComfyUI
canvas uses a light theme. This avoids tinting the editing surround or mixing
light theme tokens with dark-only control text. Native ComfyUI still owns node
ports, graph controls, resizing and the dialog's host environment.

Older recipe input corrections remain active and are labelled. Clear correction
is explicit and undoable. Their values are not silently moved or dropped.

## Verification

- 51 Python tests passed on the isolated RTX PRO 6000 Modal worker, including
  native film tests, signed/above-one float preservation, disabled still output
  and the neutral correction node's no-copy path. No neural generation ran.
- 14 JavaScript tests passed across the suites: thumbnail cancellation, source
  changes, image failure/retry, cache reuse, live stream revisions, UI controls,
  old recipe preservation, undo, and export cancellation.
- New example graph checked for reciprocal links, slot types and cycles. New
  node widget counts/order matched `/object_info` on ComfyUI 0.39.0.
- Actual Nodes 2.0 inline editor and enlarged dialog exercised on frontend
  1.55.14. All 12 native 384px look thumbnails loaded, including during playback.
- Keyboard wheel editing changed the tint, enabled Reset and showed Modified;
  reset restored neutral. Keyboard comparison divider changed from 50 to 51.
- At a 320px viewport the Studio, header, sidebar, footer and content had no
  horizontal overflow; the video stayed above the independently scrolling panel.
- Browser screenshot evidence is saved locally under `.runtime/studio-redesign-*.png`.
- Desktop dark-theme text and primary-button contrast measured. Final explicit
  neutral palette additionally checked numerically. Reduced-motion guards and
  forced-color focus styles present in source.

Not verified: screen-reader speech output, RTL, 200% browser/text zoom, a new
end-to-end LTX reconstruction, or this workflow on the user's separate model
instance. This is not a comprehensive accessibility certification or a claim
of universal 24fps performance. The video monitor remains SDR.

## Running the graph

`examples/Fotufilm - Balance + Studio + optional still - Modal.json` uses the
existing LTX 2.5 Modal model paths. Balance Source sits between reconstruction
and Studio/final export. Archive keeps uncorrected HDR. Save final still starts
disabled and uses `stage=finish`, linear ACEScg input, and Studio's recipe.

Change graph corrections and use Comfy Run; cached upstream results can be reused.
Use Studio's live color controls for fast finishing adjustments. Save to node
before running a graph export or still branch. See `grading-controls.md` for
source and finished-frame color spaces and legacy correction behavior.

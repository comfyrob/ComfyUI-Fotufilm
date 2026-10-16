# Looks and output branches

Updated 2026-10-16 on `explore/film-look-library`.

## 54 editable looks and 28 stocks

The library opens on All. Collections are Cinema, Portrait, Slide, Vintage,
B&W and Experimental. Search includes look names, stock names and descriptions.
Star a card to save it to Favorites on this browser; favorites and search do
not alter the active recipe. The selected look remains pinned above the cards.

The first 36 recipes and their IDs are unchanged. This branch adds:

| Collection | New looks |
| --- | --- |
| Cinema | Reala dailies, Dense release print, Muted thriller |
| Portrait | Daylight portrait, Warm interior, Clean beauty |
| Slide | Travel chrome, Quiet landscape, Summer chrome |
| Vintage | Faded home movie, Seventies print, Cool telecine |
| B&W | Studio monochrome, Grainy night, Soft documentary |
| Experimental | Instant memory, Silver retention, Phoenix shift |

Twelve additional **existing Fotufilm profiles** are exposed: Kodachrome 25/64,
CineStill 400D, UltraMax 400, Pro 160NS, Reala 500D, Eterna Vivid 500,
HP5 Plus 400, T-Max 100, Delta 3200, Instax Mini and Phoenix 200.
These are bundled upstream simulations, not new measurements made by this pack.

A stock is an ingredient; a look combines stock, film size, print/scan, texture
and optional finishing color. Changing a stock keeps the selected look name
with a Modified indicator. Color remains editable in the separate Color Grade
node. Selecting a look preserves input correction. Keep my color settings
preserves the current finishing grade; otherwise the look supplies its defaults.

Silver retention is a creative bleach-inspired contrast/desaturation treatment.
Phoenix shift is a creative cross-process-inspired grade. Neither claims a
chemical processing simulation. Instant memory uses the Instax profile with
our existing Medium film-size setting for texture scale; it adds no border or
physical Instax frame geometry. No Osmo presets, tables or shaders are included.

The new Kodachrome slide looks use Reference exposure and the existing eligible
HDR output path. Instant reflection-print and negative-print looks finish to
SDR even from HDR input. Playback continues to show an SDR display conversion.

## Preview and compatibility

Only visible look cards and the pinned selected look request first-frame
renders. The editor cancels stale batches on source/filter changes and reuses
cached images by source, complete recipe and installed engine. Playback retains
scheduler priority. Thumbnail size is unchanged at 384px; main preview and
export resolution/frame settings are unchanged.

`GET /fotufilm/catalogue` reports the profiles in the server's configured stock
bundle. Missing profiles remain visible but disabled. A failed inventory check
explains that the editor must be reopened after updating the server. Rendering
a missing profile also raises an explicit error; it cannot silently become a
different stock. CPU/macOS fallback runtimes may have a different catalogue.

`web/viewer/catalogue.js` is the versioned data module; `model.js` retains recipe
composition. Stock metadata records profile provenance and candidate defaults.
The Film selector changes just that ingredient, preserving the other controls;
finished look cards apply their complete recipe.

[`examples/studio-looks.json`](../examples/studio-looks.json) contains every full
recipe for graph/API use. Regenerate with `node scripts/export_looks.mjs`; verify
with `--check`. Old workflow recipe values are not migrated or overwritten.

## Current outputs

The current combined Film + Color Grade workflows already use native optional
save branches. See [the current HDR-choice workflow guide](hdr-choice-workflow.md).
This catalogue experiment does not change those branches or require an archive
between HDR reconstruction and film processing.

### External sources considered

- [FujifilmCameraProfiles](https://github.com/abpy/FujifilmCameraProfiles): camera
  matching profiles and LUTs, licensed CC BY-NC-SA 4.0. Its main LUTs expect a
  linear-contrast camera rendering in the specified sRGB or Display P3 space;
  its conversion LUTs expect a Provia rendering. Those are not interchangeable
  with our linear ACEScg HDR frames or Fotufilm's linear P3 output. No assets or
  numeric tables from that project are bundled here. A future optional LUT
  node needs an explicit color/transfer contract and license/provenance handling.
- [Redlamp film simulations](https://github.com/pdcgomes/redlamp#film-simulations):
  its offline film model bakes scene-referred 33³ tables, with separate spatial
  effects at runtime. That is a useful future performance/stock-expansion path,
  not a preset JSON format Fotufilm can load. Reusing those assets would require
  adapting the table domain, tone mapping and effects to our engine. Current
  additions do not copy Redlamp code, tables or tuned values.

## Validation

31 JavaScript checks and 72 remote Python/native checks passed. Every new look
was also rendered on a real video frame for a visual contact sheet. See the
[experiment validation record](film-look-library-plan.md#validation-record--2026-10-16)
for scope and limitations. Production pins are unchanged.

## Historical output design (0.3.3)

The following records the older custom exporters and the rationale for moving
to native outputs. Its proposed refactor is now reflected in the current
workflow guide above; it is not an outstanding requirement of this experiment.

## What the optional nodes actually do

| Workflow label | Work performed | Why keep it optional? |
| --- | --- | --- |
| Export finished video (`FotufilmDevelopVideo`) | Applies the saved recipe to the complete source, then encodes MP4, ProRes 422 HQ or eligible HLG. Saves the recipe alongside it. | Editing does not need a full-clip export after every change. |
| Archive HDR source (`FilmFinishSaveHDRMaster`) | Saves the reconstructed, ungraded linear frames as RGB32F EXRs with color primaries, plus the original clip/audio, frame rate, manifest and float previews in `.ffhdr.zip`. | A durable checkpoint avoids another LTX run after a restart, but consumes disk space and time. Studio already accepts linear frames directly. |
| Save final still (`FotufilmInspectFrame`) | Develops one selected frame with the saved recipe and writes a full-resolution EXR. | Useful for a still handoff; unnecessary for normal video editing. |

The `master` socket is a reference to the archive file, not a richer type of HDR
pixel. It is supported for reopening saved sessions, not required between LTX
and Studio. The latest workflow branches the archive off the LTX output; it is
not in Studio's critical path. `enabled=false` skips the output's own work, but
does not lazily suppress every connected upstream node in ComfyUI.

Studio's Export video button is an alternative to the graph export branch.
Use one when you want a delivery. The graph export follows its connected input
and saved recipe, while the button exports the source currently selected in
Studio. They need not both run.

## Can these use native ComfyUI nodes?

Yes, with a smaller color-conversion step between processing and saving. The
following is the recommended refactor, **not implemented by this release**:

```
LTX linear ACEScg ── optional source correction ── Fotufilm develop
        │                                              │
        └─ optional source archive                     └─ delivery conversion
                                                              │
                                                  Create Video → Save Video
```

Current core [`CreateVideo` / `SaveVideo`](https://github.com/Comfy-Org/ComfyUI/blob/master/comfy_extras/nodes_video.py)
support SDR, HLG and PQ, plus audio, frame rate and 8/10-bit selection. A refactor
can retain Fotufilm for processing and use native nodes for final file saving.
Core expects already encoded sRGB, HLG or PQ pixels. Selecting “HDR” does not
convert linear ACEScg into HLG. Our existing Develop Frames returns **linear
Display P3**, so it also needs an explicit delivery conversion. The current
custom exporter already performs this conversion and bounds video memory by
processing frames sequentially. A naive whole-video IMAGE batch replacement
would increase memory use. ProRes is not among the current core SaveVideo codec
choices. Keep a specialized streaming/ProRes path where useful.

For stills or an EXR sequence, core
[`Save Image (Advanced)`](https://github.com/Comfy-Org/ComfyUI/blob/master/comfy_extras/nodes_images.py)
can write 32-bit float. Its current `linear` option labels pixels Rec.709, while
`HDR` decodes HLG and labels Rec.2020. Passing ACEScg or linear P3 straight into
either is incorrect. Convert to linear Rec.709 without clipping before
`input_color_space=linear`, or extend the writer with explicit linear primaries.
Negative and over-white float values must survive that conversion.

A native EXR sequence is easier to exchange with other applications. It does
not provide our archive's original audio, FPS manifest or one-file reopen
behavior by itself. Those can be separate graph branches/metadata rather than
a mandatory custom bundle. Similarly, Select Frame → matching color conversion
→ Save Image (Advanced) can replace the specialized still writer. The render
stage must apply the recipe exactly once.

The isolated Studio test build exposes these core save options. The user's
model-serving build must be checked before changing its workflow. No core pin,
archive format, existing output node or workflow wiring changed in 0.3.3.

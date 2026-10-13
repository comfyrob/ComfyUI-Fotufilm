# Looks and optional output branches

Updated 2026-10-12 for 0.3.3.

## 24 editable looks

Studio now offers Cinema, Portrait, Slide, Vintage and B&W filters. A filter only
changes the cards shown; it never changes the active recipe. Only the selected
family's thumbnails are requested, and completed thumbnails remain cached.

The original 12 recipes are unchanged. Added: Chrome road, Silver print,
Tungsten print, Window light, Rose portrait, Vivid daylight, Blue hour slide,
Amber slide, Faded travel, Everyday 35, Documentary 16 and Soft silver.

These are original combinations of existing Fotufilm profiles, print choices,
film sizes and Gear finishing controls. They are not new measured film stocks
or exact Fuji camera simulations. Silver print uses contrast/desaturation to
suggest a bleach-bypass look; it does not simulate retained silver chemistry.
The three new slide looks retain Reference exposure and are eligible for the
existing HLG export path. Preview remains SDR. The other looks finish to SDR,
including when developing an HDR source.

Selecting a look preserves source correction. “Keep my color settings” also
preserves the current finishing grade instead of loading the preset's grade.
Reset restores that look's finishing defaults. Old workflows keep their recipe
and seed; adding a catalogue entry does not replace saved settings.

[`examples/studio-looks.json`](../examples/studio-looks.json) contains every full
recipe for graph/API use. Copy an entry's `recipe` object into a recipe input.
Regenerate with `node scripts/export_looks.mjs`; verify with `--check`.

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

## Verification

- 52 Python checks passed on the remote Modal GPU, including all 24 recipes on
  a color ramp with SDR and 8× HDR-range input; representative new recipes were
  checked to produce distinct, finite output.
- 17 JavaScript checks passed, including filter isolation, visible-family
  thumbnail requests, preserved input correction, undo and independent defaults.
- The isolated Studio deployment serves the exact updated catalogue (SHA-256
  matches the local module). Main model environment pins were not changed.
- A new visual check in ComfyUI could not complete because browser automation
  timed out. Native render and DOM tests passed; this is not a visual approval
  of each look on production footage or a new playback benchmark.

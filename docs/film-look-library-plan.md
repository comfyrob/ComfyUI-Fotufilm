# Film and look library experiment

Status: implemented on the experimental branch, 2026-10-16. Branch: `explore/film-look-library`, based on
`2dcacf5`. The first catalogue milestone is implemented: 28 stocks, 54 looks, search,
favorites, visible-card previews and installed-stock checks. Engine settings and
workflow wiring are unchanged. Native GPU validation is pending; the production
deployment has not been repinned. The sections below retain the implementation
brief and explain the decisions.

## Goal

Make the embedded ComfyUI film editor a fast, approachable way to discover a
finished video look. Expand the useful range of choices while preserving
Fotufilm processing, separate colour grading, full-resolution exports and the
existing SDR / NVIDIA / generative LTX source workflow.

A **stock** supplies the film's simulated response. A **look** is an editable
recipe combining a stock, print/scan choice, film size, texture and optional
colour adjustments. Changing an ingredient should keep the originating look
visible with a Modified label. More entries should mean more useful choices,
not more controls to learn.

## Verified starting point

- `web/viewer/model.js`: 16 selectable stocks and 36 original look recipes.
- Six browsing filters: All, Cinema, Portrait, Slide, Vintage and B&W.
- The local pinned CUDA engine resources contain 46 stock profiles: 30 are
  not exposed in the stock selector. Availability is not a fidelity rating or
  proof that every fallback runtime supports the same profile.
- Engine `9242d189` includes updated Fuji profiles and grain. Our adapter still
  selects legacy halation. Evaluate another halation model as a separate
  experiment; avoid changing engine behaviour while judging new recipes.
- Processing accepts float HDR sources. Current playback is an SDR display
  conversion; an HDR input does not make every film recipe an HDR output.

[Osmo's public catalogue](https://osmo.inc/tools/film-emulation) advertises 126
stocks and looks combined. Its useful reference is the breadth of finished
choices: cinema, photographic, period, monochrome and experimental treatments.
Catalogue coverage, ease of selection and matching pixels are different goals.
This branch targets the first two with independently authored recipes.

## 1. Make the catalogue easy to extend

Extract stock and look definitions from the UI implementation into a versioned
data module. Retain existing stable IDs and saved recipes. Store category,
short description, stock dependency, defaults, engine compatibility and
provenance alongside each entry. Keep exported `studio-looks.json` in sync.

Check available profiles against the installed engine before showing a stock
as selectable. Report unavailable dependencies clearly, without silently
substituting a different stock. Keep the 36 existing recipes unchanged so old
workflows remain reproducible with their pinned runtime.

## 2. Expose a first group of 12 existing engine profiles

These are candidates for validation, not new measured profiles we have created:

| Family | Candidate stock IDs | What they add to the library |
| --- | --- | --- |
| Reversal / period | `kodachrome25`, `kodachrome64` | More period slide starting points |
| Colour negative | `cinestill400d`, `ultramax400`, `pro160ns` | More daylight and photographic choices |
| Motion picture | `reala500d`, `eternavivid500` | More cinema starting points |
| Monochrome | `hp5plus400`, `tmax100`, `delta3200` | A broader range of monochrome profiles |
| Instant / experimental | `instaxmini`, `phoenix200` | More distinctive creative directions |

Promote each only after checking native rendering, its useful default exposure,
grain scale, highlight response and compatibility with our display/output path.
Descriptions should follow observed behaviour rather than assumed brand traits.

Further candidates include Agfachrome, Aerocolor, Superia 200, FP4 and the Lomo
profiles. Infrared/Aerochrome-inspired results from ordinary RGB video must be
described as creative colour treatments; they cannot recover uncaptured IR.
Missing stock variants need appropriate profiles, not renamed existing ones.

## 3. Author 18 genuinely different creative looks

Start with three directions per collection; names below are working titles:

| Collection | Directions to explore |
| --- | --- |
| Cinema | Neutral dailies, dense release print, muted thriller |
| Portrait | Soft daylight, warm interior, clean beauty |
| Slide | Travel chrome, restrained landscape, vivid summer |
| Vintage | Faded home movie, warm seventies print, cool telecine |
| B&W | Fine studio, grainy night, soft documentary |
| Experimental | Instant colour, silver-retention-inspired, cross-process-inspired |

Avoid duplicating current looks under new names. Reuse or replace a proposed
direction when it offers no useful distinction from the existing catalogue.
Do not multiply each recipe into arbitrary warmth/grain variants to inflate
the count. Those remain editable controls.

Colour overrides belong to the same saved recipe consumed by the separate
Colour Grade node. Keep user input correction intact. Respect the existing
Keep my colour settings behaviour, and make any preset finishing adjustments
visible in that node. Do not apply those adjustments twice.

True bleach bypass and cross processing may require additional engine work.
Until then, label approximations as inspired treatments. Do not copy Osmo's
private tables, shaders or preset values. Retain the existing engine/profile
notices and document the provenance of any additional third-party assets.

## 4. Keep browsing simple and responsive

- Keep All as the default and the selected look prominent; no Start Here group.
- Add useful collection filters, search and favourites as the library grows.
- Show each look on the clip's first frame, with a short visual description.
- Preserve stable card dimensions and selection while thumbnails load.
- Render visible cards first, lazily request offscreen cards, and cancel stale
  requests when the clip or filter changes. Existing cached thumbnails and
  background scheduling should be extended rather than replaced.
- Share the decoded source frame and cache by source, recipe and engine.
  Editing/playback must take priority over a large catalogue render queue.

Keep the full float processing path and current playback resolution/frame
settings. Expanding the catalogue should not lower preview quality or make
selecting a look rerun LTX/NVIDIA inference.

## 5. Validate and promote in small releases

Use the existing automated recipe, selection, thumbnail and native-render
checks. Add coverage only for new compatibility/migration behaviour. Verify
new stock IDs exist and recipes are finite on SDR and above-white float input.
Inspect representative skin, sky, bright lights and moving texture to catch
unusable defaults, flicker and overly similar presets. This is practical
acceptance work, not a separate Osmo comparison study.

Measure look-selection-to-current-frame display on the remote ComfyUI setup,
including a cold selection and a cached selection. Do not mistake native
render time for end-to-end response time. Test browsing a larger library while
playing; thumbnail work must not starve the active preview.

The first implementation milestone is up to 28 exposed stocks and 54 looks,
subject to the checks above. Review that collection before expanding toward
all 46 bundled profiles or a larger library. Only promote the experimental
branch and update deployment pins after the working catalogue is ready.

## Implementation map

- Catalogue and recipe defaults: `web/viewer/model.js` (extract data module).
- Browse, selection and card layout: `web/viewer/studio.js`.
- Thumbnail requests: follow the existing implementation and
  `tests/look-previews.test.mjs` before modifying scheduling.
- Recipe interchange: `scripts/export_looks.mjs`, `examples/studio-looks.json`.
- Compatibility: `recipe.py`, `runtime/float-engine-lock.json` and installed
  stock resources; avoid changing colour/engine contracts for a catalogue edit.
- Documentation: update `docs/looks-and-outputs.md` when implementing; it still
  describes an older 24-look release and must not define the current baseline.

# Everyday color controls

Grade now opens with one set of controls for the finished look: Exposure,
Warmth, Tint, Contrast and Saturation. These edit the existing `grading.finish`
values after Fotufilm. They do not reinterpret or migrate saved recipes.

The three visible color wheels tint Shadows, Midtones and Highlights. They use
Gear's lift/gamma/gain operations, which affect overlapping tonal ranges rather
than isolated masks. Click or drag to add a tint, use arrow keys for small edits,
or Home/double-click to center the tint. Each wheel has a brightness slider and
a reset for that wheel. The overall offset wheel, highlights/shadows sliders and
vibrance are under More color controls.

Advanced: before-film correction contains the original `grading.balance` controls.
An Edited badge identifies existing input corrections even while collapsed.
Changing these values changes the light/color passed into the film simulation;
changing the everyday controls adjusts the already-developed result. The two
stages have independent resets. Film and look selection remain unchanged.

Advanced tools contains the histogram, still inspection and explicit graph run.
Save a still defaults to Final look. Frame version to save selects only the
processing stage of the EXR still, not playback, grading or video export:

- Original: active source without grading or film.
- Corrected input: input grading, before film.
- Film only: input grading and Fotufilm, before the finishing grade.
- Final look: all of the above, including the finishing grade.

The live preview remains SDR. The EXR preserves the available float/HDR values at
the chosen stage. Saving an EXR does not create missing HDR detail.

Verification: seven JavaScript tests cover stage separation, preservation of
existing corrections, wheel keyboard/reset behavior, still selection, seeking
and the stream client. The Nodes 2.0 dialog was checked at 1280px and 320px widths,
including a keyboard wheel edit and horizontal overflow checks. Screen-reader
speech output, RTL and 200% text resizing were not tested in this pass.

The subsequent interaction upgrade adds numeric entry, moves grain/halation
beside everyday color, and preserves input corrections during look changes.
See [interaction-upgrade.md](interaction-upgrade.md) for current selection,
transport and test-export behavior.

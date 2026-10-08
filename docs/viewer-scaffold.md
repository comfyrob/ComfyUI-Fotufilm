# Fotufilm Studio: interface scaffold

The canvas node is a compact monitor. **Open studio** expands it into a workspace inside ComfyUI; the viewer and transport stay visible while the recipe column scrolls. **Save to node** commits the recipe. Closing or Escape discards the draft, like Gear's grade panel.

Visual direction: neutral charcoal stage `#181a1b`, panel `#242728`, raised controls `#303536`, text `#edf0ee`, secondary text `#b0b9b6`, pale jade selection `#b6dfcf`. System sans for controls and tabular numerals for time. Color surrounds footage as little as possible. No marketing header, dashboard cards or progress overlay.

```
Fotufilm / Studio                 Interface preview       Cancel   Save to node
┌───────────────────────────────────────────────┬────────────────────────────┐
│ Source: Original / Enhanced HDR               │ Current look               │
│                                               │ Clean cinema / Modified    │
│                VIDEO                          │ Looks | Customize          │
│       original ↔ current render               │                            │
│                                               │ First-frame look tiles     │
│ Playback, frame step, loop, audio, zoom        │ or film / light / texture  │
│ Filmstrip + scrubber                          │ controls                   │
└───────────────────────────────────────────────┴────────────────────────────┘
Source resolution / display information           Preview render (next phase)
```

## Working in this scaffold

- HTML video playback, scrubbing, loop, mute, playback speed, frame-step (using supplied FPS), zoom/pan, fullscreen and keyboard controls.
- Original/render wipe comparison when both videos are available. A second **Enhanced HDR source** input has its own source toggle; this does not claim HDR monitor output.
- Preset selection, film/print/format, light and texture controls, modified-look state, reset and recipe serialization.
- Compact node → studio → save/cancel roundtrip. The preview node passes VIDEO through unchanged and returns a validated recipe. It performs no film development.
- Current rendered output remains identified separately from unsaved recipe changes; no CSS filters or fake Fotufilm results.

## Deliberately not implemented

On-demand GPU preview jobs, render caching, progressive resolution, HDR float transport/display mapping, scopes, new neural HDR generation and final export orchestration. The render button explains this scope. Source thumbnails are explicitly labeled until real recipe renders are connected.

## Rendering contract for the next phase

ComfyUI owns Fotufilm rendering. The viewer submits a source identifier, complete recipe, frame/range and requested resolution; the backend returns a versioned still or playable cached clip. Only the latest requested recipe may replace the displayed render. The current clip continues playing while its replacement is built, then swaps at the matching time. Heavy work stays on the user's Modal GPU environment. A stronger server alone does not remove encode, transfer or browser decode costs.

Reference: https://github.com/oumad/ComfyUI_Gear/blob/main/web/gear_grade.js (interaction reference only; no Gear rendering code copied).

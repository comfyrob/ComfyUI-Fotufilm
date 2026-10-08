# Nodes 2.0 validation — 2026-10-07

## Prepared

- Connected SDR finishing example: Load Video, Studio, Develop Video, Return to Studio.
- Connected LTX 2.5 HDR example: seven functional root nodes, one note, 25 nodes in an editable reconstruction subgraph.
- All example node types, input names and output counts checked against the isolated ComfyUI server's registered schemas. Graph link integrity and cycle checks pass.
- Exact model names and HDR transforms retained from the existing LTX 2.5 lab. No fresh LTX inference run in this UI test.

## Deployed

- Current adapter/frontend overlay deployed to the isolated CPU-only Modal review app. No model volume or GPU attached; normal generation deployments were not modified.
- Nodes 2.0 explicitly enabled in the review instance. Full HDR graph loads, and its reconstruction subgraph opens with grouped internal stages. The only setup warnings are the five intentionally absent LTX model files.

## Executed

Three CPU contract tests passed with the actual ComfyUI API:

1. Connected graph/subgraph links are valid and acyclic; the Studio recipe does not feed LTX.
2. Save HDR Master returns a directly resolvable archive handle. EXR samples retain 4.0, -0.125 and 1.5 without clipping. Invalid handle types and outside-output paths are rejected.
3. Return to Studio carries the exact originating session token and validated recipe. Independent Studio executions get different sessions.

Browser checks with Nodes 2.0:

- Expanded DOM editor, compact node, and larger Studio dialog open successfully.
- 960 × 540 existing preview clip plays and loops; play/pause, compare and zoom respond.
- Look → film change preserves the look label and Modified state after Save, collapse and reopen.
- Recipe changes flag a stale render; Cancel restores the saved recipe and up-to-date status.
- Actual CPU graph `Load Video → Studio → Return to Studio`, using a second pre-rendered clip, queues from the editor and returns its result to that same editor. No generation or native film rendering is involved in this handoff test.
- Final inline viewer height is bounded to 645 CSS pixels. Compact-player styles no longer shrink the inline video. No browser console errors captured in the final test session.

## Limits

This validates the UI, queue/return wiring and lossless master handoff. It does not benchmark GPU render performance, prove preview/export color parity, validate a calibrated HDR display, or rerun the complete LTX → Fotufilm pipeline. Native film rendering remains queued, not an instant response to every slider movement. The regular GPU image pin must include this nodepack revision before using the new graph there.

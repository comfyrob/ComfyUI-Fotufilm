# Studio interaction upgrade

Implemented in the ComfyUI custom node and its expanded dialog. Source:
workshop research `research/osmo-2026-10-12/handoff.md`. No Osmo code, assets,
shader tables or presets are included.

## Controls and look selection

Color & texture groups the five everyday finishing controls with grain and
halation. Wheels stay visible. Before-film correction remains advanced. Texture
still runs in the Fotufilm stage; moving a control does not move its math.

Color/texture and advanced film sliders have numeric entry. Enter/blur commits,
Escape cancels only the text edit, arrows step, Shift+arrows step ten times.
Values respect the existing node's ranges and units. An edit does not change
recipe schema or color math. Undo includes the selected look identity.

Input corrections always survive choosing or resetting a look. They belong to
the clip and have their own Edited state/reset. The look's Modified badge excludes
these independent input corrections. By default each look supplies its own
finishing grade. The optional **Keep my color settings** replaces that entire
finishing grade with the current values, including wheels; it is not additive
math on top of a preset. Reset this look restores its finishing/film/texture
settings while retaining input correction. This browsing preference is per
open Studio session. Thumbnails use the same selection policy.

## Drag transport and feedback

During a pointer drag, the client holds at most one gesture revision in flight
and keeps only the newest pending recipe. A presented current sent revision can
be followed by the latest pending update; unsent intermediate controls need not
be rendered. Release immediately sends the final exact recipe. Playback source
frames are still delivered sequentially: this is control-event coalescing, not
frame skipping to inflate fps. Native processing uses the same float input,
film, spatial effects and grade at the selected preview size.

New servers advertise gesture-H.264 support. During dragging they use the warm
H.264 monitor encoder; release returns PNG. Old clients/servers retain their
paused PNG behavior. H.264 is compressed 8-bit SDR monitoring; PNG is lossless
only relative to the SDR display pixels at preview resolution. Neither is an
HDR master. Exports remain independent and full resolution.

Preparing/updating/up-to-date states identify pending changes. Current revisions
carry server queue, setup and processing durations. Client samples use one
`performance.now()` clock from edit to canvas callback, with completion recorded
after the synchronous draw. This is not physical display scan-out latency.
`Studio.getPreviewMetrics()` / `live.getMetrics()` expose a bounded 120-sample
buffer with superseded/sent/drawn state, bytes and durations for diagnostics.
No client/server wall clocks are subtracted. These samples stay in the client;
they are not uploaded analytics.

Thumbnail rendering runs only while paused in Looks, and is cancelled when
editing or leaving that panel. It no longer warms unrelated films while the
color controls are in use. An already-running native call can finish before the
next interactive job; the scheduler cannot interrupt an arbitrary GPU kernel.

## Test exports

**Export video** remains the entire clip. **Test 5 seconds** starts at the
playhead, keeps the selected format and original resolution, and stops at the
clip end if fewer frames remain. Frame count is `min(round(fps*5), remaining)`;
spatial effects/grain use absolute source indices and audio seeks to that same
start. Cancel export cancels the job. No graph execution, LTX rerun or master
archive is needed. Existing HLG eligibility rules still apply.

## Validation and limits

46 Python tests passed on the isolated RTX PRO 6000 worker, including exact PNG
settling parity, trial frame indices/audio seek, float/HDR preservation, cache
invalidation, encoders and optional graph outputs. Eleven JS tests cover numeric
commit/cancel, look identity/undo, preserved corrections, trial/cancel and
coalesced/stale stream revisions. The served module was checked at the test URL.

An actual WAN fixture (Mac client → Modal us-east, RTX PRO 6000, five-second
24fps demo upscaled to 1280×720 as a workload, Vision3 250D, same-frame finishing
saturation edits) alternated ten PNG and ten gesture responses:

| Send → complete packet receipt | PNG | Gesture H.264 |
|---|---:|---:|
| Median | 265 ms | 144 ms |
| p95 (nearest rank, only 10 samples) | 562 ms | 929 ms |
| Median image payload | 1,340,566 bytes | 8,844 bytes |

The first H.264 encoder use cost 691 ms on the server. Steady responses were
smaller/faster, but cold response and p95 did not improve in this run. Initial
film preview took 19.4 seconds. Following these edits, all 120 source frames
arrived in order at 23.08 fps. These are packet measurements, excluding browser
decode/draw; they do not establish universal real-time performance or browser
end-to-end p95. No artificial WAN shaping was used. Full-resolution/HDR exports
were not compared visually across engines.

The in-app browser automation timed out during reload/navigation and screenshot
capture. The refreshed UI has not been visually signed off in Nodes 2.0 in this
pass. DOM interaction tests passed; do not describe those as a completed browser
layout test. The previous UI was visually tested before these changes.

The isolated finishing deployment was updated; the main model environment and
its weights were not changed. Upstream v1.12 was reviewed but not installed;
see `upstream-2026-10-12.md` for rendering changes and migration checks.

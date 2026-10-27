# Interactive performance is a release requirement

Rob's priority: responsive film/color edits and real-time playback inside ComfyUI custom nodes. Keep source resolution, frame count, HDR range, and film quality intact; do not silently lower them to advertise a higher frame rate.

- Profile decode/HDR conversion, film, grading, encoding, queue and delivery separately. A powerful GPU does not accelerate CPU work automatically.
- Benchmark SDR and tagged 4K HDR sources on the target RTX runtime at 960px and 1280px after changes to source loading, processing or playback. Include first-pass and cached results, input/output frame counts, engine/encoder identity, and numerical color parity.
- Compare the same clip, recipe, hardware and settings before/after. Local Mac testing verifies functionality, not RTX performance. Report server throughput separately from delivered playback FPS.
- Preserve existing working paths. Performance regressions block recommending an update; do not replace a measured regression with a claim that stronger hardware will fix it.
- Keep AI inference remote. Local Comfy Desktop is for UI and lightweight CPU checks. Do not restart a user's active remote session for a benchmark.

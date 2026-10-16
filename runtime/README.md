# Native runtime sources

The Linux installer assembles a runtime from:

- [Fotufilm v1.11](https://github.com/DhaliwalX/fotufilm-engine/releases/tag/v1.11): native engine, resources, stock profiles and licenses. The embedded desktop browser is excluded.
- This pack’s CUDA float-input extension, identified by `float-engine-lock.json`: upstream `9242d189` and StrictFloat AOT schedules with an additive memory-input ABI. Source and build steps are in `ComfyFloatInput.swift` and `../scripts/build_linux_float.sh`. The v1.11 upstream library remains installed for Vulkan/CPU compatibility, with its original resources. CUDA resources are bundled alongside the new binary and installed into `float-resources/`.
- The official PyAV 12.3.0 Linux wheel, identified by `ffmpeg-lock.json`: the dependency closure of FFmpeg 6 libraries, without replacing ComfyUI's Python `av` module. `package_ffmpeg.py` normalizes SONAME / NEEDED names only; it preserves executable code and records each alias and the wheel provenance.
- Checksum-pinned Ubuntu Noble packages in `system-libraries-lock.json`: missing TIFF/curl dependencies. Files are extracted privately; no operating-system package installation is performed.

Each archive checksum is checked before extraction. The assembled runtime includes licenses and provenance for its components. No native binary or AI model is stored in Git.

Sources: [PyAV](https://github.com/PyAV/PyAV/tree/v12.3.0), [PyAV FFmpeg build](https://github.com/PyAV/FFmpeg), [FFmpeg](https://ffmpeg.org/download.html), [Ubuntu archive](https://archive.ubuntu.com/ubuntu/). These components retain their respective licenses; the PyAV binding's BSD license does not replace codec library licenses. Preserve those notices and meet the applicable source-distribution requirements if you redistribute a built container/runtime.

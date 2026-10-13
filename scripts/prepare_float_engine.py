"""Apply the additive float input and select a CUDA-only AOT Linux build.

Run against the pinned Fotufilm checkout, before cef/build-engine-linux.sh.
This does not change film math, precision, parameters, profiles or grain.
The upstream runtime remains available for Vulkan and CPU hosts.
"""
from pathlib import Path
import re
import shutil
import subprocess
import sys

PIN='f602857a031a6a9c9b0966284ff989eb3046c323'
root=Path(sys.argv[1]).resolve()
if subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()!=PIN:
    raise SystemExit('The float input patch requires the pinned Fotufilm revision.')
if (root/'.comfy-float-input-v1').is_file():
    raise SystemExit('This checkout is already patched; run cef/build-engine-linux.sh directly to rebuild.')
shutil.copyfile(Path(__file__).resolve().parents[1]/'runtime/ComfyFloatInput.swift',root/'Sources/FotufilmHost/ComfyFloatInput.swift')
header=root/'Sources/CFotufilmHost/include/fotufilm.h'
with header.open('a') as out:
    out.write('\n// ComfyUI additive memory input; scene-linear Rec.2020 RGBA float32.\n')
    out.write('void *fotufilm_image_from_rgba32f(const float *pixels, uint32_t width, uint32_t height, size_t count, char **error);\n')
p=root/'Sources/FotufilmHalide/FotufilmHalideLinux.cpp';s=p.read_text()
s=s.replace('#include <HalideRuntimeVulkan.h>','// CUDA-only build: no Vulkan runtime dependency.')
s=s.replace('    extern "C" int fotufilm_aot_vulkan_##variant_name(FOTUFILM_AOT_FRAME_SIGNATURE);','')
s=re.sub(r'const AotVariant kVulkanVariants\[\] = \{.*?\n\};','',s,flags=re.S)
s=s.replace('return device == kCuda ? halide_cuda_device_interface() : halide_vulkan_device_interface();','return halide_cuda_device_interface();')
a=s.index('    if (wanted == "cuda")');b=s.index('\n}',a)
s=s[:a]+'    if (wanted == "vulkan") return kNone;\n    return answers(kCuda) ? kCuda : kNone;'+s[b:]
s=s.replace('const FrameFunction pipeline = device == kCuda\n        ? fotufilm::aot::select_variant(kCudaVariants, std::size(kCudaVariants), feature_mask)\n        : fotufilm::aot::select_variant(kVulkanVariants, std::size(kVulkanVariants), feature_mask);','const FrameFunction pipeline = fotufilm::aot::select_variant(kCudaVariants, std::size(kCudaVariants), feature_mask);')
p.write_text(s)
p=root/'tools/generate-halide-aot-linux.sh';s=p.read_text().replace('for device in cuda vulkan; do','for device in cuda; do').replace(' "$HALIDE/include/HalideRuntimeVulkan.h"','');p.write_text(s)
p=root/'tools/generate_halide_ios.cpp';s=p.read_text();s=re.sub(r'        for \(const auto feature : \{Halide::Target::Vulkan,.*?runtime.set_feature\(feature\);','        // CUDA-only runtime; the normal CUDA graph and StrictFloat variants are unchanged.',s,flags=re.S);p.write_text(s)

(root/'.comfy-float-input-v1').write_text(PIN+'\n')

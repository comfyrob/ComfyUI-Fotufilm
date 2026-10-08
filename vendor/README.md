# Gear grading

`gear_grading.py` is vendored from [oumad/ComfyUI_Gear](https://github.com/oumad/ComfyUI_Gear), revision `cee4806315e99c8adadc4710d03650146f55f5af`, under the accompanying MIT license. Copyright 2026 Mohamed Oumoumad.

The upstream file is unchanged. `../grading.py` adapts its ACEScct grading operations to AP1 input/output so wide-gamut source pixels do not pass through Gear's Rec.709 input clamp. Neutral grades bypass processing exactly. Preview and final export use the same adapter.

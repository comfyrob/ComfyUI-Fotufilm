# CUDA initialization during LTX sampling

An error at `SamplerCustomAdvanced` does not necessarily mean that the graph or model is wrong. On the tested Modal image (`nvidia/cuda:13.0.1-runtime-ubuntu24.04`, Python 3.12, PyTorch 2.10.0+cu130), even a small BF16 linear operation failed with `CUBLAS_STATUS_NOT_INITIALIZED` before importing any custom nodes.

The process loaded `libcublas.so.13` from PyTorch's installed NVIDIA package (13.1.0.3), but `libcublasLt.so.13` from the base image (13.0.2.14). These two libraries must come from a matching installation. This is distinct from an out-of-memory error or a corrupt model.

## Fix the image, then restart the server

For this exact Python/CUDA image, set the search order **before Python starts**:

```python
image = image.env({
    "LD_LIBRARY_PATH": (
        "/usr/local/lib/python3.12/site-packages/nvidia/cu13/lib:"
        "/usr/local/nvidia/lib:/usr/local/nvidia/lib64:/usr/local/cuda/lib64"
    ),
})
```

Adapt the package path to the installed Python environment. Do not copy the `cu13` path into a CUDA 12 environment. Keep the NVIDIA driver paths. Changing `os.environ` inside a custom node after Torch has loaded its libraries does not repair the running process.

On the remote GPU worker, this small check should pass before attempting the full workflow:

```python
import torch

x = torch.randn(1, 1024, 128, device="cuda", dtype=torch.bfloat16)
w = torch.randn(4096, 128, device="cuda", dtype=torch.bfloat16)
b = torch.randn(4096, device="cuda", dtype=torch.bfloat16)
y = torch.nn.functional.linear(x, w, b)
assert torch.isfinite(y).all()
torch.cuda.synchronize()
print(y.shape)
```

This only validates CUDA linear algebra. A successful LTX sampling/decode run is still required to validate the workflow. The fix does not change the model, sampling settings, resolution, frame count, or film simulation.

## A separate error: incomplete model download

`Tensor ... extends past the end of the file` means the safetensors header describes more data than the file contains. Check whether an existing installer is still writing it before starting another download. A model can appear in ComfyUI's dropdown while incomplete.

With persistent volumes, the installer and an already-running server may see different snapshots. Complete and commit the download, then safely reload the volume or start a fresh server. Do not replace or delete a model that another process is still downloading.

The observed distilled BF16 transformer expects **42,018,190,584 bytes**. The distilled Comfy INT8 ConvRot transformer expects **21,504,034,224 bytes**. A matching size/header is a structural check, not a checksum verification.

## Validation on 2026-10-15

After restarting the main Modal ComfyUI server with the corrected search path, the previously failing graph completed successfully: 1280×720, 97 frames, 24 fps, the distilled INT8 ConvRot transformer, SDR-to-HDR IC-LoRA, seed 42 and the original eight Euler steps. Total graph execution was 72.45 seconds. Both Film and Color received the same linear HDR source. A full-size Fotufilm preview completed, and source frame 48 contained finite Rec.2020 float pixels ranging from 0.000115 to 1.56737.

Validation job: `ca2b5af7-8392-4d85-a5c0-3779a7c5df49`. This verifies the current combined graph's INT8 LTX branch; it does not claim BF16 inference or every other GPU/runtime combination has been tested.

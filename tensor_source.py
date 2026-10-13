"""A scene-linear Comfy IMAGE batch; no intermediate master archive required."""
import math
from pathlib import Path

import torch

from .grading import TO_2020, convert
from .finish_pipeline import resize_float


class TensorSource:
    def __init__(self, images, fps, color_space, playback):
        if not isinstance(images, torch.Tensor) or images.ndim != 4 or images.shape[-1] != 3:
            raise ValueError('Connect an IMAGE batch of linear RGB video frames.')
        count, height, width, _ = images.shape
        if not 0 < count <= 100_000 or not 0 < height * width <= 40_000_000:
            raise ValueError('Unsupported frame count or dimensions.')
        if not math.isfinite(fps) or not 1 <= fps <= 120 or color_space not in TO_2020:
            raise ValueError('Specify the frame rate and linear input color space.')
        # Hold the graph-owned storage without a second full-video copy. Individual
        # frames are copied on read; grading never modifies the upstream batch.
        self.images = images.detach()
        self.nbytes = images.untyped_storage().nbytes()
        self.path = Path(playback)
        self.is_hdr = True
        self.info = dict(width=width, height=height, frames=count, fps=float(fps),
                         duration=count/fps, colorSpace=color_space, hdr=True, direct=True)

    def frames(self, start=0, count=None, edge=None):
        stop = min(len(self.images), start + (count or len(self.images)))
        for index in range(start, stop):
            if torch.cuda.is_available():
                with torch.inference_mode():
                    rgb=convert(self.images[index].to(device='cuda',dtype=torch.float32),self.info['colorSpace'],'linear-rec2020')
                    if edge and max(rgb.shape[:2])>edge:
                        scale=edge/max(rgb.shape[:2])
                        rgb=torch.nn.functional.interpolate(rgb.permute(2,0,1)[None],size=tuple(max(1,round(v*scale)) for v in rgb.shape[:2]),mode='area')[0].permute(1,2,0)
                    frame=rgb.cpu().numpy().copy()
                if not torch.isfinite(torch.from_numpy(frame)).all():
                    raise ValueError(f'Non-finite source pixels at frame {index}.')
                yield index,frame
                continue
            frame = self.images[index].to(device='cpu', dtype=torch.float32).numpy().copy()
            if not torch.isfinite(torch.from_numpy(frame)).all():
                raise ValueError(f'Non-finite source pixels at frame {index}.')
            yield index, resize_float(convert(frame, self.info['colorSpace'], 'linear-rec2020'), edge)

    def audio_path(self, directory):
        return self.path

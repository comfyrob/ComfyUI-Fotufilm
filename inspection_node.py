"""A branchable inspection output for ComfyUI graphs."""
import json
import uuid
from pathlib import Path

import folder_paths
import numpy as np
import torch
from comfy_api.latest import io

from .grading import convert
from .hdr_nodes import HDRMaster, resolve_master
from .inspection import STAGES, inspection_frame, publish_inspection, write_inspection
from .preview_node import DEFAULT_RECIPE, preview_file
from .recipe import validate_recipe


class FotufilmInspectFrame(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='FotufilmInspectFrame', display_name='Fotufilm · Save Still (EXR)',
            category='Film Finish', is_output_node=True,
            description='Save one full-resolution float EXR for core HDR inspection. Connect one video, '
                        'HDR master or IMAGE batch. Stage source inspects connected pixels unchanged '
                        'apart from explicit color conversion. Other stages apply this recipe. '
                        'Exposure in core’s viewer changes viewing only, not the saved grade.',
            inputs=[io.Int.Input('frame', default=0, min=0),
                    io.Combo.Input('stage', options=list(STAGES), default='source', advanced=True),
                    io.String.Input('recipe_json', default=DEFAULT_RECIPE, multiline=True),
                    io.Combo.Input('input_color_space', options=['linear Rec.2020', 'linear Display P3',
                        'linear Rec.709', 'linear ACEScg', 'sRGB'], default='linear Rec.2020', advanced=True),
                    HDRMaster.Input('master', optional=True), io.Video.Input('video', optional=True),
                    io.Image.Input('images', optional=True), io.Boolean.Input('enabled', default=True, optional=True)],
            outputs=[io.Image.Output('linear_rec2020'), io.String.Output('color_space')])

    @classmethod
    def execute(cls, frame, stage, recipe_json, input_color_space, master=None, video=None, images=None, enabled=True):
        if not enabled:
            return io.NodeOutput(None, 'linear Rec.2020')
        if sum(x is not None for x in (master, video, images)) != 1:
            raise ValueError('Connect exactly one of master, video or images.')
        recipe = validate_recipe(json.loads(recipe_json))
        from .finish_pipeline import Source
        if images is not None:
            if images.ndim != 4 or images.shape[-1] < 3:
                raise ValueError('Expected an IMAGE batch [frames, height, width, channels].')
            class TensorSource:
                info = {'frames': len(images), 'width': images.shape[2], 'height': images.shape[1]}

                def frames(self, start=0, count=None, edge=None):
                    rgb = images[start, ..., :3].detach().cpu().float().numpy()
                    spaces = {'linear Rec.2020': 'linear-rec2020', 'linear Display P3': 'linear-p3',
                              'linear Rec.709': 'linear-rec709', 'linear ACEScg': 'linear-acescg', 'sRGB': 'linear-rec709'}
                    if input_color_space not in spaces:
                        raise ValueError('Unknown input color space.')
                    if not np.isfinite(rgb).all():
                        raise ValueError('Input contains non-finite pixels.')
                    if input_color_space == 'sRGB':
                        if rgb.min() < 0 or rgb.max() > 1:
                            raise ValueError('Choose a linear color space for HDR pixels.')
                        rgb = np.where(rgb <= .04045, rgb / 12.92, ((rgb + .055) / 1.055) ** 2.4)
                    yield start, convert(rgb, spaces[input_color_space], 'linear-rec2020')
            source = TensorSource()
            origin = {'kind': 'connected IMAGE', 'inputColorSpace': input_color_space}
        else:
            from .studio_server import resolve_file
            path = resolve_master('', master) if master is not None else resolve_file(preview_file(video, 'Inspection source'))
            source = Source(path)
            origin = {'kind': 'HDR master' if master is not None else 'video', 'name': path.name}
        rgb, _ = inspection_frame(source, recipe, frame, stage)
        path = Path(folder_paths.get_output_directory()) / 'fotufilm-inspections' / f'{stage}-{frame:06d}-{uuid.uuid4().hex}.exr'
        write_inspection(rgb, path, {'frame': frame, 'stage': stage, 'source': origin, 'recipe': recipe})
        result = publish_inspection(path)
        # Older Comfy versions get a normal PNG thumbnail and a separate EXR download.
        image = result['exr'] if result['exr'].get('asset_preview') else result['poster']
        return io.NodeOutput(torch.from_numpy(rgb.copy())[None], 'linear Rec.2020',
                             ui={'images': [image], 'files': [result['exr']] if image is result['poster'] else []})

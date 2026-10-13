"""Optional, branchable source correction using the same float Gear math as Studio."""
import torch
import comfy.model_management
from comfy_api.latest import io

from .grading import SCALARS, VECTORS, apply_grade, convert, neutral_grade, validate_grading

SPACES = {'linear ACEScg': 'linear-acescg', 'linear Rec.2020': 'linear-rec2020',
          'linear Rec.709': 'linear-rec709', 'linear Display P3': 'linear-p3', 'sRGB': 'linear-rec709'}


class FotufilmBalanceFrames(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        scalars = [io.Float.Input(key, default=value[2], min=value[0], max=value[1], step=.01,
                                 advanced=key not in ('exposure', 'temperature', 'tint', 'contrast', 'saturation'))
                   for key, value in SCALARS.items()]
        wheels = [io.Float.Input(f'{key}_{channel}', default=value[2], min=value[0], max=value[1],
                                 step=.005, advanced=True)
                  for key, value in VECTORS.items() for channel in 'rgb']
        return io.Schema(node_id='FotufilmBalanceFrames', display_name='Fotufilm · Balance Source',
            category='Film Finish',
            description='Optional Gear color correction before film. Connect IMAGE frames from HDR reconstruction '
                        'or Get Video Components. Outputs linear ACEScg for Studio and export. Queue to apply; '
                        'cached LTX frames are reused. Studio Before/after then shows this corrected source versus '
                        'the finished look. No film, display tone mapping or saving occurs here.',
            inputs=[io.Image.Input('images'), io.Combo.Input('input_color_space', options=list(SPACES), default='linear ACEScg'),
                    io.Boolean.Input('enabled', default=True), *scalars, *wheels],
            outputs=[io.Image.Output('linear_acescg'), io.String.Output('color_space')])

    @classmethod
    def execute(cls, images, input_color_space='linear ACEScg', enabled=True, **controls):
        if input_color_space not in SPACES:
            raise ValueError('Choose the color space of the connected frames.')
        if images.ndim != 4 or images.shape[-1] != 3 or not len(images):
            raise ValueError('Expected RGB frames [frames, height, width, 3].')
        grade = neutral_grade()
        known = set(SCALARS) | {f'{k}_{c}' for k in VECTORS for c in 'rgb'}
        if set(controls) - known:
            raise ValueError('Unknown source correction control.')
        for key in SCALARS:
            if key in controls: grade[key] = controls[key]
        for key in VECTORS:
            grade[key] = [controls.get(f'{key}_{channel}', grade[key][i]) for i, channel in enumerate('rgb')]
        grade = validate_grading({'balance': grade})['balance'] if enabled else neutral_grade()
        # A neutral/disabled ACEScg branch should not duplicate a whole HDR video.
        if input_color_space == 'linear ACEScg' and grade == neutral_grade() and images.dtype == torch.float32:
            if not torch.isfinite(images).all():
                raise ValueError('Source contains non-finite pixels.')
            return io.NodeOutput(images, 'linear ACEScg')
        frames = []
        with torch.inference_mode():
            for frame in images:
                comfy.model_management.throw_exception_if_processing_interrupted()
                rgb = frame.float()
                if not torch.isfinite(rgb).all():
                    raise ValueError('Source contains non-finite pixels.')
                if input_color_space == 'sRGB':
                    if rgb.min() < 0 or rgb.max() > 1:
                        raise ValueError('Choose a linear color space for HDR pixels.')
                    rgb = torch.where(rgb <= .04045, rgb / 12.92, ((rgb + .055) / 1.055).pow(2.4))
                rgb = convert(rgb, SPACES[input_color_space], 'linear-acescg')
                frames.append(apply_grade(rgb, grade, 'linear-acescg'))
        return io.NodeOutput(torch.stack(frames), 'linear ACEScg')

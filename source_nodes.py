"""Explicit source routing. No inference, display transform, or hidden archive."""
import torch
from comfy_api.latest import io
from .grading import convert

METHODS = {'Original SDR': 'original', 'NVIDIA HDR': 'nvidia', 'LTX 2.5 HDR': 'ltx'}


class FotufilmLTXHDRDecode(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='FotufilmLTXHDRDecode', display_name='LTX HDR Decode · On demand',
            category='Film Finish/Source',
            description='Calls the installed LTX HDR decoder with saving disabled. Unlike the upstream optional saver, this is not an output root, so an unselected LTX branch stays idle. ACEScct yields linear ACEScg; legacy LogC3 yields linear Rec.709.',
            inputs=[io.Image.Input('image'),io.Combo.Input('transfer',options=['acescct','logc3'],default='acescct'),
                    io.Float.Input('exposure',default=0,min=-10,max=10,step=.1,tooltip='Affects only the tonemapped output, not hdr_linear.')],
            outputs=[io.Image.Output('tonemapped'),io.Image.Output('hdr_linear')])

    @classmethod
    def execute(cls,image,transfer='acescct',exposure=0):
        import nodes
        upstream=nodes.NODE_CLASS_MAPPINGS.get('LTXVHDRDecodePostprocess')
        if upstream is None:
            raise RuntimeError('Install the workflow-pinned ComfyUI-LTXVideo pack to decode LTX HDR.')
        result=getattr(upstream(),upstream.FUNCTION)(image=image,transfer=transfer,exposure=exposure,save_exr=False)
        return io.NodeOutput(*result)


class FotufilmSelectSource(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='FotufilmSelectSource', display_name='Fotufilm · Choose HDR Method',
            category='Film Finish/Source',
            description='Choose one prepared source. Only the selected branch executes. All inputs must already be linear Rec.709; this node does not convert colors. Keep other output nodes on unselected branches muted.',
            inputs=[io.Combo.Input('method', options=list(METHODS), default='Original SDR'),
                    io.Image.Input('original', lazy=True, optional=True, tooltip='SDR decoded to linear Rec.709 with Convert Image Color Space.'),
                    io.Image.Input('nvidia', lazy=True, optional=True, tooltip='RTX HDR PQ converted to linear with Convert Image Color Space.'),
                    io.Image.Input('ltx', lazy=True, optional=True, tooltip='LTX linear ACEScg converted to linear Rec.709 after Remove Padding.')],
            outputs=[io.Image.Output('linear_rec709')])

    @classmethod
    def check_lazy_status(cls, method, original=None, nvidia=None, ltx=None):
        key = METHODS[method]
        return [key] if {'original': original, 'nvidia': nvidia, 'ltx': ltx}[key] is None else []

    @classmethod
    def execute(cls, method, original=None, nvidia=None, ltx=None):
        key = METHODS[method]
        image = {'original': original, 'nvidia': nvidia, 'ltx': ltx}[key]
        if image is None:
            raise ValueError(f'Connect the {method} branch before selecting it.')
        return io.NodeOutput(image)


class FotufilmLinearToRec709(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='FotufilmLinearToRec709', display_name='Fotufilm · Linear to Rec.709',
            category='Film Finish/Source',
            description='Convert linear color coordinates for native EXR saving. Preserves negative and above-white values; no tone mapping, clipping, or HDR generation. Do not supply PQ, HLG or ACEScct encoded pixels.',
            inputs=[io.Image.Input('images'), io.Combo.Input('source', options=['linear-acescg', 'linear-p3', 'linear-rec2020', 'linear-rec709'], default='linear-acescg')],
            outputs=[io.Image.Output('linear_rec709')])

    @classmethod
    def execute(cls, images, source='linear-acescg'):
        if images.ndim != 4 or images.shape[-1] not in (3, 4):
            raise ValueError('Expected a batch of RGB or RGBA linear frames.')
        if not torch.isfinite(images).all():
            raise ValueError('Linear frames contain non-finite values.')
        rgb = convert(images[..., :3].float(), source, 'linear-rec709')
        if images.shape[-1] == 4:
            rgb = torch.cat((rgb, images[..., 3:].float()), dim=-1)
        return io.NodeOutput(rgb)

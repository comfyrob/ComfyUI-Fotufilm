import json
import tempfile
import uuid
from pathlib import Path

import folder_paths
import numpy as np
import torch
import comfy.model_management
from comfy_api.latest import ComfyExtension, Input, InputImpl, io

from .hdr_nodes import FilmFinishHDRPad, FilmFinishHDRRestore, FilmFinishSaveHDRVideo, FilmFinishSaveHDRMaster, FotufilmDevelopHDRMaster, FotufilmLoadHDRMaster
from .recipe import validate_recipe
from .preview_node import FotufilmStudio, FotufilmStudioReview

WEB_DIRECTORY = './web'


class FotufilmDevelopVideo(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id="FotufilmDevelopVideo", display_name="Fotufilm · Develop Video",
            category="Film Finish", is_output_node=True, inputs=[io.Video.Input("video"),
            io.String.Input("recipe_json", multiline=True),
            io.Int.Input("seed", default=0, min=0, max=2147483647),
            io.Combo.Input("format", options=["mp4", "prores422hq", "hlg"], default="mp4")],
            outputs=[io.Video.Output("video"), io.String.Output("resolved_recipe")])

    @classmethod
    def execute(cls, video: Input.Video, recipe_json: str, seed: int, format="mp4"):
        recipe = validate_recipe(json.loads(recipe_json))
        recipe["seed"] = recipe["seed"] if recipe["seed"] is not None else seed
        with tempfile.TemporaryDirectory(prefix="fotufilm-video-") as directory:
            source = video.get_stream_source()
            if not isinstance(source, str):
                path = Path(directory) / "input.mp4"
                source.seek(0)
                with path.open("wb") as output:
                    while chunk := source.read(4 * 1024 * 1024):
                        output.write(chunk)
                source = str(path)
            from .finish_pipeline import Source, render_clip
            extension = "mov" if format == "prores422hq" else "mp4"
            output_path = str(Path(folder_paths.get_output_directory()) / f"fotufilm-{uuid.uuid4().hex}.{extension}")
            render_clip(Source(source), recipe, output_path, format,
                        interrupt=comfy.model_management.throw_exception_if_processing_interrupted)
            from .video_delivery import repair_packet_durations
            repair_packet_durations(output_path)
            if format == "prores422hq":
                from .video_delivery import repair_prores_color
                repair_prores_color(output_path, 1)
            if format == "hlg":
                import av
                with av.open(output_path) as output:
                    context = output.streams.video[0].codec_context
                    if int(context.color_trc) != 18 or int(context.color_primaries) != 9:
                        Path(output_path).unlink(missing_ok=True)
                        raise ValueError("This film/print finish did not produce Rec.2020 HLG video. Choose a direct-view slide film with Reference exposure.")
            Path(output_path).with_suffix(".recipe.json").write_text(json.dumps(recipe, indent=2))
            return io.NodeOutput(InputImpl.VideoFromFile(output_path), json.dumps(recipe), ui={"files": [
                {"filename": Path(output_path).name, "subfolder": "", "type": "output"}]})


class FotufilmDevelopFrames(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id="FotufilmDevelopFrames", display_name="Fotufilm · Develop Frames",
            category="Film Finish", description="Film simulation on float frames. Returns display-linear P3 before SDR shoulder; do not apply another film or print tone map.",
            inputs=[io.Image.Input("images"), io.String.Input("recipe_json", multiline=True),
                io.Combo.Input("input_color_space", options=["sRGB", "linear Rec.709", "linear Rec.2020", "linear Display P3"]),
                io.Int.Input("seed", default=0, min=0, max=2147483647),
                io.Int.Input("start_frame", default=0, min=0)],
            outputs=[io.Image.Output("linear_p3"), io.String.Output("color_space")])

    @classmethod
    def execute(cls, images, recipe_json, input_color_space, seed, start_frame):
        recipe = validate_recipe(json.loads(recipe_json))
        base_seed = recipe["seed"] if recipe["seed"] is not None else seed
        from .finish_pipeline import Finisher
        from .grading import convert
        recipe['seed'] = base_seed
        spaces={'sRGB':'linear-rec709','linear Rec.709':'linear-rec709',
                'linear Rec.2020':'linear-rec2020','linear Display P3':'linear-p3'}
        frames = []
        with tempfile.TemporaryDirectory(prefix='fotufilm-frames-') as directory:
            finisher=Finisher(recipe,directory)
            try:
                for index,image in enumerate(images):
                    comfy.model_management.throw_exception_if_processing_interrupted()
                    rgb=image[..., :3].detach().cpu().numpy().astype(np.float32)
                    if not np.isfinite(rgb).all():raise ValueError('Input frames contain non-finite pixels.')
                    if input_color_space=='sRGB':
                        if rgb.min()<0 or rgb.max()>1:raise ValueError('Choose a linear input space for HDR.')
                        rgb=np.where(rgb<=.04045,rgb/12.92,((rgb+.055)/1.055)**2.4)
                    rgb=convert(rgb,spaces[input_color_space],'linear-rec2020')
                    frames.append(torch.from_numpy(finisher.frame(rgb,start_frame+index)))
            finally:finisher.close()
        return io.NodeOutput(torch.stack(frames).to(images.device),'linear Display P3')



class FilmFinishExtension(ComfyExtension):
    async def on_load(self):
        from .studio_server import install_routes
        install_routes()

    async def get_node_list(self):
        return [FotufilmDevelopVideo, FotufilmDevelopFrames, FilmFinishHDRPad, FilmFinishHDRRestore, FilmFinishSaveHDRVideo, FilmFinishSaveHDRMaster, FotufilmDevelopHDRMaster, FotufilmStudio, FotufilmStudioReview, FotufilmLoadHDRMaster]


async def comfy_entrypoint():
    return FilmFinishExtension()

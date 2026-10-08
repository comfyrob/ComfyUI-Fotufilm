import json
import tempfile
import uuid
from pathlib import Path

import folder_paths
import numpy as np
import OpenEXR
import torch
import comfy.model_management
from comfy_api.latest import ComfyExtension, Input, InputImpl, io

from .hdr_nodes import FilmFinishHDRPad, FilmFinishHDRRestore, FilmFinishSaveHDRVideo, FilmFinishSaveHDRMaster, FotufilmDevelopHDRMaster
from .native import Engine
from .recipe import render_request, validate_recipe
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
        engine = Engine()
        try:
            with tempfile.TemporaryDirectory(prefix="fotufilm-video-") as directory:
                source = video.get_stream_source()
                if not isinstance(source, str):
                    path = Path(directory) / "input.mp4"
                    source.seek(0)
                    with path.open("wb") as output:
                        while chunk := source.read(4 * 1024 * 1024):
                            output.write(chunk)
                    source = str(path)
                descriptor, _ = engine.call("importPath", {"path": source})
                extension = "mov" if format == "prores422hq" else "mp4"
                output_path = str(Path(folder_paths.get_output_directory()) / f"fotufilm-{uuid.uuid4().hex}.{extension}")
                request = render_request(recipe, recipe["seed"], descriptor["handle"], edge=None)
                # exportOptions reports *still-image* HDR support, which is false
                # on Linux. The native video writer checks film eligibility itself.
                request.update(path=output_path, format="hevc10" if format == "hlg" else format,
                               hdr=format == "hlg", videoProcessing="quality")
                request["edit"]["video"] = {"encoding": "standard", "audio": True}
                def progress(_):
                    if comfy.model_management.processing_interrupted():
                        engine.cancel()
                engine.call("exportVideo", request, progress=progress)
                from .video_delivery import repair_packet_durations
                repair_packet_durations(output_path)
                if format == "prores422hq":
                    from .video_delivery import repair_prores_color
                    repair_prores_color(output_path, 12)
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
        finally:
            engine.close()


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
        primaries = {
            "linear Rec.709": (0.64, 0.33, 0.30, 0.60, 0.15, 0.06, 0.3127, 0.3290),
            "sRGB": (0.64, 0.33, 0.30, 0.60, 0.15, 0.06, 0.3127, 0.3290),
            "linear Rec.2020": (0.708, 0.292, 0.170, 0.797, 0.131, 0.046, 0.3127, 0.3290),
            "linear Display P3": (0.68, 0.32, 0.265, 0.690, 0.15, 0.06, 0.3127, 0.3290),
        }
        engine = Engine()
        frames = []
        try:
            with tempfile.TemporaryDirectory(prefix="fotufilm-frames-") as directory:
                path = str(Path(directory) / "frame.exr")
                for index, image in enumerate(images):
                    comfy.model_management.throw_exception_if_processing_interrupted()
                    rgb = image[..., :3].detach().cpu().numpy().astype(np.float32)
                    if not np.isfinite(rgb).all():
                        raise ValueError("Input frames contain non-finite pixels.")
                    if input_color_space == "sRGB":
                        if rgb.min() < 0 or rgb.max() > 1:
                            raise ValueError("sRGB input must be between 0 and 1; choose a linear input space for HDR.")
                        rgb = np.where(rgb <= 0.04045, rgb / 12.92, ((rgb + 0.055) / 1.055) ** 2.4)
                    OpenEXR.File({"chromaticities": primaries[input_color_space]},
                        {"R": rgb[:, :, 0], "G": rgb[:, :, 1], "B": rgb[:, :, 2]}).write(path)
                    request = render_request(recipe, (base_seed + start_frame + index) % 2147483648, edge=None)
                    frames.append(torch.from_numpy(engine.render_float(path, rgb.shape[1], rgb.shape[0], request)))
            return io.NodeOutput(torch.stack(frames).to(images.device), "linear Display P3")
        finally:
            engine.close()


class FilmFinishExtension(ComfyExtension):
    async def get_node_list(self):
        return [FotufilmDevelopVideo, FotufilmDevelopFrames, FilmFinishHDRPad, FilmFinishHDRRestore, FilmFinishSaveHDRVideo, FilmFinishSaveHDRMaster, FotufilmDevelopHDRMaster, FotufilmStudio, FotufilmStudioReview]


async def comfy_entrypoint():
    return FilmFinishExtension()

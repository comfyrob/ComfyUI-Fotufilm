"""Lightweight video/recipe handoff for the ComfyUI studio scaffold."""
import json
import shutil
import uuid
from pathlib import Path

import folder_paths
from comfy_api.latest import Input, io

from .recipe import validate_recipe

DEFAULT_RECIPE = (Path(__file__).parent / 'examples/vision250d-clean.recipe.json').read_text()


def preview_file(video, label):
    source = video.get_stream_source()
    suffix = Path(source).suffix.lower() if isinstance(source, str) else '.mp4'
    if suffix not in ('.mp4', '.webm', '.mov', '.m4v'):
        raise ValueError('Use MP4, WebM or MOV for video preview. Float EXR preview is not connected in this scaffold.')
    root = Path(folder_paths.get_temp_directory())
    root.mkdir(parents=True, exist_ok=True)
    destination = root / f'fotufilm-preview-{uuid.uuid4().hex}{suffix}'
    try:
        if isinstance(source, str):
            shutil.copyfile(source, destination)
        else:
            position = source.tell()
            try:
                source.seek(0)
                with destination.open('wb') as target:
                    shutil.copyfileobj(source, target, length=4 * 1024 * 1024)
            finally:
                source.seek(position)
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    return {'filename': destination.name, 'subfolder': '', 'type': 'temp', 'label': label}


class FotufilmStudio(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id='FotufilmStudio', display_name='Fotufilm · Studio', category='Film Finish',
            description='Open a video studio inside ComfyUI. Interface scaffold: edit and save the film recipe, play clips and compare an existing render. VIDEO passes through unchanged; connect the recipe output to Develop Video for rendering.',
            is_output_node=True,
            inputs=[io.Video.Input('video'), io.String.Input('recipe_json', multiline=True, default=DEFAULT_RECIPE),
                    io.Float.Input('fps', default=24, min=1, max=120),
                    io.Video.Input('rendered_preview', optional=True), io.Video.Input('enhanced_source', optional=True)],
            outputs=[io.Video.Output('source_video'), io.String.Output('recipe_json')],
        )

    @classmethod
    def execute(cls, video: Input.Video, recipe_json: str, fps: float, rendered_preview=None, enhanced_source=None):
        recipe = validate_recipe(json.loads(recipe_json))
        files = {'source': preview_file(video, 'Original video')}
        if rendered_preview is not None:
            files['rendered'] = preview_file(rendered_preview, 'Existing Fotufilm render')
        if enhanced_source is not None:
            files['enhanced'] = preview_file(enhanced_source, 'Enhanced HDR source')
        return io.NodeOutput(video, json.dumps(recipe), ui={'fotufilm_studio': [{**files, 'fps': fps}]})

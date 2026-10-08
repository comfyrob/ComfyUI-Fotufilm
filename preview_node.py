"""Lightweight video/recipe handoff for the ComfyUI studio scaffold."""
import json
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path

import folder_paths
from comfy_api.latest import Input, io

from .recipe import validate_recipe

DEFAULT_RECIPE = (Path(__file__).parent / 'examples/vision250d-clean.recipe.json').read_text()
StudioContext = io.Custom('FOTUFILM_STUDIO')


@dataclass(frozen=True)
class StudioSession:
    token: str
    recipe: dict


def preview_file(video, label):
    source = video.get_stream_source()
    suffix = Path(source).suffix.lower() if isinstance(source, str) else '.mp4'
    if suffix not in ('.mp4', '.webm', '.mov', '.m4v'):
        raise ValueError('Use MP4, WebM or MOV for video preview. Float EXR preview is not connected in this scaffold.')
    if isinstance(source, str):
        path = Path(source).resolve()
        for kind, directory in [('output', folder_paths.get_output_directory()), ('input', folder_paths.get_input_directory()), ('temp', folder_paths.get_temp_directory())]:
            root = Path(directory).resolve()
            if path.is_relative_to(root):
                relative = path.relative_to(root)
                return {'filename': relative.name, 'subfolder': str(relative.parent) if relative.parent != Path('.') else '', 'type': kind, 'label': label}
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
            description='Expandable video and film recipe editor. Connect recipe_json to a Develop node and studio to Return to Studio downstream. The finished preview returns without a graph cycle.',
            is_output_node=True,
            inputs=[io.Video.Input('video'), io.String.Input('recipe_json', multiline=True, default=DEFAULT_RECIPE),
                    io.Float.Input('fps', default=24, min=1, max=120, advanced=True),
                    io.Video.Input('rendered_preview', optional=True), io.Video.Input('enhanced_source', optional=True)],
            outputs=[io.Video.Output('source_video'), io.String.Output('recipe_json'), StudioContext.Output('studio')],
        )

    @classmethod
    def execute(cls, video: Input.Video, recipe_json: str, fps: float, rendered_preview=None, enhanced_source=None):
        recipe = validate_recipe(json.loads(recipe_json))
        session = StudioSession(uuid.uuid4().hex, recipe)
        files = {'source': preview_file(video, 'Original video')}
        if rendered_preview is not None:
            files['rendered'] = preview_file(rendered_preview, 'Existing Fotufilm render')
        if enhanced_source is not None:
            files['enhanced'] = preview_file(enhanced_source, 'Enhanced HDR source')
        return io.NodeOutput(video, json.dumps(recipe), session,
                             ui={'fotufilm_studio': [{**files, 'fps': fps, 'token': session.token}]})


class FotufilmStudioReview(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id='FotufilmStudioReview', display_name='Fotufilm · Return to Studio',
                         category='Film Finish', is_output_node=True,
                         description='Returns the finished video to its originating Studio. Connect downstream of Develop; never wire the result back upstream.',
                         inputs=[StudioContext.Input('studio'), io.Video.Input('rendered'),
                                 io.Video.Input('enhanced_source', optional=True)],
                         outputs=[io.Video.Output('video')])

    @classmethod
    def execute(cls, studio, rendered, enhanced_source=None):
        if not isinstance(studio, StudioSession):
            raise ValueError('Connect the studio output of Fotufilm Studio.')
        media = {'token': studio.token, 'rendered': preview_file(rendered, 'Fotufilm render'),
                 'rendered_recipe': studio.recipe}
        if enhanced_source is not None:
            media['enhanced'] = preview_file(enhanced_source, 'Enhanced HDR source')
        return io.NodeOutput(rendered, ui={'fotufilm_review': [media]})

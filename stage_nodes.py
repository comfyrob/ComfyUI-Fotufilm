"""Separate film and grading controls sharing one float-source preview engine.

These nodes compose a recipe, not an eagerly materialized video. The downstream
export applies that recipe once to the same connected linear source frames.
"""
import json
from comfy_api.latest import io
from .preview_node import FotufilmStudio, DEFAULT_RECIPE
from .grading import validate_grading
from .recipe import validate_recipe


def compose_grade(recipe_json, adjustments_json='{}'):
    recipe=validate_recipe(json.loads(recipe_json))
    changes=json.loads(adjustments_json)
    # Only explicitly adjusted controls override a look's default finishing grade.
    validated=validate_grading({'finish':changes})['finish']
    recipe['grading']=validate_grading(recipe.get('grading'))
    recipe['grading']['finish'].update({key:validated[key] for key in changes})
    return recipe


class FotufilmFilmStudio(FotufilmStudio):
    @classmethod
    def define_schema(cls):
        schema=super().define_schema()
        schema.node_id='FotufilmFilmStudio'
        schema.display_name='Fotufilm · Film Emulation'
        schema.description='Choose a film/look recipe. Preview applies it to the connected source. Color Grade can edit its finishing colors downstream without another film pass. source_video remains the original; use recipe_json with Export finished video.'
        return schema


class FotufilmColorGrade(FotufilmStudio):
    @classmethod
    def define_schema(cls):
        schema=super().define_schema()
        schema.node_id='FotufilmColorGrade'
        schema.display_name='Fotufilm · Color Grade'
        schema.description='Connect Film Emulation recipe_json, the same source VIDEO and optional linear IMAGE frames. Live Gear grading reuses the cached film frames. Saved adjustments override look defaults. Outputs a combined recipe for full-resolution export; source_video is unchanged.'
        schema.inputs.insert(2,io.String.Input('adjustments_json',default='{}',multiline=True,advanced=True))
        return schema

    @classmethod
    def execute(cls,video,recipe_json=DEFAULT_RECIPE,fps=24,adjustments_json='{}',**kwargs):
        recipe=compose_grade(recipe_json,adjustments_json)
        return super().execute(video,json.dumps(recipe),fps,**kwargs)

import json
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
p=types.ModuleType('film_finish');p.__path__=[str(ROOT)];sys.modules.setdefault('film_finish',p)
from comfy_api.latest import io
from film_finish.stage_nodes import FotufilmFilmEditor,FotufilmGradeEditor
from film_finish.preview_node import FotufilmStudio,DEFAULT_RECIPE
from film_finish.recipe import validate_recipe
from film_finish import runtime_paths

class SlimEditorTests(unittest.TestCase):
    def test_settings_only_outputs_preserve_live_preview_handoff(self):
        ui={'fotufilm_studio':[{'token':'test-session'}]}
        for cls in (FotufilmFilmEditor,FotufilmGradeEditor):
            schema=cls.define_schema()
            self.assertEqual(len(schema.outputs),1)
            self.assertTrue(schema.is_output_node)
            self.assertFalse({'master','enhanced_source','rendered_preview'} & {i.id for i in schema.inputs})
            with patch.object(FotufilmStudio,'execute',return_value=io.NodeOutput(None,DEFAULT_RECIPE,None,None,ui=ui)) as run:
                result=cls.execute(None,DEFAULT_RECIPE,24)
                self.assertEqual(result.result,(DEFAULT_RECIPE,))
                self.assertEqual(result.ui,ui)
                self.assertEqual(run.call_count,1)

    def test_authored_engine_is_preserved_but_renderer_is_recorded(self):
        recipe=json.loads(DEFAULT_RECIPE)
        with patch('film_finish.recipe.runtime_revision',return_value='installed-test-revision'):
            resolved=validate_recipe(recipe)
        self.assertEqual(resolved['engine'],recipe['engine'])
        self.assertEqual(resolved['render_engine'],'installed-test-revision')
        self.assertNotIn('render_engine',recipe)

    def test_custom_runtime_is_not_mislabelled_as_packaged(self):
        with patch.object(runtime_paths,'library_path',return_value=Path('/tmp/external-engine.so')):
            self.assertEqual(runtime_paths.runtime_revision(),'external-runtime')

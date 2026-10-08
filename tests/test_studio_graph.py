"""Run with ComfyUI's Python (--cpu); no model inference or GPU required."""
import json
import sys
import tempfile
import types
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

APP = Path(__file__).resolve().parents[1]
package = types.ModuleType('film_finish')
package.__path__ = [str(APP)]
sys.modules.setdefault('film_finish', package)

class GraphTests(unittest.TestCase):
    def test_connected_hdr_graph_and_subgraph_have_valid_acyclic_links(self):
        data=json.loads((APP/'examples/Film Finish - Studio + LTX 2.5 HDR.json').read_text())
        for graph in [data]+data['definitions']['subgraphs']:
            nodes={n['id']:n for n in graph['nodes']}
            edges={id:[] for id in nodes}
            ids=set()
            for entry in graph['links']:
                id,a,o,b,i,t = entry if isinstance(entry,list) else [entry[x]for x in ['id','origin_id','origin_slot','target_id','target_slot','type']]
                self.assertNotIn(id,ids);ids.add(id)
                if a!=-10:
                    self.assertIn(id,nodes[a]['outputs'][o]['links']);self.assertEqual(nodes[a]['outputs'][o]['type'],t)
                if b!=-20:self.assertEqual(nodes[b]['inputs'][i]['link'],id)
                if a in nodes and b in nodes:edges[a].append(b)
            visiting=set();done=set()
            def visit(id):
                self.assertNotIn(id,visiting,'graph contains a cycle')
                if id in done:return
                visiting.add(id)
                for child in edges[id]:visit(child)
                visiting.remove(id);done.add(id)
            for id in edges:visit(id)
        # Recipe edits cannot reach the LTX subgraph input.
        self.assertEqual(data['nodes'][2]['inputs'][0]['link'],2)
        self.assertEqual(data['links'][1][1],1)

class HandoffTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import folder_paths
        except ImportError:
            raise unittest.SkipTest('Run with ComfyUI on PYTHONPATH')
        from film_finish import hdr_nodes, preview_node
        cls.hdr=hdr_nodes;cls.preview=preview_node;cls.paths=folder_paths

    def test_float_master_output_connects_without_copy_or_reupload(self):
        import numpy as np
        import OpenEXR
        import torch
        from comfy_api.latest import InputImpl
        with tempfile.TemporaryDirectory() as directory, patch.object(self.paths,'get_output_directory',return_value=directory):
            frames=torch.tensor([4.,-.125,1.5]).expand(2,4,6,3).clone()
            video=InputImpl.VideoFromFile(str(APP/'tests/codec-smoke.mp4'))
            result=self.hdr.FilmFinishSaveHDRMaster.execute(frames,video,24,'linear-acescg','test/master')
            master=result.result[0];path=self.hdr.resolve_master('',master)
            self.assertTrue(path.is_file())
            with zipfile.ZipFile(path) as archive:
                exr=Path(directory)/'frame.exr';exr.write_bytes(archive.read('master/000001.exr'))
            with OpenEXR.File(str(exr),separate_channels=True) as image:
                np.testing.assert_array_equal(image.channels()['R'].pixels,frames[1,:,:,0].numpy())
                self.assertLess(float(image.channels()['G'].pixels.min()),0)
            with self.assertRaises(ValueError):self.hdr.resolve_master('',self.hdr.HDRMasterFile('/etc/passwd'))
            with self.assertRaises(ValueError):self.hdr.resolve_master('',{'path':str(path)})

    def test_return_has_same_session_and_exact_recipe(self):
        from comfy_api.latest import InputImpl
        video=InputImpl.VideoFromFile(str(APP/'tests/codec-smoke.mp4'))
        result=self.preview.FotufilmStudio.execute(video,self.preview.DEFAULT_RECIPE,24)
        original,recipe,session,master=result.result
        review=self.preview.FotufilmStudioReview.execute(session,video)
        self.assertIs(original,video)
        self.assertIs(review.result[0],video)
        self.assertEqual(review.ui['fotufilm_review'][0]['token'],result.ui['fotufilm_studio'][0]['token'])
        self.assertEqual(review.ui['fotufilm_review'][0]['rendered_recipe'],json.loads(recipe))
        another=self.preview.FotufilmStudio.execute(video,recipe,24)
        self.assertNotEqual(session.token,another.result[2].token)

if __name__=='__main__':unittest.main()

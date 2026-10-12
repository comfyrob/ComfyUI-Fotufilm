"""Float/color/asset contracts; tiny CPU fixtures, no neural or native film inference."""
import copy
import json
import sys
import tempfile
import threading
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import OpenEXR
import torch

APP = Path(__file__).resolve().parents[1]
package = types.ModuleType('film_finish'); package.__path__ = [str(APP)]
sys.modules.setdefault('film_finish', package)
from film_finish.inspection import inspection_frame, write_inspection, asset_preview, publish_inspection
from film_finish.preview_runtime import PreviewRuntime
from film_finish.grading import convert
from film_finish.hdr_master import PRIMARIES


class FloatSource:
    path = Path('test.ffhdr.zip')
    info = {'width': 12, 'height': 8, 'frames': 3}
    def frames(self, start=0, count=None, edge=None):
        if edge is not None:raise AssertionError('Inspection must never downsample')
        yield start, np.broadcast_to(np.array([-.125, .18, 8.], dtype='float32') + start,
                                    (8, 12, 3)).copy()


class InspectionTests(unittest.TestCase):
    def setUp(self):
        self.recipe = json.loads((APP/'examples/vision250d-clean.recipe.json').read_text())
        self.source = FloatSource()

    def test_source_and_balance_do_not_initialize_film_engine(self):
        with patch('film_finish.finish_pipeline.Finisher', side_effect=AssertionError('Film should not run')):
            original, _ = inspection_frame(self.source, self.recipe, 0, 'source')
            recipe = copy.deepcopy(self.recipe); recipe['grading'] = {'balance': {'exposure': 1}}
            balanced, _ = inspection_frame(self.source, recipe, 0, 'balance')
        np.testing.assert_array_equal(original, next(self.source.frames())[1])
        np.testing.assert_allclose(balanced, original*2, rtol=2e-5, atol=2e-6)
        self.assertEqual(original.shape, (8, 12, 3))
        self.assertLess(original.min(), 0); self.assertGreater(original.max(), 1)

    def test_film_inspection_reuses_cache_and_finish_is_a_separate_stage(self):
        calls = []
        class FakeFinisher:
            film_signature = 'same-film'
            def __init__(self, *args): pass
            def develop(self, rgb, index): calls.append(index); return rgb * 2
            def finish(self, rgb): return rgb * 3
            def close(self): pass
        with tempfile.TemporaryDirectory() as directory:
            runtime = PreviewRuntime(Path(directory)/'cache', 'test')
            try:
                with patch('film_finish.finish_pipeline.Finisher', FakeFinisher):
                    film, first = inspection_frame(self.source, self.recipe, 1, 'film', runtime=runtime, fingerprint='a')
                    finish, second = inspection_frame(self.source, self.recipe, 1, 'finish', runtime=runtime, fingerprint='a')
                expected = convert(next(self.source.frames(1))[1]*2, 'linear-p3', 'linear-rec2020')
                np.testing.assert_array_equal(film, expected)
                np.testing.assert_allclose(finish, film*3, rtol=1e-6)
                self.assertEqual(calls, [1]); self.assertEqual(first['filmRenderedFrames'], 1)
                self.assertEqual(second['filmCacheHits'], 1)
            finally: runtime.close()

    def test_exr_roundtrip_has_exact_float_pixels_and_rec2020_metadata(self):
        rgb, _ = inspection_frame(self.source, self.recipe, 0, 'source')
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'frame.exr'
            metadata = write_inspection(rgb, path, {'frame': 0, 'stage': 'source'})
            with OpenEXR.File(str(path), separate_channels=True) as image:
                actual = np.stack([image.channels()[c].pixels for c in 'RGB'], axis=-1)
                np.testing.assert_array_equal(actual, rgb)
                self.assertEqual(actual.dtype, np.float32)
                np.testing.assert_allclose(image.header()['chromaticities'], PRIMARIES['linear-rec2020'])
            self.assertEqual(json.loads(path.with_suffix('.json').read_text()), metadata)
            self.assertFalse(metadata['displayTransformBaked'])
            self.assertTrue(path.with_suffix('.png').is_file())
            self.assertFalse(list(Path(directory).glob('*.part')))

    def test_invalid_frame_stage_and_nonfinite_pixels_rejected(self):
        for index, stage in [(True,'source'),(-1,'source'),(3,'source'),(0,'unknown')]:
            with self.assertRaises(ValueError):inspection_frame(self.source, self.recipe, index, stage)
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):write_inspection(np.full((1,1,3),np.nan),Path(directory)/'bad.exr',{})
            self.assertFalse(list(Path(directory).iterdir()))

    def test_old_and_new_asset_protocols_and_registration_failure(self):
        import folder_paths
        from server import PromptServer
        import film_finish.studio_server as server
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); path = root/'frame.exr'
            rgb, _ = inspection_frame(self.source, self.recipe, 0, 'source')
            write_inspection(rgb,path,{})
            def new_register(path, job_id, preview_ref=None):
                self.assertIsNone(job_id); self.assertIsNotNone(preview_ref)
                return types.SimpleNamespace(id='asset-test')
            manager = types.SimpleNamespace(enabled=True, register_executed_output=new_register)
            with patch.object(PromptServer,'instance',types.SimpleNamespace(asset_manager=manager),create=True), \
                 patch.object(folder_paths,'get_previews_directory',return_value=str(root/'previews'),create=True), \
                 patch.object(server.folder_paths,'get_output_directory',return_value=str(root)):
                result = publish_inspection(path,register=True)
                self.assertEqual(result['assetId'],'asset-test'); self.assertIsNone(result['warning'])
                ref = result['exr']['asset_preview']; self.assertTrue((root/'previews'/ref['filename']).is_file())
                from blake3 import blake3
                self.assertRegex(ref['filename'], r'^[0-9a-f]{64}\.(jpg|webp)$')
                self.assertEqual(ref['filename'], blake3((root/'previews'/ref['filename']).read_bytes()).hexdigest()+'.jpg')
                manager.register_executed_output = lambda path, job_id: types.SimpleNamespace(id='old-asset')
                self.assertIsNone(asset_preview(path))
                self.assertEqual(publish_inspection(path,register=True)['assetId'],'old-asset')
                manager.enabled = False
                result = publish_inspection(path,register=True)
                self.assertNotIn('asset_preview',result['exr']); self.assertIsNotNone(result['warning'])
                manager.enabled = True
                def failing(path, job_id, preview_ref=None): raise RuntimeError('test failure')
                manager.register_executed_output = failing
                with self.assertLogs(level='WARNING'):result = publish_inspection(path,register=True)
                self.assertIsNotNone(result['warning']); self.assertTrue(path.is_file())

    def test_cancelled_inspection_never_processes_or_publishes(self):
        from film_finish.studio_server import inspect_job
        job = {'cancel':threading.Event()};job['cancel'].set()
        with patch('film_finish.studio_server.inspection_frame',side_effect=AssertionError('Unexpected render')):
            list(inspect_job(job,None,None,0,'source'))
        self.assertEqual(job['status'],'cancelled');self.assertNotIn('result',job)

    def test_studio_job_saves_the_selected_hdr_master_frame_without_video_render(self):
        import folder_paths
        from film_finish import studio_server
        from film_finish.hdr_master import write_master
        from film_finish.finish_pipeline import Source
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            images = torch.tensor([-.125,.18,8.]).expand(3,8,12,3).clone()
            images[2] *= 2
            master = root/'source.ffhdr.zip'
            write_master(images,24,'linear-rec2020',APP/'tests/codec-smoke.mp4',master,proxy_edge=8)
            runtime = PreviewRuntime(root/'cache','test')
            job = {'cancel':threading.Event()}
            try:
                with patch.object(folder_paths,'get_output_directory',return_value=str(root)), \
                     patch.object(studio_server,'preview_runtime',return_value=runtime), \
                     patch('film_finish.inspection.asset_preview',return_value=None), \
                     patch('film_finish.studio_server.render_clip_steps',side_effect=AssertionError('Unexpected video render')):
                    list(studio_server.inspect_job(job,{'source':Source(master),'fingerprint':'master'},self.recipe,2,'source'))
                self.assertEqual(job['status'],'complete')
                result=job['result'];self.assertEqual(result['frame'],2)
                exr=root/result['exr']['subfolder']/result['exr']['filename']
                with OpenEXR.File(str(exr),separate_channels=True) as image:
                    actual=np.stack([image.channels()[c].pixels for c in 'RGB'],axis=-1)
                np.testing.assert_array_equal(actual,images[2].numpy())
                self.assertEqual((result['width'],result['height']),(12,8))
            finally:runtime.close()

    def test_inspection_example_has_no_inference_dependency_and_links_master(self):
        graph=json.loads((APP/'examples/Fotufilm - Inspect HDR frame.json').read_text())
        nodes={node['id']:node for node in graph['nodes']}
        self.assertEqual({n['type'] for n in nodes.values()}, {'FotufilmLoadHDRMaster','FotufilmInspectFrame','MarkdownNote'})
        for id,origin,slot,target,input_slot,kind in graph['links']:
            self.assertIn(id,nodes[origin]['outputs'][slot]['links'])
            self.assertEqual(nodes[target]['inputs'][input_slot]['link'],id)
            self.assertEqual(nodes[target]['inputs'][input_slot]['type'],kind)

    def test_node_branches_from_float_frames_without_changing_range(self):
        import folder_paths
        from film_finish.inspection_node import FotufilmInspectFrame
        images = torch.tensor([-.125,.18,8.]).expand(3,8,12,3).clone()
        schema = FotufilmInspectFrame.define_schema()
        self.assertEqual(schema.node_id,'FotufilmInspectFrame')
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(folder_paths,'get_output_directory',return_value=directory), \
             patch('film_finish.inspection.asset_preview',return_value=None):
            result = FotufilmInspectFrame.execute(1,'source',json.dumps(self.recipe),'linear Display P3',images=images)
            expected = convert(images[1].numpy(),'linear-p3','linear-rec2020')
            np.testing.assert_array_equal(result.result[0][0].numpy(), expected)
            self.assertEqual(result.result[1], 'linear Rec.2020')
            self.assertEqual(len(list(Path(directory).rglob('*.exr'))),1)
            with self.assertRaises(ValueError):
                FotufilmInspectFrame.execute(0,'source',json.dumps(self.recipe),'linear Rec.2020',images=images,video=object())

if __name__ == '__main__':unittest.main()

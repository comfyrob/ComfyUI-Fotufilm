"""Real float/grade/preview contracts. Runs in Comfy's CPU test environment."""
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch
APP=Path(__file__).resolve().parents[1]
package=types.ModuleType('film_finish');package.__path__=[str(APP)];sys.modules.setdefault('film_finish',package)

class GradingTests(unittest.TestCase):
    def setUp(self):
        import numpy as np
        from film_finish import grading
        self.np=np;self.g=grading

    def test_identity_retains_negative_and_hdr_values_exactly(self):
        rgb=self.np.array([[[-.125,.18,12.]]],dtype='float32')
        self.np.testing.assert_array_equal(self.g.apply_grade(rgb,self.g.neutral_grade(),'linear-rec2020'),rgb)

    def test_exposure_doubles_linear_light(self):
        rgb=self.np.array([[[.02,.18,4.],[1.,2.,8.]]],dtype='float32')
        grade=self.g.neutral_grade();grade['exposure']=1
        self.np.testing.assert_allclose(self.g.apply_grade(rgb,grade,'linear-rec2020'),rgb*2,rtol=2e-5,atol=2e-6)

    def test_explicit_color_conversions_roundtrip(self):
        rgb=self.np.array([[[-.1,.18,12.]]],dtype='float32')
        for space in ('linear-rec709','linear-rec2020','linear-acescg','linear-p3'):
            self.np.testing.assert_allclose(self.g.convert(self.g.convert(rgb,space,'linear-rec2020'),'linear-rec2020',space),rgb,atol=2e-6)

    def test_invalid_grade_rejected(self):
        for settings in ({'balance':{'exposure':float('nan')}},{'finish':{'gamma':[0,1,1]}},{'finish':{'tone_mapping':2}}):
            with self.assertRaises(ValueError):self.g.validate_grading(settings)

class NativeTests(unittest.TestCase):
    def test_still_matches_same_frame_in_export_pipeline(self):
        import numpy as np
        from PIL import Image
        from film_finish.finish_pipeline import Source,Finisher,render_still
        from film_finish.master_export import delivery
        source=Source(APP/'tests/codec-smoke.mp4')
        recipe=json.loads((APP/'examples/vision250d-clean.recipe.json').read_text())
        recipe['params']['grain']=0
        recipe['grading']={'balance':{'exposure':.4},'finish':{'saturation':.8}}
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);after=root/'after.png';before=root/'before.png'
            render_still(source,recipe,after,before,0,160)
            worker=Finisher(recipe,root)
            try:
                index,rgb=next(source.frames(0,1,160))
                expected=(delivery(worker.frame(rgb,index),False,1)/257).round().astype('uint8')
                np.testing.assert_array_equal(np.asarray(Image.open(after)),expected)
            finally:worker.close()

    def test_source_paths_cannot_escape_comfy_directories(self):
        import folder_paths
        from film_finish.studio_server import resolve_file
        with tempfile.TemporaryDirectory() as directory,patch.object(folder_paths,'get_input_directory',return_value=directory):
            with self.assertRaises(ValueError):resolve_file({'filename':'../../etc/passwd','type':'input'})
            with self.assertRaises(ValueError):resolve_file({'filename':'/etc/passwd','type':'input'})

class RenderContractTests(unittest.TestCase):
    def test_hdr_source_keeps_float_headroom_through_balance(self):
        import numpy as np
        import torch
        from film_finish.hdr_master import write_master
        from film_finish.finish_pipeline import Source
        from film_finish.grading import apply_grade,neutral_grade
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'test.ffhdr.zip'
            frames=torch.tensor([-.125,.18,8.]).expand(4,16,32,3).clone()
            write_master(frames,24,'linear-rec2020',APP/'tests/codec-smoke.mp4',path,proxy_edge=32)
            source=Source(path);index,rgb=next(source.frames(2,1,16))
            self.assertEqual(index,2);self.assertTrue(source.info['hdr']);self.assertEqual(rgb.shape,(8,16,3))
            grade=neutral_grade();grade['exposure']=-1
            np.testing.assert_allclose(apply_grade(rgb,grade,'linear-rec2020'),rgb*.5,rtol=2e-4,atol=2e-5)
            self.assertGreater(float(rgb.max()),1)

    def test_export_retains_frame_count_timing_and_audio(self):
        import av
        from film_finish.finish_pipeline import Source,render_clip
        import subprocess,imageio_ffmpeg
        recipe=json.loads((APP/'examples/vision250d-clean.recipe.json').read_text())
        recipe['params']['grain']=0
        recipe['grading']={'balance':{'exposure':.2},'finish':{'contrast':1.05}}
        with tempfile.TemporaryDirectory() as directory:
            original=Path(directory)/'source.mp4'
            subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),'-loglevel','error','-y','-f','lavfi','-i','testsrc2=size=64x64:rate=24','-f','lavfi','-i','sine=frequency=440','-t','0.5','-c:v','libx264','-c:a','aac',str(original)],check=True)
            source=Source(original)
            target=Path(directory)/'finished.mp4'
            result=render_clip(source,recipe,target,'mp4',edge=160,count=4)
            with av.open(str(target)) as output:
                stream=output.streams.video[0]
                self.assertEqual(len(list(output.decode(stream))),4)
                self.assertAlmostEqual(float(stream.average_rate),source.info['fps'],places=3)
                self.assertEqual((stream.width,stream.height),(result['width'],result['height']))
                self.assertEqual(int(stream.codec_context.color_primaries),1)
            with av.open(str(source.path)) as input_video, av.open(str(target)) as output:
                self.assertEqual(bool(output.streams.audio),bool(input_video.streams.audio))
            self.assertTrue(target.with_suffix('.recipe.json').is_file())

    def test_prores_and_hlg_have_explicit_delivery_tags(self):
        import av
        from film_finish.finish_pipeline import Source,render_clip
        recipe=json.loads((APP/'examples/vision250d-clean.recipe.json').read_text())
        recipe.update(stock='ektachromee100',digitalReference='reference-exposure')
        recipe['params']['grain']=0
        source=Source(APP/'tests/codec-smoke.mp4')
        with tempfile.TemporaryDirectory() as directory:
            for format_id,ext,expected in [('prores422hq','mov',(1,13,1)),('hlg','mp4',(9,18,9))]:
                with self.subTest(format=format_id):
                    path=Path(directory)/('finish.'+ext)
                    render_clip(source,recipe,path,format_id,count=1)
                    with av.open(str(path)) as video:
                        next(video.decode(video=0));c=video.streams.video[0].codec_context
                        self.assertEqual((int(c.color_primaries),int(c.color_trc),int(c.colorspace)),expected)

    def test_cancelled_job_does_not_publish_a_result(self):
        import threading
        from film_finish.studio_server import execute_job
        job={'status':'queued','cancel':threading.Event()};job['cancel'].set()
        execute_job(job,None,None,'frame',160,0,'mp4')
        self.assertEqual(job['status'],'cancelled');self.assertNotIn('result',job)

if __name__=='__main__':unittest.main()

"""Check the native-save handoff retains float data and uses the monitor transform."""
import importlib
import json
import sys
import types
import unittest
from pathlib import Path
import torch

ROOT=Path(__file__).resolve().parents[1]
p=types.ModuleType('film_finish');p.__path__=[str(ROOT)];sys.modules.setdefault('film_finish',p)

class NativeVideoOutputTests(unittest.TestCase):
    def test_float_and_sdr_outputs_share_render_but_keep_different_ranges(self):
        from film_finish.display_transform import encode_sdr
        from comfy_extras.nodes_video import CreateVideo
        pack=importlib.import_module('film_finish.__init__')
        entry=next(x for x in json.loads((ROOT/'examples/studio-looks.json').read_text()) if x['id']=='balanced-slide')
        recipe=entry['recipe'];recipe['grading']['finish']['exposure']=1
        ramp=torch.linspace(.01,12,96).reshape(1,1,96,1).expand(2,64,96,3).clone()
        original=ramp.clone()
        result=pack.FotufilmDevelopFrames.execute(ramp,json.dumps(recipe),'linear Rec.709',1,0).result
        linear,space,sdr=result
        self.assertEqual(space,'linear Display P3');self.assertEqual(linear.shape,sdr.shape)
        self.assertGreater(linear.max().item(),1)
        self.assertGreaterEqual(sdr.min().item(),0);self.assertLessEqual(sdr.max().item(),1)
        torch.testing.assert_close(sdr,encode_sdr(linear,knee=.7))
        torch.testing.assert_close(ramp,original)
        video=CreateVideo.execute(sdr,24,color_space='sRGB',bit_depth=8).result[0]
        self.assertEqual(video.get_frame_count(),2)
        self.assertAlmostEqual(float(video.get_frame_rate()),24)

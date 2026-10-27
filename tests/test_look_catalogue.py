"""Exercise shipped recipes against the actual pinned native engine, including HDR."""
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path

APP=Path(__file__).resolve().parents[1]
package=types.ModuleType('film_finish');package.__path__=[str(APP)]
sys.modules.setdefault('film_finish',package)

class LookCatalogueTests(unittest.TestCase):
    def test_shipped_looks_render_finite_distinct_sdr_and_hdr(self):
        import numpy as np
        from film_finish.finish_pipeline import Finisher
        from film_finish.preview_runtime import PreviewRuntime
        from film_finish.recipe import validate_recipe
        entries=json.loads((APP/'examples/studio-looks.json').read_text())
        # Neutral ramp, saturated patches and over-white values exercise the
        # real film profile lookup and both Gear/Fotufilm processing stages.
        ramp=np.linspace(.001,1,64,dtype=np.float32)
        rgb=np.stack(np.meshgrid(ramp,ramp),axis=-1)
        rgb=np.concatenate((rgb,np.full((64,64,1),.18,dtype=np.float32)),axis=-1)
        results={}
        with tempfile.TemporaryDirectory() as directory:
            runtime=PreviewRuntime(Path(directory)/'cache','catalogue-test')
            try:
                for entry in entries:
                    with self.subTest(look=entry['id']):
                        worker=Finisher(validate_recipe(entry['recipe']),directory,runtime)
                        try:
                            for gain in (1,8):
                                result=worker.frame(rgb*gain,0)
                                self.assertEqual(result.shape,rgb.shape)
                                self.assertTrue(np.isfinite(result).all())
                                self.assertGreater(float(result.std()),.001)
                                if gain==1:results[entry['id']]=result.copy()
                        finally:worker.close()
            finally:runtime.close()
        for a,b in [('clean','chrome-road'),('print','silver-print'),('warm','soft-window'),
                    ('slide','vivid-daylight'),('slide','cool-slide'),('silver','soft-silver'),
                    ('reala-dailies','seventies-print'),('dense-release','muted-thriller'),
                    ('daylight-160','clean-beauty'),('quiet-landscape','summer-chrome'),
                    ('studio-mono','grainy-night'),('instant-memory','phoenix-shift')]:
            self.assertGreater(float(np.abs(results[a]-results[b]).mean()),.001,(a,b))

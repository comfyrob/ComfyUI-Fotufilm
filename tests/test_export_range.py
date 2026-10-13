import sys
import types
import unittest
from pathlib import Path
p=types.ModuleType('film_finish');p.__path__=[str(Path(__file__).resolve().parents[1])];sys.modules.setdefault('film_finish',p)
from film_finish.export_range import export_range

class ExportRangeTests(unittest.TestCase):
    def test_trial_uses_absolute_frame_and_clamps_at_end(self):
        info={'frames':240,'fps':24}
        self.assertEqual(export_range(info,'trial',48),(48,120))
        self.assertEqual(export_range(info,'trial',239),(239,1))
        self.assertEqual(export_range(info),(0,240))
        for kind,start in [('bogus',0),('full',48),('trial',True),('trial',-1),('trial',240),('trial',.5)]:
            with self.assertRaises(ValueError):export_range(info,kind,start)

class TrialDeliveryTests(unittest.TestCase):
    def test_trial_passes_absolute_indices_and_seeks_audio(self):
        import tempfile, subprocess, json
        from unittest.mock import patch
        import numpy as np
        import av, imageio_ffmpeg
        from film_finish.finish_pipeline import Source, render_clip
        root=Path(__file__).resolve().parents[1]
        recipe=json.loads((root/'examples/vision250d-clean.recipe.json').read_text())
        seen=[]
        class IndexedFinisher:
            def __init__(self,*args):pass
            def frame(self,rgb,index):
                seen.append(index)
                return np.full_like(rgb,index/48)
            def close(self):pass
        with tempfile.TemporaryDirectory() as directory:
            source_path=Path(directory)/'source.mp4';target=Path(directory)/'trial.mp4'
            subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),'-v','error','-y',
                '-f','lavfi','-i','testsrc2=size=64x64:rate=24',
                '-f','lavfi','-i',r'aevalsrc=sin(2*PI*if(lt(t\,0.5)\,440\,880)*t):s=48000',
                '-t','1','-c:v','libx264','-c:a','aac',str(source_path)],check=True)
            source=Source(source_path)
            with patch('film_finish.finish_pipeline.Finisher',IndexedFinisher):
                result=render_clip(source,recipe,target,'mp4',start=12,count=12)
            self.assertEqual(seen,list(range(12,24)))
            self.assertEqual(result['start'],.5);self.assertEqual(result['frames'],12)
            with av.open(str(target)) as clip:
                self.assertEqual(len(list(clip.decode(video=0))),12)
            with av.open(str(target)) as clip:
                audio=np.concatenate([frame.to_ndarray()[0] for frame in clip.decode(audio=0)])
            spectrum=np.abs(np.fft.rfft(audio[:16000]*np.hanning(min(len(audio),16000))))
            peak=np.fft.rfftfreq(min(len(audio),16000),1/48000)[spectrum.argmax()]
            self.assertAlmostEqual(peak,880,delta=5)

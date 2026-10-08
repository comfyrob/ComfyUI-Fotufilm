"""Quality and invalidation contracts for reusable native previews."""
import copy
import json
import sys
import tempfile
import threading
import types
import unittest
from pathlib import Path
from unittest.mock import patch

APP = Path(__file__).resolve().parents[1]
package = types.ModuleType('film_finish')
package.__path__ = [str(APP)]
sys.modules.setdefault('film_finish', package)


class SchedulerTests(unittest.TestCase):
    def test_current_frame_preempts_clip_and_clip_resumes_without_losing_frames(self):
        from film_finish.preview_scheduler import PreviewScheduler
        entered, release = threading.Event(), threading.Event()
        order = []
        def clip():
            order.append('clip-0');entered.set()
            if not release.wait(5):raise TimeoutError('test synchronization')
            yield
            for i in range(1,4):order.append(f'clip-{i}');yield
            return 4
        def frame():
            order.append('interactive')
            if False:yield
        worker = PreviewScheduler()
        try:
            long = worker.submit(10, clip)
            self.assertTrue(entered.wait(5))
            urgent = worker.submit(0, frame)
            release.set()
            urgent.result(5);self.assertEqual(long.result(5),4)
            self.assertEqual(order,['clip-0','interactive','clip-1','clip-2','clip-3'])
        finally:release.set();worker.shutdown()

    def test_shutdown_closes_suspended_work(self):
        from film_finish.preview_scheduler import PreviewScheduler
        entered, release, closed = threading.Event(), threading.Event(), threading.Event()
        def job():
            try:
                entered.set();release.wait(5);yield
            finally:closed.set()
        worker=PreviewScheduler()
        future=worker.submit(10,job)
        self.assertTrue(entered.wait(5));worker.shutdown(wait=False);release.set();worker.shutdown()
        self.assertTrue(closed.is_set())
        with self.assertRaises(InterruptedError):future.result()


class FloatCacheTests(unittest.TestCase):
    def test_disk_is_lossless_bounded_and_recovers_from_invalid_file(self):
        import numpy as np
        from film_finish.preview_runtime import FloatDiskCache
        with tempfile.TemporaryDirectory() as directory:
            cache=FloatDiskCache(directory,limit=500)
            pixels=np.array([[[-.125,.18,16.]]],dtype=np.float32)
            cache.put('a',pixels)
            np.testing.assert_array_equal(cache.get('a'),pixels)
            (Path(directory)/'a.npy').write_bytes(b'bad')
            self.assertIsNone(cache.get('a'))
            for i in range(10):cache.put(str(i),pixels)
            self.assertLessEqual(cache.bytes,500)
            self.assertIsNone(cache.get('0'))
            np.testing.assert_array_equal(cache.get('9'),pixels)

    def test_memory_cache_is_immutable_and_accounts_for_replacements(self):
        import numpy as np
        from film_finish.preview_runtime import FloatLRU
        cache=FloatLRU(24);pixels=np.ones((1,1,3),dtype=np.float32)
        for name in ('a','b','a','c'):cache.put(name,pixels)
        self.assertEqual(cache.bytes,24);self.assertIsNone(cache.get('b'))
        self.assertFalse(cache.get('a').flags.writeable)
        pixels[:]=5
        np.testing.assert_array_equal(cache.get('a'),np.ones_like(pixels))


class NativeReuseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import subprocess,imageio_ffmpeg
        cls.fixture=tempfile.TemporaryDirectory()
        cls.source_path=Path(cls.fixture.name)/'four-frames.mp4'
        subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),'-v','error','-y','-stream_loop','-1',
                        '-i',str(APP/'tests/codec-smoke.mp4'),'-frames:v','4','-an','-c:v','libx264',str(cls.source_path)],check=True)

    @classmethod
    def tearDownClass(cls):cls.fixture.cleanup()

    def test_finish_only_reuses_native_float_but_balance_film_seed_and_source_invalidate(self):
        import numpy as np
        from PIL import Image
        from film_finish.finish_pipeline import Source, render_still
        from film_finish.preview_runtime import PreviewRuntime
        source=Source(self.source_path)
        recipe=json.loads((APP/'examples/vision250d-clean.recipe.json').read_text())
        # Keep grain enabled: cached output must also preserve the same texture realization.
        recipe['grading']={'balance':{'exposure':.2},'finish':{'saturation':.8}}
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);runtime=PreviewRuntime(root/'cache','test',memory_limit=1024*1024)
            def preview(value,identity='source',index=0,edge=160):
                return render_still(source,value,root/'after.png',root/'before.png',index,edge,
                                    runtime=runtime,fingerprint=identity)
            try:
                self.assertEqual(preview(recipe)['filmRenderedFrames'],1)
                engine=runtime.engine
                changed=copy.deepcopy(recipe);changed['grading']['finish']['saturation']=1.12
                with patch.object(engine,'render_float',side_effect=AssertionError('Unnecessary film rerender')):
                    info=preview(changed)
                self.assertEqual(info['filmCacheHits'],1);self.assertEqual(info['decodedFrames'],0)
                actual=np.asarray(Image.open(root/'after.png')).copy()
                render_still(source,changed,root/'reference.png',root/'original.png',0,160)
                np.testing.assert_array_equal(actual,np.asarray(Image.open(root/'reference.png')))
                self.assertIs(runtime.engine,engine)
                # Exercise disk reuse after RAM eviction, still with exactly the same pixels.
                runtime.film_cache.clear()
                with patch.object(engine,'render_float',side_effect=AssertionError('Disk cache missed')):
                    self.assertEqual(preview(changed)['filmCacheHits'],1)
                np.testing.assert_array_equal(actual,np.asarray(Image.open(root/'after.png')))
                for field in ('balance','stock','grain','seed','source','frame','resolution'):
                    altered=copy.deepcopy(recipe);identity='source';index=0;edge=160
                    if field=='balance':altered['grading']['balance']['exposure']=.4
                    elif field=='stock':altered['stock']='gold200'
                    elif field=='grain':altered['params']['grain']=.8
                    elif field=='seed':altered['seed']=8
                    elif field=='source':identity='changed-file'
                    elif field=='frame':index=1
                    else:edge=32
                    with self.subTest(field=field):
                        self.assertEqual(preview(altered,identity,index,edge)['filmRenderedFrames'],1)
            finally:runtime.close()

    def test_cached_clip_retains_every_frame_and_matches_uncached_encoding(self):
        import av
        import numpy as np
        from film_finish.finish_pipeline import Source,render_clip
        from film_finish.preview_runtime import PreviewRuntime
        source=Source(self.source_path)
        recipe=json.loads((APP/'examples/vision250d-clean.recipe.json').read_text())
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);runtime=PreviewRuntime(root/'cache','test')
            try:
                render_clip(source,recipe,root/'first.mp4',edge=160,count=3,runtime=runtime,fingerprint='s')
                recipe['grading']={'finish':{'contrast':1.1,'exposure':.2}}
                with patch.object(runtime.engine,'render_float',side_effect=AssertionError('Rerendered film')):
                    result=render_clip(source,recipe,root/'cached.mp4',edge=160,count=3,runtime=runtime,fingerprint='s')
                self.assertEqual(result['filmCacheHits'],3);self.assertEqual(result['decodedFrames'],0)
                render_clip(source,recipe,root/'reference.mp4',edge=160,count=3)
                with av.open(str(root/'cached.mp4')) as a,av.open(str(root/'reference.mp4')) as b:
                    actual=list(a.decode(video=0));expected=list(b.decode(video=0))
                    self.assertEqual(len(actual),3);self.assertEqual(len(expected),3)
                    for left,right in zip(actual,expected):
                        np.testing.assert_array_equal(left.to_ndarray(format='rgb24'),right.to_ndarray(format='rgb24'))
            finally:runtime.close()

    def test_interrupted_clip_removes_partial_output_but_preserves_finished_float_frames(self):
        from film_finish.finish_pipeline import Source,render_clip_steps
        from film_finish.preview_runtime import PreviewRuntime
        source=Source(self.source_path)
        recipe=json.loads((APP/'examples/vision250d-clean.recipe.json').read_text())
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);runtime=PreviewRuntime(root/'cache','test')
            target=root/'cancelled.mp4'
            steps=render_clip_steps(source,recipe,target,edge=160,count=3,runtime=runtime,fingerprint='s')
            try:
                next(steps);steps.close()
                self.assertFalse(target.exists());self.assertGreater(runtime.disk.bytes,0)
            finally:steps.close();runtime.close()

    def test_hdr_float_cache_matches_fresh_native_output_before_display_conversion(self):
        import numpy as np
        import torch
        from film_finish.finish_pipeline import Source,Finisher
        from film_finish.hdr_master import write_master
        from film_finish.preview_runtime import PreviewRuntime,SourceCursor,render_stats
        recipe=json.loads((APP/'examples/vision250d-clean.recipe.json').read_text())
        recipe.update(stock='ektachromee100',digitalReference='reference-exposure')
        recipe['grading']={'finish':{'exposure':.15}}
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);bundle=root/'source.ffhdr.zip'
            light=torch.tensor([-.125,.18,8.]).expand(2,16,32,3).clone()
            write_master(light,24,'linear-rec2020',self.source_path,bundle,proxy_edge=32)
            source=Source(bundle);runtime=PreviewRuntime(root/'cache','test')
            cursor=SourceCursor(source,None);worker=Finisher(recipe,root,runtime)
            try:
                stats=render_stats();actual=runtime.finished_frame(cursor,'hdr',0,worker,stats)
                expected=worker.frame(next(source.frames(0,1))[1],0)
                np.testing.assert_array_equal(actual,expected)
                self.assertEqual(stats['filmRenderedFrames'],1)
                runtime.film_cache.clear()
                cached=runtime.finished_frame(cursor,'hdr',0,worker,stats)
                np.testing.assert_array_equal(cached,expected);self.assertEqual(stats['filmCacheHits'],1)
            finally:cursor.close();worker.close();runtime.close()


if __name__=='__main__':unittest.main()

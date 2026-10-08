"""Run on a render worker: python scripts/benchmark_previews.py /path/to/video.mp4.

Measures unchanged-resolution native previews, with grain enabled, and asserts
that cached and uncached paths produce identical display pixels/video frames.
Does not run models, submit Comfy workflows, or touch user outputs.
"""
import argparse
import copy
import ctypes
import json
import statistics
import sys
import tempfile
import time
import types
from pathlib import Path

APP=Path(__file__).resolve().parents[1]
package=types.ModuleType('film_finish');package.__path__=[str(APP)]
sys.modules.setdefault('film_finish',package)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('source')
    parser.add_argument('--edge',type=int,default=960)
    parser.add_argument('--frames',type=int,default=24)
    parser.add_argument('--baseline',help='Optional previous finish_pipeline.py for before/after profiling')
    args=parser.parse_args()
    import av
    import numpy as np
    from PIL import Image
    from film_finish.finish_pipeline import Source,render_still,render_clip
    from film_finish.preview_runtime import PreviewRuntime
    reference_still,reference_clip=render_still,render_clip
    if args.baseline:
        import importlib.util
        spec=importlib.util.spec_from_file_location('film_finish._baseline_pipeline',args.baseline)
        previous=importlib.util.module_from_spec(spec);spec.loader.exec_module(previous)
        reference_still,reference_clip=previous.render_still,previous.render_clip
    source=Source(args.source)
    recipe=json.loads((APP/'examples/vision250d-clean.recipe.json').read_text())
    recipe['grading']={'balance':{'exposure':.25},'finish':{'saturation':.85}}
    report={'source':source.info,'edge':args.edge,'grain':recipe['params']['grain'],'previousPipeline':bool(args.baseline)}
    with tempfile.TemporaryDirectory(prefix='fotufilm-benchmark-') as directory:
        root=Path(directory);runtime=PreviewRuntime(root/'cache','benchmark')
        def still(label,value,reuse):
            start=time.monotonic()
            function=render_still if reuse else reference_still
            options={'runtime':runtime,'fingerprint':'benchmark-source','reuse_before':True} if reuse else {}
            info=function(source,value,root/(label+'.png'),root/('shared-before.png' if reuse else label+'-before.png'),0,args.edge,**options)
            elapsed=time.monotonic()-start
            print(json.dumps({'label':label,'seconds':round(elapsed,4),'imageBytes':(root/(label+'.png')).stat().st_size,**info}),flush=True)
            return elapsed
        try:
            report['coldUncachedSeconds']=still('cold',recipe,False)
            report['primeCacheSeconds']=still('prime',recipe,True)
            pointer=runtime.engine.lib.fotufilm_engine_describe(runtime.engine.handle)
            try:report['backend']=json.loads(ctypes.string_at(pointer))['backend']
            finally:runtime.engine.lib.fotufilm_free(pointer)
            uncached=[];cached=[]
            for i,saturation in enumerate((.9,1.05,.75)):
                changed=copy.deepcopy(recipe);changed['grading']['finish']['saturation']=saturation
                uncached.append(still(f'uncached-{i}',changed,False))
                cached.append(still(f'cached-{i}',changed,True))
                np.testing.assert_array_equal(np.asarray(Image.open(root/f'uncached-{i}.png')),
                                               np.asarray(Image.open(root/f'cached-{i}.png')))
            report['finishUncachedMedianSeconds']=statistics.median(uncached)
            report['finishCachedMedianSeconds']=statistics.median(cached)
            report['finishSpeedup']=statistics.median(uncached)/statistics.median(cached)
            changed=copy.deepcopy(recipe);changed['grading']['balance']['exposure']=.3
            report['balanceUncachedSeconds']=still('balance-uncached',changed,False)
            report['balanceReusedEngineSeconds']=still('balance-reuse',changed,True)
            np.testing.assert_array_equal(np.asarray(Image.open(root/'balance-uncached.png')),
                                           np.asarray(Image.open(root/'balance-reuse.png')))
            count=min(args.frames,source.info['frames'])
            start=time.monotonic()
            render_clip(source,recipe,root/'prime.mp4',edge=args.edge,count=count,runtime=runtime,fingerprint='benchmark-source')
            report['primeClipSeconds']=time.monotonic()-start
            changed=copy.deepcopy(recipe);changed['grading']['finish']['contrast']=1.08
            start=time.monotonic()
            reference_clip(source,changed,root/'reference.mp4',edge=args.edge,count=count)
            report['clipUncachedSeconds']=time.monotonic()-start
            start=time.monotonic()
            info=render_clip(source,changed,root/'cached.mp4',edge=args.edge,count=count,runtime=runtime,fingerprint='benchmark-source')
            report['clipCachedSeconds']=time.monotonic()-start
            report['clipCacheHits']=info['filmCacheHits'];report['clipFrames']=info['frames']
            with av.open(str(root/'reference.mp4')) as ref,av.open(str(root/'cached.mp4')) as cached_video:
                original=list(ref.decode(video=0));actual=list(cached_video.decode(video=0))
                assert len(original)==len(actual)==count
                for a,b in zip(original,actual):np.testing.assert_array_equal(a.to_ndarray(format='rgb24'),b.to_ndarray(format='rgb24'))
            report['pixelParity']='exact'
        finally:runtime.close()
    print('BENCHMARK_RESULT '+json.dumps(report,sort_keys=True),flush=True)


if __name__=='__main__':main()

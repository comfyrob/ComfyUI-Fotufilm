"""Shared, bounded-memory preview and export pipeline: Gear → Fotufilm → Gear."""
import json
import shutil
import subprocess
import tempfile
import zipfile
import time
from fractions import Fraction
from pathlib import Path

import av
import imageio_ffmpeg
import numpy as np
import OpenEXR
import torch
import torch.nn.functional as F
from PIL import Image

from .grading import apply_grade, convert, validate_grading
from .hdr_master import PRIMARIES, read_manifest
from .native import Engine
from .recipe import render_request, validate_recipe
from .runtime_paths import stocks_path
from .preview_runtime import SourceCursor, digest, render_stats


def resize_float(rgb, edge):
    height,width=rgb.shape[:2]
    if not edge or max(width,height)<=edge: return rgb
    scale=edge/max(width,height)
    return F.interpolate(torch.from_numpy(np.ascontiguousarray(rgb)).permute(2,0,1)[None],
        size=(max(1,round(height*scale)),max(1,round(width*scale))),mode='area')[0].permute(1,2,0).numpy()


class Source:
    def __init__(self, path):
        self.path=Path(path)
        self.is_hdr=self.path.name.endswith('.ffhdr.zip')
        if self.is_hdr:
            self.info=read_manifest(self.path)
        else:
            with av.open(str(self.path)) as container:
                video=container.streams.video[0]
                if int(video.codec_context.color_trc) in (16,18):
                    raise ValueError('For HDR finishing connect the float HDR master, not an encoded HLG/PQ playback file.')
                if int(video.codec_context.color_primaries) not in (0,1,2):
                    raise ValueError('This encoded video is not tagged Rec.709. Use a float HDR master with explicit primaries.')
                fps=float(video.average_rate or video.guessed_rate or 24)
                duration=float(video.duration*video.time_base) if video.duration else float(container.duration or 0)/1e6
                self.info={'width':video.width,'height':video.height,'fps':fps,'frames':video.frames or round(duration*fps),'colorSpace':'linear-rec709'}
        self.info={**self.info,'hdr':self.is_hdr,'duration':self.info['frames']/self.info['fps']}
        if not 0<self.info['frames']<=100_000 or self.info['width']*self.info['height']>40_000_000:
            raise ValueError('Unsupported video duration or dimensions.')

    def frames(self, start=0, count=None, edge=None):
        stop=min(self.info['frames'],start+(count or self.info['frames']))
        if self.is_hdr:
            with zipfile.ZipFile(self.path) as bundle, tempfile.TemporaryDirectory(prefix='fotufilm-read-') as directory:
                frame_path=Path(directory)/'source.exr'
                for index in range(start,stop):
                    info=bundle.getinfo(f'master/{index:06d}.exr')
                    if info.file_size>512*1024**2:raise ValueError('Oversized EXR member.')
                    frame_path.write_bytes(bundle.read(info))
                    with OpenEXR.File(str(frame_path),separate_channels=True) as image:
                        rgb=np.stack([image.channels()[c].pixels for c in 'RGB'],axis=-1).astype(np.float32)
                    if rgb.shape!=(self.info['height'],self.info['width'],3) or not np.isfinite(rgb).all():
                        raise ValueError('Invalid HDR frame data.')
                    yield index,resize_float(convert(rgb,self.info['colorSpace'],'linear-rec2020'),edge)
        else:
            with av.open(str(self.path)) as container:
                stream=container.streams.video[0]
                for index,frame in enumerate(container.decode(stream)):
                    if index>=stop:break
                    if index<start:continue
                    rgb=frame.to_ndarray(format='rgb48le').astype(np.float32)/65535
                    rgb=np.where(rgb<=.04045,rgb/12.92,((rgb+.055)/1.055)**2.4)
                    yield index,resize_float(convert(rgb,'linear-rec709','linear-rec2020'),edge)

    def audio_path(self,directory):
        if not self.is_hdr:return self.path
        path=Path(directory)/self.info['playback']
        with zipfile.ZipFile(self.path) as bundle:
            info=bundle.getinfo(self.info['playback'])
            if info.file_size>2*1024**3:raise ValueError('Oversized playback member.')
            with bundle.open(info) as src,path.open('wb') as dest:shutil.copyfileobj(src,dest)
        return path


def hdr_eligible(recipe):
    data=json.loads((stocks_path()/(recipe['stock']+'.json')).read_text())
    return bool(data.get('isReversal') and not data.get('isReflectionPrint') and recipe['medium']=='screen' and recipe['digitalReference']=='reference-exposure')


class Finisher:
    def __init__(self,recipe,directory,runtime=None):
        self.recipe=validate_recipe(recipe)
        self.grading=validate_grading(self.recipe.get('grading'))
        self.runtime=runtime
        self._engine=None
        self.path=Path(directory)/'working.exr'
        self.request=render_request(self.recipe,self.recipe.get('seed') or 0,edge=None)
        self.film_signature=digest([self.request,self.grading['balance']])
        self.hdr=hdr_eligible(self.recipe)

    @property
    def engine(self):
        if self.runtime is not None:return self.runtime.engine
        if self._engine is None:self._engine=Engine()
        return self._engine

    def develop(self,rgb,index):
        rgb=apply_grade(rgb,self.grading['balance'],'linear-rec2020')
        OpenEXR.File({'chromaticities':PRIMARIES['linear-rec2020']},
            {c:np.ascontiguousarray(rgb[:,:,i]) for i,c in enumerate('RGB')}).write(str(self.path))
        self.request['edit']['seed']=((self.recipe.get('seed') or 0)+index*0x7f4a7c15)&0xffffffff
        return self.engine.render_float(str(self.path),rgb.shape[1],rgb.shape[0],self.request)

    def finish(self,rgb):
        return apply_grade(rgb,self.grading['finish'],'linear-p3')

    def frame(self,rgb,index):
        return self.finish(self.develop(rgb,index))

    def close(self):
        if self._engine is not None:self._engine.close();self._engine=None


def render_still(source,recipe,destination,before_path,index=0,edge=960,*,runtime=None,fingerprint=None,reuse_before=False):
    from .master_export import delivery
    started=time.monotonic();stats=render_stats()
    with tempfile.TemporaryDirectory(prefix='fotufilm-still-') as directory:
        finisher=Finisher(recipe,directory,runtime)
        cursor=SourceCursor(source,edge)
        try:
            before_cached=reuse_before and Path(before_path).is_file()
            if runtime is not None:
                rgb=None if before_cached else runtime.source_frame(cursor,fingerprint,index,stats)
                result=runtime.finished_frame(cursor,fingerprint,index,finisher,stats,source_rgb=rgb)
            else:
                rgb=cursor.read(index)
                result=finisher.frame(rgb,index)
            processed=time.monotonic()
            knee=.7 if finisher.hdr else 1
            # PNG compression effort changes byte size, never pixel precision.
            Image.fromarray((delivery(result,False,knee)/257).round().astype('uint8')).save(destination,compress_level=1)
            if not before_cached:
                Image.fromarray((delivery(convert(rgb,'linear-rec2020','linear-p3'),False,knee)/257).round().astype('uint8')).save(before_path,compress_level=1)
            return {'width':result.shape[1],'height':result.shape[0],'frame':index,'hdrEligible':finisher.hdr,
                    'processingSeconds':round(processed-started,4),'displaySeconds':round(time.monotonic()-processed,4),**stats}
        finally:cursor.close();finisher.close()


def render_clip(source,recipe,destination,format_id='mp4',edge=None,start=0,count=None,
                interrupt=lambda:None,progress=lambda value:None,before=False,*,runtime=None,fingerprint=None):
    steps=render_clip_steps(source,recipe,destination,format_id,edge,start,count,interrupt,progress,before,
                            runtime=runtime,fingerprint=fingerprint)
    try:
        while True:next(steps)
    except StopIteration as done:return done.value
    finally:steps.close()


def render_clip_steps(source,recipe,destination,format_id='mp4',edge=None,start=0,count=None,
                interrupt=lambda:None,progress=lambda value:None,before=False,*,runtime=None,fingerprint=None):
    from .master_export import delivery
    hdr=format_id=='hlg'
    if format_id not in ('mp4','prores422hq','hlg'):raise ValueError('Unsupported export format.')
    process=None;finisher=None;cursor=SourceCursor(source,edge);stats=render_stats()
    with tempfile.TemporaryDirectory(prefix='fotufilm-finish-') as directory:
        directory=Path(directory)
        try:
            eligible=hdr_eligible(recipe)
            if not before:finisher=Finisher(recipe,directory,runtime)
            if hdr and not eligible:raise ValueError('HDR delivery requires direct-view slide film with Reference exposure.')
            fps=Fraction(source.info['fps']).limit_denominator(100000)
            scale=min(1,(edge or max(source.info['width'],source.info['height']))/max(source.info['width'],source.info['height']))
            width,height=[max(1,round(source.info[k]*scale)) for k in ('width','height')]
            width+=width%2;height+=height%2
            total=min(count or source.info['frames'],source.info['frames']-start)
            audio=source.audio_path(directory)
            matrix='bt2020' if hdr else 'bt709'
            args=[imageio_ffmpeg.get_ffmpeg_exe(),'-hide_banner','-loglevel','error','-y',
                '-f','rawvideo','-pixel_format','rgb48le','-video_size',f'{width}x{height}','-framerate',str(fps),'-i','pipe:0',
                '-ss',str(start/float(fps)),'-i',str(audio),'-map','0:v:0','-map','1:a?',
                '-vf',f'scale=in_color_matrix={matrix}:out_color_matrix={matrix}','-c:a','aac','-af','apad','-t',str(total/float(fps))]
            if format_id=='prores422hq':args+=['-c:v','prores_ks','-profile:v','3','-pix_fmt','yuv422p10le','-bsf:v','prores_metadata=color_primaries=1:color_trc=13:colorspace=1']
            elif hdr:args+=['-c:v','libx265','-preset','fast','-crf','14','-pix_fmt','yuv420p10le','-tag:v','hvc1','-x265-params','colorprim=bt2020:transfer=arib-std-b67:colormatrix=bt2020nc:range=limited']
            else:args+=['-c:v','libx264','-preset','veryfast' if edge else 'medium','-crf','17' if edge else '16','-pix_fmt','yuv420p']
            args+=['-color_primaries','bt2020' if hdr else 'bt709','-color_trc','arib-std-b67' if hdr else 'iec61966-2-1',
                '-colorspace','bt2020nc' if hdr else 'bt709','-movflags','+faststart+write_colr',str(destination)]
            with (directory/'encode.log').open('w+b') as log:
                process=subprocess.Popen(args,stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=log)
                rendered=0
                for index in range(start,start+total):
                    interrupt()
                    if runtime is not None:
                        output=(convert(runtime.source_frame(cursor,fingerprint,index,stats),'linear-rec2020','linear-p3') if before
                                else runtime.finished_frame(cursor,fingerprint,index,finisher,stats))
                    else:
                        rgb=cursor.read(index)
                        output=convert(rgb,'linear-rec2020','linear-p3') if before else finisher.frame(rgb,index)
                    if not np.isfinite(output).all():raise ValueError('Non-finite rendered pixels.')
                    output=np.pad(output,((0,height-output.shape[0]),(0,width-output.shape[1]),(0,0)),mode='edge')
                    process.stdin.write(delivery(output,hdr,.7 if eligible else 1).tobytes())
                    rendered+=1;progress(rendered/total)
                    yield
                process.stdin.close()
                deadline=time.monotonic()+300
                while process.poll() is None:
                    interrupt()
                    if time.monotonic()>deadline:raise TimeoutError('Video encoding timed out.')
                    time.sleep(.01)
                    yield
                if process.returncode:
                    log.seek(0);raise RuntimeError('Encoding failed: '+log.read(1000).decode(errors='replace'))
                if rendered!=total:raise ValueError('Source ended before its reported frame count.')
            Path(destination).with_suffix('.recipe.json').write_text(json.dumps(recipe,indent=2))
            return {'frames':rendered,'fps':float(fps),'width':width,'height':height,'start':start/float(fps),'hdrEligible':eligible,**stats}
        except BaseException:
            if process and process.poll() is None:process.kill();process.wait()
            Path(destination).unlink(missing_ok=True)
            raise
        finally:
            cursor.close()
            if finisher:finisher.close()

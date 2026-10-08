"""Same-origin ComfyUI preview jobs. No workflow submission or model inference.

Only existing Comfy input/output assets can be registered. Processing is
serialized and preemptible between frames; a newer editor request supersedes
its previous work. Cache files are bounded and live in Comfy's temp directory.
"""
import asyncio
import atexit
import hashlib
import json
import threading
import time
import uuid
from collections import OrderedDict
from pathlib import Path

import folder_paths
from aiohttp import web

from .finish_pipeline import Source, hdr_eligible, render_clip_steps, render_still
from .preview_runtime import PreviewRuntime
from .preview_scheduler import PreviewScheduler
from .recipe import validate_recipe

ASSETS=OrderedDict()
JOBS=OrderedDict()
CLIENTS={}
LOCK=threading.RLock()
LIMIT=2*1024**3
PIPELINE_SIGNATURE=hashlib.sha256(b''.join((Path(__file__).parent/name).read_bytes() for name in ('finish_pipeline.py','preview_runtime.py','grading.py','master_export.py','native.py','recipe.py','vendor/gear_grading.py'))).hexdigest()
RUNTIME=None


def preview_runtime():
    global RUNTIME
    if RUNTIME is None:RUNTIME=PreviewRuntime(cache_root()/'float-frames',PIPELINE_SIGNATURE)
    return RUNTIME


def close_runtime():
    global RUNTIME
    if RUNTIME is not None:RUNTIME.close();RUNTIME=None


EXECUTOR=PreviewScheduler(cleanup=close_runtime)
atexit.register(EXECUTOR.shutdown,wait=False)


def descriptor(path):
    path=Path(path).resolve()
    for kind,getter in [('input',folder_paths.get_input_directory),('output',folder_paths.get_output_directory),('temp',folder_paths.get_temp_directory)]:
        root=Path(getter()).resolve()
        if path.is_relative_to(root):
            relative=path.relative_to(root)
            return {'filename':relative.name,'subfolder':str(relative.parent) if relative.parent!=Path('.') else '', 'type':kind}
    raise ValueError('Asset must be in a Comfy input, output or temp directory.')


def resolve_file(value):
    if not isinstance(value,dict):raise ValueError('Expected a Comfy file descriptor.')
    getters={'input':folder_paths.get_input_directory,'output':folder_paths.get_output_directory,'temp':folder_paths.get_temp_directory}
    if value.get('type') not in getters:raise ValueError('Invalid asset directory.')
    root=Path(getters[value['type']]()).resolve()
    filename=value.get('filename','');subfolder=value.get('subfolder','')
    if not isinstance(filename,str) or not isinstance(subfolder,str):raise ValueError('Invalid filename.')
    path=(root/subfolder/filename).resolve()
    if not path.is_relative_to(root) or not path.is_file():raise ValueError('Asset unavailable or outside Comfy directories.')
    if not (path.name.endswith('.ffhdr.zip') or path.suffix.lower() in ('.mp4','.mov','.webm','.m4v')):raise ValueError('Unsupported video asset.')
    return path


def register_file(value):
    path=resolve_file(value)
    stat=path.stat()
    fingerprint=hashlib.sha256(f'{path}:{stat.st_size}:{stat.st_mtime_ns}'.encode()).hexdigest()
    with LOCK:
        for token,asset in ASSETS.items():
            if asset['fingerprint']==fingerprint:
                ASSETS.move_to_end(token)
                return {'asset':token,'info':asset['source'].info,'playback':asset.get('playback')}
    source=Source(path);token=uuid.uuid4().hex
    playback=None
    if source.is_hdr:
        import zipfile,shutil
        target=cache_root()/(fingerprint+'-source'+Path(source.info['playback']).suffix)
        if not target.is_file():
            with zipfile.ZipFile(path) as bundle:
                member=bundle.getinfo(source.info['playback'])
                if member.file_size>2*1024**3:raise ValueError('Oversized playback member.')
                with bundle.open(member) as src,target.open('wb') as dest:shutil.copyfileobj(src,dest)
        playback=descriptor(target)
    with LOCK:
        ASSETS[token]={'source':source,'fingerprint':fingerprint,'playback':playback}
        while len(ASSETS)>64:ASSETS.popitem(last=False)
    return {'asset':token,'info':source.info,'playback':playback}


def cache_root():
    root=Path(folder_paths.get_temp_directory())/'fotufilm-studio'
    root.mkdir(parents=True,exist_ok=True)
    return root


def prune_cache(protect=()):
    protect=set(protect)
    for job in list(JOBS.values()):protect.update(job.get('_paths',()))
    files=sorted(cache_root().glob('*'),key=lambda p:p.stat().st_mtime)
    size=sum(p.stat().st_size for p in files if p.is_file())
    for path in files:
        if size<=LIMIT:break
        if str(path) not in protect and path.is_file():
            length=path.stat().st_size;path.unlink(missing_ok=True);size-=length


def execute_job(job,asset,recipe,mode,edge,index,format_id):
    steps=execute_job_steps(job,asset,recipe,mode,edge,index,format_id)
    try:
        while True:next(steps)
    except StopIteration:pass
    finally:steps.close()


def execute_job_steps(job,asset,recipe,mode,edge,index,format_id):
    def interrupt():
        if job['cancel'].is_set():raise InterruptedError('Superseded or cancelled.')
    def progress(value):job['progress']=value
    try:
        interrupt();job['status']='running';started=time.monotonic()
        job['queueSeconds']=round(started-job.get('submitted',started),3)
        source=asset['source'];root=cache_root()
        key=hashlib.sha256(json.dumps([PIPELINE_SIGNATURE,asset['fingerprint'],recipe,mode,edge,index if mode=='frame' else 0,format_id],sort_keys=True).encode()).hexdigest()
        extension='.png' if mode=='frame' else '.mov' if format_id=='prores422hq' else '.mp4'
        destination=root/(key+extension)
        before_path=root/(key+'-before'+extension)
        if mode=='frame':
            before_key=hashlib.sha256(json.dumps([PIPELINE_SIGNATURE,asset['fingerprint'],edge,index,hdr_eligible(recipe),'before-frame']).encode()).hexdigest()
            before_path=root/(before_key+'.png')
        if mode=='export':destination=Path(folder_paths.get_output_directory())/f'fotufilm-{uuid.uuid4().hex}{extension}'
        job['_paths']={str(destination),str(before_path)}
        runtime=preview_runtime()
        scale=min(1,edge/max(source.info['width'],source.info['height'])) if mode!='export' else 1
        width,height=[max(1,round(source.info[k]*scale)) for k in ('width','height')]
        if mode!='frame':width+=width%2;height+=height%2
        info={'cached':destination.is_file(),'width':width,'height':height}
        if mode=='frame':
            if not destination.is_file() or not before_path.is_file():
                info.update(render_still(source,recipe,destination,before_path,index,edge,
                                         runtime=runtime,fingerprint=asset['fingerprint'],reuse_before=True))
            interrupt()
            result={'after':descriptor(destination),'before':descriptor(before_path),'frame':index}
        else:
            # Bounded automatic playback previews; exports retain the complete source.
            count=min(source.info['frames'],max(1,round(source.info['fps']*20))) if mode=='clip' else None
            if not destination.is_file():
                info.update((yield from render_clip_steps(source,recipe,destination,format_id,edge if mode=='clip' else None,
                    count=count,interrupt=interrupt,progress=progress,runtime=runtime,fingerprint=asset['fingerprint'])))
            interrupt()
            result={'after':descriptor(destination),'frames':count or source.info['frames'],'fps':source.info['fps']}
            if mode=='clip':
                # Film eligibility determines only the terminal SDR shoulder.
                before_key=hashlib.sha256(json.dumps([PIPELINE_SIGNATURE,asset['fingerprint'],edge,recipe['stock'],recipe['medium'],recipe['digitalReference'],'before']).encode()).hexdigest()
                before_path=root/(before_key+'.mp4')
                job['_paths'].add(str(before_path))
                if not before_path.is_file():
                    yield from render_clip_steps(source,recipe,before_path,'mp4',edge,count=count,before=True,interrupt=interrupt,
                                                  runtime=runtime,fingerprint=asset['fingerprint'])
                result['before']=descriptor(before_path)
        interrupt()
        result.update(info,seconds=round(time.monotonic()-started,3),queueSeconds=job['queueSeconds'],recipe=recipe,source=source.info,mode=mode)
        job.update(status='complete',result=result,progress=1)
        prune_cache({str(destination),str(before_path)})
    except InterruptedError:job['status']='cancelled'
    except Exception as error:job.update(status='error',error=str(error))
    finally:
        job.pop('_paths',None)
        job['finished']=time.monotonic()


def cancel_job(job):
    job['cancel'].set()
    future=job.get('future')
    if future and future.cancel():job.update(status='cancelled',finished=time.monotonic())


async def body(request):
    if request.content_length and request.content_length>65536:raise ValueError('Request too large.')
    value=await request.json()
    if not isinstance(value,dict):raise ValueError('Expected an object.')
    return value


def install_routes():
    from server import PromptServer
    routes=PromptServer.instance.routes
    @routes.post('/fotufilm/source')
    async def source(request):
        try:return web.json_response(await asyncio.to_thread(register_file,await body(request)))
        except (ValueError,KeyError,OSError) as error:return web.json_response({'error':str(error)},status=400)

    @routes.post('/fotufilm/preview')
    async def preview(request):
        try:
            value=await body(request)
            asset=ASSETS.get(value.get('asset'))
            if not asset:raise ValueError('Source expired; reconnect the video.')
            recipe=validate_recipe(value.get('recipe'))
            mode=value.get('mode','frame');edge=value.get('edge',960);index=value.get('frame',0)
            if mode not in ('frame','clip','export'):raise ValueError('Invalid preview mode.')
            if type(edge) is not int or not 128<=edge<=1920:raise ValueError('Preview size must be 128–1920 pixels.')
            if type(index) is not int or not 0<=index<asset['source'].info['frames']:raise ValueError('Invalid frame number.')
            format_id=value.get('format','mp4') if mode=='export' else 'mp4'
            if format_id not in ('mp4','prores422hq','hlg'):raise ValueError('Unsupported export format.')
            client=value.get('client')
            if not isinstance(client,str) or not 1<=len(client)<=128:raise ValueError('Invalid editor session.')
            with LOCK:
                previous=JOBS.get(CLIENTS.get(client))
                if previous and mode!='export':cancel_job(previous)
                if sum(j['status'] in ('queued','running') and not j['cancel'].is_set() for j in JOBS.values())>=8:
                    raise ValueError('Preview queue is busy. Try again shortly.')
                job={'id':uuid.uuid4().hex,'status':'queued','progress':0,'cancel':threading.Event(),'submitted':time.monotonic()}
                JOBS[job['id']]=job
                if mode!='export':CLIENTS[client]=job['id']
                for old in list(JOBS):
                    if len(JOBS)<=128:break
                    if JOBS[old]['status'] not in ('queued','running'):JOBS.pop(old)
                while len(CLIENTS)>128:CLIENTS.pop(next(iter(CLIENTS)))
                priority=(30 if value.get('channel')=='looks' else 0) if mode=='frame' else 10 if mode=='clip' else 20
                job['future']=EXECUTOR.submit(priority,execute_job_steps,job,asset,recipe,mode,edge,index,format_id)
            return web.json_response({'job':job['id']})
        except (ValueError,KeyError,TypeError) as error:return web.json_response({'error':str(error)},status=400)

    @routes.get('/fotufilm/jobs/{id}')
    async def status(request):
        job=JOBS.get(request.match_info['id'])
        if not job:return web.json_response({'error':'Preview job expired.'},status=404)
        return web.json_response({k:v for k,v in job.items() if k not in ('cancel','finished','future','submitted','_paths')})

    @routes.post('/fotufilm/jobs/{id}/cancel')
    async def cancel(request):
        job=JOBS.get(request.match_info['id'])
        if job:cancel_job(job)
        return web.json_response({'cancelled':bool(job)})

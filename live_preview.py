"""Bounded, continuous preview frames. No clip export, temp images or job polling.

Processing stays float32 through Gear and Fotufilm. H.264 is only the terminal
SDR monitor transport; exports and EXR inspection never consume these pixels.
"""
import asyncio
import copy
import json
import io
import math
import struct
import tempfile
import time
from fractions import Fraction

import av
import numpy as np
import torch
from aiohttp import web
from PIL import Image

from .finish_pipeline import Finisher
from .grading import apply_grade
from .preview_runtime import PrefetchCursor, digest, render_stats
from .recipe import validate_recipe


def display_rgb(rgb, knee, grade=None, source_space='linear-p3', exposure=0):
    from .display_transform import encode_sdr
    with torch.inference_mode():
        light = torch.tensor(rgb, device='cuda', dtype=torch.float32) if torch.cuda.is_available() else rgb
        if grade is not None: light=apply_grade(light,grade,source_space)
        encoded=encode_sdr(light,source_space,knee,exposure)
        if isinstance(encoded,torch.Tensor): return (encoded*255).round().byte().cpu().numpy()
        return np.rint(encoded*255).astype('uint8')


class MonitorEncoder:
    def __init__(self, width, height, fps):
        self.size = (width, height)
        self.pts = 0
        errors = []
        for name in ('h264_nvenc', 'libx264'):
            try:
                codec = av.CodecContext.create(name, 'w')
                codec.width, codec.height = width, height
                codec.pix_fmt = 'yuv420p'
                codec.time_base = Fraction(1, 1_000_000)
                codec.framerate = Fraction(fps).limit_denominator(100_000)
                codec.max_b_frames = 0
                codec.color_primaries = 1
                codec.color_trc = 13
                codec.colorspace = 1
                codec.color_range = 1
                codec.gop_size = max(1, round(fps))
                codec.options = ({'preset':'p1','tune':'ull','rc':'constqp','qp':'16','delay':'0',
                                  'forced-idr':'1','profile':'baseline'} if name=='h264_nvenc' else
                                 {'preset':'ultrafast','tune':'zerolatency','crf':'16','profile':'baseline',
                                  'x264-params':'repeat-headers=1:scenecut=0'})
                codec.open()
                self.codec, self.name = codec, name
                break
            except (av.FFmpegError, ValueError) as error:
                errors.append(str(error))
        else:
            raise RuntimeError('No low-latency monitor encoder available: '+'; '.join(errors))

    def encode(self, rgb, keyframe=False):
        frame = av.VideoFrame.from_ndarray(rgb, format='rgb24')
        frame = frame.reformat(format='yuv420p', src_colorspace='ITU709', dst_colorspace='ITU709')
        frame.color_primaries, frame.color_trc, frame.colorspace, frame.color_range = 1, 13, 1, 1
        self.pts += 1
        frame.pts = self.pts
        frame.time_base = self.codec.time_base
        if keyframe:
            frame.pict_type = av.video.frame.PictureType.I
        packets = self.codec.encode(frame)
        if len(packets) != 1:
            raise RuntimeError('Monitor encoder buffered a frame; zero-delay mode is required.')
        return bytes(packets[0]), packets[0].is_keyframe, self.pts


class LiveRenderer:
    def __init__(self, asset, edge, runtime):
        self.asset, self.runtime, self.edge = asset, runtime, edge
        self.cursor = PrefetchCursor(asset['source'], edge)
        self.directory = tempfile.TemporaryDirectory(prefix='fotufilm-live-')
        self.finisher, self.recipe = None, None
        self.encoder = None
        self.force_keyframe = False

    def render(self, recipe, index, compare, revision, still=False, queue_ms=0, setup_ms=0, view=None):
        started = time.perf_counter()
        if recipe != self.recipe:
            if self.finisher: self.finisher.close()
            self.finisher = Finisher(recipe, self.directory.name, self.runtime)
            self.recipe = copy.deepcopy(recipe)
        from .display_transform import validate_view, view_knee
        view=validate_view(view)
        stats = render_stats()
        rgb = self.runtime.source_frame(self.cursor, self.asset['fingerprint'], index, stats)
        decoded = time.perf_counter()
        key = digest([self.runtime.key(self.cursor.source, self.asset['fingerprint'], index, self.edge),
                      self.finisher.film_signature])
        needs_film=view['stage']!='source' or (compare and view['comparison']=='film')
        developed = self.runtime.film_cache.get(key) if needs_film else None
        if needs_film and developed is None:
            developed = self.finisher.develop(rgb, index)
            self.runtime.film_cache.put(key, developed, take_ownership=True)
        filmed = time.perf_counter()
        knee=view_knee(view,recipe,self.finisher.hdr)
        stage=view['stage']
        after = display_rgb(rgb if stage=='source' else developed, knee,
                            self.finisher.grading['finish'] if stage=='finish' else None,
                            source_space='linear-rec2020' if stage=='source' else 'linear-p3', exposure=view['exposure'])
        finished = time.perf_counter()
        h, w = after.shape[:2]
        # Both halves always come from this same frame, source and recipe.
        if compare:
            before = display_rgb(developed if view['comparison']=='film' else rgb, knee, source_space='linear-p3' if view['comparison']=='film' else 'linear-rec2020', exposure=view['exposure'])
            after = np.concatenate((after, before), axis=1)
        after = np.pad(after, ((0,h%2),(0,after.shape[1]%2),(0,0)), mode='edge')
        displayed = time.perf_counter()
        size = (after.shape[1], after.shape[0])
        reset = self.encoder is None or self.encoder.size != size
        if still:
            output = io.BytesIO()
            Image.fromarray(after).save(output, format='PNG', compress_level=1)
            data, keyframe, stamp = output.getvalue(), True, 0
        else:
            if reset: self.encoder = MonitorEncoder(*size, self.cursor.source.info['fps'])
            data, keyframe, stamp = self.encoder.encode(after, keyframe=reset or self.force_keyframe)
            self.force_keyframe = False
        end = time.perf_counter()
        meta = dict(revision=revision, frame=index, timestamp=stamp, key=keyframe, reset=reset,
                    width=w, height=h, codedWidth=size[0], codedHeight=size[1], compare=compare,
                    view=view, colorSpace=self.cursor.source.info.get('colorSpace'), display='sRGB / SDR', encoder='png' if still else self.encoder.name, memoryInput=bool(self.runtime._engine is not None and self.runtime._engine.memory_input is not None),
                    ms=dict(queue=round(queue_ms,2), setup=round(setup_ms,2), source=round((decoded-started)*1000,2), film=round((filmed-decoded)*1000,2),
                            grade=round((finished-filmed)*1000,2), display=round((displayed-finished)*1000,2),
                            encode=round((end-displayed)*1000,2), total=round((end-started)*1000,2)))
        header = json.dumps(meta, separators=(',',':')).encode()
        return struct.pack('!I',len(header))+header+data

    def close(self):
        self.cursor.close()
        if self.finisher: self.finisher.close()
        self.encoder = None
        self.directory.cleanup()


async def stream(request, assets, executor, runtime_factory):
    """Latest controls, with a bounded acknowledgement window sized for the RTT."""
    ws = web.WebSocketResponse(compress=False, max_msg_size=65536, heartbeat=20)
    await ws.prepare(request)
    await ws.send_json({"capabilities":["gesture-h264","revision-timing"]})
    state = None
    wake = asyncio.Event()
    pending = {}
    window = 8
    round_trip = None
    renderer = None
    sequence = 0
    stopped = False

    def work(snapshot, index, submitted):
        nonlocal renderer
        begun=time.perf_counter()
        identity = (snapshot['asset'], snapshot['edge'])
        if renderer is None or getattr(renderer,'identity',None) != identity:
            if renderer: renderer.close()
            renderer = LiveRenderer(snapshot['_asset'], snapshot['edge'], runtime_factory())
            renderer.identity = identity
        result = renderer.render(snapshot['recipe'], index, snapshot['compare'], snapshot['revision'], still=not (snapshot['playing'] or snapshot['interacting']),
            queue_ms=(begun-submitted)*1000,setup_ms=(time.perf_counter()-begun)*1000,view=snapshot['view'])
        return result
        yield

    async def send_frames():
        nonlocal sequence, state
        last_revision = -1
        index = 0
        due = time.monotonic()
        while not stopped:
            if state is None or len(pending)>=window or (not state['playing'] and state['revision']==last_revision):
                wake.clear()
                await wake.wait()
                continue
            snapshot = dict(state)
            if snapshot['revision'] != last_revision:
                index = snapshot['frame']
                due = time.monotonic()
            remaining = due-time.monotonic()
            if remaining>0:
                wake.clear()
                try: await asyncio.wait_for(wake.wait(), remaining)
                except asyncio.TimeoutError: pass
                if state['revision'] != snapshot['revision']: continue
            if snapshot['revision'] != last_revision:
                await ws.send_json({'phase':'preparing' if renderer is None else 'rendering','revision':snapshot['revision']})
            packet = await asyncio.wrap_future(executor.submit(0, work, snapshot, index, time.perf_counter()))
            if stopped: break
            # Drop obsolete *control revisions*, never silently skip source frames
            # to claim a frame rate the engine did not actually deliver.
            if state['revision'] != snapshot['revision']:
                # Keep the encoder warm. Recreating NVENC here costs hundreds of
                # milliseconds; an IDR restores dependencies after the dropped packet.
                renderer.force_keyframe = True
                continue
            sequence += 1
            pending[sequence] = time.monotonic()
            await ws.send_bytes(struct.pack('!I',sequence)+packet)
            last_revision = snapshot['revision']
            index += 1
            if index >= snapshot['_asset']['source'].info['frames']:
                if snapshot['loop']: index = 0
                else:
                    state = {**state,'playing':False}
                    await ws.send_json({'ended':True,'revision':snapshot['revision']})
            due = max(due+1/(snapshot['_asset']['source'].info['fps']*snapshot['rate']), time.monotonic())

    task = asyncio.create_task(send_frames())
    async def report_failure():
        if task.cancelled() or ws.closed: return
        error = task.exception()
        if error:
            await ws.send_json({'error':str(error)})
            await ws.close()
    task.add_done_callback(lambda _: asyncio.create_task(report_failure()))
    try:
        async for message in ws:
            if message.type != web.WSMsgType.TEXT: break
            value = json.loads(message.data)
            if 'ack' in value:
                sent = pending.pop(value['ack'], None)
                if sent is not None:
                    elapsed = time.monotonic()-sent
                    round_trip = elapsed if round_trip is None else .8*round_trip+.2*elapsed
                    fps = state['_asset']['source'].info['fps']*state['rate'] if state else 24
                    window = max(3, min(12, math.ceil(round_trip*fps)+2))
                wake.set(); continue
            asset = assets.get(value.get('asset'))
            if not asset: raise ValueError('Preview source expired. Reconnect or run Studio once.')
            frame, edge, revision = value.get('frame',0), value.get('edge',1280), value.get('revision')
            if type(frame) is not int or not 0<=frame<asset['source'].info['frames']: raise ValueError('Invalid frame.')
            if type(edge) is not int or not 128<=edge<=1920: raise ValueError('Invalid preview resolution.')
            if type(revision) is not int or revision<0: raise ValueError('Invalid control revision.')
            if state and revision<=state['revision']: continue
            rate = value.get('rate',1)
            if rate not in (.5,1,1.5,2): raise ValueError('Invalid playback rate.')
            from .display_transform import validate_view
            state = dict(view=validate_view(value.get('view')),asset=value['asset'], _asset=asset, recipe=validate_recipe(value.get('recipe')),
                         frame=frame,edge=edge,revision=revision,playing=value.get('playing') is True,interacting=value.get('interacting') is True,
                         compare=value.get('compare') is True,loop=value.get('loop') is not False,rate=rate)
            wake.set()
            if task.done(): task.result()
    except (ValueError,KeyError,TypeError) as error:
        await ws.send_json({'error':str(error)})
    finally:
        stopped = True
        wake.set()
        # Let any native call finish on its owning worker before closing resources.
        try: await task
        except Exception as error:
            if not ws.closed: await ws.send_json({'error':str(error)})
        if renderer:
            def cleanup():
                renderer.close()
                if False: yield
            await asyncio.wrap_future(executor.submit(0,cleanup))
        await ws.close()
    return ws

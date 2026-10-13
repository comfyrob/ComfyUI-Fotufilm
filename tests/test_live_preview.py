import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import torch

ROOT=Path(__file__).resolve().parents[1]
p=types.ModuleType('film_finish');p.__path__=[str(ROOT)];sys.modules.setdefault('film_finish',p)


class DirectSourceTests(unittest.TestCase):
    def test_direct_frames_keep_negative_and_hdr_values_and_do_not_mutate_input(self):
        from film_finish.tensor_source import TensorSource
        images=torch.tensor([-.125,.18,8.]).expand(3,4,6,3).clone()
        source=TensorSource(images,24,'linear-rec2020',ROOT/'tests/codec-smoke.mp4')
        self.assertEqual(source.images.data_ptr(),images.data_ptr())
        frames=list(source.frames(start=1,count=2))
        self.assertEqual([i for i,_ in frames],[1,2])
        np.testing.assert_array_equal(frames[0][1],images[1].numpy())
        frames[0][1][:]=0
        self.assertEqual(float(images[1,0,0,2]),8.)
        self.assertTrue(source.info['direct'])
        self.assertEqual(source.info['duration'],3/24)

    def test_studio_registers_hdr_without_creating_archive(self):
        import folder_paths
        from comfy_api.latest import InputImpl
        from film_finish.preview_node import FotufilmStudio,DEFAULT_RECIPE
        from film_finish.studio_server import ASSETS
        from film_finish.hdr_nodes import FilmFinishSaveHDRMaster
        with tempfile.TemporaryDirectory() as directory, patch.object(folder_paths,'get_temp_directory',return_value=directory):
            video=InputImpl.VideoFromFile(str(ROOT/'tests/codec-smoke.mp4'))
            images=torch.full((2,4,6,3),4.)
            output=FotufilmStudio.execute(video,DEFAULT_RECIPE,24,images=images,input_color_space='linear-rec2020')
            direct=output.ui['fotufilm_studio'][0]['direct']
            self.assertEqual(ASSETS[direct['asset']]['source'].images.data_ptr(),images.data_ptr())
            self.assertFalse(list(Path(directory).rglob('*.zip')))
            with patch('film_finish.hdr_master.write_master',side_effect=AssertionError('Unwanted save')):
                saved=FilmFinishSaveHDRMaster.execute(images,video,24,'linear-rec2020','master',enabled=False)
            self.assertIsNone(saved.result[0])
            ASSETS.pop(direct['asset'])


class StreamTests(unittest.TestCase):
    def test_monitor_encoder_emits_every_frame_without_buffering_and_decodes(self):
        import av
        from film_finish.live_preview import MonitorEncoder
        encoder=MonitorEncoder(128,72,24)
        decoder=av.CodecContext.create('h264','r')
        decoded=[]
        for index in range(12):
            data,key,pts=encoder.encode(np.full((72,128,3),index*15,np.uint8),keyframe=index==0)
            if index==0:self.assertTrue(key)
            self.assertEqual(pts,index+1)
            decoded.extend(decoder.decode(av.Packet(data)))
        decoded.extend(decoder.decode(None))
        self.assertEqual(len(decoded),12)
        levels=[frame.to_ndarray(format='rgb24').mean() for frame in decoded]
        self.assertTrue(all(a<b for a,b in zip(levels,levels[1:])))

    def test_keyframe_after_obsolete_frame_keeps_encoder_and_decodes(self):
        import av
        from film_finish.live_preview import MonitorEncoder
        encoder=MonitorEncoder(128,72,24)
        decoder=av.CodecContext.create('h264','r')
        first,_,_=encoder.encode(np.zeros((72,128,3),np.uint8),keyframe=True)
        self.assertEqual(len(decoder.decode(av.Packet(first))),1)
        encoder.encode(np.full((72,128,3),80,np.uint8))  # Obsolete control revision.
        latest,key,pts=encoder.encode(np.full((72,128,3),160,np.uint8),keyframe=True)
        self.assertTrue(key);self.assertEqual(pts,3)
        decoded=decoder.decode(av.Packet(latest))
        self.assertEqual(len(decoded),1)
        self.assertGreater(decoded[0].to_ndarray(format='rgb24').mean(),150)

    def test_display_stage_matches_existing_sdr_delivery(self):
        from film_finish.live_preview import display_rgb
        from film_finish.master_export import delivery
        rgb=np.random.default_rng(12).uniform(-.2,4,(12,16,3)).astype(np.float32)
        for knee in (.7,1):
            expected=(delivery(rgb,False,knee)/257).round().astype('uint8')
            with patch('torch.cuda.is_available',return_value=False):
                np.testing.assert_array_equal(display_rgb(rgb,knee),expected)

class NativeMemoryTests(unittest.TestCase):
    def test_memory_input_matches_legacy_exr_for_half_representable_hdr(self):
        from film_finish.native import Engine
        from film_finish.recipe import render_request
        from film_finish.hdr_master import PRIMARIES
        import OpenEXR
        engine=Engine()
        if engine.memory_input is None:
            engine.close();self.skipTest('Upstream runtime without memory ABI')
        # Upstream DecodeEXR.cpp uses Imf::Rgba (half), even for FLOAT files.
        # Compare representable inputs so this checks film/primaries parity,
        # not the old decoder's quantization. Memory input stays float32.
        rgb=np.random.default_rng(12).uniform(-.05,6,(48,64,3)).astype(np.float16).astype(np.float32)
        recipe=json.loads((ROOT/'examples/vision250d-clean.recipe.json').read_text())
        request=render_request(recipe,12,edge=None)
        try:
            with tempfile.TemporaryDirectory() as directory:
                path=Path(directory)/'input.exr'
                OpenEXR.File({'chromaticities':PRIMARIES['linear-rec2020']},
                    {c:np.ascontiguousarray(rgb[...,i]) for i,c in enumerate('RGB')}).write(str(path))
                np.testing.assert_allclose(engine.render_rgb(rgb,request),
                    engine.render_float(path,64,48,request),rtol=2e-5,atol=2e-5)
        finally:engine.close()

    @unittest.skipUnless(torch.cuda.is_available(),'CUDA parity test')
    def test_cuda_grade_preserves_cpu_math(self):
        from film_finish.grading import apply_grade,apply_grade_accelerated,validate_grading
        rgb=np.random.default_rng(22).uniform(-.02,4,(32,48,3)).astype(np.float32)
        grade=validate_grading({'finish':{'exposure':.3,'temperature':.1,'contrast':1.2,'saturation':.8}})['finish']
        np.testing.assert_allclose(apply_grade_accelerated(rgb,grade,'linear-p3'),
                                   apply_grade(rgb,grade,'linear-p3'),rtol=2e-5,atol=2e-5)

class PrefetchTests(unittest.TestCase):
    def test_sequential_play_seek_and_loop_preserve_frame_order(self):
        from film_finish.preview_runtime import PrefetchCursor
        class Source:
            info={'frames':8}
            def frames(self,start=0,edge=None):
                for i in range(start,8):yield i,np.full((2,2,3),i,np.float32)
        cursor=PrefetchCursor(Source(),1280)
        try:
            for index in (0,1,2,6,7,0,4,3):
                np.testing.assert_array_equal(cursor.read(index),np.full((2,2,3),index,np.float32))
        finally:cursor.close()

if __name__=='__main__':unittest.main()

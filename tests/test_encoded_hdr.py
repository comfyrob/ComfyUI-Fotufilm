"""CPU regression coverage for HDR MP4s, independent of the native film library."""
import sys
import types
import tempfile
import subprocess
import unittest
from pathlib import Path

import av
import imageio_ffmpeg
import numpy as np
import torch

APP = Path(__file__).resolve().parents[1]
package = types.ModuleType('film_finish'); package.__path__ = [str(APP)]
sys.modules.setdefault('film_finish', package)
from film_finish.encoded_hdr import linearize_hdr, linearize_hdr_tensor, decode_rgb, processing_rgb, playback_proxy
from film_finish.finish_pipeline import Source


class EncodedHDRTests(unittest.TestCase):
    def test_tensor_transfer_matches_float32_reference_for_colored_highlights(self):
        codes = np.random.default_rng(51).uniform(0, 1, (18, 32, 3)).astype(np.float32)
        codes[0, :3] = [[0, 0, 0], [.75, .75, .75], [1, 1, 1]]
        for transfer in (16, 18):
            with self.subTest(transfer=transfer):
                result = linearize_hdr_tensor(torch.from_numpy(codes), transfer).numpy()
                self.assertEqual(result.dtype, np.float32)
                np.testing.assert_allclose(result, linearize_hdr(codes, transfer), rtol=1e-4, atol=2e-5)

    @unittest.skipUnless(torch.cuda.is_available(), 'CUDA HDR decode parity')
    def test_cuda_processing_preserves_full_and_resized_hdr_pixels(self):
        from film_finish.finish_pipeline import resize_float
        codes = np.random.default_rng(37).integers(0, 65536, (36, 64, 3), dtype=np.uint16)
        frame = av.VideoFrame.from_ndarray(codes, format='rgb48le')
        for transfer in (16, 18):
            for edge in (None, 32, 19):
                with self.subTest(transfer=transfer, edge=edge):
                    reference = resize_float(decode_rgb(frame, transfer), edge)
                    actual = processing_rgb(frame, transfer, edge)
                    self.assertEqual(actual.dtype, np.float32)
                    self.assertEqual(actual.shape, reference.shape)
                    self.assertGreater(actual.max(), 1)
                    np.testing.assert_allclose(actual, reference, rtol=1e-4, atol=2e-5)

    def test_reference_white_and_headroom(self):
        hlg = np.array([[[0, 0, 0], [.75, .75, .75], [1, 1, 1]]], np.float32)
        decoded = linearize_hdr(hlg, 18)
        self.assertEqual(decoded.dtype, np.float32)
        np.testing.assert_allclose(decoded[0, 0], 0, atol=1e-7)
        np.testing.assert_allclose(decoded[0, 1], 1, atol=1e-6)
        np.testing.assert_allclose(decoded[0, 2], 4.9261, rtol=1e-3)
        # Independently published PQ code values for 100 and 1000 cd/m².
        pq = linearize_hdr(np.array([.50807842, .7518271, 1], np.float32), 16)
        np.testing.assert_allclose(pq, np.array([100, 1000, 10000]) / 203, rtol=2e-4)
        self.assertEqual(pq.dtype, np.float32)

    @staticmethod
    def movie(path, transfer, primaries='bt2020'):
        # Frame-varying neutral 10-bit YUV fixture, with B frames and audio.
        rgb = np.stack([np.full((32, 64, 3), round(v * 65535), '<u2')
                        for v in (.5, .75, 1, .6, .8, .4)])
        command = [imageio_ffmpeg.get_ffmpeg_exe(), '-v', 'error', '-y',
                   '-f', 'rawvideo', '-pixel_format', 'rgb48le', '-video_size', '64x32',
                   '-framerate', '48', '-i', 'pipe:0', '-f', 'lavfi', '-i', 'sine=frequency=440',
                   '-t', str(6 / 48), '-c:v', 'libx264', '-crf', '0', '-pix_fmt', 'yuv420p10le',
                   '-vf', 'scale=in_color_matrix=bt2020:out_color_matrix=bt2020',
                   '-color_trc', transfer, '-color_primaries', primaries, '-colorspace', 'bt2020nc',
                   '-x264-params', f'colorprim={primaries}:transfer={transfer}:colormatrix=bt2020nc',
                   '-bsf:v', f'h264_metadata=colour_primaries={9 if primaries=="bt2020" else 1}:transfer_characteristics={18 if transfer=="arib-std-b67" else 16}:matrix_coefficients=9',
                   '-movflags', '+write_colr', '-c:a', 'aac', str(path)]
        subprocess.run(command, input=rgb.tobytes(), check=True, capture_output=True)
        from film_finish.video_delivery import repair_h264_color
        repair_h264_color(path,9 if primaries=='bt2020' else 1,18 if transfer=='arib-std-b67' else 16,9)

    def test_hlg_and_pq_files_keep_float_range_timing_and_audio(self):
        for transfer in ('arib-std-b67', 'smpte2084'):
            with self.subTest(transfer=transfer), tempfile.TemporaryDirectory() as directory:
                root = Path(directory); path = root / 'input.mp4'
                self.movie(path, transfer)
                source = Source(path)
                self.assertTrue(source.is_hdr); self.assertFalse(source.is_archive)
                self.assertEqual(source.info['fps'], 48)
                self.assertEqual(source.info['frames'], 6)
                self.assertEqual(source.audio_path(root), path)
                frames = list(source.frames())
                self.assertEqual(frames[0][1].dtype, np.float32)
                self.assertGreater(frames[2][1].max(), 4)
                if transfer == 'arib-std-b67':
                    np.testing.assert_allclose(frames[1][1], 1, atol=.015)
                for index in (4, 1, 5):
                    number, rgb = next(source.frames(index, 1))
                    self.assertEqual(number, index)
                    np.testing.assert_array_equal(rgb, frames[index][1])
                target = root / 'proxy.mp4'
                playback_proxy(source, target, edge=64)
                with av.open(str(target)) as output:
                    stream = output.streams.video[0]
                    self.assertEqual(stream.codec_context.format.name, 'yuv420p')
                    self.assertEqual(int(stream.codec_context.color_trc), 13)
                    self.assertEqual(float(stream.average_rate), 48)
                    self.assertEqual(len(list(output.decode(stream))), 6)
                    self.assertTrue(output.streams.audio)

    def test_ambiguous_hdr_gamut_is_not_silently_guessed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'wrong-gamut.mp4'
            self.movie(path, 'arib-std-b67', 'bt709')
            with self.assertRaisesRegex(ValueError, 'BT.2020'):
                Source(path)


if __name__ == '__main__': unittest.main()

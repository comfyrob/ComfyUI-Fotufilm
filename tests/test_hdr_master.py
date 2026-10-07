import sys
import tempfile
import types
import unittest
from pathlib import Path

import numpy as np
import OpenEXR
import torch

APP = Path(__file__).resolve().parents[1]
package = types.ModuleType('film_finish')
package.__path__ = [str(APP)]
sys.modules.setdefault('film_finish', package)
from film_finish.hdr_master import write_master, read_manifest, read_member, TO_REC2020
from film_finish.master_export import delivery


class MasterTests(unittest.TestCase):
    def test_lossless_exr_and_float_proxy_keep_headroom(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = torch.tensor([4.0, -0.125, 1.5]).expand(2, 4, 6, 3).clone()
            target = root / 'source.ffhdr.zip'
            manifest = write_master(source, 24, 'linear-rec709', APP / 'tests/codec-smoke.mp4', target, proxy_edge=3)
            self.assertEqual(read_manifest(target), manifest)
            self.assertEqual((manifest['proxyWidth'], manifest['proxyHeight']), (3, 2))
            frame = root / 'frame.exr'
            frame.write_bytes(read_member(target, 'master/000001.exr', 100000))
            with OpenEXR.File(str(frame), separate_channels=True) as image:
                actual = np.stack([image.channels()[channel].pixels for channel in 'RGB'], axis=-1)
                np.testing.assert_array_equal(actual, source[1].numpy())
            proxy = np.frombuffer(read_member(target, 'preview/000001.rgba32f', 96), dtype='<f4').reshape(2, 3, 4)
            np.testing.assert_allclose(proxy[0, 0, :3], source[0, 0, 0].numpy() @ TO_REC2020['linear-rec709'].T, rtol=1e-6)
            self.assertGreater(float(proxy.max()), 1)
            with self.assertRaises(ValueError):
                read_member(target, 'preview/000001.rgba32f', 95)

    def test_aces_conversion_matches_colour_science(self):
        import colour
        expected = colour.matrix_RGB_to_RGB(colour.RGB_COLOURSPACES['ACEScg'], colour.RGB_COLOURSPACES['ITU-R BT.2020'], chromatic_adaptation_transform='Bradford')
        np.testing.assert_allclose(TO_REC2020['linear-acescg'], expected, atol=2e-7)

    def test_aces_master_keeps_a_1280_pixel_preview_at_source_resolution(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'aces.ffhdr.zip'
            pixels = torch.tensor([4., 2., .5]).expand(1, 2, 1280, 3).clone()
            manifest = write_master(pixels, 24, 'linear-acescg', APP / 'tests/codec-smoke.mp4', target)
            self.assertEqual((manifest['proxyWidth'], manifest['proxyHeight']), (1280, 2))
            self.assertEqual(manifest['colorSpace'], 'linear-acescg')
            proxy = np.frombuffer(read_member(target, 'preview/000000.rgba32f', 1280 * 2 * 16), dtype='<f4').reshape(2, 1280, 4)
            np.testing.assert_allclose(proxy[0, 0, :3], [4.06030684, 1.999059455, .44451817], atol=1e-6)

    def test_interrupted_write_never_publishes_partial_master(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'source.ffhdr.zip'
            def interrupt():
                raise InterruptedError('cancelled')
            with self.assertRaises(InterruptedError):
                write_master(torch.ones(1, 2, 2, 3), 24, 'linear-rec2020', APP / 'tests/codec-smoke.mp4', target, interrupt)
            self.assertFalse(target.exists())
            self.assertFalse(target.with_suffix('.part').exists())

    def test_hlg_delivery_retains_distinct_highlights(self):
        encoded = delivery(np.array([[[1., 1., 1.], [2., 2., 2.], [4., 4., 4.]]], dtype=np.float32), True, 0.7)
        self.assertTrue(np.all(np.diff(encoded[0, :, 0].astype(int)) > 0))
        self.assertLess(encoded.max(), 65535)


if __name__ == '__main__':
    unittest.main()

import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import torch

APP = Path(__file__).resolve().parents[1]
package = types.ModuleType('film_finish'); package.__path__ = [str(APP)]
sys.modules.setdefault('film_finish', package)
from film_finish.balance_node import FotufilmBalanceFrames
from film_finish.inspection_node import FotufilmInspectFrame


class BalanceTests(unittest.TestCase):
    def test_neutral_acescg_branch_does_not_duplicate_the_video(self):
        source = torch.zeros((2,4,6,3), dtype=torch.float32)
        self.assertIs(FotufilmBalanceFrames.execute(source).result[0], source)
        self.assertIs(FotufilmBalanceFrames.execute(source, enabled=False, exposure=2).result[0], source)

    def test_hdr_exposure_preserves_negative_and_above_one_pixels_without_mutation(self):
        source = torch.tensor([-.125, .18, 8.]).expand(2, 4, 6, 3).clone()
        saved = source.clone()
        result = FotufilmBalanceFrames.execute(source, exposure=1)
        torch.testing.assert_close(result.result[0], source * 2, rtol=2e-5, atol=2e-6)
        torch.testing.assert_close(source, saved)
        self.assertEqual(result.result[1], 'linear ACEScg')
        self.assertEqual(result.result[0].dtype, torch.float32)

    def test_srgb_is_decoded_once_and_disabled_correction_still_converts_input(self):
        from film_finish.grading import convert
        source = torch.full((1, 2, 3, 3), .5)
        result = FotufilmBalanceFrames.execute(source, 'sRGB', False, exposure=4).result[0]
        expected = convert(((source+.055)/1.055)**2.4, 'linear-rec709', 'linear-acescg')
        torch.testing.assert_close(result, expected)
        with self.assertRaises(ValueError): FotufilmBalanceFrames.execute(source*3, 'sRGB')

    def test_disabled_still_branch_never_reads_source_or_writes(self):
        with patch('film_finish.inspection_node.inspection_frame', side_effect=AssertionError('must not render')):
            result = FotufilmInspectFrame.execute(0,'finish','{}','linear ACEScg',enabled=False)
        self.assertIsNone(result.result[0])

    def test_bad_values_and_channels_rejected(self):
        source = torch.zeros((1,2,3,3))
        for kwargs in [dict(exposure=float('nan')),dict(gain_r=-1),dict(unknown=1)]:
            with self.assertRaises(ValueError): FotufilmBalanceFrames.execute(source, **kwargs)
        with self.assertRaises(ValueError): FotufilmBalanceFrames.execute(torch.zeros((1,2,3,4)))

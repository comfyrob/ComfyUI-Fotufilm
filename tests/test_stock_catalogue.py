"""The selector must describe installed resources, not assume every runtime is equal."""
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

APP = Path(__file__).resolve().parents[1]
package = types.ModuleType('film_finish')
package.__path__ = [str(APP)]
sys.modules.setdefault('film_finish', package)
from film_finish.runtime_paths import stock_catalogue


class StockCatalogueTests(unittest.TestCase):
    def test_inventory_excludes_malformed_and_mismatched_profiles(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'valid.json').write_text(json.dumps({'id': 'valid'}))
            (root / 'wrong.json').write_text(json.dumps({'id': 'another'}))
            (root / 'bad.json').write_text('{')
            with patch('film_finish.runtime_paths.stocks_path', return_value=root), patch('film_finish.runtime_paths.runtime_revision', return_value='installed'):
                self.assertEqual(stock_catalogue(), {'engine': 'installed', 'stocks': ['valid']})

    def test_missing_resource_directory_returns_empty_inventory(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch('film_finish.runtime_paths.stocks_path', return_value=Path(directory)/'absent'), patch('film_finish.runtime_paths.runtime_revision', return_value='installed'):
                self.assertEqual(stock_catalogue()['stocks'], [])

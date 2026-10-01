# -*- coding: utf-8 -*-
import tempfile
import unittest
from pathlib import Path

from asset_context import ensure_browser_directory


class AssetBrowserDirectoryTests(unittest.TestCase):
    def test_category_directory_is_created_below_the_asset_root(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp) / '资产库'
            path = ensure_browser_directory(base, 'characters')
            self.assertEqual(path, (base / 'assets' / 'characters').resolve())
            self.assertTrue(path.is_dir())
            self.assertFalse((base / 'assets' / 'props').exists())

    def test_all_returns_the_shared_asset_directory(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp) / '资产库'
            self.assertEqual(ensure_browser_directory(base, 'all'), (base / 'assets').resolve())

    def test_unknown_category_is_rejected_without_creating_directories(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp) / '资产库'
            with self.assertRaisesRegex(ValueError, '分类无效'):
                ensure_browser_directory(base, 'unknown')
            self.assertFalse(base.exists())

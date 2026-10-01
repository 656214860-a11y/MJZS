# -*- coding: utf-8 -*-
"""资产历史版本恢复的无界面回归测试。"""
import tempfile
import unittest
from pathlib import Path

from agent.core import read, save
from desktop import Desktop


class _Status:
    def __init__(self):
        self.value = ""

    def set(self, value):
        self.value = value


class _AssetDesktop:
    def __init__(self, base):
        self._base = Path(base)
        self.status = _Status()
        self.page = None

    def asset_base(self):
        return self._base

    def show(self, page):
        self.page = page


class AssetRestoreTests(unittest.TestCase):
    def test_restores_latest_history_image_and_updates_manifest(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            history = base / "assets" / "characters" / "历史版本"
            history.mkdir(parents=True)
            original = history / "CHAR_001_20260926.png"
            original.write_bytes(b"image")
            save(base / "assets.json", {"CHAR_001": {"name": "主角"}})
            view = _AssetDesktop(base)

            self.assertTrue(Desktop.restore_asset_image(view, "CHAR_001", ask=False))

            restored = base / "assets" / "characters" / "CHAR_001.png"
            self.assertEqual(restored.read_bytes(), b"image")
            self.assertFalse(original.exists())
            self.assertEqual(read(base / "assets.json")["CHAR_001"]["image"],
                             "assets/characters/CHAR_001.png")

    def test_never_overwrites_existing_asset_file(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            folder = base / "assets" / "characters"
            history = folder / "历史版本"
            history.mkdir(parents=True)
            original = history / "CHAR_001_20260926.png"
            original.write_bytes(b"old")
            existing = folder / "CHAR_001.png"
            existing.write_bytes(b"new")
            save(base / "assets.json", {"CHAR_001": {"name": "主角"}})
            view = _AssetDesktop(base)

            with self.assertRaisesRegex(ValueError, "恢复目标已存在同名图片"):
                Desktop.restore_asset_image(view, "CHAR_001", ask=False)

            self.assertEqual(existing.read_bytes(), b"new")
            self.assertTrue(original.exists())

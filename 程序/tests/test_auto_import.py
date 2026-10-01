# -*- coding: utf-8 -*-
"""生成图片自动导入回归。"""
import json
import struct
import tempfile
import unittest
import zlib
from pathlib import Path


def png_bytes(w=2, h=2):
    def chunk(kind, data):
        content = kind + data
        return struct.pack(">I", len(data)) + content + struct.pack(">I", zlib.crc32(content) & 0xffffffff)

    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    raw = b"".join(b"\x00" + b"\x00\x00\x00" * w for _ in range(h))
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")


class AutoImportTests(unittest.TestCase):
    def make_project(self, td, asset_id, name, prompt):
        project = Path(td) / "p"
        base = project / "episode"
        (base / "assets/资产清单").mkdir(parents=True)
        (base / "assets/资产清单/assets.json").write_text(
            json.dumps({asset_id: {"name": name, "image_prompt": prompt}}, ensure_ascii=False), encoding="utf-8"
        )
        (project / "config.json").write_text(json.dumps({"asset_library_dir": "episode"}), encoding="utf-8")
        return project, base

    def test_import_pending_generated(self):
        with tempfile.TemporaryDirectory() as td:
            project, base = self.make_project(td, "CHAR_001", "A", "x")
            from asset_context import generated_dir
            from asset_batch import image_ready
            from native_assets import import_pending_generated

            (generated_dir(base) / "CHAR_001_seedream_abc.png").write_bytes(png_bytes())
            self.assertIn("CHAR_001", import_pending_generated(project, base))
            self.assertTrue(image_ready(base, "CHAR_001"))
            self.assertEqual(import_pending_generated(project, base), [])

    def test_pending_generated_precheck(self):
        with tempfile.TemporaryDirectory() as td:
            project, base = self.make_project(td, "CHAR_002", "B", "y")
            from asset_context import generated_dir
            from asset_batch import image_ready
            from native_assets import import_pending_generated, pending_generated

            generated = generated_dir(base)
            (generated / "CHAR_002_seedream_x.png").write_bytes(png_bytes())
            (generated / "no_id_here.png").write_bytes(png_bytes())
            self.assertEqual(pending_generated(project, base), ["CHAR_002"])
            self.assertFalse(image_ready(base, "CHAR_002"))
            self.assertEqual(import_pending_generated(project, base), ["CHAR_002"])
            self.assertTrue(image_ready(base, "CHAR_002"))
            self.assertEqual(pending_generated(project, base), [])

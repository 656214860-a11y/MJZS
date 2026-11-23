# -*- coding: utf-8 -*-
"""资产图片制作的设置写入：_AssetControls.selected 统一走 save_prefs（W6B-FIX-P1）。"""
import json, os, sys, tempfile, types, unittest
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.chdir(HERE)

import native_assets


def _controls(project):
    return types.SimpleNamespace(
        project=project,
        prefsfile=project / "ui_settings.json",
        model=types.SimpleNamespace(get=lambda: "模型甲"),
        aspect=types.SimpleNamespace(get=lambda: "9:16"),
        update_hint=lambda: None)


class SelectedSavePrefsTests(unittest.TestCase):
    def test_writes_prefs_when_project_exists(self):
        with tempfile.TemporaryDirectory() as td:
            proj = Path(td) / "p"
            proj.mkdir()
            (proj / "ui_settings.json").write_text(
                json.dumps({"other": 1}, ensure_ascii=False), encoding="utf-8")
            native_assets._AssetControls.selected(_controls(proj))
            prefs = json.loads((proj / "ui_settings.json").read_text(encoding="utf-8"))
        self.assertEqual(prefs.get("asset_workflow"),
                         {"model": "模型甲", "aspect_ratio": "9:16",
                          "quality": "medium", "seed": 42})
        self.assertEqual(prefs.get("other"), 1)

    def test_missing_project_raises_and_does_not_recreate(self):
        with tempfile.TemporaryDirectory() as td:
            proj = Path(td) / "p"
            with self.assertRaises(ValueError) as ctx:
                native_assets._AssetControls.selected(_controls(proj))
            self.assertIn("项目目录不存在或已被移动", str(ctx.exception))
            self.assertFalse(proj.exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)

# -*- coding: utf-8 -*-
"""分镜回收的设置写入：recycle_files 统一走 save_prefs（W6B-FIX-P1）。"""
import json, os, sys, tempfile, unittest
from pathlib import Path
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.chdir(HERE)

import orchestrator.storyboard_selection  # noqa: F401 保证它在打桩之前已经导入
import domain.storyboard_catalog_service as catalog_service
from orchestrator.storyboard_recycle_service import recycle_files

REAL_LINKED_PATH = catalog_service.linked_path


def _make_project(td):
    proj = (Path(td) / "p").resolve()
    (proj / "writing").mkdir(parents=True)
    (proj / "ui_settings.json").write_text(
        json.dumps({"final_storyboard_json": "MARK", "other": 1}, ensure_ascii=False),
        encoding="utf-8")
    return proj


class RecycleSavePrefsTests(unittest.TestCase):
    def test_clears_final_pointer_when_project_exists(self):
        with tempfile.TemporaryDirectory() as td:
            proj = _make_project(td)
            source = proj / "writing" / "第1集_剧本.md"
            source.write_text("正文", encoding="utf-8")
            resolved = source.resolve()

            def fake(context, value):
                if value == "MARK":
                    return resolved
                return REAL_LINKED_PATH(context, value)

            with mock.patch("domain.storyboard_catalog_service.linked_path",
                            side_effect=fake):
                recycle_files(proj, "script", [source])
            prefs = json.loads((proj / "ui_settings.json").read_text(encoding="utf-8"))
        self.assertEqual(prefs.get("final_storyboard_json"), "")
        self.assertEqual(prefs.get("other"), 1)

    def test_missing_project_raises_and_does_not_recreate(self):
        with tempfile.TemporaryDirectory() as td:
            proj = _make_project(td)
            source = proj / "writing" / "第1集_剧本.md"
            source.write_text("正文", encoding="utf-8")
            resolved = source.resolve()
            moved = Path(td) / "moved"

            def fake(context, value):
                if value == "MARK":
                    # 模拟「读完设置、还没写回去的时候项目被改名」。
                    proj.rename(moved)
                    return resolved
                return REAL_LINKED_PATH(context, value)

            with mock.patch("domain.storyboard_catalog_service.linked_path",
                            side_effect=fake):
                with self.assertRaises(ValueError) as ctx:
                    recycle_files(proj, "script", [source])
            self.assertIn("项目目录不存在或已被移动", str(ctx.exception))
            self.assertFalse(proj.exists())
            prefs = json.loads((moved / "ui_settings.json").read_text(encoding="utf-8"))
            self.assertEqual(prefs.get("final_storyboard_json"), "MARK")


if __name__ == "__main__":
    unittest.main(verbosity=2)

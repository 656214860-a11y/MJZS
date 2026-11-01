# -*- coding: utf-8 -*-
"""回收站路径安全自检。"""
import tempfile
import unittest
from pathlib import Path

from storyboard_files import recycle_plan
from storyboard_recycle_service import recycle_plan as service_recycle_plan, recycle_files


def make_project(td):
    proj = Path(td) / "p"
    (proj / "writing").mkdir(parents=True)
    return proj


class RecyclePlanTests(unittest.TestCase):
    def test_service_recycles_file_into_recoverable_batch(self):
        with tempfile.TemporaryDirectory() as td:
            proj = make_project(td)
            source = proj / "writing" / "第1集_剧本.md"
            source.write_text("正文", encoding="utf-8")
            batch = recycle_files(proj, "script", [source])
            self.assertFalse(source.exists())
            self.assertTrue((batch / "恢复位置.json").is_file())

    def test_valid_script(self):
        with tempfile.TemporaryDirectory() as td:
            proj = make_project(td)
            file_path = proj / "writing" / "第1集_剧本.md"
            file_path.write_text("正文", encoding="utf-8")
            targets = recycle_plan(proj, "script", file_path)
            self.assertEqual(targets, [file_path.resolve()])
            self.assertEqual(service_recycle_plan(proj, "script", file_path), targets)

    def test_outside_project_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            proj = make_project(td)
            outside = Path(td) / "x.md"
            outside.write_text("x", encoding="utf-8")
            with self.assertRaises(ValueError):
                recycle_plan(proj, "script", outside)

    def test_missing_file_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            proj = make_project(td)
            with self.assertRaises(ValueError):
                recycle_plan(proj, "script", proj / "writing" / "第2集_不存在.md")

    def test_wrong_kind_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            proj = make_project(td)
            file_path = proj / "writing" / "第1集_剧本.md"
            file_path.write_text("正文", encoding="utf-8")
            with self.assertRaises(ValueError):
                recycle_plan(proj, "badkind", file_path)

    def test_recycle_goes_through_shared_recycler_and_restores(self):
        from storyboard_recycle_service import latest_recycle_batch, restore_latest_recycled_files
        with tempfile.TemporaryDirectory() as td:
            proj = make_project(td)
            source = proj / "writing" / "第1集_剧本.md"
            source.write_text("正文", encoding="utf-8")
            batch = recycle_files(proj, "script", [source])
            self.assertEqual(batch.parent.name, "回收站")
            folder, names = latest_recycle_batch(proj)
            self.assertEqual(folder.resolve(), batch.resolve())
            self.assertEqual(names, ["writing/第1集_剧本.md"])
            restore_latest_recycled_files(proj)
            self.assertEqual(source.read_text(encoding="utf-8"), "正文")

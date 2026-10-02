# -*- coding: utf-8 -*-
"""第 68 期任务 12：06 首帧管理页在「全部分镜」下要列出已采用每一份分镜的镜头。

用户原话：「全部页面->选择分镜的下拉框->『全部分镜』功能无法正确显示全部内容」。
"""
from skip_reasons import (
    MISSING_NODE,
    PLATFORM_DIRECTORY_LINK,
    PLATFORM_TKINTER,
    PLATFORM_TK_DISPLAY,
    PLATFORM_WORKING_SET,
    REQUIRES_BUNDLED_SKILL,
)
import json, os, sys, tempfile, time, unittest
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
PROGRAM = os.path.dirname(HERE)
sys.path.insert(0, PROGRAM)
os.chdir(PROGRAM)


def shot(sid, title):
    return {"id": sid, "title": title, "duration": 5, "characters": ["CHAR_001"], "location": "LOC_001",
            "frame": "frames/%s.png" % sid, "video_prompt": "画面", "frame_prompt": "窗边的猫", "dialogue": []}


def make_project(td, scope=None):
    """一份「已采用两份分镜」的项目：EP001 一镜、EP002 两镜，都在 storyboard/分镜拆分 下。"""
    proj = Path(td) / "p"
    (proj / "episode" / "frames").mkdir(parents=True)
    (proj / "episode" / "assets.json").write_text("{}", encoding="utf-8")
    first = {"episode_id": "EP001", "title": "第一集", "shots": [shot("SH001", "甲")]}
    second = {"episode_id": "EP002", "title": "第二集",
              "shots": [shot("EP002_SH001", "乙"), shot("EP002_SH002", "丙")]}
    (proj / "episode" / "episode.json").write_text(json.dumps(first, ensure_ascii=False), encoding="utf-8")
    (proj / "config.json").write_text(json.dumps({
        "episode_dir": str(proj / "episode"), "episode_file": str(proj / "episode" / "episode.json"),
        "budget_seconds": 0, "reserve_seconds": 0, "live_enabled": False}, ensure_ascii=False), encoding="utf-8")
    folder = proj / "storyboard" / "分镜拆分"
    folder.mkdir(parents=True, exist_ok=True)
    for name, data in (("episode.json", first), ("ep002.json", second)):
        (folder / name).write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    settings = {"adopted_storyboards": ["storyboard/分镜拆分/episode.json", "storyboard/分镜拆分/ep002.json"],
                "frame_json": "storyboard/分镜拆分/episode.json"}
    if scope:
        settings["asset_scope"] = scope
    (proj / "ui_settings.json").write_text(json.dumps(settings, ensure_ascii=False), encoding="utf-8")
    # 这两份 JSON 的 mtime 顶到将来一点：storyboard_storage.normalize 只整理 3 秒以上的旧文件，
    # 别在用例中途把文件名换掉（同 test_ui_edges.adopt_storyboard_fixture 的理由）。
    stamp = time.time() + 900
    for path in folder.glob("*.json"):
        os.utime(path, (stamp, stamp))
    return proj


class FrameSourceTests(unittest.TestCase):
    """第 68 期任务 12：一屏里能看到几份分镜的镜头，由「选择分镜」那个范围偏好说了算。"""

    @classmethod
    def setUpClass(cls):
        try:
            import tkinter as tk
        except Exception:
            cls.tk = None
        else:
            cls.tk = tk

    def setUp(self):
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.win = self.tk.Tk()
        self.win.withdraw()
        self.addCleanup(self.win.destroy)

    def open_page(self, scope=None):
        from desktop import Desktop
        from local_video import open_studio
        self.proj = make_project(self.tmp.name, scope=scope)
        self.desktop = Desktop(self.win, root=PROGRAM)
        self.desktop.root = self.proj
        self.desktop.studio = open_studio(self.proj)
        from pet_state import PAGE_OF
        self.desktop.show(PAGE_OF['keyframe'])     # 07 首帧管理
        self.win.update_idletasks()
        return self.desktop

    def widgets(self, kind):
        found = []

        def walk(widget):
            if isinstance(widget, kind):
                found.append(widget)
            for child in widget.winfo_children():
                walk(child)

        walk(self.desktop.content)
        return found

    def table(self):
        from tkinter import ttk
        return self.widgets(ttk.Treeview)[0]

    def combos(self):
        from tkinter import ttk
        return self.widgets(ttk.Combobox)

    def test_the_whole_scope_lists_every_adopted_storyboard(self):
        self.open_page()
        self.assertEqual(set(self.table().get_children()), {"SH001", "EP002_SH001", "EP002_SH002"},
                         "两份已采用分镜的 3 个镜头都要列在这一屏里")
        self.assertEqual(list(self.combos()[1].cget("values")),
                         ["SH001", "EP002_SH001", "EP002_SH002"], "「选中镜头」也要跟着列全")
        self.assertEqual(self.desktop.header_status.cget("text"), "当前 JSON：全部 2 份已采用分镜")

    def test_the_one_file_scope_still_shows_only_that_file(self):
        self.open_page(scope="current")
        self.assertEqual(list(self.table().get_children()), ["SH001"], "「只这一份」就只列这一份")

    def test_each_row_reads_its_own_storyboard_directory(self):
        """第二份分镜的首帧在它自己的根目录下：那一行要认出「已导入」，别一份也不认。"""
        from tests.test_ui_edges import real_png
        self.open_page()
        folder = self.proj / "storyboard" / "frames"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "EP002_SH001.png").write_bytes(real_png())
        from pet_state import PAGE_OF
        self.desktop.show(PAGE_OF['keyframe'])
        self.win.update_idletasks()
        table = self.table()
        self.assertEqual(table.set("EP002_SH001", "status"), "已导入")
        self.assertEqual(table.set("SH001", "status"), "待生成 / 待导入")
        self.assertEqual(table.set("SH001", "file"), "—", "还没导入首帧的那一行写「—」")
        self.assertEqual(table.set("EP002_SH002", "status"), "待生成 / 待导入")

    def test_two_storyboards_may_share_a_shot_number(self):
        """两份分镜各有一个同号镜头时，两行也要各占一行（行编号分得开才建得出来）。"""
        self.open_page()
        folder = self.proj / "storyboard" / "分镜拆分"
        other = json.loads((folder / "ep002.json").read_text(encoding="utf-8"))
        other["shots"] = [shot("SH001", "同号"), shot("EP002_SH002", "丙")]
        (folder / "ep002.json").write_text(json.dumps(other, ensure_ascii=False), encoding="utf-8")
        from pet_state import PAGE_OF
        self.desktop.show(PAGE_OF['keyframe'])
        self.win.update_idletasks()
        rows = list(self.table().get_children())
        self.assertEqual(len(rows), 3, "同号的两镜也要各占一行")
        self.assertEqual(len(set(rows)), 3)
        self.assertIn("SH001@episode", rows, "撞号时行编号带上它那一份分镜的名字")
        self.assertIn("SH001@ep002", rows)


if __name__ == "__main__":
    unittest.main(verbosity=2)

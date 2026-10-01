# -*- coding: utf-8 -*-
"""05 分镜定稿那个文本框的自检（第 45 期）。运行：python test_final_viewer.py

用户这一轮提的两条：
- 「文本框内鼠标滑动，提高文字下滑速度」——一格滚轮滚 9 行（原来 3 行）；
- 「用户如有改动文字，自动弹窗提醒用户是否保存」——改完字停一会儿、或焦点离开这个框时问一句。
"""
import json, os, sys, tempfile, time, unittest
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
PROGRAM = str(Path(HERE).parent)
sys.path.insert(0, PROGRAM)
os.chdir(PROGRAM)

import storyboard_files


def make_project(td, shots=40):
    proj = Path(td) / "p"
    (proj / "episode" / "frames").mkdir(parents=True)
    (proj / "episode" / "assets.json").write_text("{}", encoding="utf-8")
    episode = {"episode_id": "EP001", "title": "看它，别看我",
               "shots": [{"id": "SH%03d" % (index + 1), "title": "镜头", "duration": 5,
                          "characters": ["CHAR_001"], "location": "LOC_001",
                          "frame": "frames/SH%03d.png" % (index + 1),
                          "video_prompt": "画面", "frame_prompt": "窗边的猫", "dialogue": []}
                         for index in range(shots)]}
    (proj / "episode" / "episode.json").write_text(json.dumps(episode, ensure_ascii=False), encoding="utf-8")
    (proj / "config.json").write_text(json.dumps({
        "episode_dir": str(proj / "episode"), "episode_file": str(proj / "episode" / "episode.json"),
        "budget_seconds": 0, "reserve_seconds": 0, "live_enabled": False}, ensure_ascii=False), encoding="utf-8")
    # 工作分镜属于 03 初步分镜阶段；旧 storyboard/ 仅允许兼容读取。
    from project_stages import storyboard
    sb_dir = storyboard(proj) / "分镜拆分"
    sb_dir.mkdir(parents=True, exist_ok=True)
    target = sb_dir / "episode.json"
    target.write_text(json.dumps(episode, ensure_ascii=False), encoding="utf-8")
    (proj / "ui_settings.json").write_text(json.dumps(
        {"adopted_storyboards": ["03初步分镜/分镜拆分/episode.json"],
         "frame_json": "03初步分镜/分镜拆分/episode.json"}, ensure_ascii=False), encoding="utf-8")
    # 这份 JSON 的 mtime 顶到将来一点：normalize 只整理 3 秒以上的旧文件，别在用例中途被改名。
    stamp = time.time() + 600
    os.utime(target, (stamp, stamp))
    return proj, target


class FinalViewerCase(unittest.TestCase):
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
            self.skipTest("tkinter 不可用")
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.project, self.source = make_project(self.tmp.name)
        import desktop
        self.desktop_module = desktop
        original_choose = desktop.Desktop.choose_project
        desktop.Desktop.choose_project = lambda self: None    # 别去开本机真项目
        self.addCleanup(setattr, desktop.Desktop, "choose_project", original_choose)
        self.win = self.tk.Tk()
        self.win.withdraw()
        self.addCleanup(self.win.destroy)
        from local_video import open_studio
        self.app = desktop.Desktop(self.win, root=PROGRAM)
        self.app.root = self.project
        self.app.studio = open_studio(self.project)
        # 第 62 期任务 7：打开项目后的第一拍要做一次「启动对账」，工作集指针歪了会重建页面。
        # 真机上那一拍早在用户动手前就走完了；这里也先让它走掉，免得用例抓着被重建掉的控件。
        self.app.poll_auto_adopt()
        self.asked = []
        self.errors = []
        original_yes = storyboard_files.messagebox.askyesno
        original_error = storyboard_files.messagebox.showerror
        storyboard_files.messagebox.askyesno = lambda *a, **k: (self.asked.append(a), self.answer)[1]
        storyboard_files.messagebox.showerror = lambda *a, **k: self.errors.append(a)
        self.addCleanup(setattr, storyboard_files.messagebox, "askyesno", original_yes)
        self.addCleanup(setattr, storyboard_files.messagebox, "showerror", original_error)
        self.answer = True
        # show() 使用零基索引；资产管理置为 04 后，分镜定稿（06）位于索引 5。
        self.app.show(5)
        self.win.update_idletasks()
        self.viewer = self.find_viewer(self.app.content)
        self.assertIsNotNone(self.viewer, "04 那一页有那个 JSON 文本框")

    def find_viewer(self, widget):
        for child in widget.winfo_children():
            if isinstance(child, self.tk.Text) and child.get("1.0", "end-1c").lstrip().startswith("{"):
                return child
            found = self.find_viewer(child)
            if found is not None:
                return found
        return None

    def live_path(self):
        """这份 JSON 现在的路径：维护那一下可能已经把它改成规范名，别名表里记着新名字。"""
        import storyboard_storage
        return storyboard_storage.resolved_alias(self.project, "03初步分镜/分镜拆分/episode.json")

    def saved_path(self):
        """这份 JSON 存完之后落在哪儿：顺着别名表一格一格走到头。

        规范名是拿**标题**拼的（`storyboard_storage.canonical_name`）：用户改了标题，维护那一下
        会接着把它改成新名字，别名表里于是有「旧名 → 规范名 → 又一个新的规范名」这样一串。
        并行整跑时事件循环被拖住几秒，这一下就会真的发生（第 47 期的对照实验里必现），
        所以读盘前要顺着走，而不是拿存之前算好的那个路径去读。
        """
        import storyboard_storage
        root = self.project / "03初步分镜" / "分镜拆分"
        alias_file = root / storyboard_storage.ALIAS_FILE
        aliases = json.loads(alias_file.read_text(encoding="utf-8")) if alias_file.is_file() else {}
        rel, seen = "03初步分镜/分镜拆分/episode.json", set()
        while rel in aliases and rel not in seen:
            seen.add(rel)
            rel = aliases[rel]
        return (self.project / rel).resolve()

    def disk_text(self):
        return json.loads(self.live_path().read_text(encoding="utf-8"))

    def type_over(self, text):
        self.viewer.delete("1.0", "end")
        self.viewer.insert("1.0", text)


import unittest


class WheelSpeedTests(FinalViewerCase):
    """用户要的「文本框内鼠标滑动，提高文字下滑速度」。"""

    def test_one_notch_scrolls_more_lines_than_before(self):
        self.assertGreaterEqual(storyboard_files.VIEWER_WHEEL_LINES, 9,
                                "第 45 期：原来一格 3 行，现在要更快")
        self.assertIn("<MouseWheel>", self.viewer.bind(), "滚轮挂在这个框上")

    def test_the_wheel_really_moves_the_text(self):
        self.win.deiconify()
        self.win.update()
        try:
            self.viewer.yview_moveto(0.0)
            before = self.viewer.yview()[0]
            self.viewer.event_generate("<MouseWheel>", delta=-120, x=6, y=6)
            self.win.update()
            self.assertGreater(self.viewer.yview()[0], before, "往下滚轮＝内容往下走")
        finally:
            self.win.withdraw()


class SaveReminderTests(FinalViewerCase):
    """用户要的「改动文字后自动弹窗提醒是否保存」。"""

    def test_an_untouched_box_never_asks(self):
        self.viewer.event_generate("<FocusOut>")
        self.win.update()
        self.assertEqual(self.asked, [], "没改过字不打扰")

    def test_leaving_the_box_asks_and_saves(self):
        data = self.disk_text()
        data["title"] = "改过的标题"
        self.type_over(json.dumps(data, ensure_ascii=False, indent=2))
        self.viewer.event_generate("<FocusOut>")
        self.win.update()
        self.assertEqual(len(self.asked), 1, "改过字离开这个框：问一句")
        self.assertEqual(self.disk_text()["title"], "改过的标题", "点「保存」＝真的写回项目")

    def test_saying_no_puts_the_disk_copy_back(self):
        """「不保存」＝盘上那份一个字不动（读到的是现在这个路径上的那份）。"""
        self.answer = False
        path = self.live_path()
        before = path.read_text(encoding="utf-8")
        self.type_over('{"episode_id": "EP001", "shots": []}')
        self.viewer.event_generate("<FocusOut>")
        self.win.update()
        self.assertEqual(len(self.asked), 1)
        self.assertEqual(path.read_text(encoding="utf-8"), before, "点「不保存」＝一个字都不动")
        self.assertIn("SH001", self.viewer.get("1.0", "end-1c"), "框里恢复成盘上那一份")

    def test_broken_json_is_reported_and_not_written(self):
        path = self.live_path()
        before = path.read_text(encoding="utf-8")
        self.type_over('{"episode_id": ')
        self.viewer.event_generate("<FocusOut>")
        self.win.update()
        self.assertEqual(len(self.asked), 1)
        self.assertEqual(len(self.errors), 1, "改坏了要说明白，而不是写坏文件")
        self.assertIn("JSON", self.errors[0][1])
        self.assertEqual(path.read_text(encoding="utf-8"), before)

    def test_a_maintenance_rename_is_followed_by_the_next_save(self):
        """第 45 期：维护那一下把工作稿改成规范名（别名表记着），接着存要写在新名字上。

        原来照旧往旧名字写：旁边会多出一份内容不同的 `episode.json`，项目里于是有两份「当前
        分镜」。现在落盘前先按别名表认一次真路径。
        """
        import storyboard_storage
        stamp = time.time()
        os.utime(self.source, (stamp, stamp))       # 这一份放旧了，维护才有权整理它
        moved = storyboard_storage.normalize(self.project, min_age=0)
        self.assertTrue(moved, "这一下确实把工作稿改成了规范名")
        live = self.saved_path()
        self.assertNotEqual(live, self.source, "旧名字已经不在盘上了")
        data = json.loads(live.read_text(encoding="utf-8"))
        data["title"] = "改名之后接着改"
        self.type_over(json.dumps(data, ensure_ascii=False, indent=2))
        self.viewer.event_generate("<FocusOut>")
        self.win.update()
        self.assertEqual(len(self.asked), 1)
        self.assertEqual(json.loads(self.saved_path().read_text(encoding="utf-8"))["title"], "改名之后接着改",
                         "写在新名字上（维护后来又按新标题改一次名也照样跟得住）")
        self.assertFalse(self.source.exists(), "旧名字不会因为这次保存又被造出来")

    def test_pausing_after_typing_asks_without_leaving_the_box(self):
        """打完字停一会儿就提醒，不用等焦点离开。

        第 56 期：这一条原来靠「造一个 <KeyRelease> 事件」把去抖挂上，而造出来的键盘事件
        根本送不到这个窗（并行整跑里它不是系统焦点窗；量过：连着造 8 秒，这个框一次都没收到）。
        那次红就是「框里的字还在、一次都没问」。去抖改成认 <<Modified>>（内容一变就挂，
        与字是怎么进来的无关）之后，把字打进去、把事件循环泵过去就行，不再看系统焦点。
        """
        data = self.disk_text()
        data["title"] = "打完字停一会儿"
        self.win.deiconify()
        self.win.update()
        try:
            self.type_over(json.dumps(data, ensure_ascii=False, indent=2))
            self.win.update()                     # 让 <<Modified>> 派下来，去抖挂上
            deadline = time.monotonic() + max(6.0, storyboard_files.VIEWER_SAVE_ASK_MS / 1000.0 + 5)
            while not self.asked and time.monotonic() < deadline:
                self.win.update(); self.win.update_idletasks()
                time.sleep(0.02)
        finally:
            self.win.withdraw()
        self.assertEqual(len(self.asked), 1, "打字停下来一会儿就提醒（不用等焦点离开）")
        self.assertEqual(self.disk_text()["title"], "打完字停一会儿")

    def test_drawing_the_page_again_does_not_ask(self):
        self.app.show(5)
        self.win.update_idletasks()
        self.assertEqual(self.asked, [], "只是重新画一遍这一页：一个字都没改，不问")


class ButtonRowTests(FinalViewerCase):
    """第 68 期任务 6：05 分镜定稿那一行按用户给的顺序排，主动作高亮。"""

    def row_buttons(self):
        """这一页里所有按钮，按建的先后：[…]。"""
        from tkinter import ttk

        found = []

        def walk(widget):
            for child in widget.winfo_children():
                if isinstance(child, (ttk.Button, self.tk.Button)):
                    found.append(child)
                walk(child)

        walk(self.app.content)
        return found

    def button(self, label):
        return next(b for b in self.row_buttons() if str(b.cget("text")) == label)

    def test_the_json_button_is_gone(self):
        self.assertNotIn("打开选中 JSON", [str(b.cget("text")) for b in self.row_buttons()],
                         "第 68 期任务 6：这颗按钮删掉（要看 JSON 就点这一行）")

    def test_the_manual_button_is_the_highlighted_entry(self):
        manual = self.button("手动同步资产")
        self.assertEqual(str(manual.cget("style")), "Tokens.Primary.TButton",
                         "主动作要使用设计系统的高亮按钮")
        self.assertIn("刷新列表", [str(b.cget("text")) for b in manual.master.winfo_children()],
                      "「刷新列表」还留在这一行")

    def test_the_stage_config_sits_to_the_right_of_the_manual_button(self):
        manual = self.button("手动同步资产")
        self.assertIs(manual.master, self.app.stage_button.master, "两颗按钮在同一行")
        order = manual.master.winfo_children()
        self.assertLess(order.index(manual), order.index(self.app.stage_button),
                        "「阶段配置」要在「手动同步资产」右边")
        # 第 71 期任务 3：这一行是 FlowBar，它按「控件建出来的先后」从左往右排（见
        # responsive_ui.FlowBar.layout），所以「右边第一位」＝它在子控件清单里紧跟主动作，
        # 排在「刷新列表」前面。
        def slot(label):
            for index, child in enumerate(order):
                if hasattr(child, "cget") and str(child.cget("text")) == label:
                    return index
            self.fail("这一行里没有「%s」" % label)
        self.assertLess(slot("手动同步资产"), slot("阶段配置"))
        self.assertLess(slot("阶段配置"), slot("刷新列表"), "「刷新列表」排在它右边")
        self.assertLess(slot("刷新列表"), slot("分镜目录"))

    def test_refresh_sits_left_of_the_storyboard_folder(self):
        order = self.button("手动同步资产").master.winfo_children()
        labels = [str(child.cget("text")) for child in order if hasattr(child, "cget")]
        self.assertLess(labels.index("刷新列表"), labels.index("分镜目录"),
                        "「刷新列表」挪到「分镜目录」左边")


if __name__ == "__main__":
    unittest.main(verbosity=2)

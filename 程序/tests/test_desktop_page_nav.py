# -*- coding: utf-8 -*-
"""L4-U7d：10 视频生成页——输入框位置与其他页一致。

视频页过去收起统一状态栏（``desktop_page_nav._show_reset_page``），共享输入框整块下移
43px（盘点报告核实2）。本文件用真窗口量输入框工具行的实际纵坐标（T1），并守住
「统一状态栏与视频工作台底栏同显、底栏信息一条不少」（T2）。
"""
import os, sys, tempfile, unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from skip_reasons import PLATFORM_TKINTER
from ui_edges_support import (
    UiEdgeCase, PROGRAM, PAGE, make_adopted_project,
)
from widget_test_support import widget_list, widget_texts

WINDOW_SIZES = ("1280x800", "1024x680", "880x600")


class VideoPageStatusBarTests(UiEdgeCase):
    """视频页底栏与共享输入框的几何契约。"""

    def _desktop(self, td, size):
        """在指定窗口尺寸下打开桌面并载入一份已采用分镜的临时项目。"""
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        import desktop as desktop_module
        original = desktop_module.Desktop.choose_project
        desktop_module.Desktop.choose_project = lambda self: None
        self.addCleanup(setattr, desktop_module.Desktop, "choose_project", original)
        proj = make_adopted_project(td)
        win = self.tk.Tk(); win.geometry(size + "+0+0")
        def quiet_destroy():
            try:
                win.destroy()
            except Exception:
                pass
        self.addCleanup(quiet_destroy)
        from desktop import Desktop
        from local_video import open_studio
        d = Desktop(win, root=PROGRAM)
        d.root = proj
        d.studio = open_studio(proj)
        return d, win

    def _settle(self, win):
        for _ in range(4):
            win.update(); win.update_idletasks()

    def _toolbar_y(self, d):
        """共享输入框工具行（✦／＋／麦克风／模型下拉框／发送钮所在行）的纵坐标。"""
        return d.shared_input.icon_row.winfo_rooty()

    def test_input_toolbar_y_matches_script_page(self):
        """T1（对应 R1）：三档窗口下视频页输入框工具行的 y 与剧本准备页相同。"""
        for size in WINDOW_SIZES:
            with self.subTest(size=size), tempfile.TemporaryDirectory() as td:
                d, win = self._desktop(td, size)
                d.show(PAGE["script"]); self._settle(win)
                script_y = self._toolbar_y(d)
                d.show(PAGE["video"], video_mode="local"); self._settle(win)
                video_y = self._toolbar_y(d)
                self.assertEqual(video_y, script_y,
                                 "%s 下视频页输入框工具行比剧本准备页低 %dpx" % (size, video_y - script_y))

    def test_status_bar_and_workbench_footer_stay_visible(self):
        """T2（对应 R2）：统一状态栏与工作台底栏同显，底栏原有信息一条不少。"""
        with tempfile.TemporaryDirectory() as td:
            d, win = self._desktop(td, "1280x800")   # 无 Tk 时在 _desktop 里跳过
            from tkinter import ttk
            d.show(PAGE["video"], video_mode="local"); self._settle(win)
            self.assertTrue(d.status_bar.winfo_ismapped(), "视频页也要显示统一状态栏")
            footer = d.video.footer
            self.assertTrue(footer.winfo_ismapped(), "工作台底栏仍在窗口里")
            buttons = set(widget_texts(footer, (ttk.Button, self.tk.Button)))
            for text in ("手动制作视频", "播放视频", "查看全部版本", "本地设置",
                         "通过", "打开素材目录", "恢复任务编号", "打开视频目录",
                         "需修改", "批量生成勾选镜头", "删除勾选镜头",
                         "打开剪辑成片目录", "清空日志"):
                self.assertIn(text, buttons, "工作台底栏少了按钮：" + text)
            labels = set(widget_texts(footer, (ttk.Label, self.tk.Label)))
            for text in ("验收备注：", "动态日志"):
                self.assertIn(text, labels, "工作台底栏少了标签：" + text)
            progress = [w for w in widget_list(footer, ttk.Label)
                        if str(w.cget("textvariable")) == str(d.video.progress_text)]
            self.assertTrue(progress and progress[0].winfo_ismapped(),
                            "「SH0XX…」进度行不在窗口里")
            shared = [w for w in widget_list(footer, ttk.Label)
                      if str(w.cget("textvariable")) == str(d.video.shared_progress)]
            self.assertTrue(shared and shared[0].winfo_ismapped(),
                            "「本地：…／线上：…」进度行不在窗口里")
            self.assertTrue(d.video.note.winfo_ismapped(), "验收备注输入框不在窗口里")
            self.assertTrue(d.video.log.winfo_ismapped(), "动态日志内容框不在窗口里")


if __name__ == "__main__":
    unittest.main()

# -*- coding: utf-8 -*-
"""LEAK 资源轮回归：对话框销毁后提示回调撤销；14 页切换三轮资源有界。

A：三虎云提示所在的 BaseDialog 销毁时，标签先于窗口的 <Destroy> 处理被 Tcl 删除；
``_hint_stop`` 若仍无条件 configure 标签，就会留下
``invalid command name ".!basedialog...label"`` 的 swallowed 警告。
B：逐页切换两轮后，第三轮的控件数、待执行 after 任务数与线程数不得继续增长。
"""
import os
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

HERE = str(Path(__file__).resolve().parent)
PROGRAM = str(Path(HERE).parent)
sys.path.insert(0, PROGRAM)
sys.path.insert(0, HERE)
os.chdir(PROGRAM)

from skip_reasons import PLATFORM_TKINTER, PLATFORM_TK_DISPLAY


class _TkCase(unittest.TestCase):
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
        try:
            self.win = self.tk.Tk()
        except Exception:
            self.skipTest(PLATFORM_TK_DISPLAY)
        self.win.withdraw()
        self.addCleanup(self._destroy_root)
        import app_logging
        self.app_logging = app_logging

    def _destroy_root(self):
        try:
            self.win.destroy()
        except Exception:
            pass


class _FakePet:
    """Cloud 只读主窗口和贴片画布；不启动真正的宠物线程。"""

    def __init__(self, tk, win):
        self.win = win
        self.canvas = tk.Canvas(win, width=64, height=64)
        self.canvas.pack()
        self.paws = None

    def attending(self):
        return True


class _HintHost:
    """只带 CloudHintMixin 所需字段的宿主，用来单独验证 _hint_stop。"""

    def __init__(self, tk, parent):
        self.parent = parent
        self.hint = tk.Label(parent, text='')
        from ui.pet_cloud_hint import CloudHintState
        self.hint_state = CloudHintState(on=True, x=0)
        self.reply = None
        self.chat_row = None
        self.busy = False
        self.errors = []

    def _replies(self):
        return []


class HintTeardownTests(_TkCase):
    def _cloud(self):
        from ui.pet_cloud import Cloud
        cloud = Cloud(_FakePet(self.tk, self.win))
        self.addCleanup(self._destroy_cloud, cloud)
        return cloud

    @staticmethod
    def _destroy_cloud(cloud):
        try:
            if cloud.win is not None:
                cloud.win.destroy()
        except Exception:
            pass

    def test_cloud_dialog_destroy_revokes_hint_callback(self):
        cloud = self._cloud()
        cloud.show(pinned=True, hold=10000)
        self.win.update()
        job = cloud.hint_state.job
        self.assertIsNotNone(job, "对话框显示后应登记滚动提示定时器")
        before = len(self.app_logging.recent_swallowed())

        cloud.win.destroy()
        self.win.update()

        self.assertIsNone(cloud.win)
        self.assertIsNone(cloud.hint_state.job)
        self.assertIsNone(cloud.hint)
        self.assertNotIn(str(job), tuple(self.win.tk.call('after', 'info')))
        self.assertEqual(self.app_logging.recent_swallowed()[before:], [])

    def test_hint_stop_after_dialog_destroy_is_silent(self):
        from ui_widgets import BaseDialog
        dialog = BaseDialog(self.win, 'hint host', modal=False)
        self.addCleanup(dialog.close)
        dialog.withdraw()
        host = _HintHost(self.tk, dialog)
        dialog.close()
        self.win.update()
        before = len(self.app_logging.recent_swallowed())

        from ui import pet_cloud_hint
        pet_cloud_hint.CloudHintMixin._hint_stop(host)
        pet_cloud_hint.CloudHintMixin._hint_tick(host)

        self.assertEqual(self.app_logging.recent_swallowed()[before:], [])


def _count_after(win):
    return len(win.tk.call('after', 'info'))


def _count_widgets(widget):
    return 1 + sum(_count_widgets(child) for child in widget.winfo_children())


class PageSwitchGrowthTests(_TkCase):
    def _open_desktop(self, td):
        import ui_edges_support
        import white_model_service
        from desktop import Desktop
        from local_video import open_studio
        # 白模页会探测结果目录的写权限；把探测目录也放进临时项目，别碰真实用户目录。
        from env_test_support import patched_env
        patched_env(self, **{white_model_service.WORKSPACE_ENV: Path(td) / "white-model"})
        app = Path(td) / "app"
        app.mkdir()
        desktop = Desktop(self.win, root=app)
        self.addCleanup(desktop.cancel_timers)
        desktop.startup_controller.cancel()
        desktop.root = ui_edges_support.make_populated_project(td)
        desktop.studio = open_studio(desktop.root)
        return desktop

    def _measure(self, desktop, rounds):
        import desktop_page_registry
        table = []
        for index in range(rounds):
            started = time.monotonic()
            # 开机招呼是一次性的定时云朵，到点后才建对话框；不收回就会在慢机器上落进第 2／3 轮，被当成页面泄漏。
            pet = getattr(desktop, 'pet', None)
            if pet is not None:
                pet.cancel_greet()
            for page in range(len(desktop_page_registry.PAGES)):
                desktop.go_page(page)
                self.win.update()
            for _ in range(20):
                self.win.update()
                time.sleep(0.01)
            table.append({
                "round": index + 1,
                "children": len(self.win.winfo_children()),
                "widgets": _count_widgets(self.win),
                "after": _count_after(self.win),
                "threads": threading.active_count(),
                "seconds": round(time.monotonic() - started, 1),
            })
        return table

    def test_three_rounds_of_all_pages_stop_growing(self):
        with tempfile.TemporaryDirectory() as td:
            desktop = self._open_desktop(td)
            table = self._measure(desktop, 3)
        for row in table:
            sys.stderr.write("LEAK_PAGE_ROUND %r\n" % row)
        for key in ("children", "widgets", "after", "threads"):
            self.assertEqual(table[1][key], table[2][key],
                             "round 3 still grows %s: %r" % (key, table))


if __name__ == "__main__":
    unittest.main()

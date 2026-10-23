# -*- coding: utf-8 -*-
"""换页冻结绘制：旧页留在屏幕上，新页布局稳定后一次画出；超时与异常路径都会解冻。"""
import os, sys, tempfile, time, unittest
from pathlib import Path
from unittest import mock

HERE = str(Path(__file__).resolve().parents[1])
sys.path.insert(0, HERE)
sys.path.insert(0, str(Path(__file__).resolve().parent))
os.chdir(HERE)

from skip_reasons import PLATFORM_TKINTER, PLATFORM_WINDOWS_ONLY
from pet_state import PAGE_OF as PAGE


def visible(widget):
    import ctypes
    return bool(ctypes.windll.user32.IsWindowVisible(int(widget.winfo_id())))


class PaintFreezeTests(unittest.TestCase):
    def setUp(self):
        try:
            import tkinter as tk
        except Exception:
            self.skipTest(PLATFORM_TKINTER)
        if sys.platform != 'win32':
            self.skipTest(PLATFORM_WINDOWS_ONLY)
        self.tk = tk
        self.root = tk.Tk(); self.root.geometry('400x300+0+0')
        self.addCleanup(self.root.destroy)
        self.canvas = tk.Canvas(self.root); self.canvas.pack(fill='both', expand=True)
        self.root.update()

    def pump(self, seconds):
        end = time.perf_counter() + seconds
        while time.perf_counter() < end:
            self.root.update(); time.sleep(0.01)

    def test_freeze_hides_drawing_and_thaw_restores_it(self):
        from desktop_layout_resize import PaintFreeze
        freeze = PaintFreeze(self.canvas)
        self.assertTrue(freeze.freeze())
        self.assertFalse(visible(self.canvas), '冻结期间这块区域不上屏')
        self.assertFalse(freeze.freeze(), '重复冻结只算一次')
        self.assertTrue(freeze.thaw())
        self.assertTrue(visible(self.canvas))
        self.assertFalse(freeze.thaw())

    def test_freeze_times_out_by_itself(self):
        from desktop_layout_resize import PaintFreeze
        freeze = PaintFreeze(self.canvas, max_ms=30)
        freeze.freeze()
        self.pump(0.15)
        self.assertFalse(freeze.frozen)
        self.assertTrue(visible(self.canvas), '没人解冻也不能一直卡着画面')

    def test_unviewable_widget_is_left_alone(self):
        from desktop_layout_resize import PaintFreeze
        self.root.withdraw(); self.root.update()
        self.assertFalse(PaintFreeze(self.canvas).freeze())

    def test_thaw_keeps_a_widget_tk_unmapped_meanwhile_hidden(self):
        from desktop_layout_resize import PaintFreeze
        freeze = PaintFreeze(self.canvas)
        freeze.freeze()
        self.canvas.pack_forget(); self.root.update_idletasks()
        freeze.thaw()
        self.assertFalse(visible(self.canvas), '打开重画不能把 Tk 已收起的控件又亮出来')


class PageSwitchFreezeTests(unittest.TestCase):
    def open_desktop(self, td):
        import tkinter as tk
        import test_ui_edges
        from desktop import Desktop
        from local_video import open_studio
        win = tk.Tk(); win.geometry('1200x800+0+0')
        self.addCleanup(win.destroy)
        app = Path(td) / 'app'; app.mkdir()
        d = Desktop(win, root=app)
        self.addCleanup(d.cancel_timers)
        d.startup_controller.cancel()
        d.root = test_ui_edges.make_populated_project(td)
        d.studio = open_studio(d.root)
        win.update()
        return win, d

    def test_page_switch_stays_frozen_until_layout_settles(self):
        try:
            import tkinter  # noqa: F401
        except Exception:
            self.skipTest(PLATFORM_TKINTER)
        if sys.platform != 'win32':
            self.skipTest(PLATFORM_WINDOWS_ONLY)
        with tempfile.TemporaryDirectory() as td:
            win, d = self.open_desktop(td)
            d.show(PAGE['assets']); win.update()
            self.assertTrue(visible(d.canvas))
            d.show(PAGE['script'])
            self.assertFalse(visible(d.canvas), '拆旧建新期间旧页像素留在屏幕上，新页半成品不上屏')
            win.update_idletasks()
            self.assertFalse(d._page_paint_freeze.frozen, '布局稳定后立即解冻，不等超时')
            self.assertTrue(visible(d.canvas))
            self.assertTrue(d.content.winfo_ismapped())

    def test_failed_page_build_thaws(self):
        try:
            import tkinter  # noqa: F401
        except Exception:
            self.skipTest(PLATFORM_TKINTER)
        if sys.platform != 'win32':
            self.skipTest(PLATFORM_WINDOWS_ONLY)
        with tempfile.TemporaryDirectory() as td:
            win, d = self.open_desktop(td)
            with mock.patch.object(d, 'asset_page', side_effect=RuntimeError('坏页')), \
                 mock.patch.object(d.notifier, 'error'):
                d.go(PAGE['assets'])
            self.assertFalse(d._page_paint_freeze.frozen)
            self.assertTrue(visible(d.canvas))

    def test_page_switch_repaints_sidebar_once_settled(self):
        try:
            import tkinter  # noqa: F401
        except Exception:
            self.skipTest(PLATFORM_TKINTER)
        if sys.platform != 'win32':
            self.skipTest(PLATFORM_WINDOWS_ONLY)
        import desktop_layout
        with tempfile.TemporaryDirectory() as td:
            win, d = self.open_desktop(td)
            d.show(PAGE['assets']); win.update()
            with mock.patch.object(desktop_layout, 'repaint_area') as repaint:
                d.show(PAGE['script']); d.show(PAGE['video'])
                repaint.assert_not_called()
                win.update_idletasks()
            repaint.assert_called_once_with(d.sidebar_canvas)
            self.assertIsNone(d._sidebar_before_page, '落定后不再挂着上一轮的侧栏快照')

    def test_sidebar_shift_during_page_switch_is_logged(self):
        try:
            import tkinter  # noqa: F401
        except Exception:
            self.skipTest(PLATFORM_TKINTER)
        if sys.platform != 'win32':
            self.skipTest(PLATFORM_WINDOWS_ONLY)
        import desktop_layout
        with tempfile.TemporaryDirectory() as td:
            win, d = self.open_desktop(td)
            d.show(PAGE['assets']); win.update()
            d._sidebar_before_page = ((0.0, 0.5), 'stale', -1, 0, 0)
            with self.assertLogs(desktop_layout.LOGGER, level='INFO') as logs:
                d.thaw_page_paint()
            self.assertIn('侧栏几何变化', logs.output[0])
            d._sidebar_before_page = d._sidebar_geometry()
            with self.assertNoLogs(desktop_layout.LOGGER, level='INFO'):
                d.thaw_page_paint()

    def test_repaint_area_skips_unviewable_widget(self):
        try:
            import tkinter as tk
        except Exception:
            self.skipTest(PLATFORM_TKINTER)
        from desktop_layout_resize import repaint_area
        root = tk.Tk(); self.addCleanup(root.destroy)
        canvas = tk.Canvas(root); canvas.pack()
        root.withdraw(); root.update()
        self.assertFalse(repaint_area(canvas))


if __name__ == '__main__':
    unittest.main()

# -*- coding: utf-8 -*-
"""「页面第一次画完」按页耗时指标：从 show() 开始量到 Tk 空闲布局完成。"""
import inspect
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

HERE = str(Path(__file__).resolve().parents[1])
sys.path.insert(0, HERE)
sys.path.insert(0, str(Path(__file__).resolve().parent))
os.chdir(HERE)

from skip_reasons import PLATFORM_TKINTER, PLATFORM_TK_DISPLAY

import app_logging


class PagePaintMetricTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import tkinter as tk
            cls.tk = tk
        except Exception:
            cls.tk = None

    def _make_desktop(self, td):
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        from desktop import Desktop
        try:
            window = self.tk.Tk()
        except self.tk.TclError as exc:
            self.skipTest(PLATFORM_TK_DISPLAY + ': ' + str(exc))
        window.withdraw()
        app = Path(td) / 'app'
        app.mkdir()
        (app / 'config.json').write_text(json.dumps({
            'downloads_root': str(Path(td) / 'downloads'),
        }), encoding='utf-8')
        (app / 'projects.json').write_text(json.dumps({
            'active': None, 'projects': [],
        }), encoding='utf-8')
        desktop = Desktop(window, root=app)
        desktop.startup_controller.cancel()
        return window, desktop

    def _cleanup(self, window, desktop):
        if desktop is not None:
            try:
                desktop.cancel_timers()
            except Exception:
                pass
        if window is not None:
            try:
                window.destroy()
            except Exception:
                pass

    def test_page_switch_records_paint_metric_with_page_key(self):
        from desktop import PAGE
        app_logging._metrics.clear()
        window = desktop = None
        with tempfile.TemporaryDirectory(prefix='page-paint-metric-') as td:
            window, desktop = self._make_desktop(td)
            desktop.show(PAGE['script_structure'])
            window.update_idletasks()
            window.update()
        snap = app_logging.metrics_snapshot()
        self.assertIn('page.paint.script_structure', snap)
        self.assertGreaterEqual(snap['page.paint.script_structure']['count'], 1)
        self._cleanup(window, desktop)

    def test_rapid_switch_records_only_last_page(self):
        from desktop import PAGE
        app_logging._metrics.clear()
        window = desktop = None
        with tempfile.TemporaryDirectory(prefix='page-paint-rapid-') as td:
            window, desktop = self._make_desktop(td)
            desktop.show(PAGE['script'])
            desktop.show(PAGE['script_structure'])
            window.update_idletasks()
            window.update()
        snap = app_logging.metrics_snapshot()
        self.assertIn('page.paint.script_structure', snap)
        self.assertNotIn('page.paint.script', snap)
        self._cleanup(window, desktop)

    def test_destroyed_window_measurement_is_silent(self):
        app_logging._metrics.clear()
        window = desktop = None
        with tempfile.TemporaryDirectory(prefix='page-paint-destroy-') as td:
            window, desktop = self._make_desktop(td)
            window.destroy()
            # 已销毁窗口上再调度/作废测量必须静默，不向调用方抛 TclError。
            app_logging.begin_page_paint(desktop, 'page.paint.script')
            app_logging._schedule_page_paint(desktop, 1, 0.0, 'page.paint.script')
        self._cleanup(None, desktop)

    def test_record_elapsed_preserves_existing_shape(self):
        app_logging._metrics.clear()
        app_logging.record_elapsed('page.paint.assets', 1200.0, 1000.0)
        row = app_logging.metrics_snapshot()['page.paint.assets']
        self.assertEqual(row['count'], 1)
        self.assertEqual(row['slow'], 1)

    def test_page_paint_decorator_preserves_show_identity(self):
        from desktop import Desktop
        self.assertEqual(Desktop.show.__name__, 'show')
        self.assertIn('self.fit_content()', inspect.getsource(Desktop.show))
        self.assertTrue(hasattr(Desktop.show, '__wrapped__'))


if __name__ == '__main__':
    unittest.main()

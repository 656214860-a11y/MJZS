# -*- coding: utf-8 -*-
"""「页面第一次画完」按页耗时指标：从 show() 开始量到 Tk 空闲布局完成。"""
import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

HERE = str(Path(__file__).resolve().parents[1])
sys.path.insert(0, HERE)
sys.path.insert(0, str(Path(__file__).resolve().parent))
os.chdir(HERE)

from skip_reasons import PLATFORM_TKINTER, PLATFORM_TK_DISPLAY

import infra.app_logging as app_logging


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
        # R3008：每实例首个画完的页记 .boot 相位名。
        self.assertIn('page.paint.script_structure.boot', snap)
        self.assertGreaterEqual(snap['page.paint.script_structure.boot']['count'], 1)
        self._cleanup(window, desktop)

    def test_page_switch_records_fit_breakdown_counters(self):
        """R2990：首帧计时窗内的布局等待 polls 与布局轮次记入 counters，供首帧分解。"""
        from desktop import PAGE
        app_logging._metrics.clear()
        app_logging._counters.clear()
        window = desktop = None
        with tempfile.TemporaryDirectory(prefix='page-paint-fit-') as td:
            window, desktop = self._make_desktop(td)
            desktop.show(PAGE['script_structure'])
            window.update_idletasks()
            window.update()
            for _ in range(30):
                window.update()
        snap = app_logging.metrics_snapshot()
        counters = snap.get('counters') or {}
        self.assertIn('page.paint.script_structure.boot.fitwaits', counters)
        self.assertIn('page.paint.script_structure.boot.fitpasses', counters)
        self.assertGreaterEqual(counters['page.paint.script_structure.boot.fitpasses'], 0)
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
        self.assertIn('page.paint.script_structure.boot', snap)
        self.assertNotIn('page.paint.script', snap)
        self.assertNotIn('page.paint.script.boot', snap)
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
            # 窗口已销毁：不得记下一条虚假的绘制耗时。
            self.assertNotIn('page.paint.script', app_logging.metrics_snapshot())
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
        self.assertTrue(hasattr(Desktop.show, '__wrapped__'))

    def test_page_paint_waits_for_layout_without_clearing_other_idle_jobs(self):
        """REQ-S01-22 回归（SLOWPAGE）：等布局时只登记定时器让位，不在 after_idle 里跑别人的空闲回调。

        首次显示的项目副本上指标曾记两次（394ms 与 1055ms）：等待布局的 after_idle 回调
        被重排后，在同一趟空闲处理里把页面自己排好的建页工作一并跑掉了。
        """
        window = desktop = None
        with tempfile.TemporaryDirectory(prefix='page-paint-wait-') as td:
            window, desktop = self._make_desktop(td)
            desktop._fit_pending = True
            other_idle = []
            job = None
            original_record = app_logging.record_elapsed
            app_logging.record_elapsed = lambda name, elapsed, *a, **k: other_idle.append(('recorded', name))
            try:
                app_logging.begin_page_paint(desktop, 'page.paint.script')
                job = desktop._page_paint_job
                window.after_idle(lambda: other_idle.append(('other', 'page build')))
                for _ in range(20):
                    window.update_idletasks()
                self.assertIn(('other', 'page build'), other_idle,
                              '测量等待期间不应阻止同一解释器里其他已排队的空闲工作')
                self.assertNotIn('page.paint.script', [name for kind, name in other_idle if kind == 'recorded'])
                self.assertTrue(job is not None)
            finally:
                app_logging.record_elapsed = original_record
        self._cleanup(window, desktop)

    def test_page_paint_records_once_per_show(self):
        """REQ-S01-22：一次 show() 只记一条 page.paint.*，重复测量不能把同一页记两次。"""
        from desktop import PAGE
        app_logging._metrics.clear()
        window = desktop = None
        with tempfile.TemporaryDirectory(prefix='page-paint-once-') as td:
            window, desktop = self._make_desktop(td)
            desktop.show(PAGE['script'])
            desktop._fit_pending = True
            window.update()
            window.update_idletasks()
            window.update()
        snap = app_logging.metrics_snapshot()
        self.assertEqual(snap.get('page.paint.script.boot', {}).get('count'), 1)
        self._cleanup(window, desktop)

    def test_second_paint_uses_steady_metric_name(self):
        """R3008：只有首个画完的页带 .boot；之后的翻页回到稳态指标名。"""
        from desktop import PAGE
        app_logging._metrics.clear()
        window = desktop = None
        with tempfile.TemporaryDirectory(prefix='page-paint-steady-') as td:
            window, desktop = self._make_desktop(td)
            desktop.show(PAGE['script'])
            deadline = time.perf_counter() + 8
            while time.perf_counter() < deadline:
                window.update()
                if 'page.paint.script.boot' in app_logging.metrics_snapshot():
                    break
                time.sleep(0.005)
            desktop.show(PAGE['script_structure'])
            deadline = time.perf_counter() + 8
            while time.perf_counter() < deadline:
                window.update()
                if 'page.paint.script_structure' in app_logging.metrics_snapshot():
                    break
                time.sleep(0.005)
        snap = app_logging.metrics_snapshot()
        self.assertIn('page.paint.script.boot', snap)
        self.assertIn('page.paint.script_structure', snap)
        self.assertNotIn('page.paint.script_structure.boot', snap)
        self._cleanup(window, desktop)


if __name__ == '__main__':
    unittest.main()

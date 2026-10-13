# -*- coding: utf-8 -*-
"""切页提速：侧栏点回来整页复用（CACHED_PAGES），同页刷新／换项目照旧重建。"""
import os, sys, tempfile, unittest
from unittest import mock
from pathlib import Path

HERE = str(Path(__file__).resolve().parents[1])
sys.path.insert(0, HERE)
sys.path.insert(0, str(Path(__file__).resolve().parent))
os.chdir(HERE)

from skip_reasons import PLATFORM_TKINTER
from pet_state import PAGE_OF as PAGE


class PageCacheTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import tkinter as tk
            cls.tk = tk
        except Exception:
            cls.tk = None

    def open_desktop(self, td):
        import test_ui_edges
        from desktop import Desktop
        from local_video import open_studio
        win = self.tk.Tk(); win.withdraw()
        self.addCleanup(win.destroy)
        app = Path(td) / 'app'; app.mkdir()
        d = Desktop(win, root=app)
        # 缓存测试自行装入项目，不运行首帧后的新建／今日项目选择流程。
        d.startup_controller.cancel()
        d.root = test_ui_edges.make_populated_project(td)
        d.studio = open_studio(d.root)
        return win, d

    def holder(self, d):
        return d._page_cache[PAGE['storyboard']]['holder']

    def test_nav_back_reuses_page_and_restores_stage_button(self):
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        with tempfile.TemporaryDirectory() as td:
            win, d = self.open_desktop(td)
            d.go_page(PAGE['storyboard']); win.update_idletasks()
            first, button = self.holder(d), d.stage_button
            self.assertIsNotNone(button)
            d.go_page(PAGE['assets']); win.update_idletasks()
            self.assertTrue(first.winfo_exists())
            self.assertFalse(first.winfo_ismapped())
            d.go_page(PAGE['storyboard']); win.update_idletasks()
            self.assertIs(self.holder(d), first)
            self.assertIs(d.stage_button, button)

    def test_same_page_refresh_and_plain_show_rebuild(self):
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        with tempfile.TemporaryDirectory() as td:
            win, d = self.open_desktop(td)
            d.go_page(PAGE['storyboard']); win.update_idletasks()
            first = self.holder(d)
            d.show(PAGE['storyboard']); win.update_idletasks()
            self.assertFalse(first.winfo_exists())
            second = self.holder(d)
            d.go_page(PAGE['assets']); d.show(PAGE['storyboard']); win.update_idletasks()
            self.assertFalse(second.winfo_exists())

    def test_project_change_drops_cache(self):
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        import test_ui_edges
        with tempfile.TemporaryDirectory() as td, tempfile.TemporaryDirectory() as other:
            win, d = self.open_desktop(td)
            d.go_page(PAGE['storyboard']); d.go_page(PAGE['assets'])
            first = self.holder(d)
            d.root = test_ui_edges.make_populated_project(other)
            d.go_page(PAGE['storyboard']); win.update_idletasks()
            self.assertFalse(first.winfo_exists())
            self.assertEqual(d._page_cache[PAGE['storyboard']]['root'], d.root)

    def test_hidden_page_ignores_clicks_on_other_pages(self):
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        with tempfile.TemporaryDirectory() as td:
            win, d = self.open_desktop(td)
            win.deiconify()
            d.go_page(PAGE['storyboard']); d.go_page(PAGE['assets']); win.update()
            d.status.set('别的页')
            d.content.event_generate('<Button-1>', x=1, y=1); win.update()
            self.assertEqual(d.status.get(), '别的页')

    def test_nav_highlight_is_drawn_before_page_builds(self):
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        with tempfile.TemporaryDirectory() as td:
            win, d = self.open_desktop(td)
            d.go_page(PAGE['script'])
            seen = []
            real = d.go
            d.go = lambda index, **kw: (seen.append(str(d.nav[index].cget('style'))), real(index, **kw))
            d.go_page(PAGE['assets'])
            self.assertEqual(seen, ['Selected.Nav.TButton'])

    def open_watched_storyboard(self, td):
        """截取扫描入口与结果应用定时器，不启动实际文件监听线程。"""
        import tk_timers
        captured = {}
        real_repeat = tk_timers.repeat
        def watch(widget, snapshot, refresh, interval=1500):
            captured['refresh'] = refresh
            return mock.Mock()
        def repeat(widget, interval, callback):
            if callback.__name__ == 'apply_background_catalog':
                captured['apply'] = callback
                return mock.Mock()
            return real_repeat(widget, interval, callback)
        for name, replacement in (('watch_changes_async', watch), ('repeat', repeat)):
            patcher = mock.patch.object(tk_timers, name, replacement)
            patcher.start(); self.addCleanup(patcher.stop)
        win, d = self.open_desktop(td)
        d.go_page(PAGE['storyboard']); win.update_idletasks()
        self.assertEqual(set(captured), {'refresh', 'apply'})
        return win, d, captured['refresh'], captured['apply']

    def queue_background_catalog(self, refresh):
        """执行真正的扫描入口并入队；应用回调仍由测试单独驱动。"""
        with mock.patch('storyboard_files.threading.Thread') as worker:
            worker.return_value.start.side_effect = lambda: worker.call_args.kwargs['target']()
            refresh()
            worker.assert_called_once()
            worker.return_value.start.assert_called_once_with()

    def tree_rows(self, holder):
        from tkinter import ttk
        pending, rows = [holder], set()
        while pending:
            widget = pending.pop(); pending.extend(widget.winfo_children())
            if isinstance(widget, ttk.Treeview):
                rows.update(widget.get_children())
        return rows

    def test_hidden_page_file_change_leaves_visible_page_alone(self):
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        with tempfile.TemporaryDirectory() as td:
            win, d, refresh, apply = self.open_watched_storyboard(td)
            holder = self.holder(d)
            d.go_page(PAGE['assets']); win.update_idletasks()
            self.assertIsNot(d.content, holder)
            script = d.root / 'writing' / '第2集.md'
            script.write_text('# 第2集\n新剧本内容。', encoding='utf-8')
            d.status.set('用户在别的页')
            self.queue_background_catalog(refresh)
            self.assertNotIn(str(script), self.tree_rows(holder), '扫描完成后应等待 Tk 应用结果')
            apply()
            self.assertIn(str(script), self.tree_rows(holder), '隐藏页应应用真正的目录变更')
            self.assertEqual(d.status.get(), '用户在别的页')
            d.go_page(PAGE['storyboard'])
            self.assertIs(self.holder(d), holder)
            self.assertIn(str(script), self.tree_rows(holder), '切回缓存页应立即看到更新后的列表')

    def assert_background_failure_status(self, method, expected):
        with tempfile.TemporaryDirectory() as td:
            win, d, refresh, apply = self.open_watched_storyboard(td)
            holder = self.holder(d)
            d.go_page(PAGE['assets']); win.update_idletasks()
            with mock.patch('storyboard_files.StoryboardPageController.' + method,
                            side_effect=OSError('目录暂不可读')) as failing:
                for visible in (False, True):
                    with self.subTest(visible=visible):
                        if visible:
                            d.go_page(PAGE['storyboard'])
                        d.status.set('当前页状态')
                        self.queue_background_catalog(refresh)
                        apply()
                        if visible:
                            self.assertEqual(d.status.get(), expected + '目录暂不可读')
                        else:
                            self.assertEqual(d.status.get(), '当前页状态')
                        self.assertTrue(holder.winfo_exists())
                        self.assertIs(self.holder(d), holder)
                self.assertEqual(failing.call_count, 2, '两次扫描结果都必须实际消费')

    def test_hidden_page_scan_failure_leaves_visible_status_alone(self):
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        self.assert_background_failure_status('refresh_catalogs', '分镜目录刷新失败，将在下次文件变动后重试：')

    def test_hidden_page_apply_failure_leaves_visible_status_alone(self):
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        self.assert_background_failure_status('apply_catalogs', '分镜目录结果已过期，将在下次文件变动后重试：')


if __name__ == '__main__':
    unittest.main()

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
        import ui_edges_support
        from desktop import Desktop
        from local_video import open_studio
        win = self.tk.Tk(); win.withdraw()
        self.addCleanup(win.destroy)
        app = Path(td) / 'app'; app.mkdir()
        d = Desktop(win, root=app)
        self.addCleanup(d.cancel_timers)
        # 缓存测试自行装入项目，不运行首帧后的新建／今日项目选择流程。
        d.startup_controller.cancel()
        d.root = ui_edges_support.make_populated_project(td)
        d.studio = open_studio(d.root)
        return win, d

    def holder(self, d):
        return d._page_cache[PAGE['storyboard']]['holder']

    def test_nav_back_reuses_page_and_restores_stage_button(self):
        """R2942：页面级「阶段配置」按钮已删除——换页回来只验页面缓存与共享输入框复用。"""
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        with tempfile.TemporaryDirectory() as td:
            win, d = self.open_desktop(td)
            d.go_page(PAGE['storyboard']); win.update_idletasks()
            first, shared = self.holder(d), d.shared_input
            self.assertIsNone(d.stage_button)
            d.go_page(PAGE['assets']); win.update_idletasks()
            self.assertTrue(first.winfo_exists())
            self.assertFalse(first.winfo_ismapped())
            d.go_page(PAGE['storyboard']); win.update_idletasks()
            self.assertIs(self.holder(d), first)
            self.assertIs(d.shared_input, shared, '共享输入框跨页复用同一实例')

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
        import ui_edges_support
        with tempfile.TemporaryDirectory() as td, tempfile.TemporaryDirectory() as other:
            win, d = self.open_desktop(td)
            d.go_page(PAGE['storyboard']); win.update_idletasks(); d.go_page(PAGE['assets']); win.update_idletasks()
            first = self.holder(d)
            d.root = ui_edges_support.make_populated_project(other)
            d.go_page(PAGE['storyboard']); win.update_idletasks()
            self.assertFalse(first.winfo_exists())
            self.assertEqual(d._page_cache[PAGE['storyboard']]['root'], d.root)

    def test_hidden_page_ignores_clicks_on_other_pages(self):
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        with tempfile.TemporaryDirectory() as td:
            win, d = self.open_desktop(td)
            win.deiconify()
            d.go_page(PAGE['storyboard']); win.update_idletasks(); d.go_page(PAGE['assets']); win.update()
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
            win.update_idletasks()
            self.assertEqual(seen, ['Selected.Nav.TButton'])

    def test_rapid_navigation_builds_only_last_request(self):
        if self.tk is None:self.skipTest(PLATFORM_TKINTER)
        with tempfile.TemporaryDirectory() as td:
            win, d = self.open_desktop(td)
            with mock.patch.object(d, 'go') as build:
                for page in (1, 2, 4, 3, 1):d.go_page(page)
                build.assert_not_called()
                self.assertEqual(str(d.nav[1].cget('style')), 'Selected.Nav.TButton')
                win.update_idletasks()
                build.assert_called_once_with(1, video_mode=None)

    def test_structure_cache_reuses_and_invalidates_on_content_change(self):
        if self.tk is None:self.skipTest(PLATFORM_TKINTER)
        from script_workspace_service import script_structure_documents
        with tempfile.TemporaryDirectory() as td:
            win, d = self.open_desktop(td)
            page = PAGE['script_structure']
            directory = script_structure_documents(d.root).source_directory
            directory.mkdir(parents=True, exist_ok=True)
            source = directory / '项目剧本.md'
            source.write_text('第一场\n人物走进房间。', encoding='utf-8')
            d.go_page(page); win.update_idletasks()
            first = d.content
            d.go_page(PAGE['storyboard']); win.update_idletasks()
            d.go_page(page); win.update_idletasks()
            self.assertIs(d.content, first)
            d.go_page(PAGE['storyboard']); win.update_idletasks()
            docs = script_structure_documents(d.root)
            source = docs.source_documents[0]
            source.write_text(source.read_text(encoding='utf-8')+'\n修改内容', encoding='utf-8')
            d.go_page(page); win.update_idletasks()
            self.assertFalse(first.winfo_exists())
            self.assertIsNot(d.content, first)

    def test_navigation_cancels_old_stage_announcement(self):
        if self.tk is None:self.skipTest(PLATFORM_TKINTER)
        with tempfile.TemporaryDirectory() as td:
            win, d = self.open_desktop(td)
            # R1948：没有待办时换页不挂播报；这条用例只验「连续换页只播最后一页」，先让每页都有待办。
            with mock.patch.object(d, 'pet_stage_wanted', return_value=True),                     mock.patch.object(d, 'pet_at_stage') as announce, mock.patch.object(win, 'after', wraps=win.after) as scheduled:
                d.go_page(PAGE['script_structure']); win.update_idletasks()
                old_job = d._pet_stage_job
                old_speak = next(call.args[1] for call in scheduled.call_args_list
                                 if len(call.args)>1 and getattr(call.args[1], '__name__', '')=='speak')
                d.go_page(PAGE['storyboard']); win.update_idletasks()
                self.assertNotIn(old_job, win.tk.call('after', 'info'))
                current_job = d._pet_stage_job
                current_speak = [call.args[1] for call in scheduled.call_args_list
                                 if len(call.args)>1 and getattr(call.args[1], '__name__', '')=='speak'][-1]
                win.after_cancel(current_job)
                old_speak()
                announce.assert_not_called()
                current_speak()
                announce.assert_called_once_with(PAGE['storyboard'])

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
        with mock.patch('storyboard_files.threading.Thread') as worker:
            worker.return_value.start.side_effect = lambda: worker.call_args.kwargs['target']()
            d.go_page(PAGE['storyboard']); win.update_idletasks()
        captured['apply']()
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
            win.update_idletasks()
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
                            win.update_idletasks()
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

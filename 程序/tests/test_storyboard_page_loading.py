"""初步分镜的首次加载与异步结果生命周期。"""
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

import test_page_cache


class StoryboardPageLoadingTests(unittest.TestCase):
    setUpClass = classmethod(test_page_cache.PageCacheTests.setUpClass.__func__)
    open_desktop = test_page_cache.PageCacheTests.open_desktop
    holder = test_page_cache.PageCacheTests.holder
    tree_rows = test_page_cache.PageCacheTests.tree_rows

    def pump(self, win, predicate):
        deadline = time.monotonic() + 5
        while not predicate() and time.monotonic() < deadline:
            win.update()
            time.sleep(.005)
        self.assertTrue(predicate(), '后台结果应完成回填')

    def test_initial_catalog_scan_never_runs_on_ui_thread(self):
        from storyboard_page_controller import StoryboardPageController
        from pet_state import PAGE_OF
        original = StoryboardPageController.refresh_catalogs
        calls = []
        def scan(controller):
            calls.append(threading.get_ident())
            return original(controller)
        with tempfile.TemporaryDirectory() as td:
            win, d = self.open_desktop(td)
            self.addCleanup(d.cancel_timers)
            with mock.patch.object(StoryboardPageController, 'refresh_catalogs', scan):
                d.show(PAGE_OF['storyboard'])
                holder = self.holder(d)
                self.pump(win, lambda: bool(self.tree_rows(holder)))
            self.assertTrue(calls)
            self.assertNotIn(threading.get_ident(), calls)

    def test_manual_refresh_rejects_an_older_initial_result(self):
        from pet_state import PAGE_OF
        import tk_timers
        captured = {}
        real_repeat = tk_timers.repeat
        def repeat(widget, interval, callback):
            if callback.__name__ == 'apply_background_catalog':
                captured['apply'] = callback
                return lambda: None
            return real_repeat(widget, interval, callback)
        with tempfile.TemporaryDirectory() as td:
            win, d = self.open_desktop(td)
            self.addCleanup(d.cancel_timers)
            with mock.patch('storyboard_files.watch_files'), mock.patch.object(tk_timers, 'repeat', repeat), mock.patch('storyboard_files.threading.Thread') as worker:
                d.show(PAGE_OF['storyboard'])
                worker.call_args.kwargs['target']()  # 旧扫描已完成，但尚未应用
                script = d.root / 'writing' / '第2集.md'
                script.write_text('# 第2集\n新的剧本内容', encoding='utf-8')
                holder = self.holder(d)
                pending = [holder]
                while pending:
                    widget = pending.pop()
                    pending.extend(widget.winfo_children())
                    if 'text' in widget.keys() and str(widget.cget('text')) == '刷新列表':
                        widget.invoke()
                        break
                else:
                    self.fail('缺少刷新入口')
                self.assertIn(str(script), self.tree_rows(holder))
                captured['apply']()
                self.assertIn(str(script), self.tree_rows(holder), '迟到快照不能覆盖手动刷新')

    def test_batched_rows_keep_order_selection_and_cancel_old_fill(self):
        from tkinter import ttk
        from storyboard_table_ui import insert_entries
        win = self.tk.Tk(); win.withdraw()
        self.addCleanup(win.destroy)
        tree = ttk.Treeview(win, columns=('file', 'content', 'time', 'location'))
        root = Path(tempfile.gettempdir()).resolve()
        entries = [dict(path=root / f'EP{i:03}.md', title=str(i), preview='预览', created=1) for i in range(91)]
        callbacks, complete = [], []
        def schedule(delay, callback):
            callbacks.append(callback)
            return str(len(callbacks))
        with mock.patch.object(tree, 'after', schedule), mock.patch.object(tree, 'after_cancel') as cancel, mock.patch('storyboard_table_ui.content_preview', side_effect=AssertionError('不应在UI读取预览')), mock.patch('storyboard_table_ui.has_synced_assets', side_effect=AssertionError('无同步列无需探测文件')):
            insert_entries(tree, root, entries, batch_size=40, on_complete=lambda: complete.append('first'))
            self.assertEqual(len(tree.get_children()), 40)
            self.assertEqual(len(callbacks), 1)
            callbacks.pop(0)()
            self.assertEqual(len(tree.get_children()), 80)
            callbacks.pop(0)()
            expected = tuple(str(row['path']) for row in entries)
            self.assertEqual(tree.get_children(), expected)
            self.assertEqual(complete, ['first'])
            selected = expected[8]
            tree.selection_set(selected); tree.focus(selected)
            insert_entries(tree, root, entries[::-1], batch_size=40)
            self.assertEqual(len(tree.get_children()), 91, '刷新期间保留旧行，避免清空闪烁')
            while callbacks:callbacks.pop(0)()
            self.assertEqual(tree.get_children(), expected[::-1])
            self.assertEqual(tree.selection(), (selected,))
            self.assertEqual(tree.focus(), selected)
            insert_entries(tree, root, entries, batch_size=40, on_complete=lambda: complete.append('stale'))
            stale = callbacks.pop(0)
            insert_entries(tree, root, entries[:1], batch_size=40, on_complete=lambda: complete.append('new'))
            stale()
            self.assertEqual(tree.get_children(), expected[:1])
            self.assertEqual(complete, ['first', 'new'])
            cancel.assert_called()
            insert_entries(tree, root, entries, batch_size=40)
            cancel.reset_mock()
            tree.destroy()
            cancel.assert_called_once()

    def test_late_result_cannot_apply_after_destroy_or_project_switch(self):
        from pet_state import PAGE_OF
        from storyboard_page_controller import StoryboardPageController
        import tk_timers
        for change in ('destroy', 'project'):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as td:
                win, d = self.open_desktop(td)
                self.addCleanup(d.cancel_timers)
                captured = {}
                real_repeat = tk_timers.repeat
                def repeat(widget, interval, callback):
                    if callback.__name__ == 'apply_background_catalog':
                        captured['apply'] = callback
                        return lambda: None
                    return real_repeat(widget, interval, callback)
                with mock.patch('storyboard_files.watch_files'), mock.patch.object(tk_timers, 'repeat', repeat), mock.patch('storyboard_files.threading.Thread') as worker:
                    d.show(PAGE_OF['storyboard'])
                    worker.call_args.kwargs['target']()
                    if change == 'destroy':
                        self.holder(d).destroy()
                    else:
                        d.root = Path(td) / 'another-project'
                    d.status.set('当前页面状态')
                    with mock.patch.object(StoryboardPageController, 'apply_catalogs') as apply:
                        captured['apply']()
                    apply.assert_not_called()
                    self.assertEqual(d.status.get(), '当前页面状态')

    def test_initial_error_is_visible_and_manual_refresh_recovers(self):
        from pet_state import PAGE_OF
        from storyboard_page_controller import StoryboardPageController
        import tk_timers
        captured = {}
        real_repeat = tk_timers.repeat
        def repeat(widget, interval, callback):
            if callback.__name__ == 'apply_background_catalog':
                captured['apply'] = callback
                return lambda: None
            return real_repeat(widget, interval, callback)
        with tempfile.TemporaryDirectory() as td:
            win, d = self.open_desktop(td)
            self.addCleanup(d.cancel_timers)
            with mock.patch('storyboard_files.watch_files'), mock.patch.object(tk_timers, 'repeat', repeat), mock.patch('storyboard_files.threading.Thread') as worker:
                d.show(PAGE_OF['storyboard'])
                with mock.patch.object(StoryboardPageController, 'refresh_catalogs', side_effect=TypeError('测试读取失败')):
                    worker.call_args.kwargs['target']()
                captured['apply']()
                labels, refresh = [], None
                pending = [self.holder(d)]
                while pending:
                    widget = pending.pop(); pending.extend(widget.winfo_children())
                    if 'textvariable' in widget.keys() and widget.cget('textvariable'):
                        labels.append(str(win.getvar(widget.cget('textvariable'))))
                    if 'text' in widget.keys() and str(widget.cget('text')) == '刷新列表':
                        refresh = widget
                self.assertIn('文件列表加载失败，请点击「刷新列表」重试', labels)
                self.assertIn('测试读取失败', d.status.get())
                self.assertIsNotNone(refresh)
                refresh.invoke()
                self.assertTrue(self.tree_rows(self.holder(d)))


if __name__ == '__main__':
    unittest.main()

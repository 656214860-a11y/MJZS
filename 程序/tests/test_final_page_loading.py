"""定稿目录首次后台扫描、过期结果与页面生命周期。"""
import json
import os
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import test_final_viewer
import test_page_cache
from infra.pet_state import PAGE_OF
from skip_reasons import PLATFORM_TKINTER


class FinalPageLoadingTests(unittest.TestCase):
    setUpClass = classmethod(test_page_cache.PageCacheTests.setUpClass.__func__)
    open_desktop = test_page_cache.PageCacheTests.open_desktop

    def setUp(self):
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.win, self.app = self.open_desktop(self.tmp.name)
        self.app.cancel_timers()
        self.addCleanup(self.app.cancel_timers)
        self.app.root, self.source = test_final_viewer.make_project(Path(self.tmp.name) / 'final')
        from local_video import open_studio
        self.app.studio = open_studio(self.app.root)

    def widgets(self, root=None):
        pending = [root or self.app.content]
        while pending:
            widget = pending.pop()
            yield widget
            pending.extend(widget.winfo_children())

    def tree(self):
        return next(widget for widget in self.widgets() if widget.winfo_class() == 'Treeview')

    def refresh_catalog(self):
        from tk_test_support import stage_context_menu
        stage_context_menu(self.tree()).invoke('刷新列表')

    def add_source(self):
        target = self.source.with_name('EP002.json')
        data = json.loads(self.source.read_text(encoding='utf-8'))
        data['episode_id'] = 'EP002'
        target.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
        stamp = time.time() + 600
        os.utime(target, (stamp, stamp))
        prefs_path = self.app.root / 'ui_settings.json'
        prefs = json.loads(prefs_path.read_text(encoding='utf-8'))
        prefs['adopted_storyboards'].append(target.relative_to(self.app.root).as_posix())
        prefs_path.write_text(json.dumps(prefs, ensure_ascii=False), encoding='utf-8')
        return target

    def controlled_page(self):
        import storyboard_files
        import tk_timers
        tasks, callbacks = [], {}
        real_thread, real_repeat = storyboard_files.threading.Thread, tk_timers.repeat

        def thread(*args, **kwargs):
            if kwargs.get('name') == 'final-storyboard-catalog-scan':
                return SimpleNamespace(start=lambda: tasks.append(kwargs['target']))
            return real_thread(*args, **kwargs)

        def repeat(widget, interval, callback):
            if callback.__name__ == 'apply_background_final_catalog':
                callbacks['apply'] = callback
                return lambda: None
            return real_repeat(widget, interval, callback)

        def watch(owner, project, refresh, interval=1500):
            callbacks['refresh'] = refresh
            return lambda: None

        self.enterContext(mock.patch.object(storyboard_files.threading, 'Thread', thread))
        self.enterContext(mock.patch.object(tk_timers, 'repeat', repeat))
        self.enterContext(mock.patch.object(storyboard_files, 'watch_files', watch))
        self.app.show(PAGE_OF['final'])
        self.assertEqual(len(tasks), 1)
        return tasks, callbacks

    def test_initial_catalog_scan_runs_only_in_background(self):
        import storyboard_files
        original = storyboard_files.catalog
        entered, release = threading.Event(), threading.Event()
        calls = []

        def scan(*args):
            calls.append(threading.get_ident())
            entered.set()
            if not release.wait(5):
                raise AssertionError('测试未释放目录扫描')
            return original(*args)

        with mock.patch.object(storyboard_files, 'catalog', scan), \
                mock.patch.object(storyboard_files, 'watch_files'):
            try:
                self.app.show(PAGE_OF['final'])
                self.assertTrue(entered.wait(2))
                tree = self.tree()
                self.assertEqual(tree.get_children(), ())
            finally:
                release.set()
            deadline = time.monotonic() + 5
            while not tree.get_children() and time.monotonic() < deadline:
                self.win.update()
                time.sleep(.005)
            self.assertIn(str(self.source), tree.get_children())
        self.assertTrue(calls)
        self.assertNotIn(threading.get_ident(), calls)

    def test_manual_refresh_rejects_older_initial_result(self):
        tasks, callbacks = self.controlled_page()
        tasks.pop(0)()
        second = self.add_source()
        self.refresh_catalog()
        expected = self.tree().get_children()
        self.assertIn(str(second), expected)
        callbacks['apply']()
        self.assertEqual(self.tree().get_children(), expected)

    def test_changes_during_scan_queue_one_more_snapshot(self):
        tasks, callbacks = self.controlled_page()
        tasks.pop(0)()
        second = self.add_source()
        callbacks['refresh']()
        callbacks['refresh']()
        callbacks['apply']()
        self.assertEqual(len(tasks), 1)
        tasks.pop(0)()
        callbacks['apply']()
        self.assertIn(str(second), self.tree().get_children())
        self.assertEqual(tasks, [])

    def test_destroyed_page_ignores_completed_catalog(self):
        tasks, callbacks = self.controlled_page()
        tasks.pop(0)()
        self.app.content.destroy()
        with mock.patch('storyboard_files.insert_entries') as insert:
            callbacks['apply']()
        insert.assert_not_called()

    def test_hidden_failure_stays_local_and_manual_refresh_recovers(self):
        tasks, callbacks = self.controlled_page()
        holder = self.app.content
        with mock.patch('storyboard_files.catalog', side_effect=TypeError('scan failed')):
            tasks.pop(0)()
        self.app.content = self.tk.Frame(self.win)
        self.app.status.set('当前页状态')
        callbacks['apply']()
        self.assertEqual(self.app.status.get(), '当前页状态')
        values = [self.win.getvar(widget.cget('textvariable')) for widget in self.widgets(holder)
                  if 'textvariable' in widget.keys() and widget.cget('textvariable')]
        self.assertTrue(any('加载失败' in str(value) and '刷新列表' in str(value) for value in values))
        self.app.content = holder
        self.refresh_catalog()
        self.assertIn(str(self.source), self.tree().get_children())

    def test_automatic_refresh_preserves_unsaved_text(self):
        tasks, callbacks = self.controlled_page()
        tasks.pop(0)()
        callbacks['apply']()
        viewer = next(widget for widget in self.widgets() if isinstance(widget, self.tk.Text))
        viewer.insert('end', '\n未保存的编辑')
        text = viewer.get('1.0', 'end-1c')
        callbacks['refresh']()
        tasks.pop(0)()
        callbacks['apply']()
        self.assertEqual(viewer.get('1.0', 'end-1c'), text)


if __name__ == '__main__':
    unittest.main()

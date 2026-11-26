"""初步分镜的首次加载与异步结果生命周期。"""
import tempfile
import threading
import time
import unittest
from pathlib import Path
from tkinter import ttk
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

    @staticmethod
    def catalog_paths(desktop):
        page = getattr(desktop, 'storyboard_editor_page', None)
        if page is None:
            return set()
        paths = set()
        for bucket in (page.catalogs or {}).values():
            for entry in bucket:
                paths.add(str(entry['path']))
        return paths

    def test_initial_catalog_scan_never_runs_on_ui_thread(self):
        from orchestrator.storyboard_page_controller import StoryboardPageController
        from infra.pet_state import PAGE_OF
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
                self.pump(win, lambda: bool(self.catalog_paths(d)))
            self.assertTrue(calls)
            self.assertNotIn(threading.get_ident(), calls)
            self.assertTrue(d.storyboard_editor_page.loaded)
            self.assertIsNotNone(d.storyboard_editor_page.active_path)

    def test_manual_refresh_rejects_an_older_initial_result(self):
        from infra.pet_state import PAGE_OF
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
                page = d.storyboard_editor_page
                page.refresh()
                self.assertIn(str(script), self.catalog_paths(d))
                captured['apply']()
                self.assertIn(str(script), self.catalog_paths(d), '迟到快照不能覆盖手动刷新')

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
        from infra.pet_state import PAGE_OF
        from orchestrator.storyboard_page_controller import StoryboardPageController
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
        from infra.pet_state import PAGE_OF
        from orchestrator.storyboard_page_controller import StoryboardPageController
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
                viewer_text = d.storyboard_editor_preview.get('1.0', 'end-1c')
                self.assertIn('分镜目录加载失败，请右键「刷新分镜列表」重试', viewer_text)
                self.assertIn('测试读取失败', d.status.get())
                d.storyboard_editor_page.refresh()
                self.assertTrue(self.catalog_paths(d))
                self.assertTrue(d.storyboard_editor_page.loaded)

    def test_shot_navigator_searches_jumps_and_counts_find_matches(self):
        """S03 编辑器针对分镜增强：左侧镜头定位按镜头号/角色/场景实时搜索并跳转，查找条带计数。"""
        import json
        from infra.pet_state import PAGE_OF
        from ui.storyboard_table_ui import extract_storyboard_shots
        sample = {
            'episode_id': 'EP001', 'title': '雨夜重逢', 'duration': 15,
            'shots': [
                {'id': 'SH001', 'title': '街道远景', 'duration': 5, 'characters': ['林夏'],
                 'location': '老街', 'dialogue': '雨下大了', 'frame_prompt': '雨夜霓虹街道'},
                {'id': 'SH002', 'title': '咖啡馆推近', 'duration': 5, 'characters': ['陈默'],
                 'location': '咖啡馆', 'dialogue': '你终于来了', 'frame_prompt': '暖灯窗边'},
                {'id': 'SH003', 'title': '天台对峙', 'duration': 5, 'characters': ['林夏', '陈默'],
                 'location': '天台', 'dialogue': '把怀表还给我', 'frame_prompt': '暴雨天台霓虹'},
            ],
        }
        with tempfile.TemporaryDirectory() as td:
            win, d = self.open_desktop(td)
            self.addCleanup(d.cancel_timers)
            board = d.root / '03初步分镜' / '分镜拆分' / 'EP001.json'
            board.parent.mkdir(parents=True, exist_ok=True)
            board.write_text(json.dumps(sample, ensure_ascii=False), encoding='utf-8')
            d.show(PAGE_OF['storyboard'])
            page = d.storyboard_editor_page
            page.show_document(board)
            win.update()
            nav = page.editor.shot_nav
            self.assertTrue(nav.visible, '多镜头分镜自动展开左侧镜头定位栏')
            self.assertEqual(len(nav.items()), 3)
            self.assertEqual(str(nav.count_label.cget('text')), '3 镜')
            # 按角色/场景关键词过滤：搜「天台」只剩 SH003 并可一键跳转高亮。
            nav.search_entry.delete(0, 'end')
            nav.search_entry.insert(0, '天台')
            win.update()
            self.assertEqual(len(nav.items()), 1)
            self.assertIn('SH003', nav.items()[0])
            self.assertEqual(str(nav.count_label.cget('text')), '1/3 镜')
            nav._jump_current()
            win.update()
            self.assertTrue(page.viewer.tag_ranges('s03_shot_hit'), '跳转后应高亮目标镜头标题行')
            # 切原始 JSON 模式同样能提取全部镜头编号。
            raw_shots = extract_storyboard_shots(json.dumps(sample, ensure_ascii=False, indent=2))
            self.assertEqual([item[1].split('｜')[0] for item in raw_shots], ['SH001', 'SH002', 'SH003'])
            # Ctrl+F 全文查找带命中计数与上下跳转。
            page.editor.show_find_bar()
            page.editor.find_entry.delete(0, 'end')
            page.editor.find_entry.insert(0, '霓虹')
            win.update()
            self.assertEqual(str(page.editor.find_count.cget('text')), '1/2')
            page.editor.find_step(1)
            self.assertEqual(str(page.editor.find_count.cget('text')), '2/2')

    def test_editor_shows_top_right_close_button_when_file_opened_and_hides_after_close(self):
        """打开文件后编辑器内部右上角显示「×」，点击后恢复空态且刷新不自动重开，重开文件再次显示。"""
        import json
        from infra.pet_state import PAGE_OF
        from ui.storyboard_table_ui import S03_EMPTY_TEXT
        sample = {
            'episode_id': 'EP001', 'title': '雨夜重逢', 'duration': 10,
            'shots': [
                {'id': 'SH001', 'title': '街道远景', 'duration': 5, 'characters': ['林夏'],
                 'location': '老街', 'dialogue': '雨下大了', 'frame_prompt': '雨夜霓虹街道'},
                {'id': 'SH002', 'title': '咖啡馆推近', 'duration': 5, 'characters': ['陈默'],
                 'location': '咖啡馆', 'dialogue': '你终于来了', 'frame_prompt': '暖灯窗边'},
            ],
        }
        with tempfile.TemporaryDirectory() as td:
            win, d = self.open_desktop(td)
            self.addCleanup(d.cancel_timers)
            win.geometry('1100x760+40+40')
            win.deiconify()
            board = d.root / '03初步分镜' / '分镜拆分' / 'EP001_雨夜重逢_分镜.json'
            board.parent.mkdir(parents=True, exist_ok=True)
            board.write_text(json.dumps(sample, ensure_ascii=False), encoding='utf-8')
            d.show(PAGE_OF['storyboard'])
            page = d.storyboard_editor_page
            self.pump(win, lambda: page.loaded)
            page.show_document(board)
            page.editor.show_find_bar()
            win.update()
            btn = page.editor.close_button
            self.assertTrue(btn.winfo_ismapped(), '打开文件后右上角关闭按钮应可见')
            self.assertEqual(str(btn.cget('text')), '×')
            self.assertFalse(hasattr(page.editor, 'doc_bar'), '顶部当前文件内容框应已移除')
            self.assertTrue(page.editor.gutter.winfo_ismapped(), '行号槽应可见')
            self.assertLess(page.editor.shot_nav.winfo_rootx(), page.editor.gutter.winfo_rootx(),
                            '镜头导航应在行号左侧')
            self.assertLess(page.editor.gutter.winfo_rootx(), page.viewer.winfo_rootx(),
                            '行号应在正文左侧')
            area = page.editor.editor_area
            self.assertGreater(btn.winfo_rootx(), area.winfo_rootx() + area.winfo_width() / 2,
                               '关闭按钮应位于编辑器右半区')
            self.assertLessEqual(btn.winfo_rootx() + btn.winfo_width(),
                                 area.winfo_rootx() + area.winfo_width(),
                                 '关闭按钮不得超出编辑器右缘')
            self.assertLessEqual(btn.winfo_rooty() - area.winfo_rooty(), 16,
                                 '关闭按钮应位于编辑器内部上沿')
            self.assertTrue(page.editor.shot_nav.visible, '多镜头分镜应展开镜头定位栏')
            btn.invoke()
            win.update()
            self.assertIsNone(page.active_path)
            self.assertFalse(btn.winfo_ismapped(), '关闭文档后关闭按钮应隐藏')
            self.assertFalse(page.editor.find_bar.winfo_ismapped(), '关闭文档后查找条应收起')
            self.assertEqual(page.viewer.get('1.0', 'end-1c'), S03_EMPTY_TEXT)
            self.assertFalse(page.editor.shot_nav.visible, '关闭文档后镜头定位栏应收起')
            self.assertIn('已关闭当前文档；项目文件保留', d.status.get())
            self.assertTrue(board.is_file(), '关闭视图不得删除项目文件')
            page.refresh()
            win.update()
            self.assertIsNone(page.active_path, '手动关闭后刷新不应把默认文档自动重开')
            page.apply_catalogs(page.catalogs, automatic=True)
            win.update()
            self.assertIsNone(page.active_path, '后台目录刷新不应把手动关闭的文档自动重开')
            self.assertFalse(btn.winfo_ismapped())
            page.show_document(board)
            win.update()
            self.assertEqual(page.active_path, board.resolve())
            self.assertTrue(btn.winfo_ismapped(), '重新打开文件后关闭按钮应再次可见')

    def test_close_document_save_failure_keeps_scene_and_valid_save_closes(self):
        """编辑态关闭先走真实保存；保存失败不丢现场，改成可保存内容后关闭并保留落盘结果。"""
        import json
        from infra.pet_state import PAGE_OF
        sample = {
            'episode_id': 'EP001', 'title': '雨夜重逢', 'duration': 5,
            'shots': [
                {'id': 'SH001', 'title': '街道远景', 'duration': 5, 'characters': ['林夏'],
                 'location': '老街', 'dialogue': '雨下大了', 'frame_prompt': '雨夜霓虹街道'},
            ],
        }
        original = json.dumps(sample, ensure_ascii=False, indent=2)
        with tempfile.TemporaryDirectory() as td:
            win, d = self.open_desktop(td)
            self.addCleanup(d.cancel_timers)
            win.geometry('1100x760+40+40')
            win.deiconify()
            board = d.root / '03初步分镜' / '分镜拆分' / 'EP001_雨夜重逢_分镜.json'
            board.parent.mkdir(parents=True, exist_ok=True)
            board.write_text(original, encoding='utf-8')
            d.show(PAGE_OF['storyboard'])
            page = d.storyboard_editor_page
            self.pump(win, lambda: page.loaded)
            page.show_document(board)
            page.begin_edit()
            page.viewer.delete('1.0', 'end')
            win.update()
            page.editor.close_button.invoke()
            win.update()
            self.assertEqual(page.active_path, board.resolve(), '空内容保存失败时不得关闭文档')
            self.assertTrue(page.editing)
            self.assertEqual(page.viewer.get('1.0', 'end-1c'), '')
            self.assertEqual(board.read_text(encoding='utf-8'), original)
            self.assertTrue(page.editor.close_button.winfo_ismapped())
            self.assertIn('保存失败，未关闭当前文档', d.status.get())
            page.viewer.insert('1.0', original)
            win.update()
            page.editor.close_button.invoke()
            win.update()
            self.assertIsNone(page.active_path)
            self.assertFalse(page.editing)
            self.assertFalse(page.raw_json_mode)
            self.assertFalse(page.editor.close_button.winfo_ismapped())
            self.assertEqual(json.loads(board.read_text(encoding='utf-8'))['episode_id'], 'EP001')

    def test_close_button_is_accessible_without_top_document_header(self):
        """S03 不渲染顶部「当前文件」内容框；只保留编辑器内部右上角可聚焦关闭×。"""
        import json
        from infra.pet_state import PAGE_OF
        sample = {
            'episode_id': 'EP001', 'title': '雨夜重逢', 'duration': 5,
            'shots': [
                {'id': 'SH001', 'title': '街道远景', 'duration': 5, 'characters': ['林夏'],
                 'location': '老街', 'dialogue': '雨下大了', 'frame_prompt': '雨夜霓虹街道'},
            ],
        }

        def descendants(widget):
            yield widget
            for child in widget.winfo_children():
                yield from descendants(child)

        with tempfile.TemporaryDirectory() as td:
            win, d = self.open_desktop(td)
            self.addCleanup(d.cancel_timers)
            win.geometry('1100x760+40+40')
            win.deiconify()
            board = d.root / '03初步分镜' / '分镜拆分' / 'EP001_雨夜重逢_分镜.json'
            board.parent.mkdir(parents=True, exist_ok=True)
            board.write_text(json.dumps(sample, ensure_ascii=False), encoding='utf-8')
            d.show(PAGE_OF['storyboard'])
            page = d.storyboard_editor_page
            self.pump(win, lambda: page.loaded)
            page.show_document(board)
            win.update()
            labels = [str(item.cget('text')) for item in descendants(page.editor.frame)
                      if isinstance(item, ttk.Label)]
            self.assertFalse(any(text.startswith('当前文件') for text in labels),
                             '顶部当前文件内容框应已移除')
            self.assertFalse(hasattr(page.editor, 'doc_title'))
            button = page.editor.close_button
            self.assertEqual(str(button.cget('style')), 'Tokens.Close.TButton')
            self.assertEqual(str(button.cget('text')), '×')
            self.assertNotEqual(str(button.cget('takefocus')), '0')
            self.assertTrue(button.bind('<Return>'), '关闭×须有回车激活绑定')
            self.assertTrue(button.winfo_ismapped())
            page.editor.close_button.invoke()
            win.update()
            self.assertFalse(button.winfo_ismapped())


if __name__ == '__main__':
    unittest.main()

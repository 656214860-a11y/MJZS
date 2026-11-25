# -*- coding: utf-8 -*-
"""REQ-S02-35：剧本结构页自动保存（R2724 反转 R1862 手动保存契约）。

真 Tk（withdraw 根窗口）：600ms 防抖落盘、未变化不写盘、退出／切换文档前 flush、
保存直接读 ``preview.get``（不依赖可能过期的 ``<<Modified>>`` 快照）、natural 走
``save_natural_script`` 且落盘后记修改习惯、structured 走 ``agent.core.save_text``
且首尾空白保留、空内容报错、只读预览不自动保存。
"""
import sys
import tempfile
import time
import tkinter as tk
import types
import unittest
from pathlib import Path
from unittest import mock

PROGRAM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROGRAM))

import agent.core  # noqa: E402
import desktop_script_edit_session  # noqa: E402
from ui_tokens import SCRIPT_EDIT_SAVE_DEBOUNCE_MS  # noqa: E402
from ui_widgets import ContextMenu  # noqa: E402
from test_ui_reading_density import _make_project, _show_script_structure  # noqa: E402


def _pump(win, seconds):
    """推进 Tk 事件循环 seconds 秒，让防抖定时器有机会触发。"""
    deadline = time.time() + seconds
    while time.time() < deadline:
        win.update()
        time.sleep(0.02)


class _FakeStatus:
    def set(self, text):
        self.text = text


class _FakePage:
    def __init__(self, confirm=None):
        self.status = _FakeStatus()
        self.win = None
        self.confirm = confirm or mock.Mock(return_value=True)
        created = []

        def context_menu(owner):
            menu = ContextMenu(owner)
            menu.menu.tk_popup = lambda *a, **k: None  # 只不真弹，避免阻塞
            created.append(menu)
            return menu
        self.script_page_services = types.SimpleNamespace(
            confirm=self.confirm, context_menu=context_menu)

    def safe(self, fn):
        return fn()


class ScriptAutosaveTests(unittest.TestCase):
    def _setup(self, kind='natural', confirm_answer=True, editable=True, content='原始内容'):
        win = tk.Tk()
        win.withdraw()
        self.addCleanup(lambda: win.winfo_exists() and win.destroy())
        preview = tk.Text(win, undo=True)
        preview.pack()
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        target = Path(tmp.name) / 'script.md'
        target.write_text(content, encoding='utf-8')
        active = {'path': str(target)}
        loaded = {'raw': content}
        # 与真实 set_preview 一致：预览先展示已读原文并处于只读态。
        preview.insert('1.0', loaded['raw'])
        preview.edit_reset()
        preview.configure(state='disabled')
        page = _FakePage(mock.Mock(return_value=confirm_answer))
        page.win = win
        from desktop_script_edit_session import _install_script_edit_controls, _reset_preview_text
        box = types.SimpleNamespace(
            preview=preview, loaded=loaded, active=active, kind=kind,
            title='自然剧本' if kind == 'natural' else '结构剧本',
            editable=editable, attribute='box',
            owner=types.SimpleNamespace())

        def set_preview(value):
            loaded['raw'] = value
            _reset_preview_text(preview, value, kind)
            preview.configure(state='disabled')
        box.set_preview = set_preview
        _install_script_edit_controls(page, box)
        win.update()  # 先让控件完成首次布局，合成事件才稳定投递
        return win, preview, page, target, page.box_edit_session

    def test_real_close_flushes_last_keystroke_and_refuses_a_failed_save(self):
        from desktop import Desktop
        for kind in ('natural', 'structured'):
            with self.subTest(kind=kind):
                win, preview, page, target, session = self._setup(kind=kind)
                page.script_structure_editor_preview_edit_session = session
                page.busy_reason = lambda: ''
                page.pet_hides_instead_of_quitting = lambda: False
                page.flush_brief = lambda: None
                page.finish_close = mock.Mock(side_effect=preview.destroy)
                session.begin_edit()
                preview.delete('1.0', 'end')
                Desktop.close(page)
                page.finish_close.assert_not_called()
                self.assertTrue(session.editing)
                self.assertTrue(preview.winfo_exists())
                preview.insert('1.0', '最后一次输入')
                Desktop.close(page)
                page.finish_close.assert_called_once_with()
                self.assertIn('最后一次输入', target.read_text(encoding='utf-8'))

    def test_page_rebuild_retains_editor_on_write_failure(self):
        from ui.desktop_page_nav import PageNavMixin
        win, preview, page, target, session = self._setup(kind='structured')
        page.script_structure_editor_preview_edit_session = session
        page.freeze_page_paint = mock.Mock()
        page.mark_nav = mock.Mock()
        page.page_index = 2
        page._show_reset_page = mock.Mock()
        session.begin_edit()
        preview.insert('end', '尚未保存')
        with mock.patch('agent.core.save_text', side_effect=OSError('磁盘已满')):
            PageNavMixin.show(page, 1)
        page._show_reset_page.assert_not_called()
        self.assertTrue(session.editing)
        self.assertIn('尚未保存', preview.get('1.0', 'end-1c'))
        self.assertNotIn('尚未保存', target.read_text(encoding='utf-8'))

    def test_debounce_interval_is_600ms(self):
        """REQ-S02-35：防抖间隔取 ui_tokens.SCRIPT_EDIT_SAVE_DEBOUNCE_MS＝600。"""
        self.assertEqual(SCRIPT_EDIT_SAVE_DEBOUNCE_MS, 600)

    def test_autosave_writes_after_debounce(self):
        """修改后防抖期内不写盘，窗口到了自动落盘。"""
        with mock.patch.object(desktop_script_edit_session, 'SCRIPT_EDIT_SAVE_DEBOUNCE_MS', 120):
            win, preview, page, target, session = self._setup(kind='structured')
            session.toggle_edit()
            win.update()
            preview.insert('end', '自动')
            win.update()
            self.assertNotIn('自动', target.read_text(encoding='utf-8'), '防抖期内不得落盘')
            _pump(win, 0.6)
            self.assertIn('自动', target.read_text(encoding='utf-8'))

    def test_exit_cancels_pending_and_flushes_immediately(self):
        """防抖定时已排上时退出编辑：取消定时并立即落盘，不重复写。"""
        with mock.patch.object(desktop_script_edit_session, 'SCRIPT_EDIT_SAVE_DEBOUNCE_MS', 120), \
                mock.patch('agent.core.save_text', wraps=agent.core.save_text) as spy:
            win, preview, page, target, session = self._setup(kind='structured')
            session.toggle_edit()
            win.update()
            preview.insert('end', 'X')
            win.update()
            self.assertIsNotNone(session.pending, '修改后应安排防抖定时')
            session.toggle_edit()   # 防抖未到就退出
            win.update()
            self.assertIsNone(session.pending)
            self.assertIn('X', target.read_text(encoding='utf-8'))
            _pump(win, 0.4)                  # 越过防抖窗口也不应再写
            self.assertEqual(spy.call_count, 1, '退出 flush 后防抖定时器不得再触发写盘')

    def test_unchanged_content_does_not_write_disk(self):
        """改了又改回原文：防抖触发时内容与基线相同，不写盘。"""
        with mock.patch.object(desktop_script_edit_session, 'SCRIPT_EDIT_SAVE_DEBOUNCE_MS', 120), \
                mock.patch('agent.core.save_text', wraps=agent.core.save_text) as spy:
            win, preview, page, target, session = self._setup(kind='structured')
            session.toggle_edit()
            win.update()
            preview.insert('end', 'x')
            win.update()
            session.undo_step()             # 撤销刚才的输入，回到原文
            win.update()
            self.assertEqual(preview.get('1.0', 'end-1c'), '原始内容')
            _pump(win, 0.5)                  # 防抖窗口过去，自动保存应判定无变化
            self.assertEqual(spy.call_count, 0, '内容未变化时不得写盘')
            self.assertEqual(target.read_text(encoding='utf-8'), '原始内容')

    def test_save_now_reads_widget_without_modified_event(self):
        """<<Modified>> 尚未派发就立即保存：直接读 preview.get，最新文本不丢。"""
        win, preview, page, target, session = self._setup(kind='structured')
        session.begin_edit()
        preview.insert('end', '即时')       # 不 update：<<Modified>> 还压在事件队列里
        session.save_now()
        self.assertIn('即时', target.read_text(encoding='utf-8'))

    def test_exit_edit_flushes_without_modified_event(self):
        """<<Modified>> 尚未派发就退出：flush 直接读文本框，最新文本不丢。"""
        win, preview, page, target, session = self._setup(kind='structured')
        session.begin_edit()
        preview.insert('end', '退出')
        session.exit_edit()
        self.assertIn('退出', target.read_text(encoding='utf-8'))
        self.assertFalse(session.editing)

    def test_natural_save_routes_and_records_edit_habit(self):
        """natural 仍走 save_natural_script，落盘成功后 _record_natural_edit 记修改习惯。"""
        win, preview, page, target, session = self._setup(kind='natural')
        with mock.patch('script_contract.save_natural_script') as natural_save, \
                mock.patch('desktop_script_edit_session._record_natural_edit') as record:
            session.toggle_edit()
            win.update()
            preview.insert('end', '习惯')
            session.save_now()
            natural_save.assert_called_once()
            args = natural_save.call_args.args
            self.assertEqual(Path(args[0]), target)
            self.assertIn('习惯', args[1])
            record.assert_called_once()
            rargs = record.call_args.args
            self.assertIs(rargs[0], page)
            self.assertEqual(rargs[1], '原始内容')
            self.assertIn('习惯', rargs[2])
            self.assertEqual(rargs[3], 'script.md')

    def test_structured_save_preserves_edge_whitespace(self):
        """structured 走 agent.core.save_text：首尾空白原样保留，只补一个换行。"""
        win, preview, page, target, session = self._setup(kind='structured')
        session.toggle_edit()
        win.update()
        preview.delete('1.0', 'end')
        preview.insert('1.0', '  首行  \n末行  ')
        win.update()
        session.save_now()
        self.assertEqual(target.read_text(encoding='utf-8'), '  首行  \n末行  \n')

    def test_empty_content_is_rejected_and_file_untouched(self):
        """清空正文：立即保存与自动保存都报错，文件不动，退出被拒留在编辑态。"""
        win, preview, page, target, session = self._setup(kind='structured')
        before = target.read_bytes()
        session.toggle_edit()
        win.update()
        preview.delete('1.0', 'end')
        win.update()
        with self.assertRaises(ValueError):
            session.save_now()
        session.autosave()                 # 自动保存路径：状态栏报错、不抛出
        self.assertIn('剧本内容不能为空', page.status.text)
        self.assertEqual(target.read_bytes(), before)
        with self.assertRaises(ValueError):
            session.exit_edit()
        self.assertTrue(session.editing, '空内容退出被拒，应留在编辑态不丢稿')

    def test_readonly_preview_never_autosaves(self):
        """从未进入编辑：修改标记与防抖回调都不触发写盘。"""
        with mock.patch('agent.core.save_text', wraps=agent.core.save_text) as spy:
            win, preview, page, target, session = self._setup(kind='structured')
            preview.edit_modified(True)
            preview.event_generate('<<Modified>>')
            win.update()
            session.autosave()
            self.assertIsNone(session.pending)
            self.assertEqual(spy.call_count, 0)
            self.assertEqual(target.read_text(encoding='utf-8'), '原始内容')


class SwitchDocumentFlushTests(unittest.TestCase):
    def test_switch_document_flushes_edit_and_exits(self):
        """REQ-S02-38：编辑态经面板回调路径切换文档：先 flush 落盘、退出编辑，再加载新文档。"""
        with tempfile.TemporaryDirectory() as td:
            project, writing = _make_project(td)
            # script_raw.md 是内部工作稿、不进自然剧本列表；要两份可选文档需再写正式命名稿。
            other = writing / 'script_other.md'
            other.write_text('另一份剧本\n', encoding='utf-8')
            third = writing / 'script_third.md'
            third.write_text('第三份剧本\n', encoding='utf-8')
            win = tk.Tk()
            win.geometry('1280x800+40+40')
            win.deiconify()
            win.update()
            self.addCleanup(lambda: win.winfo_exists() and win.destroy())
            desktop = _show_script_structure(win, project)
            session = desktop.script_structure_editor_preview_edit_session
            box = desktop.script_structure_editor_preview_content_box
            preview = desktop.script_structure_editor_preview
            box.select_document(other)
            win.update()
            session.toggle_edit()
            win.update()
            preview.insert('end', '切换前的修改')
            box.select_document(third)
            win.update()
            self.assertIn('切换前的修改', other.read_text(encoding='utf-8'),
                          '切换前必须把编辑内容落盘')
            self.assertFalse(session.editing)
            self.assertEqual(str(preview.cget('state')), 'disabled')
            self.assertIn('第三份剧本', preview.get('1.0', 'end'))
            self.assertEqual(box.active['path'], third.resolve())

    def test_failed_save_keeps_the_original_document(self):
        """REQ-S02-38：切换前落盘失败时留在原文档，不加载新文档。"""
        with tempfile.TemporaryDirectory() as td:
            project, writing = _make_project(td)
            other = writing / 'script_other.md'
            other.write_text('另一份剧本\n', encoding='utf-8')
            third = writing / 'script_third.md'
            third.write_text('第三份剧本\n', encoding='utf-8')
            win = tk.Tk()
            win.geometry('1280x800+40+40')
            win.deiconify()
            win.update()
            self.addCleanup(lambda: win.winfo_exists() and win.destroy())
            desktop = _show_script_structure(win, project)
            session = desktop.script_structure_editor_preview_edit_session
            box = desktop.script_structure_editor_preview_content_box
            preview = desktop.script_structure_editor_preview
            box.select_document(other)
            win.update()
            session.toggle_edit()
            win.update()
            preview.delete('1.0', 'end')     # 空内容保存被拒，exit_edit 抛错
            box.select_document(third)
            win.update()
            self.assertTrue(session.editing, '落盘失败应留在编辑态')
            self.assertEqual(box.active['path'], other.resolve(),
                             '落盘失败不切换文档')

    def test_close_document_flushes_edit_and_can_reopen(self):
        """关闭×只关闭当前文件视图：退出编辑的真实保存仍生效，项目文件保留且可重开。"""
        with tempfile.TemporaryDirectory() as td:
            project, writing = _make_project(td)
            other = writing / 'script_other.md'
            other.write_text('另一份剧本\n', encoding='utf-8')
            win = tk.Tk()
            win.geometry('1280x800+40+40')
            win.deiconify()
            win.update()
            self.addCleanup(lambda: win.winfo_exists() and win.destroy())
            desktop = _show_script_structure(win, project)
            session = desktop.script_structure_editor_preview_edit_session
            box = desktop.script_structure_editor_preview_content_box
            preview = desktop.script_structure_editor_preview
            box.select_document(other)
            session.toggle_edit()
            win.update()
            preview.insert('end', '关闭前修改')
            self.assertTrue(box.close_document())
            win.update()
            self.assertIn('关闭前修改', other.read_text(encoding='utf-8'))
            self.assertIsNone(box.active['path'])
            self.assertFalse(session.editing)
            self.assertFalse(box.close_button.winfo_ismapped())
            self.assertIn('尚未找到剧本准备阶段的剧本', preview.get('1.0', 'end-1c'))
            self.assertTrue(other.is_file(), '关闭视图不得删除项目文件')
            box.select_document(other)
            win.update()
            self.assertEqual(box.active['path'], other.resolve())
            self.assertTrue(box.close_button.winfo_ismapped())
            self.assertIn('关闭前修改', preview.get('1.0', 'end-1c'))

    def test_close_document_failed_save_keeps_editing_scene(self):
        """关闭前落盘失败时不丢稿：仍在原文档编辑态，关闭×保持可见。"""
        with tempfile.TemporaryDirectory() as td:
            project, writing = _make_project(td)
            other = writing / 'script_other.md'
            original = '另一份剧本\n'
            other.write_text(original, encoding='utf-8')
            win = tk.Tk()
            win.geometry('1280x800+40+40')
            win.deiconify()
            win.update()
            self.addCleanup(lambda: win.winfo_exists() and win.destroy())
            desktop = _show_script_structure(win, project)
            session = desktop.script_structure_editor_preview_edit_session
            box = desktop.script_structure_editor_preview_content_box
            preview = desktop.script_structure_editor_preview
            box.select_document(other)
            session.toggle_edit()
            win.update()
            preview.delete('1.0', 'end')     # 空内容保存被拒
            self.assertFalse(box.close_document())
            win.update()
            self.assertEqual(box.active['path'], other.resolve())
            self.assertTrue(session.editing)
            self.assertEqual(preview.get('1.0', 'end-1c'), '')
            self.assertEqual(other.read_text(encoding='utf-8'), original)
            self.assertTrue(box.close_button.winfo_ismapped())
            self.assertIn('保存失败，未关闭', desktop.status.get())


if __name__ == '__main__':
    unittest.main()

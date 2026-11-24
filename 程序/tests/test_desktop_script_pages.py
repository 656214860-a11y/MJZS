# -*- coding: utf-8 -*-
"""REQ-S02-37/38/44：剧本结构页只留一个编辑器，编辑器与底部输入框左右对齐。

REQ-S02-37：页面上没有「采用选中剧本／手动制作结构剧本／大纲／编辑／删除」五按钮，
也没有「原剧本／结构剧本」字样和文件下拉框；当前文件名与采用状态写进状态栏
``script_note`` 段。
REQ-S02-38：编辑器显示右侧面板点选的文件——自然／结构剧本可编辑，其他文档只读；
默认显示采用的自然剧本对应的结构剧本，其次采用的自然剧本，否则空态。
REQ-S02-44：三档窗口 × 文件面板开关下，编辑器与共享输入框外框 ``input_ring``
的左右边缘差为 0（口径同 test_desktop_writing_page 的 T1）。

每条用例自己建窗口、用完就关。首帧之后的后台维护换成空动作：这里只量排版与
显示内容，不该碰测试目录以外的东西。等待用「页面内容宽度已跟上画布，而且连续
两次量到的结果相同」判断重排做完；``LAYOUT_TIMEOUT`` 只是机器很忙时的上限。
"""
import sys
import tempfile
import time
import tkinter as tk
import unittest
from pathlib import Path
from tkinter import ttk
from unittest import mock

PROGRAM = Path(__file__).resolve().parents[1]
TESTS = Path(__file__).resolve().parent
for _p in (str(PROGRAM), str(TESTS)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from test_ui_reading_density import _make_project, _settle, _show_script_structure  # noqa: E402

import desktop as desktop_module     # noqa: E402
import desktop_shared_input          # noqa: E402,F401  被对齐的一方（共享输入框），--affected 消费者锚点
import ui.desktop_script_pages       # noqa: E402,F401  本用例的对象模块（剧本结构页），同上

WINDOW_SIZES = ('1280x800', '1024x680', '880x600')
LAYOUT_TIMEOUT = 30.0
REMOVED_BUTTON_TEXTS = ('采用选中剧本', '手动制作结构剧本', '大纲', '编辑', '退出', '删除')
REMOVED_PAGE_ATTRS = (
    'script_structure_manual_button',
    'script_structure_source_preview', 'script_structure_output_preview',
    'script_structure_source_box', 'script_structure_output_box',
    'script_structure_source_preview_files', 'script_structure_output_preview_files',
    'script_structure_source_preview_edit_button',
    'script_structure_output_preview_edit_button',
    'script_structure_output_preview_delete_button',
    'script_structure_source_preview_edit_session',
    'script_structure_output_preview_edit_session',
)


def _edges(widget):
    left = widget.winfo_rootx()
    return left, left + widget.winfo_width()


def _descendants(widget):
    yield widget
    for child in widget.winfo_children():
        yield from _descendants(child)


def _open_window(testcase, project, size=WINDOW_SIZES[0]):
    """建窗口＋剧本结构页桌面；后台维护静默，用完由调用方 ``addCleanup`` 关。"""
    win = tk.Tk()
    win.geometry(size + '+40+40')
    win.deiconify()
    win.update()
    testcase.addCleanup(lambda: win.winfo_exists() and win.destroy())
    quiet = mock.patch.object(desktop_module.Desktop, '_after_first_paint', lambda self: None)
    quiet.start()
    testcase.addCleanup(quiet.stop)
    desktop = _show_script_structure(win, project)
    testcase.addCleanup(_stop_desktop, desktop)
    return win, desktop


def _stop_desktop(desktop):
    try:
        desktop.cancel_timers()
    except Exception:
        pass


def _wait_panel_rows(win, desktop, timeout=10.0):
    """等右侧文件面板的后台索引渲染完，返回当前可见行 iid 列表。"""
    panel = desktop.files_panel
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        _settle(win, 2)
        loading = any('文件索引' in label or '素材库' in label
                      for label in desktop.task_queue.labels())
        if not loading and not panel._index_render_job and not panel._index_loading:
            tree = panel.script_tree
            rows = []
            for item in tree.get_children():
                rows.extend(tree.get_children(item) or (item,))
            return [str(item) for item in rows]
    return []


def _select_panel_row(win, desktop, row):
    """在右侧文件面板里点选一行，触发已登记的点选回调。"""
    desktop.files_panel.script_tree.selection_set(row)
    _settle(win, 3)


class StructurePageInputAlignmentTests(unittest.TestCase):
    """REQ-S02-44：唯一编辑器与底部共享输入框左右对齐（三档窗口 × 面板开关）。"""

    def _measure(self, desktop):
        preview = desktop.script_structure_editor_preview
        blocks = (('编辑器文本框', _edges(preview.master)),)
        return _edges(desktop.shared_input.input_ring), blocks

    def _wait_layout(self, win, desktop):
        deadline = time.monotonic() + LAYOUT_TIMEOUT
        last = None
        while time.monotonic() < deadline:
            _settle(win, 5)
            fitted = desktop.content.winfo_width() == desktop.canvas.winfo_width()
            now = self._measure(desktop)
            if fitted and now == last:
                return now
            last = now
        self.fail('窗口改尺寸后 %.0f 秒内页面没有排稳，没法量边缘' % LAYOUT_TIMEOUT)

    def _check_sizes(self, panel_open):
        with tempfile.TemporaryDirectory(prefix='s02-align-') as td:
            project, writing = _make_project(td)
            structured = writing / '结构剧本'
            structured.mkdir()
            (structured / 'script0.md').write_text(
                '# 结构化剧本\n\n## 分场剧本\n\n正文\n', encoding='utf-8')
            win, desktop = _open_window(self, project)
        panel = desktop.files_panel
        (panel.open_panel if panel_open else panel.collapse)()
        state = '文件面板开' if panel_open else '文件面板关'
        for size in WINDOW_SIZES:
            with self.subTest(size=size, panel_open=panel_open):
                win.geometry(size)
                (ring_left, ring_right), blocks = self._wait_layout(win, desktop)
                self.assertGreater(ring_right - ring_left, 200, '输入框没有显示出来，量不了')
                problems = []
                for name, (left, right) in blocks:
                    if left != ring_left:
                        problems.append('%s左缘差 %+d' % (name, left - ring_left))
                    if right != ring_right:
                        problems.append('%s右缘差 %+d' % (name, right - ring_right))
                self.assertEqual(
                    problems, [],
                    '%s（%s）和输入框外框没有对齐，单位像素，正数表示偏右' % (size, state))

    def test_editor_shares_edges_with_input_box_panel_closed(self):
        """REQ-S02-44：面板收起时编辑器左右边缘＝输入框外框。"""
        self._check_sizes(panel_open=False)

    def test_editor_shares_edges_with_input_box_panel_open(self):
        """REQ-S02-44：面板打开时编辑器左右边缘仍＝输入框外框。"""
        self._check_sizes(panel_open=True)


class ScriptStructureOneEditorTests(unittest.TestCase):
    """REQ-S02-37/38：单编辑器、无五按钮与下拉框、面板点选驱动、状态栏写文件名。"""

    def _project(self, td, *, structured=False, adopt=False):
        project, writing = _make_project(td)
        adopted = writing / '剧本_甲.md'
        adopted.write_text('第 1 集\n\n场景 2：候车室\n\n阿远：采用稿正文。\n', encoding='utf-8')
        if adopt:
            from stage_execution_service import adopt_natural_script
            adopt_natural_script(project, adopted)
        if structured:
            target = writing / '结构剧本'
            target.mkdir()
            (target / 'script0.md').write_text(
                '# 结构化剧本\n\n## 分场剧本\n\n正稿正文\n', encoding='utf-8')
        return project, writing

    def test_single_editor_and_no_removed_chrome(self):
        """REQ-S02-37：只剩一个文本编辑器；五按钮、分区字样、下拉框与旧页面属性全部去掉。"""
        with tempfile.TemporaryDirectory() as td:
            project, _writing = self._project(td, structured=True)
            win, desktop = _open_window(self, project)
        self.assertTrue(hasattr(desktop, 'script_structure_editor_preview'),
                        '应暴露唯一编辑器 script_structure_editor_preview')
        for name in REMOVED_PAGE_ATTRS:
            self.assertFalse(hasattr(desktop, name), name + ' 应已从页面属性移除')
        widgets = list(_descendants(desktop.content))
        texts = [item for item in widgets if isinstance(item, tk.Text)]
        self.assertEqual(len(texts), 1, '页面应只有一个文本编辑器')
        pickers = [item for item in widgets if isinstance(item, ttk.Combobox)]
        self.assertEqual(pickers, [], '页面上不得再有文件下拉框')
        labels = [str(item.cget('text')) for item in widgets
                  if isinstance(item, ttk.Label)]
        for text in ('原剧本', '结构剧本'):
            self.assertNotIn(text, labels, '分区字样「%s」应已删除' % text)
        buttons = [str(item.cget('text')) for item in widgets
                   if item.winfo_class() in ('TButton', 'Button')]
        for text in REMOVED_BUTTON_TEXTS:
            self.assertNotIn(text, buttons, '按钮「%s」应已删除' % text)

    def test_default_document_prefers_derived_structured(self):
        """REQ-S02-38：默认显示采用的自然剧本对应的结构剧本（血缘反查）。"""
        import script_contract
        with tempfile.TemporaryDirectory() as td:
            project, writing = self._project(td, adopt=True)
            target = script_contract.write_structured_script(project)
            win, desktop = _open_window(self, project)
        shown = desktop.script_structure_editor_preview.get('1.0', 'end-1c')
        self.assertIn('## 分场剧本', shown)
        box = desktop.script_structure_editor_preview_content_box
        self.assertEqual(box.active['path'], target.resolve())
        segment = desktop.status_bar._segments['script_note'][1].full_text
        self.assertIn('结构剧本', segment)
        self.assertIn(target.name, segment)
        self.assertIn('本地规则整理，不调用模型',
                      str(desktop.status_bar._segments['script_note'][1].tooltip.text))

    def test_default_document_falls_back_to_adopted_natural(self):
        """REQ-S02-38：还没有结构剧本时默认显示采用的自然剧本，状态栏写明采用。"""
        with tempfile.TemporaryDirectory() as td:
            project, writing = self._project(td, adopt=True)
            win, desktop = _open_window(self, project)
        shown = desktop.script_structure_editor_preview.get('1.0', 'end-1c')
        self.assertIn('阿远：采用稿正文。', shown)
        box = desktop.script_structure_editor_preview_content_box
        self.assertEqual(box.active['path'], (writing / '剧本_甲.md').resolve())
        self.assertTrue(box.editable)
        segment = desktop.status_bar._segments['script_note'][1].full_text
        self.assertIn('自然剧本', segment)
        self.assertIn('剧本_甲.md', segment)
        self.assertIn('采用', segment)

    def test_empty_state_without_documents(self):
        """REQ-S02-38：两份稿都没有时编辑器显示空态说明。"""
        with tempfile.TemporaryDirectory() as td:
            project = Path(td) / 'project'
            project.mkdir()
            win, desktop = _open_window(self, project)
        shown = desktop.script_structure_editor_preview.get('1.0', 'end-1c')
        self.assertIn('尚未找到剧本准备阶段的剧本', shown)
        box = desktop.script_structure_editor_preview_content_box
        self.assertIsNone(box.active['path'])
        self.assertFalse(box.editable)

    def test_panel_selection_displays_selected_document(self):
        """REQ-S02-38：右侧面板点选自然剧本／结构剧本，编辑器切到对应内容。"""
        with tempfile.TemporaryDirectory() as td:
            project, writing = self._project(td, structured=True, adopt=True)
            win, desktop = _open_window(self, project)
            panel = desktop.files_panel
            panel.open_panel()
            rows = _wait_panel_rows(win, desktop)
            natural_row = next((row for row in rows if row.endswith('剧本_甲.md')), None)
            structured_row = next((row for row in rows if row.endswith('script0.md')), None)
            self.assertIsNotNone(natural_row, '自然剧本应在面板里列出：%r' % (rows,))
            self.assertIsNotNone(structured_row, '结构剧本应在面板里列出：%r' % (rows,))
            _select_panel_row(win, desktop, natural_row)
            shown = desktop.script_structure_editor_preview.get('1.0', 'end-1c')
            self.assertIn('阿远：采用稿正文。', shown)
            box = desktop.script_structure_editor_preview_content_box
            self.assertEqual(box.active['path'], (writing / '剧本_甲.md').resolve())
            self.assertTrue(box.editable)
            segment = desktop.status_bar._segments['script_note'][1].full_text
            self.assertIn('剧本_甲.md', segment)
            _select_panel_row(win, desktop, structured_row)
            shown = desktop.script_structure_editor_preview.get('1.0', 'end-1c')
            self.assertIn('## 分场剧本', shown)
            self.assertEqual(box.active['path'], (writing / '结构剧本' / 'script0.md').resolve())
            self.assertTrue(box.editable)
            segment = desktop.status_bar._segments['script_note'][1].full_text
            self.assertIn('script0.md', segment)

    def test_other_document_is_readonly(self):
        """REQ-S02-38：两组剧本之外的文档只读展示，不进入编辑态。"""
        with tempfile.TemporaryDirectory() as td:
            project, writing = self._project(td, structured=True)
            other = writing.parent / '02剧本结构' / 'output' / '整理说明.md'
            other.parent.mkdir(parents=True)
            other.write_text('# 整理说明\n\n这不是剧本文档。\n', encoding='utf-8')
            win, desktop = _open_window(self, project)
            panel = desktop.files_panel
            panel.open_panel()
            rows = _wait_panel_rows(win, desktop)
            row = next((item for item in rows if item.endswith('整理说明.md')), None)
            if row is None:
                # 面板索引未覆盖该目录时，直接走页面登记的同一条回调路径验证只读判定。
                desktop.script_structure_editor_preview_content_box.select_document(other)
                _settle(win, 3)
            else:
                _select_panel_row(win, desktop, row)
            shown = desktop.script_structure_editor_preview.get('1.0', 'end-1c')
            self.assertIn('这不是剧本文档。', shown)
            box = desktop.script_structure_editor_preview_content_box
            session = desktop.script_structure_editor_preview_edit_session
            self.assertFalse(box.editable, '两组剧本之外的文档应为只读')
            self.assertFalse(session.editable)
            errors = []

            def safe(fn):
                try:
                    return fn()
                except ValueError as exc:
                    errors.append(str(exc))
            desktop.safe = safe
            desktop.safe(session.toggle_edit)
            win.update()
            self.assertEqual(errors, ['当前没有可修改的剧本文档。'])
            self.assertEqual(str(desktop.script_structure_editor_preview.cget('state')), 'disabled')
            self.assertIn('只读', desktop.status_bar._segments['script_note'][1].full_text)


if __name__ == '__main__':
    unittest.main()

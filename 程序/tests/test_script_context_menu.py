# -*- coding: utf-8 -*-
"""REQ-S02-35/37/39/40：剧本结构页文本框右键菜单（R2724；REQ-S02-37 起「编辑」迁入菜单首项）。

真 Tk（withdraw 根窗口）：右键菜单按 REQ-S02-39 顺序——「编辑」（编辑中显示
「退出编辑」）、「后退一步／前进一步／复原全文／立即保存」、「剪切／复制／粘贴／全选」、
「查找…」「大纲」「全部折叠／全部展开」，经 ``ContextMenu`` 构建；后退／前进走 Tk 原生
``edit_undo``／``edit_redo`` 并触发防抖自动保存；「复原全文」先确认、取消不动；
「立即保存」幂等；非编辑态仅「编辑／复制／全选／查找…／大纲」与两项折叠可用；
只读文档连「编辑」也禁用；没有文档时菜单退化为五个置灰项。
"""
import sys
import tempfile
import tkinter as tk
import types
import unittest
from pathlib import Path
from unittest import mock
from tkinter import ttk

PROGRAM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROGRAM))

import agent.core  # noqa: E402
from ui_widgets import ContextMenu  # noqa: E402


class _FakeStatus:
    def set(self, text):
        self.text = text


class _FakePage:
    def __init__(self, confirm=None):
        self.status = _FakeStatus()
        self.win = None
        self.confirm = confirm or mock.Mock(return_value=True)
        self.menus = []

        def context_menu(owner):
            menu = ContextMenu(owner)
            menu.menu.tk_popup = lambda *a, **k: None  # 只不真弹，避免阻塞
            self.menus.append(menu)
            return menu
        self.script_page_services = types.SimpleNamespace(
            confirm=self.confirm, context_menu=context_menu)

    def safe(self, fn):
        return fn()


def _labels(menu):
    """菜单项标签序列（跳过分隔线），与 REQ-S02-39 的顺序逐项对齐。"""
    return [menu.menu.entrycget(i, 'label') for i in range(menu.menu.index('end') + 1)
            if menu.menu.type(i) == 'command']


def _states(menu):
    return [menu.menu.entrycget(i, 'state') for i in range(menu.menu.index('end') + 1)
            if menu.menu.type(i) == 'command']


# REQ-S02-39 的完整菜单顺序（不含末尾「打开其他文件…」，假 box 没有该方法）。
_MENU_ALL = ['编辑', '后退一步', '前进一步', '复原全文', '立即保存',
             '剪切', '复制', '粘贴', '全选', '查找…', '大纲', '全部折叠', '全部展开']


class ScriptContextMenuTests(unittest.TestCase):
    def _setup(self, kind='natural', confirm_answer=True, editable=True,
               with_document=True):
        win = tk.Tk()
        win.withdraw()
        self.addCleanup(lambda: win.winfo_exists() and win.destroy())
        preview = tk.Text(win, undo=True)
        preview.pack()
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        target = Path(tmp.name) / 'script.md'
        target.write_text('原始内容', encoding='utf-8')
        active = {'path': str(target) if with_document else None}
        loaded = {'raw': '原始内容' if with_document else ''}
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
            owner=types.SimpleNamespace(page=page))

        def set_preview(value):
            loaded['raw'] = value
            _reset_preview_text(preview, value, kind)
            preview.configure(state='disabled')
        box.set_preview = set_preview
        _install_script_edit_controls(page, box)
        # 与 _ContentBox.build 一致：三件套挂 box，右键重绑到 ReadingAids 菜单。
        from script_reading import ReadingAids
        from script_outline import OutlinePanel
        from script_find_bar import FindBar
        from script_line_numbers import LineNumberGutter
        aids = ReadingAids(box)
        box.gutter = LineNumberGutter(win, preview)
        # OutlinePanel／FindBar 显隐都走 grid：宿主须与真实页面一样是 grid 布局
        # 容器，不能直接挂 win（preview 已 pack 进去，grid 会 TclError 被吞掉）。
        find_host = ttk.Frame(win)
        find_host.pack()
        box.outline = OutlinePanel(find_host, preview)
        box.outline_toggle = ttk.Label(win)
        box.find_bar = FindBar(find_host, preview, headings=aids.heading_lines,
                               reveal=aids.ensure_line_visible)
        box.aids = aids
        box.gutter.set_fold_support(aids.fold_marks, aids.toggle_fold)
        aids.refresh_fold_support()
        preview.bind('<Button-3>', aids.context_menu)
        win.update()  # 先让控件完成首次布局，合成事件才稳定投递
        return win, preview, page, target, page.box_edit_session

    def _right_click(self, win, preview):
        preview.event_generate('<Button-3>', x=5, y=5)
        win.update()

    def test_edit_menu_item_enters_and_exits_edit(self):
        """REQ-S02-37/39：右键菜单首项「编辑」进入编辑态；编辑中同位变「退出编辑」。"""
        win, preview, page, target, session = self._setup()
        self._right_click(win, preview)
        menu = page.menus[-1]
        self.assertEqual(_labels(menu)[0], '编辑')
        menu.menu.invoke(0)
        win.update()
        self.assertTrue(session.editing)
        self.assertEqual(str(preview.cget('state')), 'normal')
        self._right_click(win, preview)
        menu = page.menus[-1]
        self.assertEqual(_labels(menu)[0], '退出编辑')
        menu.menu.invoke(0)
        win.update()
        self.assertFalse(session.editing)
        self.assertEqual(str(preview.cget('state')), 'disabled')

    def test_edit_menu_item_disabled_for_readonly_document(self):
        """REQ-S02-38/39：只读文档右键菜单仍弹出，「编辑」与编辑、剪贴项置灰。"""
        win, preview, page, target, session = self._setup(editable=False)
        self._right_click(win, preview)
        menu = page.menus[-1]
        self.assertEqual(_labels(menu), _MENU_ALL)
        self.assertEqual(_states(menu), ['disabled', 'disabled', 'disabled', 'disabled',
                                       'disabled', 'disabled', 'normal', 'disabled',
                                       'normal', 'normal', 'normal', 'normal', 'normal'])
        self.assertFalse(session.editing)

    def test_menu_items_order_and_enabled_after_change(self):
        """REQ-S02-35/39：编辑态右键菜单按 REQ 顺序全列出，有改动时全部可用。"""
        win, preview, page, target, session = self._setup()
        session.toggle_edit()
        win.update()
        preview.insert('end', '改')
        win.update()
        self._right_click(win, preview)
        self.assertEqual(len(page.menus), 1)
        menu = page.menus[-1]
        self.assertIsInstance(menu, ContextMenu, '菜单必须经 ContextMenu 构建')
        expected = ['退出编辑'] + _MENU_ALL[1:]
        self.assertEqual(_labels(menu), expected)
        self.assertEqual(_states(menu), ['normal'] * len(expected))

    def test_menu_items_disabled_when_not_editing(self):
        """REQ-S02-39：非编辑态仅「编辑／复制／全选／查找…／大纲」与两项折叠可用。"""
        win, preview, page, target, session = self._setup()
        self._right_click(win, preview)
        menu = page.menus[-1]
        self.assertEqual(_labels(menu), _MENU_ALL)
        self.assertEqual(_states(menu), ['normal', 'disabled', 'disabled', 'disabled',
                                       'disabled', 'disabled', 'normal', 'disabled',
                                       'normal', 'normal', 'normal', 'normal', 'normal'])

    def test_restore_full_asks_confirm_then_restores_and_saves(self):
        """「复原全文」先确认；取消不动，确认后恢复初始原文并立即落盘。"""
        win, preview, page, target, session = self._setup(kind='structured',
                                                         confirm_answer=False)
        session.toggle_edit()
        win.update()
        preview.insert('end', '全部改动')
        win.update()
        session.save_now()                  # 先把改动落盘，证明复原会写回
        self.assertIn('全部改动', target.read_text(encoding='utf-8'))
        self._right_click(win, preview)
        menu = page.menus[-1]
        menu.menu.invoke(3)                 # 复原全文
        win.update()
        call = page.confirm.call_args
        self.assertEqual(call.args[1], '复原全文')
        self.assertTrue(call.kwargs.get('dangerous'))
        self.assertIn('全部改动', preview.get('1.0', 'end-1c'), '取消后内容不变')
        self.assertIn('全部改动', target.read_text(encoding='utf-8'), '取消后不写盘')
        page.confirm.return_value = True
        menu.menu.invoke(3)
        win.update()
        self.assertEqual(preview.get('1.0', 'end-1c'), '原始内容')
        self.assertEqual(target.read_text(encoding='utf-8'), '原始内容\n',
                         '复原后应把初始原文写回文件')
        self.assertIn('复原', page.status.text)

    def test_restore_full_disabled_without_changes(self):
        """进入编辑后未改动：「复原全文」禁用（无可复原的修改）。"""
        win, preview, page, target, session = self._setup()
        session.toggle_edit()
        win.update()
        self._right_click(win, preview)
        menu = page.menus[-1]
        self.assertEqual(_states(menu)[3], 'disabled')
        self.assertEqual(_states(menu)[1], 'normal')
        self.assertEqual(_states(menu)[2], 'normal')
        self.assertEqual(_states(menu)[4], 'normal')

    def test_undo_redo_menu_commands_walk_native_stack(self):
        """「后退一步」调 edit_undo、「前进一步」调 edit_redo，各退一步。"""
        win, preview, page, target, session = self._setup(kind='structured')
        session.toggle_edit()
        win.update()
        preview.insert('end', '改动')
        win.update()
        self._right_click(win, preview)
        menu = page.menus[-1]
        menu.menu.invoke(1)                 # 后退一步
        win.update()
        self.assertEqual(preview.get('1.0', 'end-1c'), '原始内容')
        menu.menu.invoke(2)                 # 前进一步
        win.update()
        self.assertEqual(preview.get('1.0', 'end-1c'), '原始内容改动')

    def test_immediate_save_menu_command_is_idempotent(self):
        """「立即保存」幂等：重复触发只写盘一次，第二次提示无变化。"""
        with mock.patch('agent.core.save_text', wraps=agent.core.save_text) as spy:
            win, preview, page, target, session = self._setup(kind='structured')
            session.toggle_edit()
            win.update()
            preview.insert('end', '保存')
            win.update()
            self._right_click(win, preview)
            menu = page.menus[-1]
            menu.menu.invoke(4)             # 立即保存
            win.update()
            menu.menu.invoke(4)             # 再点一次
            win.update()
            self.assertEqual(spy.call_count, 1)
            self.assertIn('保存', target.read_text(encoding='utf-8'))
            self.assertIn('没有变化', page.status.text)

    def test_empty_document_menu_is_five_disabled_items(self):
        """REQ-S02-39：没有文档时菜单退化为「编辑」加四项置灰项。"""
        win, preview, page, target, session = self._setup(with_document=False)
        # 隐藏桌面上 event_generate 不派发 Button-3 到从未有过内容的 Text
        # （实测 x=5／x=0／无坐标三种都不触发任何 bindtag；有内容的 Text 正常）。
        # 空文档菜单的内容契约改由直接调用同一绑定回调覆盖。
        box = page.box_edit_session.box
        box.aids.context_menu(types.SimpleNamespace(x_root=0, y_root=0))
        menu = page.menus[-1]
        self.assertEqual(_labels(menu), _MENU_ALL[:5])
        self.assertEqual(_states(menu), ['disabled'] * 5)
        self.assertFalse(session.editing)

    def test_copy_and_select_all_menu_items(self):
        """REQ-S02-39：「复制」把选区写进剪贴板，「全选」选中全文。"""
        win, preview, page, target, session = self._setup()
        preview.tag_add('sel', '1.0', '1.4')
        self._right_click(win, preview)
        menu = page.menus[-1]
        index = _labels(menu).index('复制')
        preview.clipboard_clear()
        preview.clipboard_append('')
        menu.menu.invoke(index)
        win.update()
        self.assertEqual(preview.clipboard_get(), '原始内容'[:4])
        menu.menu.invoke(_labels(menu).index('全选'))
        win.update()
        sel = preview.tag_ranges('sel')
        self.assertEqual(str(sel[0]), '1.0')
        self.assertEqual(preview.get('sel.first', 'sel.last'), '原始内容')

    def test_cut_and_paste_in_editing(self):
        """REQ-S02-39：编辑态「剪切」删掉选区，「粘贴」把剪贴板内容写进正文。"""
        win, preview, page, target, session = self._setup()
        session.toggle_edit()
        win.update()
        preview.tag_add('sel', '1.0', '1.2')
        self._right_click(win, preview)
        menu = page.menus[-1]
        menu.menu.invoke(_labels(menu).index('剪切'))
        win.update()
        self.assertEqual(preview.get('1.0', 'end-1c'), '内容')
        preview.mark_set('insert', 'end')
        preview.clipboard_clear()
        preview.clipboard_append('粘贴')
        menu.menu.invoke(_labels(menu).index('粘贴'))
        win.update()
        self.assertIn('粘贴', preview.get('1.0', 'end-1c'))

    def test_find_outline_fold_menu_actions(self):
        """REQ-S02-39/40：「查找…」开查找条；「大纲」开合大纲；折叠/展开收放行。"""
        win, preview, page, target, session = self._setup()
        preview.configure(state='normal')
        preview.delete('1.0', 'end')
        preview.insert('1.0', '第 1 集\n\n场景 1：旧站台\n\n阿远：我回来了。\n')
        preview.edit_reset()
        preview.configure(state='disabled')
        box = page.box_edit_session.box
        box.aids.refresh_fold_support()
        win.update()
        self._right_click(win, preview)
        menu = page.menus[-1]
        menu.menu.invoke(_labels(menu).index('查找…'))
        win.update()
        self.assertTrue(box.find_bar.visible)
        box.find_bar.hide()
        menu.menu.invoke(_labels(menu).index('大纲'))
        win.update()
        self.assertEqual(box.outline.winfo_manager(), 'grid')
        # 「全部折叠」后只剩标题行：对白行带 script_fold elide 标记。
        self.assertNotIn('script_fold', preview.tag_names('5.0'))
        menu.menu.invoke(_labels(menu).index('全部折叠'))
        win.update()
        self.assertIn('script_fold', preview.tag_names('5.0'), '全部折叠后对白行应被隐藏')
        self.assertNotIn('script_fold', preview.tag_names('3.0'), '场标题行不折叠')
        menu.menu.invoke(_labels(menu).index('全部展开'))
        win.update()
        self.assertNotIn('script_fold', preview.tag_names('5.0'), '全部展开后对白行应恢复')


if __name__ == '__main__':
    unittest.main()

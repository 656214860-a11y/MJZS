# -*- coding: utf-8 -*-
"""03 初步分镜与 05 资产管理的「少按钮页」回归。

旧版断言量三行按钮的换行几何；现行契约把动作收进右键菜单、共享发送键与右侧
项目文件面板。这里的断言跟着改查真实入口：页面上不残留旧动作按钮，右键菜单
（鼠标与 Shift+F10）仍能找到筛选、导入、制作、目录与 ComfyUI 动作，右键行会
先成为当前行，避免菜单动作落到另一项资产上。
"""
import sys
import unittest
from pathlib import Path
from tkinter import ttk
from types import SimpleNamespace
from unittest import mock

PROGRAM = Path(__file__).resolve().parents[1]
TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(PROGRAM))
sys.path.insert(0, str(TESTS))

import test_desktop_media_pages as media_fixtures  # noqa: E402  先加载自检环境
import ui.desktop_asset_pages  # noqa: E402,F401  （--affected desktop_asset_pages 的消费者）
import ui.storyboard_files  # noqa: E402,F401  （--affected storyboard_files 的消费者）
import tk_test_support  # noqa: E402
from ui.desktop_page_registry import PAGE  # noqa: E402
from ui_widgets import ContextMenu  # noqa: E402

# 旧按钮行不得重新出现在页面上；它们的入口由右键菜单与共享发送键承接。
STORYBOARD_BUTTONS = ('手动采用分镜', '手动取消采用', '打开选中JSON', '导入JSON分镜',
                      '分镜目录', '重排镜头编号', '删除选中分镜')

ASSET_BUTTONS = ('全部', '角色', '场景', '道具', '检查提示词', '识别背景人物',
                 '导入参考图', '候选图墙', '参考图目录',
                 '导入资产图片', '批量删除资产', '恢复删除资产', '资产目录',
                 '手动制作资产', '强制关闭 ComfyUI', '制作记录',
                 '桌面打开 ComfyUI', '浏览器打开 ComfyUI')

ASSET_MENU_ACTIONS = ('手动制作资产', '检查提示词', '识别背景人物',
                      '导入参考图…', '候选图墙', '打开参考图目录',
                      '导入资产图片…', '批量删除资产', '恢复删除资产', '打开资产目录',
                      '制作记录', '桌面打开 ComfyUI', '浏览器打开 ComfyUI', '强制关闭 ComfyUI')

SIZES = ('1280x800+0+0', '1024x600+0+0')


def _walk(widget):
    for child in widget.winfo_children():
        yield child
        yield from _walk(child)


def _buttons(widget):
    return [item for item in _walk(widget) if isinstance(item, ttk.Button)]


def _by_text(widget, text):
    return [item for item in _buttons(widget) if str(item.cget('text')) == text]


def _menu_labels(menu):
    end = menu.index('end')
    if end is None:
        return []
    return ['---' if menu.type(index) == 'separator' else str(menu.entrycget(index, 'label'))
            for index in range(end + 1)]


def _cascade(menu, label):
    end = menu.index('end')
    for index in range((end if end is not None else -1) + 1):
        if menu.type(index) == 'cascade' and str(menu.entrycget(index, 'label')) == label:
            return menu.nametowidget(menu.entrycget(index, 'menu'))
    raise AssertionError('右键菜单缺少级联「%s」' % label)


def _asset_menu(desktop, event=None):
    table = desktop.asset_table
    if event is None:
        event = SimpleNamespace(x_root=table.winfo_rootx() + 4,
                                y_root=table.winfo_rooty() + 4,
                                keysym='')
    return desktop.asset_page_view.context_menu(event)


class BoardAssetsButtonTests(media_fixtures._DesktopCase):
    """补上分镜前置后再看页面，页面走正常构建分支而不是空项目引导。"""

    with_storyboard = True

    def setUp(self):
        super().setUp()
        self.assertTrue(self.desktop.align_studio(), '夹具应补上视频前置（studio）')
        tk_test_support.pump(self.win, .5)

    def _close_desktop(self):
        """关窗前取消版本检查那条 after 作业，避免测试结束后报 invalid command name。"""
        super()._close_desktop()
        try:
            for job in self.win.tk.call('after', 'info'):
                if 'start_update_check' in str(self.win.tk.call('after', 'info', job)):
                    self.win.after_cancel(job)
        except Exception:
            pass

    def _open(self, page_name, size):
        page = PAGE[page_name]
        thrown = self.open_page(page)
        self.assertEqual([], thrown, '第%02d页打开时抛出 Tk 回调异常' % page)
        self.assertEqual(page, self.desktop.page_index)
        self.win.geometry(size)
        tk_test_support.pump(self.win, .8)
        return self.desktop

    def test_storyboard_single_editor_has_no_legacy_action_buttons(self):
        for size in SIZES:
            with self.subTest(size=size):
                desktop = self._open('storyboard', size)
                mapped_buttons = [b for b in _buttons(desktop.content) if b.winfo_ismapped()]
                legacy = [b for b in mapped_buttons if str(b.cget('text')) in STORYBOARD_BUTTONS]
                self.assertEqual([], legacy, '%s：03 页不应残留旧动作按钮' % size)
                unexpected = [str(b.cget('text')) for b in mapped_buttons
                              if str(b.cget('text')) != '×']
                self.assertEqual([], unexpected,
                                 '%s：编辑器内除关闭当前文件 × 外不应有常驻按钮' % size)
                for close in [b for b in mapped_buttons if str(b.cget('text')) == '×']:
                    self.assertIn(str(close.cget('takefocus')).lower(), ('1', 'true', 'yes'),
                                  '关闭当前文件按钮必须保留键盘可达性')
                page = desktop.storyboard_editor_page
                event = SimpleNamespace(x_root=100, y_root=100)
                with mock.patch('ui_widgets.ContextMenu.popup', return_value='break'):
                    page.on_context_menu(event)
                labels = _menu_labels(page.last_menu)
                for expected in ('导入 JSON 分镜…', '重排镜头编号', '打开分镜目录', '刷新分镜列表'):
                    self.assertIn(expected, labels, '03 页右键菜单应包含「%s」' % expected)

    def test_asset_filter_cascade_lists_all_four_kinds(self):
        desktop = self._open('assets', SIZES[1])
        menu = _asset_menu(desktop)
        submenu = _cascade(menu, '筛选资产')
        labels = _menu_labels(submenu)
        for label in ('全部', '角色', '场景', '道具'):
            self.assertTrue(any(item.endswith(label) for item in labels),
                            '筛选资产子菜单缺少「%s」：%s' % (label, labels))
        self.assertTrue(any(item.startswith('●') for item in labels),
                        '当前筛选档应在子菜单里用 ● 标出')

    def test_asset_menu_carries_former_button_actions(self):
        desktop = self._open('assets', SIZES[0])
        for text in ASSET_BUTTONS:
            self.assertEqual([], _by_text(desktop.content, text),
                             '05 页不应残留旧按钮「%s」' % text)
        menu = _asset_menu(desktop)
        labels = _menu_labels(menu)
        self.assertIn('筛选资产', labels)
        for expected in ASSET_MENU_ACTIONS:
            self.assertIn(expected, labels, '资产右键菜单缺少「%s」' % expected)
        texts = [str(item.cget('text')) for item in _walk(desktop.content)
                 if isinstance(item, ttk.Label)]
        self.assertTrue(any('右键菜单' in text for text in texts),
                        '页面应保留右键入口提示')

    def test_asset_menu_is_available_from_keyboard_and_send_is_registered(self):
        desktop = self._open('assets', SIZES[0])
        table = desktop.asset_table
        rows = table.get_children()
        self.assertTrue(rows, '夹具资产表至少应有一行')
        table.focus(rows[0])
        table.focus_force()
        self.win.update()
        with mock.patch.object(ContextMenu, 'popup_at', autospec=True) as popup:
            popup.side_effect = lambda menu, x, y: menu
            table.event_generate('<Shift-F10>')
            tk_test_support.pump(self.win, .2)
        self.assertTrue(popup.called, 'Shift+F10 应弹出资产右键菜单')
        self.assertEqual((rows[0],), tuple(table.selection()),
                         'Shift+F10 打开的行菜单应作用于键盘焦点行')
        self.assertIsNotNone(desktop.shared_input.stage_action('assets'),
                             '空输入框发送仍应登记为手动制作资产入口')

    def test_right_click_selects_the_row_before_menu_actions(self):
        desktop = self._open('assets', SIZES[0])
        table = desktop.asset_table
        rows = table.get_children()
        self.assertTrue(rows, '夹具资产表至少应有一行')
        row = rows[0]
        if table.selection():
            table.selection_remove(*table.selection())
        bbox = table.bbox(row, '#1')
        self.assertTrue(bbox, '第一行资产名列应已完成布局')
        x, y, width, height = bbox
        event = SimpleNamespace(x_root=table.winfo_rootx() + x + max(1, width // 2),
                                y_root=table.winfo_rooty() + y + max(1, height // 2),
                                keysym='', num=3)
        menu = _asset_menu(desktop, event)
        self.assertIsNotNone(menu)
        self.assertEqual((row,), tuple(table.selection()),
                         '右键哪一行，后续「导入／候选图墙／恢复」就应作用在哪一行')
        self.assertEqual(row, table.focus())


if __name__ == '__main__':
    unittest.main()

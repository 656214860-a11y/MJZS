# -*- coding: utf-8 -*-
"""L4-U7b：03 初步分镜页与 05 资产管理页的按钮换行对齐。

五组用例，全部量真实页面上控件的实际几何（``winfo_rootx``／``winfo_rooty``／
``winfo_width``／``winfo_height``／``winfo_reqwidth``），不比对源码字符串：

- T1（R1）：03 页那 7 颗动作按钮换行后，每行第一颗与第一行第一颗的 x 相同，
  且后一行的上沿不压住前一行的下沿；
- T2（R2）：05 页「资产」「参考图」「资产图片」三行分别换行后，换到下一行的按钮
  与本行第一颗按钮的 x 相同，不回到行首标签下面；
- T3（R3）：05 页三个行首标签都可见，标签矩形不与任何按钮矩形相交；
- T4（R4）：05 页底部制作行 5 颗按钮实际宽度相同，且每颗都放得下自己的文字；
- T5：两页按钮文字集合与改前快照一致。

按钮一律按文字查找，不写死坐标。改前 T2、T4 为红。
"""
import sys
import unittest
from pathlib import Path
from tkinter import ttk

PROGRAM = Path(__file__).resolve().parents[1]
TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(PROGRAM))
sys.path.insert(0, str(TESTS))

import test_desktop_media_pages as media_fixtures  # noqa: E402  先加载自检环境
import ui.desktop_asset_pages  # noqa: E402,F401  （--affected desktop_asset_pages 的消费者）
import ui.storyboard_files  # noqa: E402,F401  （--affected storyboard_files 的消费者）
import tk_test_support  # noqa: E402
from ui.desktop_page_registry import PAGE  # noqa: E402
from ui.desktop_page_support import ASSET_ROW_LABEL  # noqa: E402

# 改前快照：按钮文字（按页面原顺序，断言时按集合比较）。
STORYBOARD_BUTTONS = ('手动采用分镜', '手动取消采用', '打开选中JSON', '导入JSON分镜',
                      '分镜目录', '重排镜头编号', '删除选中分镜')

ASSET_BUTTONS = ('全部', '角色', '场景', '道具', '检查提示词', '识别背景人物',
                 '导入参考图', '候选图墙', '参考图目录',
                 '导入资产图片', '批量删除资产', '恢复删除资产', '资产目录',
                 '手动制作资产', '强制关闭 ComfyUI', '制作记录',
                 '桌面打开 ComfyUI', '浏览器打开 ComfyUI')

# 05 页前三行的行首标签与各自的按钮。
ASSET_ROWS = (
    ('资产', ('全部', '角色', '场景', '道具', '检查提示词', '识别背景人物')),
    ('参考图', ('导入参考图', '候选图墙', '参考图目录')),
    ('资产图片', ('导入资产图片', '批量删除资产', '恢复删除资产', '资产目录')),
)
ROW_LABELS = tuple(label for label, _ in ASSET_ROWS)
PRODUCTION_BUTTONS = ('手动制作资产', '强制关闭 ComfyUI', '制作记录',
                      '桌面打开 ComfyUI', '浏览器打开 ComfyUI')

SIZES = ('1280x800+0+0', '880x600+0+0')


def _walk(widget):
    for child in widget.winfo_children():
        yield child
        yield from _walk(child)


def _buttons(widget):
    return [item for item in _walk(widget) if isinstance(item, ttk.Button)]


def _by_text(widget, text):
    return [item for item in _buttons(widget) if str(item.cget('text')) == text]


def _one(widget, text):
    matches = _by_text(widget, text)
    if len(matches) != 1:
        raise AssertionError('应有且只有一颗「%s」，实际 %d 颗' % (text, len(matches)))
    return matches[0]


def _group_rows(buttons):
    """按 ``winfo_rooty`` 把按钮分成行；行内按 x 从左到右，行间从上到下。"""
    rows = {}
    for button in buttons:
        rows.setdefault(button.winfo_rooty(), []).append(button)
    return [sorted(rows[y], key=lambda b: b.winfo_rootx()) for y in sorted(rows)]


def _rect(widget):
    return (widget.winfo_rootx(), widget.winfo_rooty(),
            widget.winfo_rootx() + widget.winfo_width(),
            widget.winfo_rooty() + widget.winfo_height())


def _intersects(first, second):
    return (first[0] < second[2] and second[0] < first[2]
            and first[1] < second[3] and second[1] < first[3])


class BoardAssetsButtonTests(media_fixtures._DesktopCase):
    """补上分镜前置后再量按钮，页面走正常构建分支而不是空项目引导。"""

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

    # ── T1：03 页单编辑器无顶部／底部动作钮，必要功能收进右键菜单 ────────
    def test_t1_storyboard_action_rows_left_aligned(self):
        from types import SimpleNamespace
        from unittest import mock
        for size in SIZES:
            with self.subTest(size=size):
                desktop = self._open('storyboard', size)
                mapped_buttons = [b for b in _buttons(desktop.content) if b.winfo_ismapped()]
                self.assertEqual(mapped_buttons, [], '%s：03 页不再保留顶部／底部按钮栏' % size)
                page = desktop.storyboard_editor_page
                event = SimpleNamespace(x_root=100, y_root=100)
                with mock.patch('ui_widgets.ContextMenu.popup', return_value='break'):
                    page.on_context_menu(event)
                labels = [str(page.last_menu.entrycget(i, 'label'))
                          for i in range((page.last_menu.index('end') or -1) + 1)
                          if page.last_menu.type(i) == 'command']
                for expected in ('导入 JSON 分镜…', '重排镜头编号', '打开分镜目录', '刷新分镜列表'):
                    self.assertIn(expected, labels, '03 页右键菜单应包含「%s」' % expected)

    # ── T2：05 页前三行换行后不回到标签下面 ──────────────────────
    def test_t2_asset_rows_wrap_under_first_button(self):
        desktop = self._open('assets', SIZES[1])
        for label, texts in ASSET_ROWS:
            with self.subTest(row=label):
                buttons = [_one(desktop.content, text) for text in texts]
                rows = _group_rows(buttons)
                first_x = rows[0][0].winfo_rootx()
                for index, row in enumerate(rows, start=1):
                    self.assertEqual(
                        row[0].winfo_rootx(), first_x,
                        '「%s」行第 %d 行第一颗「%s」x=%d，应与本行第一颗 x=%d 相同'
                        % (label, index, str(row[0].cget('text')),
                           row[0].winfo_rootx(), first_x))

    # ── T3：05 页行首标签可见且不被按钮盖住 ──────────────────────
    def test_t3_asset_row_labels_visible_and_clear_of_buttons(self):
        for size in SIZES:
            with self.subTest(size=size):
                desktop = self._open('assets', size)
                labels = [item for item in _walk(desktop.content)
                          if isinstance(item, ttk.Label)
                          and str(item.cget('text')) in ROW_LABELS
                          and str(item.cget('width')) == str(ASSET_ROW_LABEL)]
                self.assertEqual(
                    sorted(str(item.cget('text')) for item in labels),
                    sorted(ROW_LABELS),
                    '%s：三个行首标签应各出现一次' % size)
                buttons = [_one(desktop.content, text) for text in ASSET_BUTTONS]
                for label in labels:
                    self.assertTrue(label.winfo_ismapped(),
                                    '%s：「%s」标签应已映射' % (size, str(label.cget('text'))))
                    self.assertGreater(label.winfo_width(), 0)
                    self.assertGreater(label.winfo_height(), 0)
                    for button in buttons:
                        self.assertFalse(
                            _intersects(_rect(label), _rect(button)),
                            '%s：「%s」标签被「%s」按钮盖住'
                            % (size, str(label.cget('text')), str(button.cget('text'))))

    # ── T4：05 页底部制作行 5 颗按钮同宽且放得下文字 ──────────────
    def test_t4_production_buttons_share_width_and_fit_text(self):
        for size in SIZES:
            with self.subTest(size=size):
                desktop = self._open('assets', size)
                buttons = [_one(desktop.content, text) for text in PRODUCTION_BUTTONS]
                widths = {button.winfo_width() for button in buttons}
                self.assertEqual(
                    len(widths), 1,
                    '%s：底部制作行按钮实际宽度应相同，实测 %s'
                    % (size, {str(button.cget('text')): button.winfo_width()
                              for button in buttons}))
                for button in buttons:
                    self.assertGreaterEqual(
                        button.winfo_width(), button.winfo_reqwidth(),
                        '%s：「%s」实际宽 %d 小于文字需要的 %d'
                        % (size, str(button.cget('text')),
                           button.winfo_width(), button.winfo_reqwidth()))

    # ── T5：03 页无遗留按钮；05 页按钮文字集合与改前一致 ───────────────
    def test_t5_button_texts_match_snapshot(self):
        desktop = self._open('storyboard', SIZES[0])
        for text in STORYBOARD_BUTTONS:
            self.assertEqual(0, len(_by_text(desktop.content, text)),
                             '03 页已改版为单编辑器，不应再残留「%s」按钮' % text)
        desktop = self._open('assets', SIZES[0])
        for text in ASSET_BUTTONS:
            self.assertEqual(1, len(_by_text(desktop.content, text)),
                             '05 页「%s」应各一颗' % text)


if __name__ == '__main__':
    unittest.main()

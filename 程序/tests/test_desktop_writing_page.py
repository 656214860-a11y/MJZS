# -*- coding: utf-8 -*-
"""L4-U5 页面内容区与底部输入框左右对齐（任务卡 L4-U5，L4-B6／L4-Q5）。

T1：三档窗口 × 文件面板开关，聊天框外框与输入框卡片外框的左右边缘差为 0。
T2：聊天文字区与输入文字区的文字起始列差为 0。

口径：「聊天框外框」取剧本准备页的 Box 外框 ``talk``（``Box.TFrame`` 1px 描边）
及其内容框 ``dialog``；「输入框卡片外框」取共享输入框的外框 ``input_ring``
（``_composer_shell`` 注释口径：外框由包裹层 1px 底色边承担）。「文字起始列」
＝控件内沿（bd＋highlightthickness＋padx），与首行内容无关，聊天气泡的
``lmargin`` 缩进不影响。
"""
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
TESTS = Path(__file__).resolve().parent
for _p in (str(HERE), str(TESTS)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import tk_test_support
from tests.ui_edges_support import make_minimal_project

import desktop as desktop_module
import desktop_shared_send         # 本卡对象模块（共享输入框链路，--affected 消费者锚点）
import desktop_writing_page        # 本卡对象模块（剧本准备页，同上）
from desktop import PAGE

WINDOW_SIZES = ('1280x800', '1024x680', '880x600')


class PageInputAlignmentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.win = tk_test_support.make_root()
        cls.temp = tempfile.TemporaryDirectory(prefix='l4u5-align-')
        cls._choose_project = desktop_module.Desktop.choose_project
        desktop_module.Desktop.choose_project = lambda self: None
        cls.project = make_minimal_project(cls.temp.name)
        cls.desktop = desktop_module.Desktop(cls.win, root=str(HERE))
        cls.desktop.root = cls.project
        cls.desktop.show(PAGE['script'])
        cls.pump(2)
        cls.win.deiconify()

    @classmethod
    def tearDownClass(cls):
        try:
            cls.desktop.cancel_timers()
        except Exception:
            pass
        desktop_module.Desktop.choose_project = cls._choose_project
        cls.win.destroy()
        cls.temp.cleanup()

    @classmethod
    def pump(cls, seconds=.3):
        tk_test_support.pump(cls.win, seconds)

    def setUp(self):
        if getattr(self.desktop, 'page_index', None) != PAGE['script']:
            self.desktop.show(PAGE['script'])
            self.pump(1)
        self.desktop.files_panel.collapse()
        self.pump(.3)

    # ── 测量辅助 ────────────────────────────────────────────────────
    @staticmethod
    def _edges(widget):
        return widget.winfo_rootx(), widget.winfo_rootx() + widget.winfo_width()

    @staticmethod
    def _text_start(widget):
        """文字起始列＝控件内沿（bd＋highlightthickness＋padx）。"""
        return (widget.winfo_rootx() + int(float(widget.cget('bd')))
                + int(float(widget.cget('highlightthickness')))
                + int(float(widget.cget('padx'))))

    def _frames(self):
        ctrl = self.desktop._writing_page_controller
        return ctrl.talk, ctrl.dialog, self.desktop.shared_input.input_ring

    def _settle(self, size, panel_open):
        self.win.geometry(size)
        self.pump(1.0)
        panel = self.desktop.files_panel
        (panel.open_panel if panel_open else panel.collapse)()
        self.pump(1.0)

    # ── T1：聊天框外框与输入框卡片外框左右边缘差为 0 ──────────────────
    def test_chat_frame_and_input_card_share_edges(self):
        for panel_open in (False, True):
            for size in WINDOW_SIZES:
                with self.subTest(size=size, panel_open=panel_open):
                    self._settle(size, panel_open)
                    talk, dialog, ring = self._frames()
                    state = '面板开' if panel_open else '面板关'
                    ring_left, ring_right = self._edges(ring)
                    for name, frame in (('外框', talk), ('内容框', dialog)):
                        left, right = self._edges(frame)
                        self.assertEqual(
                            left, ring_left,
                            '%s 聊天%s左缘 %d ≠ 输入框卡片外框左缘 %d（%s）'
                            % (size, name, left, ring_left, state))
                        self.assertEqual(
                            right, ring_right,
                            '%s 聊天%s右缘 %d ≠ 输入框卡片外框右缘 %d（%s）'
                            % (size, name, right, ring_right, state))

    # ── T2：聊天文字区与输入文字区的文字起始列差为 0 ──────────────────
    def test_chat_and_input_text_start_column(self):
        chat = self.desktop.idea_log
        box = self.desktop.shared_input.input
        for panel_open in (False, True):
            for size in WINDOW_SIZES:
                with self.subTest(size=size, panel_open=panel_open):
                    self._settle(size, panel_open)
                    self.assertEqual(
                        self._text_start(chat), self._text_start(box),
                        '%s 聊天文字起始列 %d ≠ 输入文字起始列 %d（面板%s）'
                        % (size, self._text_start(chat), self._text_start(box),
                           '开' if panel_open else '关'))


if __name__ == '__main__':
    unittest.main()

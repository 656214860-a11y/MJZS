# -*- coding: utf-8 -*-
"""剧本结构页：上、下两个文本框与底部输入框左右对齐（2026-11-22 报的界面问题）。

口径同 tests/test_desktop_writing_page.py 的 T1（剧本准备页的同类用例）：三档窗口 × 文件面板开关，
文本框（行号槽、正文、竖向滚动条所在的那一块）和它上方那一行（标题、下拉框、按钮）的左右边缘，
与共享输入框外框 ``input_ring`` 的左右边缘差为 0。

每条用例自己建窗口、用完就关。首帧之后的后台维护（技能同步、旧项目迁移、续期与更新检查的排程）
换成空动作：这里只量排版，不该碰测试目录以外的东西。等待用「页面内容宽度已跟上画布，而且
连续两次量到的结果相同」判断重排做完；``LAYOUT_TIMEOUT`` 只是机器很忙时的上限，平时排稳就往下走。
"""
import sys
import tempfile
import time
import tkinter as tk
import unittest
from pathlib import Path
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


def _edges(widget):
    left = widget.winfo_rootx()
    return left, left + widget.winfo_width()


class StructurePageInputAlignmentTests(unittest.TestCase):
    def _open(self):
        temp = tempfile.TemporaryDirectory(prefix='s02-align-')
        self.addCleanup(temp.cleanup)
        project, writing = _make_project(temp.name)
        structured = writing / '结构剧本'
        structured.mkdir()
        (structured / 'script0.md').write_text(
            '# 结构化剧本\n\n## 分场剧本\n\n正文\n', encoding='utf-8')
        win = tk.Tk()
        win.geometry(WINDOW_SIZES[0] + '+40+40')
        win.deiconify()
        win.update()
        self.addCleanup(lambda: win.winfo_exists() and win.destroy())
        quiet = mock.patch.object(desktop_module.Desktop, '_after_first_paint', lambda self: None)
        quiet.start()
        self.addCleanup(quiet.stop)
        desktop = _show_script_structure(win, project)
        self.addCleanup(self._stop, desktop)
        return win, desktop

    @staticmethod
    def _stop(desktop):
        try:
            desktop.cancel_timers()
        except Exception:
            pass

    def _measure(self, desktop):
        blocks = []
        for name, attribute in (('自然剧本', 'script_structure_source_preview'),
                                ('结构剧本', 'script_structure_output_preview')):
            preview = getattr(desktop, attribute)
            box = getattr(desktop, attribute + '_content_box')
            blocks.append((name + '文本框', _edges(preview.master)))
            blocks.append((name + '标题行', _edges(box.header)))
        return _edges(desktop.shared_input.input_ring), tuple(blocks)

    def _wait_layout(self, win, desktop):
        """等整页重排做完：页面内容宽度等于画布宽度，而且连续两次量到的边缘相同。"""
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
        win, desktop = self._open()
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

    def test_text_boxes_share_edges_with_input_box_panel_closed(self):
        self._check_sizes(panel_open=False)

    def test_text_boxes_share_edges_with_input_box_panel_open(self):
        self._check_sizes(panel_open=True)


if __name__ == '__main__':
    unittest.main()

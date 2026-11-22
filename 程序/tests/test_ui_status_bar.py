# -*- coding: utf-8 -*-
"""R2985 P0：StatusBar 组件（真 Tk：左区常驻段、右区四级消息、历史面板）。"""
import sys
import time
import unittest
from pathlib import Path

HERE = str(Path(__file__).resolve().parents[1])
sys.path.insert(0, HERE)
sys.path.insert(0, str(Path(__file__).resolve().parent))

import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk

from skip_reasons import PLATFORM_TK_DISPLAY
from ui import ui_theme
from ui.ui_popup import char_unit_px, measure_text_width
from ui.ui_status_bar import LEVEL_STYLE, StatusBar
from ui.ui_status_bus import Message, StatusBus
from ui_tokens import (COLORS, STATUS_BAR_EDGE_PAD, STATUS_BAR_FONT, STATUS_BAR_SEGMENT_MAX_WIDTH,
                       STATUS_BAR_SEPARATOR, STATUS_BAR_SEPARATOR_GAP)


class StatusBarTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.win = tk.Tk()
        except tk.TclError as exc:
            raise unittest.SkipTest(PLATFORM_TK_DISPLAY + ': ' + str(exc))
        cls.win.withdraw()
        cls.win.geometry('900x400+0+0')

    def setUp(self):
        self.bus = StatusBus()
        self.bar = StatusBar(self.win, self.bus, neutral='就绪')
        self.bar.pack(fill='x')
        self.pump(0.05)

    def tearDown(self):
        self.bar.shutdown()
        self.bar.destroy()
        self.pump(0.02)

    @classmethod
    def tearDownClass(cls):
        cls.win.destroy()

    def pump(self, seconds=0.3):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            self.win.update_idletasks()
            self.win.update()
            time.sleep(0.005)

    # ---- 左区常驻段 ----
    def test_segment_create_update_and_clear(self):
        label = self.bar.set_segment('path', 'D:/漫剧下载/项目')
        self.assertEqual(label.full_text, 'D:/漫剧下载/项目')
        self.assertEqual(self.bar.set_segment('path', '新路径'), label)
        self.assertEqual(label.full_text, '新路径')
        self.bar.clear_segment('path')
        self.assertNotIn('path', self.bar._segments)

    def test_segment_click_invokes_command(self):
        calls = []
        self.bar.set_segment('token', 'Token: 0', command=lambda: calls.append(1))
        self.pump(0.05)
        label = self.bar._segments['token'][1]
        label.event_generate('<Button-1>')
        self.pump(0.05)
        self.assertEqual(calls, [1])

    # ---- 右区消息 ----
    def test_message_renders_level_style(self):
        msg = Message.make('error', '生成失败')
        self.bus.publish(msg)
        self.pump(0.25)  # 必须长于 100ms 心跳周期，消息才会被泵上屏
        self.assertEqual(self.bar.message.full_text, '✕ 生成失败')
        self.assertEqual(str(self.bar.message.cget('background')), COLORS['danger_subtle'])
        self.assertEqual(str(self.bar.message.cget('foreground')), COLORS['danger_text'])

    def test_level_styles_are_token_backed(self):
        for level, keys in (('info', ('background_primary', 'text_primary')),
                            ('success', ('success_subtle', 'success_text')),
                            ('warning', ('primary_subtle', 'primary_pressed')),
                            ('error', ('danger_subtle', 'danger_text'))):
            style = LEVEL_STYLE[level]
            self.assertEqual(style['bg'], COLORS[keys[0]])
            self.assertEqual(style['fg'], COLORS[keys[1]])

    def test_transient_message_auto_expires(self):
        # ttl 必须明显长于 100ms 心跳周期，先确认上屏，再确认到期回中性。
        self.bus.publish(Message('info', '临时', ttl=400.0))
        self.pump(0.25)
        self.assertEqual(self.bar.message.full_text, '临时')
        self.pump(0.8)
        self.assertIsNone(self.bus.current)
        self.assertEqual(self.bar.message.full_text, '就绪')

    def test_error_message_persists(self):
        self.bus.publish(Message.make('error', '常驻错误'))
        self.pump(0.05)
        self.pump(0.4)
        self.assertIsNotNone(self.bus.current)
        self.assertEqual(self.bar.message.full_text, '✕ 常驻错误')

    # ---- 历史面板 ----
    def test_history_popup_lists_past_messages(self):
        self.bus.publish(Message.make('error', '第一条'))
        self.pump(0.05)
        self.bus.dismiss()
        self.pump(0.02)
        self.bar._toggle_history()
        self.pump(0.05)
        self.assertIsNotNone(self.bar._popup)
        found = []

        def walk(widget):
            for child in widget.winfo_children():
                if child.winfo_class() == 'Text':
                    found.append(child)
                walk(child)

        walk(self.bar._popup)
        self.assertTrue(found)
        self.bar._close_history()
        self.assertIsNone(self.bar._popup)

    def test_neutral_shown_after_expiry_event(self):
        self.bar._show_neutral()
        self.assertEqual(self.bar.message.full_text, '就绪')


class StatusBarLayoutTests(unittest.TestCase):
    """UX-C4：左区各段按文字定宽、空段不占位、分隔和间距一致、全栏同一字号（真 Tk，窗口要映射出来才量得到位置）。"""

    @classmethod
    def setUpClass(cls):
        try:
            cls.win = tk.Tk()
        except tk.TclError as exc:
            raise unittest.SkipTest(PLATFORM_TK_DISPLAY + ': ' + str(exc))
        ui_theme.apply(cls.win)
        cls.win.geometry('1400x300+0+0')
        cls.win.update()

    @classmethod
    def tearDownClass(cls):
        cls.win.destroy()

    def setUp(self):
        self.bus = StatusBus()
        self.bar = StatusBar(self.win, self.bus, neutral='就绪')
        self.bar.pack(fill='x')
        self.pump()

    def tearDown(self):
        self.bar.shutdown()
        self.bar.destroy()
        self.pump(0.02)

    def pump(self, seconds=0.08):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            self.win.update_idletasks()
            self.win.update()
            time.sleep(0.005)

    def text_px(self, text):
        return measure_text_width(STATUS_BAR_FONT, [text], root=self.win)

    def unit(self):
        return char_unit_px(STATUS_BAR_FONT, self.win)

    def row(self):
        """左区里看得见的控件，从左到右。"""
        shown = [w for w in self.bar.left_zone.winfo_children() if w.winfo_ismapped() and w.winfo_width() > 1]
        return sorted(shown, key=lambda w: w.winfo_x())

    def texts(self):
        return [str(w.cget('text')) for w in self.row()]

    def gaps(self):
        """相邻两个可见控件之间的空白：前一个的文字末尾到后一个的左边。"""
        row = self.row()
        return [nxt.winfo_x() - (prev.winfo_x() + self.text_px(prev.cget('text')))
                for prev, nxt in zip(row, row[1:])]

    def actual_font(self, widget):
        spec = widget.cget('font') or ttk.Style(self.win).lookup(widget.cget('style') or 'TLabel', 'font')
        return tkfont.Font(root=self.win, font=spec).actual()

    def test_short_segment_is_as_wide_as_its_text(self):
        label = self.bar.set_segment('page', '01 创意')
        self.pump()
        self.assertEqual(label.cget('text'), '01 创意')
        extra = label.winfo_width() - self.text_px('01 创意')
        self.assertGreaterEqual(extra, 0)
        self.assertLess(extra, self.unit(), '短文字的段不该比文字宽出一个字符')

    def test_empty_segment_takes_no_room_and_comes_back_in_its_place(self):
        self.bar.set_segment('page', '01 创意')
        path = self.bar.set_segment('path', '')
        self.bar.set_segment('model', '当前模型：甲')
        self.pump()
        self.assertFalse(path.winfo_ismapped())
        self.assertEqual(self.texts(), ['01 创意', STATUS_BAR_SEPARATOR, '当前模型：甲'])
        self.assertIs(self.bar.set_segment('path', 'D:/项目'), path)
        self.pump()
        self.assertEqual(self.texts(), ['01 创意', STATUS_BAR_SEPARATOR, 'D:/项目',
                                        STATUS_BAR_SEPARATOR, '当前模型：甲'])
        self.bar.set_segment('path', '')
        self.pump()
        self.assertEqual(self.texts(), ['01 创意', STATUS_BAR_SEPARATOR, '当前模型：甲'])
        self.assertIn('path', self.bar._segments)

    def test_no_separator_at_either_end_and_never_two_in_a_row(self):
        self.bar.set_segment('a', '')
        self.bar.set_segment('b', '乙')
        self.bar.set_segment('c', '')
        self.bar.set_segment('d', '丁')
        self.bar.set_segment('e', '')
        self.pump()
        self.assertEqual(self.texts(), ['乙', STATUS_BAR_SEPARATOR, '丁'])
        self.bar.set_segment('a', '甲')
        self.bar.clear_segment('d')
        self.pump()
        self.assertEqual(self.texts(), ['甲', STATUS_BAR_SEPARATOR, '乙'])
        self.bar.set_segment('b', '')
        self.pump()
        self.assertEqual(self.texts(), ['甲'])

    def test_gaps_between_visible_segments_are_equal(self):
        self.bar.set_segment('page', '01 创意')
        self.bar.set_segment('path', 'D:/漫剧下载/项目甲')
        self.bar.set_segment('model', '模型：甲')
        self.bar.set_segment('note', '已完成 3 步')
        self.pump()
        gaps = self.gaps()
        self.assertEqual(len(gaps), 6)
        self.assertEqual(len(set(gaps[0::2])), 1, '段文字到分隔符的空白各处要一样：%s' % gaps)
        self.assertEqual(len(set(gaps[1::2])), 1, '分隔符到下一段的空白各处要一样：%s' % gaps)
        self.assertLessEqual(abs(gaps[0] - gaps[1]), 2, '分隔符两侧要等距：%s' % gaps)
        self.assertGreaterEqual(gaps[1], STATUS_BAR_SEPARATOR_GAP)

    def test_separator_has_the_font_and_colour_of_segment_text(self):
        label = self.bar.set_segment('page', '01 创意')
        self.bar.set_segment('path', 'D:/项目')
        self.pump()
        separator = self.row()[1]
        self.assertEqual(str(separator.cget('text')), STATUS_BAR_SEPARATOR)
        self.assertEqual(self.actual_font(separator), self.actual_font(label))
        self.assertEqual(self.actual_font(label), tkfont.Font(root=self.win, font=STATUS_BAR_FONT).actual())
        self.assertEqual(str(separator.cget('style')), str(label.cget('style')))

    def test_segment_over_the_cap_is_cut_and_hover_keeps_the_full_text(self):
        long = 'D:/漫剧下载/' + '很长的项目路径' * 6
        label = self.bar.set_segment('path', long)
        self.pump()
        self.assertTrue(str(label.cget('text')).endswith('…'))
        self.assertEqual(label.tooltip.text, long)
        self.assertEqual(label.full_text, long)
        cap = STATUS_BAR_SEGMENT_MAX_WIDTH * self.unit()
        self.assertLess(abs(label.winfo_width() - cap), self.unit())
        short = self.bar.set_segment('path', 'D:/项目')
        self.pump()
        self.assertEqual(short.cget('text'), 'D:/项目')
        self.assertLess(short.winfo_width(), cap)

    def test_explicit_width_is_kept(self):
        label = self.bar.set_segment('note', '短', width=12)
        self.pump()
        self.assertEqual(int(str(label.cget('width'))), 12)
        self.assertLess(abs(label.winfo_width() - 12 * self.unit()), self.unit())

    def test_neutral_message_is_muted_like_the_left_zone_and_errors_stay_red(self):
        label = self.bar.set_segment('page', '01 创意')
        self.pump()
        muted = str(ttk.Style(self.win).lookup(str(label.cget('style')), 'foreground'))
        self.assertEqual(muted, COLORS['text_secondary'])
        self.assertEqual(self.bar.message.full_text, '就绪')
        self.assertEqual(str(self.bar.message.cget('foreground')), muted)
        self.assertEqual(self.actual_font(self.bar.message), self.actual_font(label))
        self.bus.publish(Message.make('error', '生成失败'))
        self.pump(0.25)
        self.assertEqual(str(self.bar.message.cget('foreground')), COLORS['danger_text'])
        self.assertEqual(str(self.bar.message.cget('background')), COLORS['danger_subtle'])

    def test_edges_use_one_padding(self):
        self.bar.set_segment('page', '01 创意')
        self.pump()
        self.assertEqual(self.bar.left_zone.winfo_x(), STATUS_BAR_EDGE_PAD)
        right = self.bar.winfo_width() - (self.bar.message.winfo_x() + self.bar.message.winfo_width())
        self.assertEqual(right, STATUS_BAR_EDGE_PAD)
        between = self.bar.message.winfo_x() - (self.bar.left_zone.winfo_x() + self.bar.left_zone.winfo_width())
        self.assertEqual(between, STATUS_BAR_EDGE_PAD)

    def test_widget_put_in_by_another_module_gets_the_same_separators(self):
        self.bar.set_segment('page', '01 创意')
        self.bar.set_segment('path', '')
        extra = tk.Label(self.bar.left_zone, text='Token: 1', font=STATUS_BAR_FONT)
        extra.pack(side='left', padx=(4, 0))
        self.bar.set_segment('model', '模型：甲')
        self.pump()
        self.assertEqual(self.texts(), ['01 创意', STATUS_BAR_SEPARATOR, 'Token: 1',
                                        STATUS_BAR_SEPARATOR, '模型：甲'])
        row = self.row()
        left = row[2].winfo_x() - (row[1].winfo_x() + row[1].winfo_width())
        right = row[4].winfo_x() - (row[3].winfo_x() + row[3].winfo_width())
        self.assertEqual(left, right, '别的模块放进来的控件，分隔符到它的距离和别的段一样')
        self.bar.set_segment('path', 'D:/项目')
        self.pump()
        self.assertEqual(self.texts(), ['01 创意', STATUS_BAR_SEPARATOR, 'D:/项目', STATUS_BAR_SEPARATOR, 'Token: 1',
                                        STATUS_BAR_SEPARATOR, '模型：甲'])

    def test_empty_widget_from_another_module_gets_no_separator(self):
        self.bar.set_segment('page', '01 创意')
        holder = tk.Frame(self.bar.left_zone)
        holder.pack(side='left')
        self.bar.set_segment('model', '模型：甲')
        self.pump()
        self.assertEqual(self.texts(), ['01 创意', STATUS_BAR_SEPARATOR, '模型：甲'])
        filled = tk.Label(holder, text='Token: 1', font=STATUS_BAR_FONT)
        filled.pack(side='left')
        self.pump(0.2)
        row = self.row()
        self.assertEqual(len(row), 5, '外来控件有了内容，状态栏要自己补上分隔符')
        self.assertIs(row[2], holder)
        self.assertEqual([str(w.cget('text')) for w in (row[1], row[3])], [STATUS_BAR_SEPARATOR] * 2)


if __name__ == '__main__':
    unittest.main()

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

from skip_reasons import PLATFORM_TK_DISPLAY
from ui.ui_status_bar import LEVEL_STYLE, StatusBar
from ui.ui_status_bus import Message, StatusBus
from ui_tokens import COLORS


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
        self.pump(0.05)
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
        self.bus.publish(Message('info', '临时', ttl=80.0))
        self.pump(0.05)
        self.assertEqual(self.bar.message.full_text, '临时')
        self.pump(0.5)
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
        text = self.bar._popup.winfo_children()
        self.assertTrue(any(w.winfo_class() == 'Text' for w in text))
        self.bar._close_history()
        self.assertIsNone(self.bar._popup)

    def test_neutral_shown_after_expiry_event(self):
        self.bar._show_neutral()
        self.assertEqual(self.bar.message.full_text, '就绪')


if __name__ == '__main__':
    unittest.main()

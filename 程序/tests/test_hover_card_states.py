# -*- coding: utf-8 -*-
"""R2997：Tooltip 悬停状态机——点击抑制重弹、卡片钉住、closeDelay grace、reshow 窗口、
被动弹层豁免与单例可见，全部用真 Tk 事件驱动验证（gui_hidden 隐藏桌面运行）。"""
import time
import tkinter as tk
import unittest
from unittest import mock

from ui_widgets import Tooltip


class HoverCardStateTests(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.root.geometry('480x300+0+0')
        self.addCleanup(self.root.destroy)
        self.button = tk.Button(self.root, text='目标')
        self.button.pack()
        # 先真正映射窗口：未映射控件上的合成 <Enter>/按键事件会被 Tk 丢弃。
        self.root.update_idletasks()
        self.root.update()
        # 隐藏桌面上后建的 Tk 根不会自动获得焦点；按键事件（Escape）只经焦点窗口投递，
        # 用 focus_force 强制获得焦点（与 test_asset_detail／test_idea_chat 同一惯例）。
        self.root.focus_force()

    def enter(self, widget=None):
        (widget or self.button).event_generate('<Enter>', x=2, y=2)
        self.root.update()

    def leave(self, widget=None):
        (widget or self.button).event_generate('<Leave>')
        self.root.update()

    def click(self, widget=None):
        (widget or self.button).event_generate('<Button-1>', x=2, y=2)
        self.root.update()

    def pump(self, seconds=0.3):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            self.root.update()

    def test_click_suppresses_repop_until_leave(self):
        """点击后指针未离开时重进不弹；离开再进入恢复悬停（报告的 bug 的回归锚）。"""
        tip = Tooltip(self.button, '说明', delay_ms=0, reshow_ms=0)
        self.enter()
        self.assertIsNotNone(tip._window)
        self.click()
        self.assertIsNone(tip._window)          # 点击即隐藏
        self.enter()                            # 指针没离开过：仍抑制
        self.assertIsNone(tip._window)
        self.leave()
        self.enter()                            # 离开再进入：恢复
        self.assertIsNotNone(tip._window)

    def test_repeated_enter_keeps_single_job_and_leave_cancels_it(self):
        """重复进入只留最新计时器；离开取消后定时到点不再弹出。"""
        tip = Tooltip(self.button, '说明', delay_ms=50)
        self.enter()
        self.enter()
        self.leave()
        self.pump(0.2)                          # 越过 50ms 显示点
        self.assertIsNone(tip._window)

    def test_reshow_window_skips_enter_delay(self):
        """关闭后 reshow 窗口内再进入跳过出现延迟。"""
        tip = Tooltip(self.button, '说明', delay_ms=60000, reshow_ms=5000)
        tip.hide()                              # 记 closed_at（无窗也记录）
        self.enter()
        self.assertIsNotNone(tip._window)       # 未等 60s，立即显示

    def test_card_close_delay_hides_after_grace(self):
        """卡片移出后 closeDelay 到点才隐藏（指针不在控件/卡片上时）。"""
        tip = Tooltip(self.button, '卡片', mode='card', delay_ms=0, close_delay_ms=50)
        self.enter()
        self.assertIsNotNone(tip._window)
        with mock.patch.object(tip, '_pointer_over', return_value=False):
            self.leave()
            self.assertIsNotNone(tip._window)   # 未到点
            self.pump(0.2)                      # 越过 closeDelay
            self.assertIsNone(tip._window)

    def test_card_close_delay_keeps_card_when_pointer_still_on_widget(self):
        """closeDelay 到点复核：指针仍在控件上即保留卡片。"""
        tip = Tooltip(self.button, '卡片', mode='card', delay_ms=0, close_delay_ms=50)
        self.enter()
        with mock.patch.object(tip, '_pointer_over', return_value=True):
            self.leave()
            self.pump(0.2)
            self.assertIsNotNone(tip._window)   # grace 复核通过：保留

    def test_pin_click_toggles_and_leave_does_not_hide(self):
        """卡片 pin_on_click：点击钉住、移出不隐藏、再点解除。"""
        tip = Tooltip(self.button, '卡片', mode='card', pin_on_click=True, delay_ms=0)
        self.enter()
        win = tip._window
        self.click()
        self.assertTrue(tip.pinned)
        self.assertIs(tip._window, win)
        self.leave()
        self.assertIsNotNone(tip._window)       # 钉住期间悬停不触发
        self.click()
        self.assertFalse(tip.pinned)
        self.assertIsNone(tip._window)

    def test_outside_click_unpins_card(self):
        """钉住后点空白处解除并隐藏。"""
        tip = Tooltip(self.button, '卡片', mode='card', pin_on_click=True, delay_ms=0)
        self.enter()
        self.click()
        self.assertTrue(tip.pinned)
        self.root.event_generate('<Button-1>', x=420, y=260)
        self.root.update()
        self.assertFalse(tip.pinned)
        self.assertIsNone(tip._window)

    def test_escape_unpins_card(self):
        """钉住后按 Escape 解除并隐藏。"""
        tip = Tooltip(self.button, '卡片', mode='card', pin_on_click=True, delay_ms=0)
        self.enter()
        self.click()
        self.assertTrue(tip.pinned)
        self.root.event_generate('<Escape>')
        self.root.update()
        self.assertFalse(tip.pinned)
        self.assertIsNone(tip._window)

    def test_window_is_passive_popup(self):
        """浮层走 make_passive_popup：带豁免标记，不抢 grab。"""
        tip = Tooltip(self.button, '说明', delay_ms=0)
        self.enter()
        self.assertTrue(getattr(tip._window, '_positioned_once', False))

    def test_only_one_visible_tip_at_a_time(self):
        """同一时刻只留一张可见卡片：新卡显示时旧卡 withdraw。"""
        other = tk.Button(self.root, text='另一个')
        other.pack()
        self.root.update_idletasks()
        a = Tooltip(self.button, '甲', delay_ms=0)
        b = Tooltip(other, '乙', delay_ms=0)
        self.enter()
        win_a = a._window
        self.enter(other)
        self.assertIsNotNone(b._window)
        self.assertFalse(win_a.winfo_viewable())


if __name__ == '__main__':
    unittest.main()

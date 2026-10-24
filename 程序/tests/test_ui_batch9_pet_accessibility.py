# -*- coding: utf-8 -*-
"""UI 批次 9：宠物层图标命中区与键盘可达。"""
from tkinter import ttk

import pet_ui_support
import ui_widgets
from tests.test_pet_ui import PetTestCase
from ui_tokens import COLORS, CONTROL_HIT_MIN


class PetAccessibilityBatch9Tests(PetTestCase):
    """真 Tk 几何与焦点：视觉图形不变，承接区不小于 32×32。"""

    def show_window(self):
        self.win.geometry('420x220')
        self.win.deiconify()
        self.win.update()

    def widget_at(self, x, y):
        """按 Tk 叠放次序在本窗口内取命中控件；不用 winfo_containing，免得被桌面上别的程序窗口挡住。"""
        parent = self.pet.paws.master
        for path in reversed(self.win.tk.splitlist(self.win.tk.call('winfo', 'children', parent))):
            widget = self.win.nametowidget(path)
            if not widget.winfo_ismapped():
                continue
            left, top = widget.winfo_rootx(), widget.winfo_rooty()
            if left <= x < left + widget.winfo_width() and top <= y < top + widget.winfo_height():
                return widget
        return None

    def test_gear_hit_target_is_32px_and_keyboard_triggers_the_same_command(self):
        calls = []
        gear = pet_ui_support.GearButton(self.win, command=lambda: calls.append('gear'))
        gear.canvas.place(x=180, y=120)
        self.show_window()
        self.assertGreaterEqual(gear.canvas.winfo_width(), CONTROL_HIT_MIN)
        self.assertGreaterEqual(gear.canvas.winfo_height(), CONTROL_HIT_MIN)
        self.assertTrue(gear.canvas.cget('takefocus'))
        gear.canvas.focus_force()
        self.win.update()
        self.assertIs(self.win.focus_get(), gear.canvas, '齿轮必须能拿到键盘焦点')
        self.assertTrue(gear.canvas.find_withtag('gear-focus'), '焦点必须可见')
        gear.canvas.event_generate('<Return>')
        gear.canvas.event_generate('<Key-space>')
        self.win.update()
        self.assertEqual(calls, ['gear', 'gear'], 'Enter 与空格都走同一回调')

    def test_each_paw_has_a_32px_target_and_tab_order(self):
        self.show_window()
        hits = self.pet.paw_hits
        self.assertEqual(len(hits), 3)
        for hit in hits:
            self.assertEqual((hit.winfo_width(), hit.winfo_height()),
                             (CONTROL_HIT_MIN, CONTROL_HIT_MIN))
            self.assertTrue(hit.cget('takefocus'))
            self.assertEqual(str(hit.cget('highlightcolor')), COLORS['focus'])
        paws_y = self.pet.paws.winfo_rooty()
        for index, hit in enumerate(hits):
            paw_centre = (paws_y + index * (pet_ui_support.PAW_SIZE + pet_ui_support.PAW_GAP)
                          + pet_ui_support.PAW_SIZE / 2 + pet_ui_support.paw_dy(index))
            hit_centre = hit.winfo_rooty() + hit.winfo_height() / 2
            self.assertLessEqual(abs(paw_centre - hit_centre), 1,
                                 '承接区中心必须对准该只猫爪')
        self.assertIs(hits[0].tk_focusNext(), hits[1], 'Tab 顺序：只提醒 → 半自动')
        self.assertIs(hits[1].tk_focusNext(), hits[2], 'Tab 顺序：半自动 → 全自动')
        hits[0].focus_force()
        self.win.update()
        self.assertIs(self.win.focus_get(), hits[0])
        self.assertTrue(self.pet.paws.find_withtag('paw-focus'), '猫爪焦点必须可见')

    def test_paw_enter_and_space_fire_the_click_action(self):
        self.show_window()
        calls = []
        self.pet.set_paw_level = calls.append
        for index, key in ((0, '<Return>'), (1, '<Key-space>'), (2, '<Return>')):
            hit = self.pet.paw_hits[index]
            hit.focus_force()
            self.win.update()
            hit.event_generate(key)
            self.win.update()
        self.assertEqual(calls, list(pet_ui_support.PAW_LEVELS))

    def test_clicks_across_the_paw_hit_union_pick_the_nearest_visual_centre(self):
        """重叠命中区里点哪儿，都该落在视觉中心最近的那只爪上（竖向猫爪列）。"""
        self.show_window()
        step = pet_ui_support.PAW_SIZE + pet_ui_support.PAW_GAP
        hits = self.pet.paw_hits
        for hit in hits:
            self.assertGreaterEqual(hit.winfo_height(), CONTROL_HIT_MIN)
        centres = [
            self.pet.paws.winfo_rooty() + index * step + pet_ui_support.PAW_SIZE / 2
            + pet_ui_support.paw_dy(index)
            for index in range(len(hits))
        ]
        self.assertGreaterEqual(centres[0] - hits[0].winfo_rooty(), CONTROL_HIT_MIN / 2)
        self.assertGreaterEqual(hits[2].winfo_rooty() + hits[2].winfo_height() - centres[2],
                                CONTROL_HIT_MIN / 2)

        left = min(hit.winfo_rootx() for hit in hits)
        right = max(hit.winfo_rootx() + hit.winfo_width() for hit in hits)
        ys = list(centres)
        for top, bottom in zip(centres, centres[1:]):
            middle = (top + bottom) / 2
            ys.extend((middle - 3, middle, middle + 3))
        ys.extend((centres[0] - 15, centres[2] + 15))

        calls = []
        self.pet.set_paw_level = calls.append
        checked = 0
        for x in (left + 3, (left + right) / 2, right - 3):
            for y in ys:
                widget = self.widget_at(x, y)
                self.assertIsNotNone(widget, '采样点必须落在某个可点控件上')
                del calls[:]
                widget.event_generate('<Button-1>', x=x - widget.winfo_rootx(),
                                      y=y - widget.winfo_rooty(),
                                      rootx=int(round(x)), rooty=int(round(y)))
                self.win.update()
                self.assertTrue(calls, '点击必须触发一只猫爪')
                chosen = pet_ui_support.PAW_LEVELS.index(calls[-1])
                distances = [abs(y - centre) for centre in centres]
                nearest = {index for index, distance in enumerate(distances)
                           if abs(distance - min(distances)) < 0.01}
                self.assertIn(chosen, nearest,
                              '点 (%s, %s) 落在 %s 爪上，最近的却是 %s'
                              % (x, y, chosen, sorted(nearest)))
                checked += 1
        self.assertGreaterEqual(checked, 21)

    def test_field_bg_reads_the_reply_widget_style(self):
        ui_widgets.setup_styles(self.win)
        style = ttk.Style(self.win)
        name = 'Tokens.LineInput.TEntry'
        original = style.lookup(name, 'fieldbackground', '')
        self.addCleanup(style.configure, name, fieldbackground=original)
        style.configure(name, fieldbackground=COLORS['background_primary'])
        cloud = self.pet.cloud()
        self.pet.open_chat()
        self.assertEqual(cloud.field_bg(), COLORS['background_primary'])
        self.assertEqual(str(cloud.hint.cget('bg')), COLORS['background_primary'])

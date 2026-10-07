"""统一输入组件的 Tk 行为回归。"""
from __future__ import annotations

import tkinter as tk
import unittest

from skip_reasons import PLATFORM_TK_DISPLAY
from ui_widgets import LineInput, TextArea, SelectBox
from ui_tokens import COMBOBOX_WIDTH, COMBOBOX_MAX_WIDTH, COMBOBOX_POPDOWN_HEIGHT


class InputWidgetTests(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
            self.root.withdraw()
        except tk.TclError as exc:
            self.skipTest(PLATFORM_TK_DISPLAY + ': ' + str(exc))

    def tearDown(self):
        if hasattr(self, "root"):
            self.root.destroy()

    def test_line_input_hides_placeholder_and_exposes_error_and_readonly_states(self):
        field = LineInput(self.root, placeholder="项目名称")
        field.pack()
        self.root.update()
        self.assertEqual(field.get(), "")
        field.insert(0, "新项目")
        self.assertEqual(field.get(), "新项目")
        field.set_error("名称重复")
        self.assertEqual(field.error_message, "名称重复")
        self.assertEqual(field.cget("style"), LineInput.ERROR_STYLE)
        field.clear_error()
        field.set_readonly(True)
        self.assertIn("readonly", field.state())

    def test_text_area_preserves_text_api_and_unifies_placeholder_error_and_readonly(self):
        area = TextArea(self.root, placeholder="填写梗概", height=2)
        area.pack()
        self.root.update()
        self.assertEqual(area.get("1.0", "end-1c"), "")
        area.insert("1.0", "故事梗概")
        self.assertEqual(area.get("1.0", "end-1c"), "故事梗概")
        area.set_error("必填")
        self.assertEqual(area.error_message, "必填")
        area.set_readonly(True)
        self.assertEqual(str(area.cget("state")), "disabled")

    def test_select_box_defaults_preserve_selection_and_variable(self):
        selected = tk.StringVar(self.root)
        box = SelectBox(self.root, values=['first', '第二'], textvariable=selected)
        self.assertIn('readonly', box.state())
        self.assertEqual(int(box.cget('height')), COMBOBOX_POPDOWN_HEIGHT)
        box.current(1)
        self.assertEqual(box.get(), '第二')
        self.assertEqual(selected.get(), '第二')

    def test_select_box_width_fits_ascii_and_cjk_with_cap_and_empty_fallback(self):
        for values, expected in [([], COMBOBOX_WIDTH), (['abc', '中文A'], 5),
                                 (['字' * 30], COMBOBOX_MAX_WIDTH)]:
            with self.subTest(values=values):
                box = SelectBox(self.root, values=values)
                self.assertEqual(int(box.cget('width')), expected)

    def test_select_box_explicit_layout_and_popup_height(self):
        box = SelectBox(self.root, values=['很长的选项'], width=1, height=4)
        self.assertEqual(int(box.cget('width')), 1)
        self.assertEqual(int(box.cget('height')), 4)

    def test_select_box_set_values_refits_in_both_directions_and_can_opt_out(self):
        box = SelectBox(self.root, values=['a'])
        box.set_values(value for value in ['中文ABC'])
        self.assertEqual(tuple(box.cget('values')), ('中文ABC',))
        self.assertEqual(int(box.cget('width')), 7)
        box.set_values(['b'])
        self.assertEqual(int(box.cget('width')), 1)
        box.set_values(['longer'], refit=False)
        self.assertEqual(int(box.cget('width')), 1)
        box.set_values([])
        self.assertEqual(int(box.cget('width')), COMBOBOX_WIDTH)

    def test_select_box_editable_and_disabled_do_not_refit(self):
        for state in ['normal', 'disabled']:
            with self.subTest(state=state):
                box = SelectBox(self.root, state=state, values=['字' * 30])
                self.assertEqual(str(box.cget('state')), state)
                self.assertEqual(int(box.cget('width')), COMBOBOX_WIDTH)
                box.set_values(['a'])
                self.assertEqual(int(box.cget('width')), COMBOBOX_WIDTH)
                if state == 'normal':
                    box.set('自定义模型')
                    self.assertEqual(box.get(), '自定义模型')

    def test_select_box_native_popup_caps_rows_and_exposes_scrollbar(self):
        self.root.deiconify()
        box = SelectBox(self.root, values=[str(i) for i in range(30)])
        box.pack()
        self.root.update()
        box.tk.call('ttk::combobox::Post', str(box))
        self.root.update()
        popup = box.tk.call('ttk::combobox::PopdownWindow', str(box))
        self.assertEqual(int(box.tk.call(popup + '.f.l', 'cget', '-height')), 12)
        self.assertEqual(int(box.tk.call('winfo', 'ismapped', popup + '.f.sb')), 1)
        box.tk.call('ttk::combobox::Unpost', str(box))

    def test_select_box_keeps_readonly_wheel_guard_and_editable_scroll(self):
        from desktop import protect_readonly_combobox
        self.root.deiconify()
        protect_readonly_combobox(self.root)
        readonly = SelectBox(self.root, values=['a', 'b', 'c'])
        editable = SelectBox(self.root, values=['a', 'b', 'c'], state='normal')
        for box in (readonly, editable):
            box.pack()
            box.current(0)
        self.root.update()
        for box in (readonly, editable):
            box.event_generate('<MouseWheel>', delta=-120, x=5, y=5)
        self.root.update()
        self.assertEqual(readonly.current(), 0)
        self.assertEqual(editable.current(), 1)

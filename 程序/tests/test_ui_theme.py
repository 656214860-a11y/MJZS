# -*- coding: utf-8 -*-
"""ui_theme 的勾选图元回归：apply() 在同一解释器里会被调用多次；第 8 轮起盯「弹窗没有那两颗键」。

运行：python test_ui_theme.py

第 30 期真窗核对发现：入口调一次 apply()、Desktop.__init__ 又调一次，每次都造一套新的勾选图，
勾选图元（DramaTick.indicator）只在第一次登记——旧图一被回收，图元就再也画不出勾选框，
整栏「选择镜头资产」的勾选框全是空的。这里盯住"旧图不能被回收"这条。
"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.chdir(HERE)

import tkinter as tk
from tkinter import ttk

import ui_theme
from ui_tokens import (COLORS, COMBOBOX_FIELD_BACKGROUND, COMBOBOX_FONT,
                       COMBOBOX_FOREGROUND, COMBOBOX_WIDTH, TEXT_DESC, TEXT_HINT,
                       TEXT_PROGRESS)
from ui_widgets import (DescriptionBlock, HintLabel, PrimaryButton, ProgressLabel,
                        SecondaryButton, setup_styles)


class TickIndicatorTests(unittest.TestCase):
    def setUp(self):
        self.win = tk.Tk()
        self.win.withdraw()
        self.addCleanup(self.win.destroy)

    def names_alive(self):
        return set(self.win.tk.call("image", "names"))

    def generation(self):
        return [str(image) for image in self.win._tick_images]

    def test_double_apply_keeps_the_images_the_element_was_built_with(self):
        ui_theme.apply(self.win)
        first = self.generation()
        ui_theme.apply(self.win)
        self.assertTrue(set(first) <= self.names_alive(),
                        "第二次 apply() 把勾选图元登记的那套图回收掉了，勾选框会画不出来")

    def test_double_apply_leaves_the_widget_images_on_the_second_generation(self):
        ui_theme.apply(self.win)
        ui_theme.apply(self.win)
        self.assertEqual(self.generation(), [str(image) for image in self.win._tick_images])
        self.assertEqual(len(self.win._tick_images), 4)
        self.assertTrue(set(self.generation()) <= self.names_alive())

    def test_every_apply_keeps_one_more_generation(self):
        ui_theme.apply(self.win)
        self.assertEqual(len(self.win._tick_images_keep), 4)
        ui_theme.apply(self.win)
        self.assertEqual(len(self.win._tick_images_keep), 8)
        self.assertTrue(all(str(image) in self.names_alive() for image in self.win._tick_images_keep))

    def test_each_window_keeps_its_own_generations(self):
        other = tk.Tk()
        other.withdraw()
        self.addCleanup(other.destroy)
        ui_theme.apply(self.win)
        ui_theme.apply(self.win)
        ui_theme.apply(other)
        self.assertEqual(len(self.win._tick_images_keep), 8)
        self.assertEqual(len(other._tick_images_keep), 4)


class TokenButtonStateTests(unittest.TestCase):
    """设计系统按钮在浅色悬停和禁用态都必须保留可读文字。"""

    def setUp(self):
        self.win = tk.Tk()
        self.win.withdraw()
        self.addCleanup(self.win.destroy)
        ui_theme.apply(self.win)

    def test_primary_hover_and_disabled_text_follow_tokens(self):
        PrimaryButton(self.win, text='发送')
        style = ttk.Style(self.win)
        self.assertEqual(style.lookup('Tokens.Primary.TButton', 'background', ('active',)),
                         COLORS['primary_subtle'])
        self.assertEqual(style.lookup('Tokens.Primary.TButton', 'foreground', ('active',)),
                         COLORS['primary'])
        self.assertEqual(style.lookup('Tokens.Primary.TButton', 'foreground', ('disabled',)),
                         COLORS['text_muted'])

    def test_secondary_hover_and_disabled_text_follow_tokens(self):
        SecondaryButton(self.win, text='阶段配置')
        style = ttk.Style(self.win)
        self.assertEqual(style.lookup('Tokens.Secondary.TButton', 'background', ('active',)),
                         COLORS['primary_subtle'])
        self.assertEqual(style.lookup('Tokens.Secondary.TButton', 'foreground', ('active',)),
                         COLORS['primary'])
        self.assertEqual(style.lookup('Tokens.Secondary.TButton', 'foreground', ('disabled',)),
                         COLORS['text_muted'])

    def test_global_and_legacy_button_styles_are_compact_and_readable(self):
        setup_styles(self.win)
        style = ttk.Style(self.win)
        for name in ('TButton', 'Primary.TButton', 'Secondary.TButton'):
            self.assertEqual(style.lookup(name, 'padding'), '12 4')
            self.assertEqual(style.lookup(name, 'background', ('active',)),
                             COLORS['primary_subtle'])
            self.assertEqual(style.lookup(name, 'foreground', ('active',)),
                             COLORS['primary'])

    def test_global_combobox_style_uses_the_design_tokens(self):
        setup_styles(self.win)
        style = ttk.Style(self.win)
        self.assertEqual(style.lookup('TCombobox', 'fieldbackground'),
                         COMBOBOX_FIELD_BACKGROUND)
        self.assertEqual(style.lookup('TCombobox', 'foreground'), COMBOBOX_FOREGROUND)
        self.assertEqual(style.lookup('TCombobox', 'font'),
                         ' '.join(tk._stringify(part) for part in COMBOBOX_FONT))
        self.assertEqual(style.lookup('TCombobox', 'padding'), '8 4')
        box = ttk.Combobox(self.win, values=('甲', '乙'))
        self.assertEqual(int(box.cget('width')), COMBOBOX_WIDTH)

    def test_text_components_keep_their_token_owned_visual_hierarchy(self):
        cases = ((HintLabel, TEXT_HINT), (DescriptionBlock, TEXT_DESC),
                 (ProgressLabel, TEXT_PROGRESS))
        for component, tokens in cases:
            widget = component(self.win, text='统一文字')
            self.assertEqual(str(widget.cget('foreground')), tokens['foreground'])
            self.assertEqual(widget.cget('wraplength'), tokens['wraplength'])
            self.assertEqual(str(widget.cget('anchor')), tokens['anchor'])
            self.assertEqual(str(widget.cget('justify')), tokens['justify'])
            self.assertEqual(tuple(widget.cget('padding')), tokens['padding'])
            self.assertEqual(widget.linespace, tokens['linespace'])
            self.assertEqual(widget.max_chars, tokens['max_chars'])

class NoPopupKeyTests(unittest.TestCase):
    """第 8 轮（收口）：弹窗右上角那两颗「最小化／最大化」删掉了，而且不许再长回来。

    第 65 期任务 5 给每个弹窗长了那两颗键（接线在 ui_theme.install_window_placement 的
    hidden_init 里，全程序只有那一处），第 67 期任务 1 又把三虎那朵云单独摘过。用户这次
    定的口径是「删掉」：画键的代码与那处接线都不在了，弹窗只剩系统标题栏那颗 ×。
    """

    GONE = ('window_buttons', 'bare_window', 'WINDOW_MIN_TEXT', 'WINDOW_MAX_TEXT',
            'WINDOW_RESTORE_TEXT', 'WINDOW_OWNER_BACK_MS')
    # 静态兜底认的是「调用与常量」：别的用例拿名字做断言（例如 hasattr）不算残留。
    LEFTOVERS = ('window_buttons(', 'bare_window(', 'WINDOW_MIN_TEXT', 'WINDOW_MAX_TEXT',
                 'WINDOW_RESTORE_TEXT')

    def setUp(self):
        self.win = tk.Tk()
        self.win.geometry('420x300+40+40')
        self.addCleanup(self.quietly, self.win.destroy)
        ui_theme.apply(self.win)
        ui_theme.install_window_placement(self.win)
        self.pump(60)

    @staticmethod
    def quietly(function, *args):
        try:
            function(*args)
        except Exception:
            pass

    def pump(self, ms):
        """推进事件循环 ms 毫秒：<Map> 那一拍要真的跑过。"""
        try:
            self.win.update()
            self.win.update_idletasks()
            self.win.after(ms, self.win.quit)
            self.win.mainloop()
        except Exception:
            pass

    def test_the_two_keys_are_gone_from_the_module(self):
        for name in self.GONE:
            self.assertFalse(hasattr(ui_theme, name), '第 8 轮起 ui_theme 不该再有 %s' % name)

    def test_a_new_popup_grows_no_key_and_no_button_row(self):
        window = tk.Toplevel(self.win)
        self.addCleanup(self.quietly, window.destroy)
        window.geometry('300x200+150+150')
        self.pump(120)
        self.assertIsNone(getattr(window, '_drama_buttons', None), '弹窗不再挂那两颗键')
        self.assertEqual(window.winfo_children(), [], '这扇空弹窗上不该多出任何一排按钮')

    def test_no_module_wires_the_two_keys_any_more(self):
        """静态兜底：全程序一处都不许再出现那两个名字（免得从旧版本粘回来）。"""
        root = os.path.dirname(os.path.abspath(__file__))
        leftovers = []
        for folder, dirs, files in os.walk(root):
            dirs[:] = [name for name in dirs
                       if name not in ('__pycache__', 'private', 'data', 'assets', 'episode')]
            for name in files:
                if not name.endswith(('.py', '.pyw')):
                    continue
                spot = os.path.join(folder, name)
                if os.path.abspath(spot) == os.path.abspath(__file__):
                    continue                     # 这一份自己写着这几个名字（就在上面 GONE 里）
                with open(spot, encoding='utf-8', errors='ignore') as handle:
                    body = handle.read()
                for token in self.LEFTOVERS:
                    if token in body:
                        leftovers.append('%s: %s' % (os.path.relpath(spot, root), token))
        self.assertEqual(leftovers, [], '第 8 轮起不该再有这些名字')



if __name__ == "__main__":
    unittest.main(verbosity=2)

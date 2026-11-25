# -*- coding: utf-8 -*-
"""ui_theme 的勾选图元回归：apply() 在同一解释器里会被调用多次；第 8 轮起盯「弹窗没有那两颗键」。

运行：python test_ui_theme.py

第 30 期真窗核对发现：入口调一次 apply()、Desktop.__init__ 又调一次，每次都造一套新的勾选图，
勾选图元（DramaTick.indicator）只在第一次登记——旧图一被回收，图元就再也画不出勾选框，
整栏「选择镜头资产」的勾选框全是空的。这里盯住"旧图不能被回收"这条。
"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.chdir(HERE)

import tkinter as tk
from tkinter import ttk

import ui_theme
import ui_tokens
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
        self.assertEqual(style.lookup('Tokens.Primary.TButton', 'fill', ('active',)),
                         COLORS['primary_hover'])
        self.assertEqual(style.lookup('Tokens.Primary.TButton', 'foreground', ('active',)),
                         COLORS['background_card'])
        self.assertEqual(style.lookup('Tokens.Primary.TButton', 'foreground', ('disabled',)),
                         COLORS['disabled_text'])

    def test_secondary_hover_and_disabled_text_follow_tokens(self):
        SecondaryButton(self.win, text='阶段配置')
        style = ttk.Style(self.win)
        self.assertEqual(style.lookup('Tokens.Secondary.TButton', 'fill', ('active',)),
                         COLORS['surface_hover'])
        self.assertEqual(style.lookup('Tokens.Secondary.TButton', 'foreground', ('active',)),
                         COLORS['text_primary'])
        self.assertEqual(style.lookup('Tokens.Secondary.TButton', 'foreground', ('disabled',)),
                         COLORS['disabled_text'])

    def test_global_and_legacy_button_styles_are_compact_and_readable(self):
        setup_styles(self.win)
        style = ttk.Style(self.win)
        for name in ('TButton', 'Primary.TButton', 'Secondary.TButton'):
            self.assertEqual(style.lookup(name, 'padding'), '12 8')
        self.assertEqual(style.lookup('TButton', 'fill', ('active',)),
                         COLORS['secondary_hover'])
        self.assertEqual(style.lookup('Primary.TButton', 'fill', ('active',)),
                         COLORS['primary_hover'])
        self.assertEqual(style.lookup('Secondary.TButton', 'fill', ('active',)),
                         COLORS['surface_hover'])
        self.assertEqual(style.lookup('Primary.TButton', 'foreground', ('active',)),
                         COLORS['background_card'])
        self.assertEqual(style.lookup('Secondary.TButton', 'foreground', ('active',)),
                         COLORS['text_primary'])

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

    def test_pale_green_hint_style_uses_slate_neutral_tokens(self):
        """UX-SLATE-PALETTE-SYNC：设置页提示条去绿改高级灰，保留样式名 PaleGreenHint.TLabel。"""
        style = ttk.Style(self.win)
        label = ttk.Label(self.win, text='设置提示', style='PaleGreenHint.TLabel')
        self.assertEqual(str(label.cget('style')), 'PaleGreenHint.TLabel')
        bg = str(style.lookup('PaleGreenHint.TLabel', 'background')).upper()
        fg = str(style.lookup('PaleGreenHint.TLabel', 'foreground')).upper()
        self.assertEqual(bg, COLORS['surface_hover'].upper())
        self.assertEqual(fg, COLORS['text_secondary'].upper())
        self.assertNotEqual(bg, COLORS['success_subtle'].upper())
        self.assertNotEqual(fg, COLORS['success_text'].upper())
        self.assertGreaterEqual(ThemePaletteTests._contrast(fg, bg), 4.5)

    def test_sidebar_project_card_current_row_uses_selection_tokens(self):
        """UX-SLATE-PALETTE-SYNC：左上角项目卡片当前项高亮使用 selection_bg 与 selection_text。"""
        from types import SimpleNamespace
        from ui.desktop_sidebar_project import ProjectNameList
        cur_path = 'C:/tmp/slate_demo_project'
        projects = [{'name': '高级灰项目', 'path': cur_path, 'status': 'making'}]
        host = SimpleNamespace(
            win=self.win,
            root=Path(cur_path),
            _picker_items=projects,
            _project_group='making',
            projects=SimpleNamespace(info={'projects': projects}),
        )
        widget = ProjectNameList(host, self.win)
        widget.pack()
        self.addCleanup(widget.close_card)
        widget.open_card()
        tree = widget.table.tree
        self.assertEqual(str(tree.tag_configure('current', 'background')).upper(),
                         COLORS['selection_bg'].upper())
        self.assertEqual(str(tree.tag_configure('current', 'foreground')).upper(),
                         COLORS['selection_text'].upper())

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


class PopupGrabSafetyTests(unittest.TestCase):
    """R772：Map 子事件和失败定位都不能留下隐形输入锁。"""

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
        except tk.TclError:
            pass

    def pump(self, milliseconds=80):
        self.win.update_idletasks()
        self.win.update()
        self.win.after(milliseconds, self.win.quit)
        self.win.mainloop()

    def test_child_map_cannot_take_popup_grab(self):
        popup = tk.Toplevel(self.win)
        self.addCleanup(self.quietly, popup.destroy)
        frame = ttk.Frame(popup)
        frame.pack()
        ttk.Label(frame, text='子控件').pack()
        ttk.Button(frame, text='按钮').pack()
        self.pump(120)
        holder = self.win.grab_current()
        self.assertIn(holder, (None, popup), '子控件 Map 不得抢走全局输入 grab')

    def test_withdrawn_popup_releases_its_grab(self):
        popup = tk.Toplevel(self.win)
        self.addCleanup(self.quietly, popup.destroy)
        ttk.Label(popup, text='复用窗口').pack()
        self.pump(120)
        popup.withdraw()
        self.pump(60)
        self.assertIsNone(self.win.grab_current(), '隐形窗口不得继续持有 grab')

    def test_place_error_restores_visibility_releases_grab_and_notifies(self):
        notices = []
        self.win._drama_place_notice = notices.append
        popup = tk.Toplevel(self.win)
        self.addCleanup(self.quietly, popup.destroy)
        popup.transient = lambda _parent: (_ for _ in ()).throw(tk.TclError('parent destroyed'))
        ttk.Label(popup, text='故障注入').pack()
        self.pump(120)
        self.assertEqual(float(popup.attributes('-alpha')), 1.0)
        self.assertIsNone(self.win.grab_current())
        self.assertTrue(notices)



class DialogFitsContentTests(PopupGrabSafetyTests.__base__):
    """弹窗首次摆位不得裁掉内容：写死的小尺寸要撑到内容大小，主窗口偏小也不压扁；
    自然尺寸的弹窗只摆位置，之后才加载的内容还能把窗口撑大。"""

    setUp, quietly, pump = PopupGrabSafetyTests.setUp, staticmethod(PopupGrabSafetyTests.quietly), PopupGrabSafetyTests.pump

    def popup(self, geometry=None, minsize=None):
        popup = tk.Toplevel(self.win)
        self.addCleanup(self.quietly, popup.destroy)
        if geometry:
            popup.geometry(geometry)
        if minsize:
            popup.minsize(*minsize)
        return popup

    def assertFits(self, popup):
        popup.update_idletasks()
        self.assertGreaterEqual(popup.winfo_width(), popup.winfo_reqwidth())
        self.assertGreaterEqual(popup.winfo_height(), popup.winfo_reqheight())

    def test_fixed_geometry_grows_to_its_content(self):
        popup = self.popup('200x80')
        for index in range(10):
            ttk.Entry(popup, width=40).pack(pady=4)
        self.pump(120)
        self.assertFits(popup)

    def test_content_wider_than_main_window_is_not_cut(self):
        self.win.geometry('420x300')
        self.pump(60)
        popup = self.popup()
        ttk.Label(popup, text='很长的一行设备说明' * 5).pack()
        self.pump(120)
        self.assertGreater(popup.winfo_reqwidth(), self.win.winfo_width())
        self.assertFits(popup)

    def test_content_added_after_placement_still_widens_the_window(self):
        popup = self.popup(minsize=(300, 120))
        ttk.Label(popup, text='正在读取…').pack()
        self.pump(120)
        self.assertGreaterEqual(popup.winfo_width(), 300, '调用方声明的下限不被 240×160 覆盖')
        ttk.Label(popup, text='赖彪的电脑（Windows 11）· 本机  首次 2026-10-23 02:03 · 最近 2026-10-31 00:40').pack()
        self.pump(120)
        self.assertGreater(popup.winfo_reqwidth(), 300)
        self.assertFits(popup)


class ThemePaletteTests(unittest.TestCase):
    """REQ-UI-THEME-1（UX-THEME-SIMPLE）：日间／夜间两套简约调色板与切换。

    卡面口径：每套只留背景／卡片／描边／文字主次／强调色／危险色等语义 token，
    两套键集一致；正文对底 ≥4.5:1、次要文字 ≥3:1、实心按钮字 ≥4.5:1。
    """

    def setUp(self):
        self._was = ui_tokens.current_theme()
        self.addCleanup(ui_tokens.set_theme, self._was)

    @staticmethod
    def _luminance(value):
        channels = [int(value[i:i + 2], 16) / 255 for i in (1, 3, 5)]
        linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
        return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]

    @classmethod
    def _contrast(cls, a, b):
        high, low = sorted((cls._luminance(a), cls._luminance(b)), reverse=True)
        return (high + 0.05) / (low + 0.05)

    def test_two_palettes_share_the_same_keys(self):
        self.assertEqual({'day', 'night'}, set(ui_tokens.THEMES))
        day, night = ui_tokens.THEMES['day'], ui_tokens.THEMES['night']
        self.assertTrue(day and night)
        self.assertEqual(set(day), set(night))
        for key, value in day.items():
            self.assertRegex(str(value), r'^#[0-9A-Fa-f]{6}$', key)

    def test_body_text_meets_contrast_in_both_palettes(self):
        for name, palette in ui_tokens.THEMES.items():
            for fg in ('text_primary', 'text_heading'):
                for bg in ('background_primary', 'background_card'):
                    ratio = self._contrast(palette[fg], palette[bg])
                    self.assertGreaterEqual(ratio, 4.5,
                                            '%s: %s on %s = %.2f' % (name, fg, bg, ratio))
            for fg in ('text_secondary', 'text_muted'):
                for bg in ('background_primary', 'background_card'):
                    ratio = self._contrast(palette[fg], palette[bg])
                    self.assertGreaterEqual(ratio, 3.0,
                                            '%s: %s on %s = %.2f' % (name, fg, bg, ratio))

    def test_solid_controls_and_status_text_meet_contrast(self):
        for name, palette in ui_tokens.THEMES.items():
            for fill in ('primary', 'primary_hover', 'primary_pressed',
                         'danger', 'danger_hover', 'danger_pressed', 'success'):
                ratio = self._contrast(palette['on_accent'], palette[fill])
                self.assertGreaterEqual(ratio, 4.5,
                                        '%s: on_accent on %s = %.2f' % (name, fill, ratio))
            for fg, bg in (('secondary_text', 'secondary_bg'),
                           ('secondary_text', 'secondary_hover'),
                           ('secondary_text', 'secondary_pressed'),
                           ('selection_text', 'selection_bg'),
                           ('danger_text', 'danger_subtle'),
                           ('danger_text', 'background_card'),
                           ('success_text', 'success_subtle'),
                           ('success_text', 'background_card'),
                           ('warning_text', 'background_card'),
                           ('primary_text', 'background_card'),
                           ('primary_text', 'background_primary')):
                ratio = self._contrast(palette[fg], palette[bg])
                self.assertGreaterEqual(ratio, 4.5,
                                        '%s: %s on %s = %.2f' % (name, fg, bg, ratio))

    def test_set_theme_swaps_the_active_palette_in_place(self):
        before = dict(ui_tokens.COLORS)
        identity = ui_tokens.COLORS
        ui_tokens.set_theme('night')
        self.assertIs(ui_tokens.COLORS, identity, 'COLORS 必须是同一个 dict，from-import 的消费者才看得到新值')
        self.assertEqual('night', ui_tokens.current_theme())
        self.assertEqual(ui_tokens.THEMES['night']['background_card'],
                         ui_tokens.COLORS['background_card'])
        self.assertNotEqual(before['background_card'], ui_tokens.COLORS['background_card'])
        ui_tokens.set_theme('day')
        self.assertEqual('day', ui_tokens.current_theme())
        self.assertEqual(before, dict(ui_tokens.COLORS))

    def test_set_theme_rebinds_derived_tokens(self):
        ui_tokens.set_theme('night')
        self.assertEqual(ui_tokens.COLORS['background_card'], ui_tokens.INPUT_BACKGROUND)
        self.assertEqual(ui_tokens.COLORS['background_card'], ui_tokens.COMBOBOX_FIELD_BACKGROUND)
        self.assertEqual(ui_tokens.COLORS['background_card'], ui_tokens.TOOLTIP_BACKGROUND)
        self.assertEqual(ui_tokens.COLORS['text_secondary'], ui_tokens.TEXT_HINT['foreground'])
        self.assertEqual(ui_tokens.COLORS['primary_text'], ui_tokens.TEXT_PROGRESS['foreground'])
        ui_tokens.set_theme('day')
        self.assertEqual(ui_tokens.COLORS['text_secondary'], ui_tokens.TEXT_HINT['foreground'])

    def test_set_theme_rejects_unknown_names(self):
        ui_tokens.set_theme('day')
        self.assertIsNone(ui_tokens.set_theme('neon'))
        self.assertEqual('day', ui_tokens.current_theme())
        self.assertIsNone(ui_tokens.set_theme(None))
        self.assertEqual('day', ui_tokens.current_theme())

    def test_resolve_theme_prefers_an_explicit_choice(self):
        self.assertEqual('night', ui_tokens.resolve_theme('night', system=lambda: 'day'))
        self.assertEqual('day', ui_tokens.resolve_theme('day', system=lambda: 'night'))
        self.assertEqual('night', ui_tokens.resolve_theme('Night', system=lambda: 'day'))

    def test_resolve_theme_follows_system_and_falls_back(self):
        for saved in (None, '', 'system', 'bogus', 42):
            with self.subTest(saved=saved):
                self.assertEqual('night', ui_tokens.resolve_theme(saved, system=lambda: 'night'))
                self.assertEqual('day', ui_tokens.resolve_theme(saved, system=lambda: 'day'))

    def test_system_theme_failure_falls_back_to_day(self):
        def boom():
            raise OSError('no registry')
        self.assertEqual('day', ui_tokens.system_theme(probe=boom))
        self.assertEqual('day', ui_tokens.system_theme(probe=lambda: None))
        self.assertEqual('day', ui_tokens.system_theme(probe=lambda: 1))
        self.assertEqual('night', ui_tokens.system_theme(probe=lambda: 0))

    def test_imported_consumers_resync_after_switch(self):
        import ui_widgets
        entity = sys.modules.get('ui.ui_theme')
        ui_tokens.set_theme('night')
        try:
            self.assertEqual(ui_tokens.COLORS['background_card'], ui_widgets.INPUT_BACKGROUND)
            self.assertEqual(ui_tokens.COLORS['background_card'], ui_widgets.COMBOBOX_FIELD_BACKGROUND)
            self.assertEqual(ui_tokens.COLORS['background_primary'], ui_widgets.CONTROL_CORNER_SURFACE)
            if entity is not None:
                self.assertEqual(ui_tokens.COLORS['background_primary'], entity.BG)
                self.assertEqual(ui_tokens.COLORS['text_primary'], entity.INK)
                self.assertEqual(ui_tokens.COLORS['primary'], entity.ACCENT)
        finally:
            ui_tokens.set_theme('day')

    def test_settings_page_offers_theme_choice_and_persists(self):
        import pet_settings_ui
        root = tk.Tk()
        root.withdraw()
        self.addCleanup(root.destroy)
        pet = Mock()
        pet.pet_settings.return_value = {'name': '三虎', 'anim': True, 'dnd': (22, 7), 'autostart': False}
        pet.snooze_label.return_value = '立刻安静'
        pet.autostart_label.return_value = '开机自启：关'
        with tempfile.TemporaryDirectory() as td:
            desktop = Mock()
            desktop.settings_file = Path(td) / 'desktop_settings.json'
            desktop.settings = {}
            desktop.refresh_ui_theme = Mock()
            pet.desktop = desktop
            frame = ttk.Frame(root)
            frame.pack()
            seams = pet_settings_ui.basic_page(frame, pet)
            self.assertIn('theme_var', seams)
            self.assertIn('theme_apply', seams)
            self.assertEqual('跟随系统', seams['theme_var'].get())
            seams['theme_apply']('夜间')
            self.assertEqual('night', ui_tokens.current_theme())
            self.assertTrue(desktop.settings_file.is_file(), '主题选择要落盘 desktop_settings.json')
            saved = json.loads(desktop.settings_file.read_text(encoding='utf-8'))
            self.assertEqual('night', saved.get('theme'))
            desktop.refresh_ui_theme.assert_called()
            seams['theme_apply']('跟随系统')
            saved = json.loads(desktop.settings_file.read_text(encoding='utf-8'))
            self.assertEqual('system', saved.get('theme'))
            self.assertIn(ui_tokens.current_theme(), ('day', 'night'))

    def test_theme_sync_and_fallback_edge_paths(self):
        import types
        from unittest.mock import patch
        dummy_support = types.SimpleNamespace(CANVAS_BG='', GEAR_COLOR=(), GEAR_HOVER=())
        with patch.dict(sys.modules, {'__dummy_none_module__': None, 'app': None, 'ui.pet_ui_support': dummy_support}):
            ui_tokens.set_theme('night')
            self.assertEqual(dummy_support.GEAR_COLOR,
                             (ui_tokens.COLORS['primary'], ui_tokens.COLORS['primary_pressed']))
            ui_tokens.set_theme('day')
        with patch.dict(os.environ, {'DRAMA_HIDDEN_DESKTOP': '0'}):
            with patch.object(ui_tokens, '_registry_apps_use_light_theme', return_value=0):
                self.assertEqual('night', ui_tokens.system_theme())
        self.assertEqual('day', ui_tokens.resolve_theme('system', system=lambda: (_ for _ in ()).throw(RuntimeError('boom'))))


class ThemeRefreshTests(unittest.TestCase):
    """夜间／日间切换后存量 tk 控件与侧栏图标跟着换色，且能切回日间。"""

    def setUp(self):
        ui_tokens.set_theme('day')
        self.win = tk.Tk()
        self.win.withdraw()
        self.addCleanup(self.win.destroy)
        self.addCleanup(ui_tokens.set_theme, 'day')

    def test_native_widgets_round_trip(self):
        day = ui_tokens.COLORS['background_card']
        canvas = tk.Canvas(self.win, bg=day)
        item = canvas.create_rectangle(0, 0, 5, 5, fill=day)
        label = tk.Label(self.win, bg=day, fg=ui_tokens.COLORS['text_primary'])
        for name in ('night', 'day'):
            ui_tokens.set_theme(name)
            ui_theme.recolor_tree(self.win, ui_tokens.previous_palette(), ui_tokens.COLORS)
            want = ui_tokens.COLORS['background_card'].lower()
            self.assertEqual(str(canvas.cget('bg')).lower(), want)
            self.assertEqual(str(canvas.itemcget(item, 'fill')).lower(), want)
            self.assertEqual(str(label.cget('bg')).lower(), want)

    def test_unrelated_colors_untouched(self):
        mapping = ui_theme.color_map(ui_tokens.THEMES['day'], ui_tokens.THEMES['night'])
        self.assertNotIn('#123456', mapping)

    def test_hover_fade_and_tick_switch_back_to_day(self):
        from ui import ui_hover_fade
        ui_theme.apply(self.win)
        button = SecondaryButton(self.win, text='测试', style='RailIcon.TButton')
        button.pack()
        style = ttk.Style(self.win)
        for name in ('night', 'day'):
            ui_tokens.set_theme(name)
            ui_theme.apply(self.win)
            ui_theme.refresh_native_widgets(self.win)
            ui_hover_fade._ensure_level_style(button, 'RailIcon.TButton', 1)
            self.assertEqual(style.layout('Fade1.RailIcon.TButton')[0][0],
                             f'Drama.RoundedFade1.{name}.RailIcon_TButton')
            self.assertEqual(style.layout('TCheckbutton')[0][1]['children'][0][0],
                             f'DramaTick.indicator.{name}')


if __name__ == "__main__":
    unittest.main(verbosity=2)

# -*- coding: utf-8 -*-
"""UX-CLOSE-X：全应用 5 处关闭 × 按钮统一契约（真 Tk 几何、悬停红底白×、日夜主题、交互行为）。"""
from __future__ import annotations

import json
import sys
import tempfile
import time
import tkinter as tk
import unittest
from pathlib import Path
from tkinter import font as tkfont
from tkinter import ttk
from unittest.mock import patch

PROGRAM = Path(__file__).resolve().parents[1]
if str(PROGRAM) not in sys.path:
    sys.path.insert(0, str(PROGRAM))
TESTS_DIR = Path(__file__).resolve().parent
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

from skip_reasons import PLATFORM_TK_DISPLAY  # noqa: E402
import desktop as desktop_module  # noqa: E402
import domain.idea_chat as idea_chat  # noqa: E402
import infra.pet_state as pet_state  # noqa: E402
from stage_execution_service import idea_chat_gateway, project_context  # noqa: E402
import ui.pet_cloud as pet_cloud  # noqa: E402
import ui.ui_theme as ui_theme  # noqa: E402
import ui_tokens  # noqa: E402
import ui_widgets  # noqa: E402
from ui.ui_status_bar import StatusBar  # noqa: E402
from ui.ui_status_bus import Message, StatusBus  # noqa: E402


def _hex_to_rgb(value: str) -> tuple[int, int, int]:
    return tuple(int(value[index:index + 2], 16) for index in (1, 3, 5))


def _settle(widget, iterations=8):
    for _ in range(iterations):
        widget.update_idletasks()
        widget.update()
        time.sleep(0.02)


def _make_minimal_project(root_dir: str) -> Path:
    project = Path(root_dir) / 'close_demo_project'
    writing = project / 'writing'
    writing.mkdir(parents=True, exist_ok=True)
    (writing / 'script_raw.md').write_text('第 1 集\n\n场景 1：旧站台\n\n阿远：你好。\n', encoding='utf-8')
    board_dir = project / '03初步分镜' / '分镜拆分'
    board_dir.mkdir(parents=True, exist_ok=True)
    sample = {
        'episode': 'EP001',
        'shots': [{'shot_id': 'S01', 'scene': '旧站台', 'visual': '雨夜站台远景', 'dialogue': '你好'}],
    }
    (board_dir / 'EP001_雨夜重逢_分镜.json').write_text(
        json.dumps(sample, ensure_ascii=False), encoding='utf-8')
    return project


def _descendants(widget):
    yield widget
    for child in widget.winfo_children():
        yield from _descendants(child)


class CloseButtonStyleAndThemeTests(unittest.TestCase):
    """统一 CloseButton 样式、尺寸、悬停图元与日/夜主题切换。"""

    def setUp(self):
        self.addCleanup(ui_tokens.set_theme, ui_tokens.current_theme())
        ui_tokens.set_theme('day')
        try:
            self.root = tk.Tk()
        except tk.TclError as exc:
            raise unittest.SkipTest(PLATFORM_TK_DISPLAY + ': ' + str(exc))
        self.root.withdraw()
        self.addCleanup(lambda: self.root.winfo_exists() and self.root.destroy())
        ui_theme.apply(self.root)
        self.style = ttk.Style(self.root)

    def test_close_button_tokens_and_subclass_contract(self):
        self.assertTrue(hasattr(ui_widgets, 'CloseButton'), 'ui_widgets 必须导出 CloseButton')
        CloseButton = ui_widgets.CloseButton
        self.assertTrue(issubclass(CloseButton, ui_widgets.SecondaryButton))
        btn = CloseButton(self.root)
        btn.pack()
        self.root.update_idletasks()
        self.assertEqual(str(btn.cget('text')), '×')
        self.assertEqual(str(btn.cget('style')), ui_tokens.CLOSE_BUTTON_STYLE)
        self.assertEqual(str(btn.cget('cursor')), 'hand2')
        self.assertNotEqual(str(btn.cget('takefocus')), '0')
        self.assertLessEqual(btn.winfo_reqwidth(), 30)
        self.assertLessEqual(btn.winfo_reqheight(), 30)
        actual = tkfont.Font(root=self.root, font=self.style.lookup(ui_tokens.CLOSE_BUTTON_STYLE, 'font')).actual()
        self.assertGreaterEqual(abs(int(actual['size'])), 14)
        self.assertEqual(actual['weight'], 'bold')

    def test_active_hover_red_and_white_cross_across_day_and_night_themes(self):
        CloseButton = ui_widgets.CloseButton
        btn = CloseButton(self.root)
        btn.pack()
        compact_btn = CloseButton(self.root, compact=True)
        compact_btn.pack()
        compact_active_btn = CloseButton(self.root, compact=True, active_surface=True)
        compact_active_btn.pack()
        for theme_name in ('day', 'night', 'day'):
            ui_tokens.set_theme(theme_name)
            ui_theme.apply(self.root)
            ui_theme.refresh_native_widgets(self.root)
            self.root.update_idletasks()
            specs = getattr(self.root, '_drama_close_button_specs', {})
            for style_name, expected_surface in (
                (ui_tokens.CLOSE_BUTTON_STYLE, ui_tokens.COLORS['background_card']),
                (ui_tokens.CLOSE_BUTTON_COMPACT_STYLE, ui_tokens.COLORS['background_card']),
                (ui_tokens.CLOSE_BUTTON_COMPACT_ACTIVE_STYLE, ui_tokens.COLORS['primary_subtle']),
            ):
                with self.subTest(theme=theme_name, style=style_name):
                    self.assertEqual(
                        str(self.style.lookup(style_name, 'foreground')).upper(),
                        ui_tokens.COLORS['text_secondary'].upper(),
                    )
                    self.assertEqual(
                        str(self.style.lookup(style_name, 'fill')).upper(),
                        expected_surface.upper(),
                    )
                    self.assertEqual(
                        str(self.style.lookup(style_name, 'foreground', ('active',))).upper(),
                        ui_tokens.COLORS['on_accent'].upper(),
                    )
                    self.assertEqual(
                        str(self.style.lookup(style_name, 'fill', ('active',))).upper(),
                        ui_tokens.COLORS['danger'].upper(),
                    )
                    self.assertEqual(
                        str(self.style.lookup(style_name, 'foreground', ('pressed',))).upper(),
                        ui_tokens.COLORS['on_accent'].upper(),
                    )
                    self.assertEqual(
                        str(self.style.lookup(style_name, 'fill', ('pressed',))).upper(),
                        ui_tokens.COLORS['danger_pressed'].upper(),
                    )
                    self.assertIn(style_name, specs)
                    active_img = specs[style_name]['images']['active']
                    pressed_img = specs[style_name]['images']['pressed']
                    cx, cy = active_img.width() // 2, active_img.height() // 2
                    self.assertEqual(tuple(active_img.get(cx, cy)), _hex_to_rgb(ui_tokens.COLORS['danger']))
                    self.assertEqual(tuple(pressed_img.get(cx, cy)), _hex_to_rgb(ui_tokens.COLORS['danger_pressed']))

    def test_hover_fade_skips_close_button_styles_without_white_flash(self):
        CloseButton = ui_widgets.CloseButton
        btn = CloseButton(self.root)
        btn.pack()
        self.root.update()
        written = []
        original_configure = btn.configure

        def record_configure(*args, **kwargs):
            if 'style' in kwargs:
                written.append(str(kwargs['style']))
            return original_configure(*args, **kwargs)

        btn.configure = record_configure
        btn.event_generate('<Enter>')
        _settle(self.root, iterations=4)
        btn.event_generate('<Leave>')
        _settle(self.root, iterations=4)
        self.assertEqual(written, [], 'Tokens.Close.* 必须跳过渐变，避免白底白×闪烁')
        self.assertEqual(str(btn.cget('style')), ui_tokens.CLOSE_BUTTON_STYLE)


class FiveSitesCloseButtonUnifyTests(unittest.TestCase):
    """验证全部 5 处关闭按钮：S02、S03、S01 模型条、状态栏消息历史浮窗、三虎云朵。"""

    def setUp(self):
        self.addCleanup(ui_tokens.set_theme, ui_tokens.current_theme())
        ui_tokens.set_theme('day')
        try:
            self.win = tk.Tk()
        except tk.TclError as exc:
            raise unittest.SkipTest(PLATFORM_TK_DISPLAY + ': ' + str(exc))
        self.win.withdraw()
        self.addCleanup(lambda: self.win.winfo_exists() and self.win.destroy())

    def _open_desktop(self, project: Path):
        self.win.deiconify()
        self.win.update()
        original = desktop_module.Desktop.choose_project
        desktop_module.Desktop.choose_project = lambda _self: None
        try:
            desktop = desktop_module.Desktop(self.win, root=PROGRAM)
        finally:
            desktop_module.Desktop.choose_project = original
        self.addCleanup(desktop.cancel_timers)
        self.win.update()
        self.win.geometry('1180x780+30+30')
        self.win.update()
        desktop.root = project
        return desktop

    def _assert_close_geometry(self, button, *, min_pt=14):
        CloseButton = ui_widgets.CloseButton
        style = ttk.Style(self.win)
        self.assertIsInstance(button, CloseButton)
        style_name = str(button.cget('style'))
        self.assertTrue(style_name.startswith('Tokens.Close.'), f'意外样式: {style_name}')
        self.assertEqual(str(button.cget('text')), '×')
        self.assertLessEqual(button.winfo_reqwidth(), 30, f'宽超限: {button.winfo_reqwidth()}')
        self.assertLessEqual(button.winfo_reqheight(), 30, f'高超限: {button.winfo_reqheight()}')
        actual = tkfont.Font(root=self.win, font=style.lookup(style_name, 'font')).actual()
        self.assertGreaterEqual(abs(int(actual['size'])), min_pt)
        self.assertEqual(actual['weight'], 'bold')

    def test_s02_s03_s01_all_use_unified_close_button_and_close_real_targets(self):
        with tempfile.TemporaryDirectory() as td:
            project = _make_minimal_project(td)
            ctx = project_context(project)
            gateway = idea_chat_gateway()
            idea_chat.append(ctx, 'user', '甲的消息', model='模型甲', gateway=gateway)
            idea_chat.append(ctx, 'assistant', '乙的消息', model='模型乙', gateway=gateway)
            desktop = self._open_desktop(project)

            # 1) S02 结构剧本编辑器关闭按钮
            desktop.show(pet_state.PAGE_OF['script_structure'])
            _settle(self.win)
            box = desktop.script_structure_editor_preview_content_box
            box.select_document(project / 'writing' / 'script_raw.md')
            _settle(self.win)
            s02_btn = box.close_button
            self._assert_close_geometry(s02_btn, min_pt=14)
            self.assertEqual(str(s02_btn.cget('style')), ui_tokens.CLOSE_BUTTON_STYLE)
            self.assertTrue(s02_btn.winfo_ismapped())
            s02_btn.invoke()
            _settle(self.win)
            self.assertIsNone(box.active['path'])
            self.assertFalse(s02_btn.winfo_ismapped())

            # 2) S03 初步分镜编辑器关闭按钮
            desktop.show(pet_state.PAGE_OF['storyboard'])
            page = desktop.storyboard_editor_page
            deadline = time.monotonic() + 5.0
            while not page.loaded and time.monotonic() < deadline:
                self.win.update()
                time.sleep(0.02)
            page.show_document(project / '03初步分镜' / '分镜拆分' / 'EP001_雨夜重逢_分镜.json')
            _settle(self.win)
            s03_btn = page.editor.close_button
            self._assert_close_geometry(s03_btn, min_pt=14)
            self.assertEqual(str(s03_btn.cget('style')), ui_tokens.CLOSE_BUTTON_STYLE)
            self.assertTrue(s03_btn.winfo_ismapped())
            s03_btn.invoke()
            _settle(self.win)
            self.assertIsNone(page.active_path)
            self.assertFalse(s03_btn.winfo_ismapped())

            # 3) S01 模型目录条关闭按钮（兼容 <Button-1> 与 invoke() 且不双触发）
            desktop.show(0)
            _settle(self.win)
            tabs = list(desktop.idea_model_bar_inner.winfo_children())
            self.assertEqual(len(tabs), 2)
            close_a = tabs[0].close_tag
            self._assert_close_geometry(close_a, min_pt=12)
            calls = []
            with patch('desktop.confirm', side_effect=lambda *a, **kw: (calls.append(a), False)[1]):
                close_a.event_generate('<Button-1>')
                close_a.event_generate('<ButtonRelease-1>')
            _settle(self.win, iterations=3)
            self.assertEqual(len(calls), 1, '点击 S01 模型关闭 × 不得双触发')
            with patch('desktop.confirm', return_value=True):
                close_a.event_generate('<Button-1>')
            _settle(self.win)
            tabs_after = list(desktop.idea_model_bar_inner.winfo_children())
            self.assertEqual(len(tabs_after), 1)
            # 剩余模型标签通过 invoke() 同样可关闭
            with patch('desktop.confirm', return_value=True):
                tabs_after[0].close_tag.invoke()
            _settle(self.win)
            self.assertEqual(list(desktop.idea_model_bar_inner.winfo_children()), [])

    def test_status_bar_history_popup_uses_unified_close_button_and_closes(self):
        ui_theme.apply(self.win)
        bus = StatusBus()
        bar = StatusBar(self.win, bus, neutral='就绪')
        bar.pack(fill='x')
        self.addCleanup(bar.shutdown)
        bus.publish(Message.make('info', '历史测试消息'))
        _settle(self.win, iterations=4)
        bar._open_history()
        _settle(self.win, iterations=4)
        self.assertIsNotNone(bar._popup)
        buttons = [w for w in _descendants(bar._popup.content) if isinstance(w, ui_widgets.CloseButton)]
        self.assertEqual(len(buttons), 1, '消息历史浮窗应使用唯一 CloseButton')
        close_btn = buttons[0]
        self._assert_close_geometry(close_btn, min_pt=14)
        self.assertEqual(str(close_btn.cget('style')), ui_tokens.CLOSE_BUTTON_STYLE)
        close_btn.invoke()
        _settle(self.win, iterations=4)
        self.assertIsNone(bar._popup)

    def test_pet_cloud_uses_unified_close_button_and_closes(self):
        ui_theme.apply(self.win)
        pet_stub = type('PetStub', (), {
            'win': self.win,
            'canvas': None,
            'root': None,
            'cloud_origin': lambda _self: (400, 400),
            'attending': lambda _self: True,
            'chat_task': None,
            'ask_agent': lambda _self, *_a, **_kw: None,
            'on_cloud_close': lambda _self: None,
        })()
        cloud = pet_cloud.Cloud(pet_stub, parent=self.win)
        self.addCleanup(lambda: cloud.win is not None and cloud.win.winfo_exists() and cloud.win.destroy())
        cloud.show(pinned=True, shape=pet_cloud.SHAPE_CLOUD)
        cloud.canvas.update_idletasks()
        close_btn = cloud.close_button
        self._assert_close_geometry(close_btn, min_pt=14)
        self.assertEqual(str(close_btn.cget('style')), ui_tokens.CLOSE_BUTTON_STYLE)
        cloud._hover_close_button()
        self.assertTrue(close_btn.instate(['active']))
        cloud._unhover_close_button()
        self.assertFalse(close_btn.instate(['active']))
        closed = []
        original_close = cloud.close
        cloud.close = lambda event=None: (closed.append(True), original_close(event))[1]
        close_btn.invoke()
        self.assertEqual(len(closed), 1)


if __name__ == '__main__':
    unittest.main()

# -*- coding: utf-8 -*-
"""REQ-S01-117：模型选择器切换模型／推理档位时保住底部输入框草稿（R4259）。

覆盖两条丢稿路径：
1. ``_choose_model``／``choose_reasoning`` 写阶段配置会触发 save/refresh 回调；
   回调若清掉 ``desktop.shared_input.input`` 的文本，必须自动还原原文、光标、
   有效选区并把焦点放回输入框（模型与档位写入不回滚）。
2. 模型浮层 ``Flyout(win, noactivate=True)`` 在 Windows 下给顶层 HWND 追加
   ``WS_EX_NOACTIVATE``：点开浮层不抢系统焦点，输入法组词不被打断；其余
   ``Flyout`` 调用方（desktop_page_nav）默认行为不变。

运行：python -B -m unittest tests.test_model_picker_draft_keep -v（含 Tk 用例走隐藏桌面 runner）
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from skip_reasons import PLATFORM_TKINTER, PLATFORM_TK_DISPLAY, PLATFORM_WINDOWS_ONLY

HERE = os.path.dirname(os.path.abspath(__file__))
PROGRAM = os.path.dirname(HERE)
sys.path.insert(0, PROGRAM)
sys.path.insert(1, HERE)
os.chdir(PROGRAM)

import stage_config

WS_EX_NOACTIVATE = 0x08000000
GWL_EXSTYLE = -20


def _exstyle(widget):
    """读出窗口顶层 HWND 的 WS_EX_* 样式位（ctypes 只读；测试断言用）。"""
    import ctypes
    from ctypes import wintypes
    api = ctypes.windll.user32
    api.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
    api.GetWindowLongPtrW.restype = ctypes.c_longlong
    return api.GetWindowLongPtrW(widget.winfo_id(), GWL_EXSTYLE)


def _descendants(widget):
    for child in widget.winfo_children():
        yield child
        yield from _descendants(child)


class DraftKeepTests(unittest.TestCase):
    """REQ-S01-117 快照还原：save/refresh 清空输入框时还原文本、光标、选区与焦点。"""

    def setUp(self):
        try:
            import tkinter as tk
        except Exception:
            self.skipTest(PLATFORM_TKINTER)
        self.tk = tk
        try:
            self.win = tk.Tk()
        except tk.TclError:
            self.skipTest(PLATFORM_TK_DISPLAY)
        self.win.withdraw()
        self.addCleanup(self.win.destroy)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

        class Fake(object):
            pass

        self.desktop = Fake()
        self.desktop.win = self.win
        self.desktop.root = Path(self.tmp.name) / 'p'
        self.desktop.root.mkdir(parents=True, exist_ok=True)
        self.desktop.app = Path(self.tmp.name) / '程序'
        self.desktop.app.mkdir(parents=True, exist_ok=True)
        self.desktop.status = tk.StringVar(master=self.win, value='')

    def _make(self, stage='script'):
        """真 SharedStageInput（内嵌 StageModelPicker）；desktop.shared_input 指回它。"""
        import desktop_shared_input
        options = {'on_send': lambda text, parsed: True,
                   'skills': [], 'engines': ()}
        box = desktop_shared_input.SharedStageInput(
            self.win, desktop=self.desktop, stage=stage, options=options)
        box.pack(fill='x')
        self.desktop.shared_input = box
        self.win.update_idletasks()
        self.addCleanup(box.destroy)
        return box

    @staticmethod
    def _inject_models(picker):
        picker._items = [('m1', '模型甲'), ('m2', '模型乙')]
        picker._by_display = {'模型甲': 'm1', '模型乙': 'm2'}
        picker.model.set('模型甲')

    def test_choose_model_restores_draft_cleared_by_refresh(self):
        """选模型触发 save→refresh 清空输入框：还原原文与光标、回焦点、模型不回滚。"""
        box = self._make()
        picker = box.model_picker
        self._inject_models(picker)
        box.set_text('帮我写第一集开场，主角林夏')
        box.input.mark_set('insert', '1.5')
        self.win.deiconify()
        box.input.focus_set()
        self.win.update()
        # 用户报告的缺陷路径：保存模型触发的刷新回调把输入框清了
        self.desktop.refresh_script_chat_for_selected_model = (
            lambda: box.input.delete('1.0', 'end'))
        picker._choose_model('m2')
        self.win.update()
        self.assertEqual(stage_config.get(self.desktop.root, 'script')['model'], 'm2',
                         '模型写入不回滚')
        self.assertEqual(box.input.get('1.0', 'end-1c'),
                         '帮我写第一集开场，主角林夏', '被清空的草稿必须还原')
        self.assertEqual(box.input.index('insert'), '1.5', '光标回到原偏移')
        self.assertIs(self.win.focus_get(), box.input, '焦点回到输入框')

    def test_choose_reasoning_restores_draft_and_selection(self):
        """选推理档位时输入框被清：还原原文与选区、回焦点、档位写入不回滚。"""
        box = self._make()
        picker = box.model_picker
        box.set_text('第一场：咖啡馆重逢，雨夜')
        box.input.tag_add('sel', '1.4', '1.9')
        box.input.mark_set('insert', '1.9')
        self.win.deiconify()
        box.input.focus_set()
        self.win.update()
        real_put = stage_config.put

        def put_then_clear(project, stage, **kwargs):
            result = real_put(project, stage, **kwargs)
            box.input.delete('1.0', 'end')
            return result

        with mock.patch.object(stage_config, 'put', side_effect=put_then_clear):
            picker.choose_reasoning('high')
        self.assertEqual(stage_config.get(self.desktop.root, 'script')['reasoning'], 'high',
                         '档位写入不回滚')
        self.assertEqual(box.input.get('1.0', 'end-1c'), '第一场：咖啡馆重逢，雨夜')
        self.assertEqual(box.input.index('sel.first'), '1.4', '选区起点还原')
        self.assertEqual(box.input.index('sel.last'), '1.9', '选区终点还原')
        self.assertIs(self.win.focus_get(), box.input)

    def test_draft_unchanged_keeps_text_and_focuses_input(self):
        """refresh 不清空时：原文原样不被删改，焦点仍回输入框。"""
        box = self._make()
        picker = box.model_picker
        self._inject_models(picker)
        box.set_text('不被动摇的草稿')
        box.input.mark_set('insert', 'end-1c')
        self.win.deiconify()
        self.win.update()
        self.desktop.refresh_script_chat_for_selected_model = lambda: None
        picker._choose_model('m2')
        self.assertEqual(box.input.get('1.0', 'end-1c'), '不被动摇的草稿')
        self.assertIs(self.win.focus_get(), box.input)

    def test_draft_keep_skips_silently_without_live_input(self):
        """desktop 没有 shared_input／input 已销毁：照常写配置，不报错。"""
        import stage_model_picker
        picker = stage_model_picker.StageModelPicker(self.win, self.desktop, 'keyframe')
        self.addCleanup(picker.destroy)
        picker._choose_model('m9')
        self.assertEqual(stage_config.get(self.desktop.root, 'keyframe')['model'], 'm9')
        picker.choose_reasoning('low')
        self.assertEqual(stage_config.get(self.desktop.root, 'keyframe')['reasoning'], 'low')
        box = self._make()
        box.input.destroy()
        picker._choose_model('m8')
        self.assertEqual(stage_config.get(self.desktop.root, 'keyframe')['model'], 'm8')

    def test_picker_popup_is_noactivate_flyout(self):
        """回归守卫：StageModelPicker._open_popup 开的是 noactivate 浮层。"""
        import ui_popup
        box = self._make()
        picker = box.model_picker
        self._inject_models(picker)
        self.win.deiconify()
        self.win.update()
        picker._open_popup()
        self.win.update_idletasks()
        top = picker._popup
        self.assertIsNotNone(top)
        self.assertTrue(top.winfo_exists())
        self.assertTrue(getattr(top, 'noactivate', False),
                        '模型浮层应是 noactivate Flyout')
        if sys.platform.startswith('win'):
            self.assertTrue(_exstyle(top) & WS_EX_NOACTIVATE,
                            '浮层顶层 HWND 应带 WS_EX_NOACTIVATE')
        picker._close_popup()
        self.assertFalse(picker._popup_open())

    def test_clicking_model_row_writes_model_and_keeps_draft(self):
        """回归守卫（真实点击路径）：点浮层模型行 → 写模型、关浮层、草稿与焦点保留。"""
        box = self._make()
        picker = box.model_picker
        self._inject_models(picker)
        box.set_text('组词中的一句草稿')
        self.win.deiconify()
        box.input.focus_set()
        self.win.update()
        self.desktop.refresh_script_chat_for_selected_model = (
            lambda: box.input.delete('1.0', 'end'))
        picker._open_popup()
        self.win.update_idletasks()
        self.win.update()
        self.assertTrue(picker._popup_open())
        target = next(w for w in _descendants(picker._popup)
                      if w.winfo_class() == 'Label' and str(w.cget('text')) == '模型乙')
        x, y = target.winfo_width() // 2, target.winfo_height() // 2
        target.event_generate('<Button-1>', x=x, y=y,
                              rootx=target.winfo_rootx() + x,
                              rooty=target.winfo_rooty() + y)
        self.win.update()
        self.assertEqual(stage_config.get(self.desktop.root, 'script')['model'], 'm2')
        self.assertFalse(picker._popup_open(), '选中即关浮层')
        self.assertEqual(box.input.get('1.0', 'end-1c'), '组词中的一句草稿')
        self.assertIs(self.win.focus_get(), box.input)


class FlyoutNoactivateTests(unittest.TestCase):
    """REQ-S01-117：noactivate 浮层不抢系统焦点；默认调用方行为不变。"""

    def setUp(self):
        try:
            import tkinter as tk
        except Exception:
            self.skipTest(PLATFORM_TKINTER)
        self.tk = tk
        try:
            self.win = tk.Tk()
        except tk.TclError:
            self.skipTest(PLATFORM_TK_DISPLAY)
        self.win.withdraw()
        self.addCleanup(self.win.destroy)

    def test_default_flyout_keeps_old_behavior(self):
        """不传参＝旧行为：desktop_page_nav 等其它调用方不加 NOACTIVATE。"""
        import ui_popup
        top = ui_popup.Flyout(self.win)
        self.addCleanup(top.destroy)
        self.assertFalse(getattr(top, 'noactivate', False))
        if sys.platform.startswith('win'):
            self.assertFalse(_exstyle(top) & WS_EX_NOACTIVATE,
                             '默认浮层不得加 WS_EX_NOACTIVATE')

    @unittest.skipUnless(sys.platform.startswith('win'), PLATFORM_WINDOWS_ONLY)
    def test_noactivate_flyout_sets_ws_ex_noactivate(self):
        import ui_popup
        top = ui_popup.Flyout(self.win, noactivate=True)
        self.addCleanup(top.destroy)
        self.assertTrue(top.noactivate, 'noactivate=True 应报告已生效')
        self.assertTrue(_exstyle(top) & WS_EX_NOACTIVATE,
                        '顶层 HWND 应追加 WS_EX_NOACTIVATE')

    @unittest.skipUnless(sys.platform.startswith('win'), PLATFORM_WINDOWS_ONLY)
    def test_apply_noactivate_failure_returns_false(self):
        """取句柄／写样式失败：记日志并返回 False（调用方退回快照还原兜底）。"""
        import ui_popup
        top = ui_popup.Flyout(self.win)
        top.destroy()
        self.assertFalse(ui_popup.apply_noactivate(top))


if __name__ == '__main__':
    unittest.main()

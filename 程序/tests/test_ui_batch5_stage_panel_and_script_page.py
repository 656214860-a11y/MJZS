"""UI 批次 5：阶段配置动作栏换行／纵向滚动兜底，剧本页卡片同宽同基准。

真 Tk 根窗口量几何：800×460、880×600、1280×800 三档下动作栏按钮不裁字，
最小窗高 430 时表单主体出现纵向滚动且底栏固定；剧本结构页两张关键卡片左边缘同一 x。
"""
import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import infra.pet_state as pet_state
import skill_panel
from skip_reasons import PLATFORM_TKINTER

PROGRAM = Path(__file__).resolve().parents[1]


def _descendants(widget):
    for child in widget.winfo_children():
        yield child
        yield from _descendants(child)


def _buttons(widget):
    return [child for child in _descendants(widget)
            if child.winfo_class() in ('TButton', 'Button')]


class StagePanelLayoutTests(unittest.TestCase):
    def setUp(self):
        try:
            self.win = tk.Tk()
        except Exception:
            self.skipTest(PLATFORM_TKINTER)
        self.win.withdraw()
        self.addCleanup(lambda: self.win.winfo_exists() and self.win.destroy())
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name) / 'project'
        app = Path(self.tmp.name) / 'program'
        root.mkdir()
        app.mkdir()
        self.desktop = SimpleNamespace(win=self.win, root=root, app=app,
                                       status=tk.StringVar(master=self.win, value=''))

    def _open_panel(self):
        self.win.geometry('1280x800')
        self.win.deiconify()
        self.win.update()
        panel = skill_panel.show(self.desktop, 'script')
        window = panel.winfo_toplevel()
        self.addCleanup(lambda: window.winfo_exists() and window.destroy())
        return panel, window

    def test_action_buttons_fit_at_three_window_sizes(self):
        panel, window = self._open_panel()
        for width, height in ((800, 460), (880, 600), (1280, 800)):
            with self.subTest(size='%dx%d' % (width, height)):
                window.geometry('%dx%d' % (width, height))
                window.update()
                self.assertTrue(panel.bottom_bar.winfo_ismapped(),
                                '底栏必须固定可见')
                self.assertLessEqual(panel.bottom_bar.winfo_y() + panel.bottom_bar.winfo_height(),
                                     panel.winfo_height())
                for button in _buttons(panel):
                    self.assertTrue(button.winfo_ismapped(), button.cget('text'))
                    self.assertGreaterEqual(button.winfo_width(), button.winfo_reqwidth(),
                                            '按钮文字被裁：%s' % button.cget('text'))
                # R2862：预设动作栏已撤（制作锁改弹窗入口），底栏只剩状态与「确认并关闭」。

    def test_short_window_scrolls_form_and_keeps_bottom_bar_fixed(self):
        panel, window = self._open_panel()
        # R2862 精简面板后最小窗高（430）内表单已放得下：滚动条只在内容真超高时出现，
        # 收起同样是正确行为；本断言验证「超高才出滚动条、底栏始终固定」。
        window.geometry('800x430')
        window.update()
        canvas = panel.form_canvas
        self.assertIsNotNone(canvas)
        region = str(canvas.cget('scrollregion')).split()
        content_h = int(region[3])
        if content_h > canvas.winfo_height() + 1:
            self.assertTrue(panel.form_scroll.winfo_manager(), '内容超高时应出现纵向滚动兜底')
        else:
            self.assertFalse(panel.form_scroll.winfo_manager(),
                             '内容放得下时滚动条应收起，不占版面')
        bar_y = panel.bottom_bar.winfo_rooty()
        canvas.yview_moveto(1.0)
        window.update()
        self.assertAlmostEqual(canvas.yview()[1], 1.0, places=3)
        self.assertEqual(panel.bottom_bar.winfo_rooty(), bar_y, '滚动时底栏不得移动')
        top = canvas.winfo_rooty()
        bottom = top + canvas.winfo_height()
        for control in panel.skill_controls:
            if control.winfo_width() <= 1:
                continue
            self.assertGreaterEqual(control.winfo_rooty(), top - 1,
                                    '滚到底后勾选项应在可视区内')
            self.assertLessEqual(control.winfo_rooty() + control.winfo_height(), bottom + 1,
                                 '滚到底后勾选项应完整可见')

    def test_recoverable_error_notifies_without_modal_dialog(self):
        desktop = SimpleNamespace(win=self.win, root=None, app=None,
                                  status=tk.StringVar(master=self.win, value=''))
        with mock.patch.object(skill_panel, 'notify') as notify:
            self.assertIsNone(skill_panel.show(desktop, 'script'))
        self.assertFalse(notify.call_args.kwargs.get('modal', True),
                         '可恢复错误不得默认模态')


class ScriptPageLayoutTests(unittest.TestCase):
    def setUp(self):
        try:
            self.win = tk.Tk()
        except Exception:
            self.skipTest(PLATFORM_TKINTER)
        self.addCleanup(lambda: self.win.winfo_exists() and self.win.destroy())
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def test_structure_cards_share_left_edge_and_width(self):
        import desktop as desktop_module
        from desktop import Desktop
        project = Path(self.tmp.name) / 'project'
        (project / 'writing').mkdir(parents=True)
        self.win.geometry('1100x760+40+40')
        original = desktop_module.Desktop.choose_project
        desktop_module.Desktop.choose_project = lambda self: None
        self.addCleanup(setattr, desktop_module.Desktop, 'choose_project', original)
        desktop = Desktop(self.win, root=PROGRAM)
        desktop.root = project
        desktop.show(pet_state.PAGE_OF['script_structure'])
        self.win.update()
        source = desktop.script_structure_source_box
        output = desktop.script_structure_output_box
        self.assertEqual(source.winfo_rootx(), output.winfo_rootx(),
                         '两张剧本卡片左边缘必须对齐')
        self.assertEqual(source.winfo_width(), output.winfo_width(),
                         '两张剧本卡片必须同宽')
        actions = desktop.script_structure_manual_button.master.master
        self.assertEqual(actions.winfo_rootx(), source.winfo_rootx(),
                         '中间动作栏与上下卡片共用同一左基准')
        self.assertEqual(actions.winfo_width(), source.winfo_width(),
                         '中间动作栏与卡片同宽')
        info = desktop.script_structure_info_label
        # R2950 页头改单行：状态居左可伸展、模型名贴右（原两行右对齐时代的 justify='right' 断言同步为 left）。
        self.assertEqual(str(info.cget('justify')), 'left')
        self.assertLessEqual(info.winfo_rootx() + info.winfo_width(),
                             source.winfo_rootx() + source.winfo_width() + 1,
                             '说明文字不得越出卡片右沿')


if __name__ == '__main__':
    unittest.main()

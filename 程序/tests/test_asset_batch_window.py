# -*- coding: utf-8 -*-
"""批量资产窗口：在已填充的演示项目上用 ComfyUI、资产工作流、Skill 三种方式打开，
点不联网、不开外部程序的按钮，确认表单、类别勾选、保存设置、云模型密钥窗口都能用。"""
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import asset_batch
from skip_reasons import PLATFORM_TKINTER

# 会联网、开外部程序、弹模态框或真开始生产的按钮不点。
SKIP = ('启动并检测', '删除模型', '选择文件', '开始资产图片制作', 'Midjourney（手动）', '阶段配置', '生成记录')


def _walk(widget):
    yield widget
    for child in widget.winfo_children():
        yield from _walk(child)


class AssetBatchWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import tkinter
            tkinter.Tk().destroy()
            cls.tk = tkinter
        except Exception:
            cls.tk = None

    def setUp(self):
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        import test_ui_edges
        from desktop import Desktop
        from local_video import open_studio
        td = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, td, True)
        self.win = self.tk.Tk()
        self.win.withdraw()
        self.addCleanup(self.win.destroy)
        (td / 'app').mkdir()
        self.desktop = Desktop(self.win, root=td / 'app')
        self.desktop.startup_controller.cancel()
        self.desktop.root = test_ui_edges.make_populated_project(td)
        self.desktop.studio = open_studio(self.desktop.root)
        self.desktop.cancel_timers()
        self.addCleanup(self.desktop.cancel_timers)
        self.background = []
        self.desktop.async_ = lambda work, done=None, **kw: self.background.append(work)
        self.errors = []
        self.desktop.notifier = mock.Mock()
        self.desktop.notifier.error.side_effect = lambda text, **kw: self.errors.append(str(text))

    def open(self, engine, ids=None):
        before = set(self.win.winfo_children())
        asset_batch.show(self.desktop, engine, selected_ids=ids)
        self.win.update()
        popup = [w for w in self.win.winfo_children() if w not in before and isinstance(w, self.tk.Toplevel)][-1]
        self.addCleanup(lambda: popup.winfo_exists() and popup.destroy())
        return popup

    def buttons(self, popup):
        return {str(w.cget('text')): w for w in _walk(popup)
                if w.winfo_class() in ('TButton', 'Button') and str(w.cget('text')) not in SKIP}

    def press(self, popup, *names):
        found = self.buttons(popup)
        before = set(self.win.winfo_children()) | set(popup.winfo_children())
        with mock.patch('webbrowser.open'), mock.patch('tkinter.messagebox.showerror'), \
                mock.patch('tkinter.messagebox.askyesno', return_value=False):
            for name in names:
                found[name].invoke()
                self.win.update()
        opened = [w for w in list(self.win.winfo_children()) + list(popup.winfo_children())
                  if w not in before and isinstance(w, self.tk.Toplevel)]
        for window in opened:
            self.addCleanup(lambda w=window: w.winfo_exists() and w.destroy())
        return opened

    def status_text(self, popup):
        return [str(w.cget('text')) for w in _walk(popup) if w.winfo_class() == 'TLabel']

    def test_comfy_window_saves_settings_toggles_categories_and_opens_key_dialog(self):
        popup = self.open('comfy')
        found = self.buttons(popup)
        for name in ('保存设置', '云模型设置', '开始批量生成并导入', '停止后续资产'):
            self.assertIn(name, found)
        checks = [w for w in _walk(popup) if w.winfo_class() == 'TCheckbutton']
        self.assertTrue(checks)
        for check in checks:
            check.invoke();check.invoke()
        self.win.update()
        self.press(popup, '保存设置')
        settings = Path(self.desktop.root) / 'ui_settings.json'
        self.assertIn('asset_batch', settings.read_text(encoding='utf-8'))
        with mock.patch('model_pool.named_key', return_value='sk-abcdefgh'):
            dialogs = self.press(popup, '云模型设置')
        self.assertEqual(1, len(dialogs))
        labels = self.status_text(dialogs[0])
        self.assertIn('已保存密钥（sk-a****）', labels)
        self.press(popup, '开始批量生成并导入', '停止后续资产')
        self.assertTrue(popup.winfo_exists())

    def test_workflow_window_opens_native_controls_and_account_dialog(self):
        popup = self.open('workflow', ['CHAR_001'])
        found = self.buttons(popup)
        account = next(name for name in found if '密钥' in name or '账号' in name)
        with mock.patch('model_pool.named_key', return_value=''):
            for name in list(found):
                if name != account and found[name].winfo_exists():
                    self.press(popup, name)
            dialogs = self.press(popup, account)
        self.assertTrue(dialogs)

    def test_skill_window_hides_local_comfy_form(self):
        popup = self.open('skill')
        found = self.buttons(popup)
        self.assertNotIn('停止后续资产', found)
        self.assertNotIn('开始批量生成并导入', found)
        self.press(popup, '保存设置')
        self.assertTrue(popup.winfo_exists())


if __name__ == '__main__':
    unittest.main()

# -*- coding: utf-8 -*-
"""批量资产窗口：在已填充的演示项目上用 ComfyUI、资产工作流、Skill 三种方式打开，
点不联网、不开外部程序的按钮，确认表单、类别勾选、保存设置、云模型密钥窗口都能用。"""
import queue
import shutil
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import asset_batch
from infra.pet_state import PAGE_OF
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
        import ui_edges_support
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
        self.desktop.root = ui_edges_support.make_populated_project(td)
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


class _Host:
    """批次结束回调用到的主窗口那几样：当前项目、当前页、状态栏、翻页、完成消息上报。"""

    def __init__(self, root, page_index):
        self.root = root
        self.page_index = page_index
        self.status = mock.Mock()
        self.shown = []
        self.reports = []
        self.finishers = []

    def show(self, index):
        self.shown.append(index)

    def pet_report(self, stage, text):
        self.reports.append((stage, text))

    def launch_comfy(self, silent=False):
        return True

    def async_(self, work, done=None, **kw):
        self.finishers.append(done)

    def current_frame_json(self):
        return None

    def asset_scope(self):
        return None

    def asset_sources(self):
        return None


class AssetBatchFinishStaysOnPageTests(unittest.TestCase):
    """REQ-S05-24：批量生成结束不把人从别的页拉回资产管理页（UX-B6B）。

    不开窗口：拿替身当批次窗，走到 start() 把结束回调交给后台任务那一步，再直接调这个回调。
    """

    RESULT = '资产批次完成：已导入 2 项'

    def _finish(self, page_index, *, project='项目甲', root='项目甲'):
        window = mock.MagicMock()
        window.app = _Host(root, page_index)
        window.project = project
        window.skill_mode = False
        window.events = queue.Queue()
        window.events.put('上一条进度消息')
        window.checks = {}
        window.work_options.return_value = {'url': 'http://127.0.0.1:8188'}
        window.controller.start_decision.return_value = SimpleNamespace(items=[], uncertain_ids=[])
        with mock.patch('stage_execution_service.require_formal_asset_generation'), \
                mock.patch.object(asset_batch, 'uncertain_assets', return_value=[]), \
                mock.patch.object(asset_batch, 'Comfy'), \
                mock.patch.object(asset_batch, 'save_settings',
                                  return_value=SimpleNamespace(ok=True, reason='')):
            asset_batch._AssetBatchWindow.start(window)
        self.assertEqual(len(window.app.finishers), 1, 'start() 应把结束回调交给后台任务一次')
        window.app.finishers[0](self.RESULT)
        return window

    def test_finish_redraws_assets_page_when_user_is_on_it(self):
        window = self._finish(PAGE_OF['assets'])
        self.assertEqual(window.app.shown, [PAGE_OF['assets']])
        window.app.status.set.assert_called_with(self.RESULT)

    def test_finish_leaves_other_pages_alone(self):
        window = self._finish(PAGE_OF['storyboard'])
        self.assertEqual(window.app.shown, [], '人在别的页时不许翻回资产管理页')
        window.app.status.set.assert_called_with(self.RESULT)
        window.status.set.assert_called_with(self.RESULT)
        self.assertEqual(window.app.reports, [('assets', self.RESULT)], '完成消息仍要上报')
        self.assertTrue(window.events.empty(), '没显示完的进度消息仍要清掉')

    def test_finish_after_project_switch_does_not_redraw(self):
        window = self._finish(PAGE_OF['assets'], root='项目乙')
        self.assertEqual(window.app.shown, [])
        window.app.status.set.assert_called_with(self.RESULT)

    def test_req_s05_53_start_writes_sg_b_advisory_to_status_bar(self):
        """REQ-S05-53：未锁定分镜预演时，批量生图启动把提醒写入状态栏且不阻塞启动。"""
        window = mock.MagicMock()
        window.app = _Host('项目甲', PAGE_OF['assets'])
        window.project = '项目甲'
        window.skill_mode = False
        window.events = queue.Queue()
        window.checks = {}
        window.work_options.return_value = {'url': 'http://127.0.0.1:8188'}
        window.controller.start_decision.return_value = SimpleNamespace(items=[], uncertain_ids=[])
        note = '提示：尚未锁定分镜预演，将先按已采用分镜制作资产'
        with mock.patch('stage_execution_service.require_formal_asset_generation', return_value=note), \
                mock.patch.object(asset_batch, 'uncertain_assets', return_value=[]), \
                mock.patch.object(asset_batch, 'Comfy'), \
                mock.patch.object(asset_batch, 'save_settings',
                                  return_value=SimpleNamespace(ok=True, reason='')):
            asset_batch._AssetBatchWindow.start(window)
        window.status.set.assert_any_call(note)
        window.app.status.set.assert_any_call(note)


class DeleteConfirmCopyTests(unittest.TestCase):
    """UX-S05-54／55：删图确认文案接引用摘要；封装抛错退回纯文案。"""

    def host(self, root='.'):
        from ui.desktop_asset_pages import AssetPagesMixin

        class Host(AssetPagesMixin):
            pass

        item = Host()
        item.root = Path(root)
        item.asset_work_hint = lambda targets, how: ''
        return item

    def test_single_delete_appends_reference_summary(self):
        host = self.host()
        with mock.patch('stage_execution_service.deletion_references',
                        return_value={'summary': '被 2 个采用镜头引用（SH001、SH002）。',
                                      'protected': True, 'shots': ['SH001', 'SH002']}):
            text = host._delete_image_confirm_text('CHAR_001', 'assets/CHAR_001.png')
        self.assertIn('删除 CHAR_001 的已导入图片', text)
        self.assertIn('被 2 个采用镜头引用', text)

    def test_batch_delete_appends_cited_count(self):
        host = self.host()

        def refs(project, aid, **_kw):
            return {'protected': aid == 'CHAR_001', 'shots': ['SH001'], 'summary': ''}

        with mock.patch('stage_execution_service.deletion_references', side_effect=refs):
            text = host._batch_delete_images_confirm_text(
                ['CHAR_001', 'CHAR_002'], 'CHAR_001、CHAR_002', 'checked')
        self.assertIn('其中 1 项被采用镜头引用：CHAR_001', text)

    def test_gateway_error_falls_back_to_plain_copy(self):
        host = self.host()
        with mock.patch('stage_execution_service.deletion_references',
                        side_effect=RuntimeError('断了')):
            single = host._delete_image_confirm_text('CHAR_001', 'a.png')
            batch = host._batch_delete_images_confirm_text(['CHAR_001'], 'CHAR_001', 'checked')
        self.assertIn('移入项目回收站', single)
        self.assertNotIn('采用镜头', single)
        self.assertIn('移入项目回收站', batch)
        self.assertNotIn('其中', batch)


if __name__ == '__main__':
    unittest.main()

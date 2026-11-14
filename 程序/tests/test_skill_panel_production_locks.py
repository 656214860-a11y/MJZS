"""R1483 制作锁控件依赖与窄窗布局。"""
import unittest
from skip_reasons import PLATFORM_TK_DISPLAY


class ProductionLockViewTests(unittest.TestCase):
    def setUp(self):
        import tkinter as tk
        try:
            self.win = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(PLATFORM_TK_DISPLAY)
        self.addCleanup(self.win.destroy)

    def test_controls_dependency_defaults_and_wrapping(self):
        from production_lock_fields import ProductionLockFields
        self.win.geometry('480x700')
        view = ProductionLockFields(self.win)
        view.pack(fill='x')
        self.win.update()
        self.assertEqual(len(view.inputs), 11)
        self.assertEqual(view.inputs['track'].get(), '')
        # 契约变更：必选缺失不再占一行文字提示，改为标签警示色（不占高度）。
        from ui_tokens import COLORS
        self.assertEqual(str(view.fields['track']['label'].cget('foreground')), COLORS['warning_text'])
        self.assertEqual(view.hints['track'].cget('text'), '')
        self.assertTrue(view.inputs['reference_mode'].instate(['disabled']))
        view.set_values({'video_model_version': 'Seedance 2.5'})
        self.win.update()
        self.assertFalse(view.inputs['reference_mode'].instate(['disabled']))
        self.assertEqual(view.inputs['reference_mode'].get(), '全能参考模式')
        ys = {child.winfo_y() for child in view.winfo_children()}
        self.assertGreater(len(ys), 1)
        for child in view.winfo_children():
            self.assertLessEqual(child.winfo_x() + child.winfo_width(), view.winfo_width())
        view.set_values({'video_model_version': 'Seedance 2.0'})
        self.assertTrue(view.inputs['reference_mode'].instate(['disabled']))
        self.assertEqual(view.hints['reference_mode'].cget('text'), '仅 Seedance 2.5')


class WorkflowLockEnablementTests(unittest.TestCase):
    """REQ-S01-57 总控未确认时制作锁灰态提示，确认后才可选并写回项目。"""

    def setUp(self):
        import tempfile
        import tkinter as tk
        from pathlib import Path
        try:
            self.win = tk.Tk()
        except tk.TclError as exc:
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

    def _panel(self):
        import skill_panel
        panel = skill_panel.Panel(self.win, self.desktop, 'script')
        self.addCleanup(panel.destroy)
        return panel

    def test_lock_notice_tells_user_to_confirm_master(self):
        """REQ-S01-57 总控未生效时，制作锁灰态旁提示先选总控并点「确认套用」。"""
        import stage_config
        panel = self._panel()
        self.assertTrue(panel.lock_inputs['aspect_ratio'].instate(['disabled']))
        self.assertIn('确认套用', panel.lock_notice.cget('text'))
        # 下拉框显示已挑的总控，但没确认：锁仍灰，提示不能被这句显示掩盖。
        panel.workflow_choice.set('AIGC全流程')
        self.assertTrue(panel.lock_inputs['aspect_ratio'].instate(['disabled']))
        self.assertIn('确认套用', panel.lock_notice.cget('text'))
        # 生效后锁解锁，提示让位给原有的旧项目兼容提示（不互相覆盖）。
        stage_config.put_workflow(self.desktop.root,
                                  {'name': 'AIGC全流程',
                                   'skill_ref': 'skills/AIGC/SKILL.md', 'lock': {}})
        panel.refresh_workflow()
        self.assertFalse(panel.lock_inputs['aspect_ratio'].instate(['disabled']))
        notice = panel.lock_notice.cget('text')
        self.assertNotIn('确认套用', notice)
        self.assertTrue(notice == '' or '旧项目兼容' in notice, notice)

    def test_check_update_option_runs_manual_check_and_restores_selection(self):
        """R2002 总控下拉框的“检查更新”是动作项：触发手动检查，下拉框回到已保存的总控。"""
        calls = []
        self.desktop.start_master_update_check = lambda manual=False: calls.append(manual)
        panel = self._panel()
        self.assertIn('检查更新', panel.workflow_box.cget('values'))
        panel.workflow_choice.set('检查更新')
        panel.choose_workflow()
        self.assertEqual(calls, [True])
        self.assertEqual(panel.workflow_choice.get(), '不使用总控')

    def test_check_update_option_without_desktop_support_only_informs(self):
        panel = self._panel()
        panel.workflow_choice.set('检查更新')
        panel.choose_workflow()
        self.assertEqual(panel.workflow_choice.get(), '不使用总控')
        self.assertIn('不支持', panel.state.cget('text'))

    def test_confirm_master_enables_locks_and_saves_change(self):
        """REQ-S01-57 选总控→确认套用→锁可选→改画幅写回 stage_config.workflow_lock。"""
        import stage_config

        def descendants(widget):
            return [child for item in widget.winfo_children()
                    for child in [item] + descendants(item)]

        panel = self._panel()
        self.assertTrue(panel.lock_inputs['aspect_ratio'].instate(['disabled']))
        panel.workflow_choice.set('AIGC全流程')
        # 真 Tk 量可见几何：根窗口映射后 transient 对话框才会显示。
        self.win.deiconify()
        self.win.update()
        from unittest import mock
        import tkinter as tk
        with mock.patch.object(tk.Misc, 'winfo_screenheight', return_value=800), \
             mock.patch.object(tk.Misc, 'winfo_screenwidth', return_value=1280):
            panel.choose_workflow()
            self.win.update()
            dialogs = [widget for widget in self.win.winfo_children()
                       if widget.winfo_class() == 'Toplevel']
            self.assertEqual(len(dialogs), 1, '选择总控后应弹出套用建议窗口')
            dialog = dialogs[0]
            buttons = {widget.cget('text'): widget for widget in descendants(dialog)
                       if widget.winfo_class() in ('TButton', 'Button')}
            confirm = buttons['确认套用']
            self.assertTrue(confirm.winfo_viewable(), '确认套用按钮不可见，用户点不到')
            bottom = confirm.winfo_rooty() - dialog.winfo_rooty() + confirm.winfo_height()
            self.assertLessEqual(bottom, dialog.winfo_height(),
                                 '确认套用按钮在窗口外，用户点不到')
            self.assertLessEqual(confirm.winfo_rooty() + confirm.winfo_height(), 800,
                                 '确认套用按钮落到屏幕外，用户点不到')
            confirm.invoke()
            self.win.update()
        self.assertFalse(panel.lock_inputs['aspect_ratio'].instate(['disabled']),
                         '确认总控后制作锁仍不可选')
        panel.lock_inputs['aspect_ratio'].set('9:16')
        panel.save_workflow_locks()
        self.assertEqual(stage_config.workflow_lock(self.desktop.root).get('aspect_ratio'),
                         '9:16')

    def test_reapply_master_after_no_master_restores_locks(self):
        """REQ-S01-81 「不使用总控」再切回同一总控，制作锁从历史投影恢复，不丢失。"""
        import skill_panel
        import stage_config

        def descendants(widget):
            return [child for item in widget.winfo_children()
                    for child in [item] + descendants(item)]

        panel = self._panel()
        # 先让项目带上 AIGC全流程 及已填的制作锁，模拟此前已套用并填过锁。
        stage_config.put_workflow(self.desktop.root, {
            'name': 'AIGC全流程', 'skill_ref': 'x/SKILL.md',
            'lock': {'AIGC全流程': {'aspect_ratio': '9:16', 'track': '短剧'}}})
        panel.refresh_workflow()
        # 切到「不使用总控」：锁挪进 workflow_lock_history。
        panel.workflow_choice.set(skill_panel.NO_MASTER)
        panel.choose_workflow()
        self.assertFalse(stage_config.current_workflow(self.desktop.root))
        self.assertEqual(stage_config.workflow_lock_history(self.desktop.root)
                         .get('AIGC全流程', {}).get('aspect_ratio'), '9:16')
        # 再切回 AIGC全流程 并确认套用：锁应被恢复。
        panel.workflow_choice.set('AIGC全流程')
        self.win.deiconify()
        self.win.update()
        from unittest import mock
        import tkinter as tk
        with mock.patch.object(tk.Misc, 'winfo_screenheight', return_value=800), \
             mock.patch.object(tk.Misc, 'winfo_screenwidth', return_value=1280):
            panel.choose_workflow()
            self.win.update()
            dialogs = [widget for widget in self.win.winfo_children()
                       if widget.winfo_class() == 'Toplevel']
            confirm = next(widget for dialog in dialogs
                           for widget in descendants(dialog)
                           if widget.winfo_class() in ('TButton', 'Button')
                           and widget.cget('text') == '确认套用')
            confirm.invoke()
            self.win.update()
        self.assertEqual(stage_config.workflow_lock(self.desktop.root).get('aspect_ratio'), '9:16')
        self.assertEqual(stage_config.workflow_lock(self.desktop.root).get('track'), '短剧')

"""制作锁横向编辑的真实 Tk 交互回归。"""
import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import skill_panel
import script_contract
import stage_config
from ui_tokens import COMBOBOX_MAX_WIDTH
from ui_widgets import SelectBox


class ProductionLockUITests(unittest.TestCase):
    def setUp(self):
        self.win = tk.Tk()
        self.win.withdraw()
        self.addCleanup(self.win.destroy)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name) / 'project'
        app = Path(self.tmp.name) / 'program'
        root.mkdir()
        app.mkdir()
        self.desktop = SimpleNamespace(win=self.win, root=root, app=app,
                                       status=tk.StringVar(master=self.win, value=''))

    def test_production_lock_inputs_save_and_wrap(self):
        import workflow_settings
        name = next(iter(workflow_settings.WORKFLOW_PRESETS))
        stage_config.put_workflow(self.desktop.root, {'name': name,
            'lock': {name: {'aspect_ratio': '9:16'}}})
        panel = skill_panel.Panel(self.win, self.desktop, 'script')
        self.addCleanup(panel.destroy)
        panel.refresh_workflow()
        legacy = script_contract.PRODUCTION_LOCK_DEFINITIONS
        self.assertEqual(list(panel.lock_inputs), [item['key'] for item in legacy])
        self.assertIs(panel.workflow_box.master.master, panel.lock_fields)
        self.assertEqual(len(panel.lock_fields.winfo_children()), len(legacy) + 1)
        for entry in panel.lock_inputs.values():
            self.assertTrue(entry.bind('<Return>'))
            self.assertTrue(entry.bind('<KeyRelease>'))
            self.assertTrue(entry.bind('<FocusOut>'))
            # 制作锁下拉改为按「选项＋当前值」最长项自适应（R1684 契约有意变更）：
            # 宽度等于最长显示项（CJK 按 2 计），封顶 COMBOBOX_MAX_WIDTH，不再是固定 6/12。
            self.assertLessEqual(int(entry.cget('width')), COMBOBOX_MAX_WIDTH)
            self.assertEqual(int(entry.cget('width')),
                             SelectBox._fit_width(tuple(entry.cget('values')), entry.get()))
        self.assertFalse(hasattr(panel, 'workflow_summary'))
        self.assertFalse(panel.lock_fields.field_visible('reference_mode'))
        self.assertFalse(panel.lock_fields.field_visible('style_base'))
        self.assertTrue(panel.lock_fields.field_visible('track'))
        self.assertEqual(set(panel.lock_inputs), {item['key'] for item in script_contract.PRODUCTION_LOCK_DEFINITIONS})
        for definition in script_contract.PRODUCTION_LOCK_DEFINITIONS:
            entry = panel.lock_inputs[definition['key']]
            self.assertIs(entry.master.master, panel.lock_fields)
        for definition in script_contract.PRODUCTION_LOCK_DEFINITIONS[5:]:
            entry = panel.lock_inputs[definition['key']]
            # 每个新增锁都通过原有失焦事件保存；折叠区也保留输入值。
            value = (definition.get('options') or ('测试导演卡',))[-1]
            if definition['key'] == 'reference_mode':
                model = panel.lock_inputs['video_model_version']
                model.delete(0, 'end')
                model.insert(0, 'Seedance 2.5')
                model.event_generate('<FocusOut>')
                self.win.update()
                self.assertFalse(entry.instate(['disabled']))
            entry.delete(0, 'end')
            entry.insert(0, value)
            entry.event_generate('<FocusOut>')
            self.win.update()
            self.assertEqual(stage_config.workflow_lock(self.desktop.root)[definition['key']], value)
        entry = panel.lock_inputs['aspect_ratio']
        self.assertEqual(entry.get(), '9:16')
        entry.delete(0, 'end')
        entry.insert(0, '16:9')
        entry.event_generate('<FocusOut>')
        self.win.update()
        self.assertEqual(stage_config.workflow_lock(self.desktop.root)['aspect_ratio'], '16:9')
        panel.refresh_workflow()
        self.assertEqual(entry.get(), '16:9')
        panel.toggle_optional_locks()
        self.assertTrue(panel.lock_fields.field_visible('reference_mode'))
        self.assertTrue(panel.lock_fields.field_visible('style_base'))
        for definition in script_contract.PRODUCTION_LOCK_DEFINITIONS[5:]:
            key = definition['key']
            self.assertEqual(panel.lock_inputs[key].get(), stage_config.workflow_lock(self.desktop.root)[key])
        panel.toggle_optional_locks()
        self.assertFalse(panel.lock_fields.field_visible('reference_mode'))
        self.assertFalse(panel.lock_fields.field_visible('style_base'))


    def test_autosave_skips_unchanged_values_and_reports_failed_write(self):
        import workflow_settings
        name = next(iter(workflow_settings.WORKFLOW_PRESETS))
        stage_config.put_workflow(self.desktop.root, {'name': name,
            'lock': {name: {'aspect_ratio': '9:16'}}})
        panel = skill_panel.Panel(self.win, self.desktop, 'script')
        self.addCleanup(panel.destroy)
        entry = panel.lock_inputs['aspect_ratio']
        with patch('stage_execution_service.save_writing_production_locks') as save:
            panel.save_workflow_locks()
            save.assert_not_called()
        entry.delete(0, 'end')
        entry.insert(0, '16:9')
        with patch('stage_execution_service.save_writing_production_locks',
                   side_effect=OSError('write denied')) as save:
            entry.event_generate('<FocusOut>')
            self.win.update()
            save.assert_called_once()
        self.assertIn('制作锁保存失败', panel.state.cget('text'))
        self.assertEqual(stage_config.workflow_lock(self.desktop.root)['aspect_ratio'], '9:16')
        entry.event_generate('<FocusOut>')
        self.win.update()
        self.assertEqual(stage_config.workflow_lock(self.desktop.root)['aspect_ratio'], '16:9')

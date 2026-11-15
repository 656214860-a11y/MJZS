"""制作锁弹窗预选的真实 Tk 交互回归（R2862：内联锁编辑器已删，改弹窗显式保存）。"""
import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import skill_panel
import script_contract
import stage_config
from production_lock_fields import ProductionLockFields
from ui_tokens import COMBOBOX_MAX_WIDTH, STAGE_PANEL_LAYOUT


def _find(widget, kind):
    """递归找出窗口里第一个 isinstance(widget, kind) 的控件。"""
    if isinstance(widget, kind):
        return widget
    for child in widget.winfo_children():
        found = _find(child, kind)
        if found is not None:
            return found
    return None


def _buttons(window, text):
    from tkinter import ttk
    found = []

    def walk(widget):
        for child in widget.winfo_children():
            if isinstance(child, ttk.Button) and child.cget('text') == text:
                found.append(child)
            walk(child)
    walk(window)
    return found


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
        self.panel = skill_panel.Panel(self.win, self.desktop, 'script')
        self.addCleanup(self.panel.destroy)

    def _open_dialog(self):
        window = self.panel.open_lock_dialog()
        self.assertIsNotNone(window)
        self.win.update()
        fields = _find(window, ProductionLockFields)
        self.assertIsNotNone(fields, '弹窗里必须挂 ProductionLockFields')
        return window, fields

    def test_lock_dialog_prefills_and_saves(self):
        stage_config.put_production_locks(self.desktop.root,
                                          {'aspect_ratio': '9:16'})
        window, fields = self._open_dialog()
        self.assertEqual(list(fields.inputs),
                         [item['key'] for item in script_contract.PRODUCTION_LOCK_DEFINITIONS])
        for definition in script_contract.PRODUCTION_LOCK_DEFINITIONS:
            entry = fields.inputs[definition['key']]
            # 契约变更（R1965 统一下拉框尺寸）：阶段配置页下拉框统一宽度，
            # 不再按最长项自适应；放不下的全名由弹出列表加宽展示。
            self.assertLessEqual(int(entry.cget('width')), COMBOBOX_MAX_WIDTH)
            self.assertEqual(int(entry.cget('width')), STAGE_PANEL_LAYOUT['select_width'])
        # 弹窗一次展示全部契约锁项（无内联折叠区）；依赖禁用仍生效。
        self.assertTrue(fields.field_visible('reference_mode'))
        self.assertTrue(fields.field_visible('style_base'))
        self.assertTrue(fields.field_visible('track'))
        self.assertEqual(fields.inputs['aspect_ratio'].get(), '9:16')
        self.assertTrue(fields.inputs['reference_mode'].instate(['disabled']),
                        '未选 Seedance 2.5 时 reference_mode 应保持禁用')
        # 模型驱动项：Seedance 2.5 才解锁 reference_mode。
        model = fields.inputs['video_model_version']
        model.delete(0, 'end')
        model.insert(0, 'Seedance 2.5')
        model.event_generate('<FocusOut>')
        self.win.update()
        self.assertFalse(fields.inputs['reference_mode'].instate(['disabled']))
        reference = fields.inputs['reference_mode']
        reference.delete(0, 'end')
        reference.insert(0, '全能参考模式')
        save = _buttons(window, '保存')
        self.assertEqual(len(save), 1)
        save[0].invoke()
        self.win.update()
        locks = stage_config.workflow_lock(self.desktop.root)
        self.assertEqual(locks['aspect_ratio'], '9:16')
        self.assertEqual(locks['reference_mode'], '全能参考模式')
        self.assertEqual(locks['video_model_version'], 'Seedance 2.5')
        self.assertEqual(self.panel.state.cget('text'), '制作锁已保存。')
        self.assertFalse(window.winfo_exists())

    def test_lock_dialog_save_failure_keeps_values(self):
        stage_config.put_production_locks(self.desktop.root,
                                          {'aspect_ratio': '9:16'})
        window, fields = self._open_dialog()
        fields.inputs['aspect_ratio'].delete(0, 'end')
        fields.inputs['aspect_ratio'].insert(0, '16:9')
        with patch('stage_execution_service.save_writing_production_locks',
                   side_effect=OSError('write denied')), \
                patch('skill_panel_workflow.notify') as notify:
            _buttons(window, '保存')[0].invoke()
            self.win.update()
        notify.assert_called_once()
        self.assertIn('制作锁保存失败', notify.call_args[0][1])
        self.assertTrue(window.winfo_exists(), '保存失败时弹窗应保留供重试')
        self.assertEqual(stage_config.workflow_lock(self.desktop.root)['aspect_ratio'], '9:16')


if __name__ == '__main__':
    unittest.main()

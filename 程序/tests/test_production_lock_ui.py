"""制作锁横向编辑的真实 Tk 交互回归。"""
import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from types import SimpleNamespace

import skill_panel
import stage_config


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

    def test_production_lock_inputs_are_horizontal_and_save(self):
        import workflow_settings
        name = next(iter(workflow_settings.WORKFLOW_PRESETS))
        stage_config.put_workflow(self.desktop.root, {'name': name,
            'lock': {name: {'aspect_ratio': '9:16'}}})
        panel = skill_panel.Panel(self.win, self.desktop, 'script')
        self.addCleanup(panel.destroy)
        panel.refresh_workflow()
        for column, entry in enumerate(panel.lock_inputs.values()):
            self.assertEqual(int(entry.master.grid_info()['row']), 0)
            self.assertEqual(int(entry.master.grid_info()['column']), column)
            self.assertTrue(entry.bind('<Return>'))
        entry = panel.lock_inputs['aspect_ratio']
        self.assertEqual(entry.get(), '9:16')
        entry.delete(0, 'end')
        entry.insert(0, '16:9')
        self.assertEqual(panel.save_workflow_locks(), 'break')
        self.assertEqual(stage_config.workflow_lock(self.desktop.root)['aspect_ratio'], '16:9')
        panel.refresh_workflow()
        self.assertEqual(entry.get(), '16:9')


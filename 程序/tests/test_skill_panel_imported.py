"""外部 SKILL 包只读展示与旧阶段选择回写。"""
import tkinter as tk
import unittest
from unittest import mock

import skill_panel
import skill_registry
import stage_config
import test_skills
from ui_widgets import HintLabel


class ImportedPackagePanelTests(unittest.TestCase):
    tk = tk
    setUp = test_skills.PanelTests.setUp

    def make_panel(self, *, existing=False):
        stage_dir = self.desktop.app / 'skills' / '01剧本准备SKILL'
        test_skills.write_skill(stage_dir, 'ordinary-skill', display='普通技能')
        package = stage_dir / 'external-package'
        package.mkdir()
        (package / 'SKILL.md').write_text(
            '---\nname: external-package\ndescription: 外部编剧技能包\n---\n外部说明', encoding='utf-8')
        registry = skill_registry.Registry(root=self.desktop.app / 'skills')
        items = registry.getByStage('script')
        imported = next(item for item in items if item.meta.get(skill_registry.IMPORTED_PACKAGE_FLAG))
        if existing:
            stage_config.put(self.desktop.root, 'script', model='qwen-max',
                             skills=['ordinary-skill', imported.name], registry=registry,
                             hollmwood_enabled=False)
        with mock.patch.object(skill_registry, 'default_registry', return_value=registry):
            panel = skill_panel.Panel(self.win, self.desktop, 'script')
        self.addCleanup(panel.destroy)
        return panel, imported

    def test_imported_package_is_readonly_and_never_selected_or_saved(self):
        panel, imported = self.make_panel()
        self.assertNotIn(imported.name, panel.vars)
        self.assertNotIn(imported.name, panel.registered_boxes)
        expected = skill_panel.registered_skill_checkbox_label(imported) + '（仅支持安装到桌面端）'
        labels = [w for w in panel.skill_controls if isinstance(w, HintLabel)]
        self.assertEqual([str(w.cget('text')) for w in labels], [expected])
        self.assertEqual(labels[0]._skill_full_name, expected)
        self.assertEqual(labels[0].winfo_manager(), 'grid')
        self.assertEqual(panel.check_all_skills(True), ['ordinary-skill'])
        self.assertEqual([item.name for item in panel.selected_skill_items()], ['ordinary-skill'])
        self.assertEqual(stage_config.get(self.desktop.root, 'script', registry=panel.registry)['skills'],
                         ['ordinary-skill'])
        self.assertEqual(panel.check_all_skills(False), [])
        with mock.patch.object(skill_panel, 'confirm') as confirm, mock.patch.object(skill_panel, 'notify'):
            panel.delete_checked_skills()
            confirm.assert_not_called()
        self.assertTrue(imported.path.is_file())

    def test_load_removes_old_imported_selection_without_changing_other_settings(self):
        panel, imported = self.make_panel(existing=True)
        entry = stage_config.get(self.desktop.root, 'script', registry=panel.registry)
        self.assertEqual(entry['skills'], ['ordinary-skill'])
        self.assertEqual(entry['model'], 'qwen-max')
        self.assertFalse(entry[stage_config.HOLLMWOOD_ENABLED])
        self.assertNotIn(imported.name, panel.selected())

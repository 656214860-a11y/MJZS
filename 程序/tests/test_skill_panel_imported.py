"""外部 SKILL 包可勾选且保留阶段选择。"""
import tkinter as tk
import unittest
from unittest import mock

import skill_panel
import skill_registry
import stage_config
import test_skills


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
                             writer_style='参考好莱坞编剧')
        with mock.patch.object(skill_registry, 'default_registry', return_value=registry):
            panel = skill_panel.Panel(self.win, self.desktop, 'script')
        self.addCleanup(panel.destroy)
        return panel, imported

    def test_imported_package_can_be_selected_and_saved(self):
        panel, imported = self.make_panel()
        self.assertIn(imported.name, panel.vars)
        self.assertIn(imported.name, panel.registered_boxes)
        box = panel.registered_boxes[imported.name]
        self.assertEqual(str(box.cget('text')), skill_panel.registered_skill_checkbox_label(imported))
        self.assertIs(box.master, panel.flow_skill_row)
        expected = {'ordinary-skill', imported.name}
        self.assertEqual(set(panel.check_all_skills(True)), expected)
        self.assertEqual({item.name for item in panel.selected_skill_items()}, expected)
        self.assertEqual(set(stage_config.get(self.desktop.root, 'script', registry=panel.registry)['skills']), expected)
        self.assertEqual(panel.check_all_skills(False), [])

    def test_load_preserves_imported_selection_and_other_settings(self):
        panel, imported = self.make_panel(existing=True)
        entry = stage_config.get(self.desktop.root, 'script', registry=panel.registry)
        self.assertEqual(set(entry['skills']), {'ordinary-skill', imported.name})
        self.assertEqual(entry['model'], 'qwen-max')
        self.assertEqual(entry[stage_config.WRITER_STYLE], '参考好莱坞编剧')
        self.assertIn(imported.name, panel.selected())

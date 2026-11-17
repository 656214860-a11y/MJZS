# -*- coding: utf-8 -*-
"""R3006 T1：SKILL 体检（注册表 problems/warnings 上屏＋发送前引用闭包干跑）与用户层根目录迁移对称。

体检服务在 ``workflow_settings.skill_health_report``：只读、``strict``＋``depth=-1``
与 ``freeze_skills`` 同口径干跑，不发送、不落盘；面板「体检」入口列问题并可点开闭包表。
"""
import shutil
import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from tkinter import ttk
from unittest import mock

import skill_panel
import skill_registry
import workflow_settings
from contract.workflow_context_budget import REQUEST_CONTEXT_MAX_CHARS
from test_skills import PanelTests, write_skill

STAGE_DIR = '01剧本准备SKILL'
ASSET_DIR = '05资产管理SKILL'


class HealthCase(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name)
        self.builtin = self.base / 'program' / 'skills'
        self.user = self.base / 'program' / 'data' / 'skills'
        (self.builtin / STAGE_DIR).mkdir(parents=True)
        (self.user / STAGE_DIR).mkdir(parents=True)
        self.roots = (self.builtin.resolve(), self.user.resolve())

    def registry(self):
        return skill_registry.Registry(self.builtin, user_root=self.user).scan(force=True)

    def report(self, registry=None, **kwargs):
        # 干跑引用解析走 skill_registry.skill_roots()；自检临时目录下钉到临时两层根。
        with mock.patch.object(skill_registry, 'skill_roots', lambda program=None: self.roots):
            return workflow_settings.skill_health_report(registry or self.registry(), **kwargs)


class HealthReportTests(HealthCase):
    def test_rows_partition_problems_and_preview_closure(self):
        good = write_skill(self.builtin / STAGE_DIR, 'good-skill', stage='剧本准备')
        good.write_text(good.read_text(encoding='utf-8') + '\n见 [说明](notes.md)\n', encoding='utf-8')
        (self.builtin / STAGE_DIR / 'notes.md').write_text('# 说明\n细则', encoding='utf-8')
        missing = write_skill(self.builtin / STAGE_DIR, 'missing-field', stage='剧本准备')
        missing.write_text(missing.read_text(encoding='utf-8').replace('constraints: [自检]\n', ''),
                           encoding='utf-8')
        broken = write_skill(self.builtin / STAGE_DIR, 'broken-ref', stage='剧本准备')
        broken.write_text(broken.read_text(encoding='utf-8') + '\n见 [缺失](missing.md)\n', encoding='utf-8')
        outside = write_skill(self.builtin / STAGE_DIR, 'outside-ref', stage='剧本准备')
        outside.write_text(outside.read_text(encoding='utf-8') + '\n见 [越界](../../outside.md)\n',
                           encoding='utf-8')

        report = self.report()
        rows = {row['name']: row for row in report['skills']}
        self.assertEqual(set(rows), {'good-skill', 'missing-field', 'broken-ref', 'outside-ref'})

        good_row = rows['good-skill']
        self.assertEqual(good_row['status'], 'ok')
        self.assertGreater(good_row['chars'], 0)
        self.assertEqual(good_row['char_limit'], REQUEST_CONTEXT_MAX_CHARS)
        self.assertTrue(any(row['status'] == 'inlined' and row['target'].endswith('notes.md')
                            for row in good_row['closure']))
        self.assertEqual({key for row in good_row['closure'] for key in row},
                         {'kind', 'status', 'target', 'depth', 'path'})

        field_row = rows['missing-field']
        self.assertTrue(any('缺字段 constraints' in item for item in field_row['problems']))
        self.assertEqual(field_row['status'], 'problem')

        broken_row = rows['broken-ref']
        self.assertIsNotNone(broken_row['error'])
        self.assertIn('引用缺失', broken_row['error'])
        self.assertEqual(broken_row['status'], 'error')
        self.assertTrue(any(row['status'] == 'missing' for row in broken_row['closure']))

        outside_row = rows['outside-ref']
        self.assertIsNotNone(outside_row['error'])
        self.assertIn('超出允许目录', outside_row['error'])
        self.assertEqual(outside_row['status'], 'error')

    def test_user_layer_rows_shadow_warning_and_stage_filter(self):
        write_skill(self.builtin / STAGE_DIR, 'lead', display='内置版')
        write_skill(self.user / STAGE_DIR, 'lead', display='用户版')
        write_skill(self.user / STAGE_DIR, 'user-only', display='用户独有')
        (self.builtin / ASSET_DIR).mkdir()
        write_skill(self.builtin / ASSET_DIR, 'asset-skill', stage='资产管理')

        report = self.report(stage='script')
        rows = {row['name']: row for row in report['skills']}
        self.assertEqual(set(rows), {'lead', 'user-only'})
        self.assertEqual(rows['lead']['layer'], 'user')
        self.assertTrue(any('覆盖内置版' in item for item in rows['lead']['warnings']))
        self.assertEqual(rows['user-only']['layer'], 'user')
        self.assertEqual(rows['user-only']['status'], 'ok')

        all_rows = {row['name'] for row in self.report()['skills']}
        self.assertIn('asset-skill', all_rows)

    def test_unattributable_lines_become_global_problems(self):
        write_skill(self.builtin / STAGE_DIR, 'script-skill', stage='剧本准备')
        (self.builtin / STAGE_DIR / 'broken.skill.md').write_text('没有 frontmatter', encoding='utf-8')

        report = self.report(stage='script')
        self.assertEqual([row['name'] for row in report['skills']], ['script-skill'])
        self.assertTrue(any('没有 name' in item for item in report['problems']))
        self.assertFalse(any('没有 name' in item for row in report['skills'] for item in row['problems']))


class UserRootMigrationTests(HealthCase):
    def test_user_root_manifest_moves_into_existing_user_stage_dir(self):
        legacy = write_skill(self.user, 'legacy-user', stage='剧本准备')
        registry = self.registry()
        skill = registry.getById('legacy-user')
        self.assertIsNotNone(skill)
        self.assertEqual(skill.layer, 'user')
        expected = self.user / STAGE_DIR / legacy.name
        self.assertEqual(skill.path, expected)
        self.assertFalse(legacy.exists())
        self.assertTrue(expected.is_file())

    def test_user_root_manifest_creates_missing_stage_dir(self):
        shutil.rmtree(self.user / STAGE_DIR)
        legacy = write_skill(self.user, 'legacy-user', stage='剧本准备')
        skill = self.registry().getById('legacy-user')
        self.assertIsNotNone(skill)
        expected = self.user / STAGE_DIR / legacy.name
        self.assertEqual(skill.path, expected)
        self.assertTrue(expected.is_file())
        self.assertFalse(legacy.exists())

    def test_unstageable_user_root_manifest_is_reported_and_left_in_place(self):
        bad = write_skill(self.user, 'no-stage', stage='不存在的阶段')
        registry = self.registry()
        self.assertIsNone(registry.getById('no-stage'))
        self.assertTrue(bad.exists())
        self.assertTrue(any('没有可识别的阶段' in item for item in registry.problems()))

    def test_builtin_root_manifest_migration_unchanged(self):
        legacy = write_skill(self.builtin, 'legacy-builtin', stage='剧本准备')
        skill = self.registry().getById('legacy-builtin')
        self.assertEqual(skill.layer, 'builtin')
        self.assertEqual(skill.path, self.builtin / STAGE_DIR / legacy.name)
        self.assertFalse(legacy.exists())


class PanelHealthTests(unittest.TestCase):
    tk = tk
    setUp = PanelTests.setUp

    def make_panel(self):
        stage_dir = self.desktop.app / 'skills' / STAGE_DIR
        broken = write_skill(stage_dir, 'broken-skill', stage='剧本准备')
        broken.write_text(broken.read_text(encoding='utf-8').replace('constraints: [自检]\n', ''),
                          encoding='utf-8')
        registry = skill_registry.Registry(root=self.desktop.app / 'skills')
        with mock.patch.object(skill_registry, 'default_registry', return_value=registry):
            panel = skill_panel.Panel(self.win, self.desktop, 'script')
        self.addCleanup(panel.destroy)
        return panel, registry

    def _widget_texts(self, widget):
        texts = []
        stack = [widget]
        while stack:
            item = stack.pop()
            try:
                if isinstance(item, tk.Text):
                    texts.append(item.get('1.0', 'end'))
                elif isinstance(item, tk.Listbox):
                    texts.extend(item.get(0, 'end'))
                elif isinstance(item, ttk.Treeview):
                    for node in item.get_children():
                        texts.extend(str(value) for value in item.item(node, 'values'))
                else:
                    texts.append(str(item.cget('text')))
            except Exception:
                pass
            stack.extend(item.winfo_children())
        return '\n'.join(texts)

    def test_manage_menu_offers_health_check(self):
        panel, _registry = self.make_panel()
        self.assertIn('体检', skill_panel.MANAGE_LABELS)

    def test_health_dialog_lists_problems_without_sending(self):
        panel, registry = self.make_panel()
        roots = (registry.root.resolve(),
                 (self.desktop.app / 'data' / 'skills').resolve())
        panel.skill_action.set('体检')
        with mock.patch.object(skill_registry, 'skill_roots', lambda program=None: roots):
            window = panel.choose_skill_action()
        self.assertIsNotNone(window)
        self.addCleanup(window.destroy)
        blob = self._widget_texts(window)
        self.assertIn('broken-skill', blob)
        self.assertIn('缺字段', blob)


if __name__ == '__main__':
    unittest.main()

"""Codex 技能同步的幂等、所有权和引用契约（只使用临时安装目录）。"""
from tests.architecture._scan import desktop_text  # R1490：Desktop 方法分布在 desktop.py 与迁出的 Mixin 模块
import os
import ast
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import codex_skill_sync as sync
from test_skills import write_skill


class CodexSkillSyncTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.program = self.base / 'program'
        self.home = self.base / 'codex' / 'skills'
        self.source = write_skill(self.program / 'skills' / '01 剧本准备SKILL', 'pipeline-script-preparation')

    def run_sync(self):
        return sync.sync_codex_skills(self.program, self.home)

    def test_materializes_only_codex_frontmatter_and_rewrites_reference(self):
        with self.source.open('a', encoding='utf-8') as stream:
            stream.write('\n[规则](../00全流程SKILL/reference.md)\n')
        result = self.run_sync()
        self.assertEqual(result['written'], ['pipeline-script-preparation'])
        target = self.home / 'pipeline-script-preparation' / 'SKILL.md'
        meta, body = sync.parse(target.read_text(encoding='utf-8'))
        self.assertEqual(set(meta), {'name', 'description'})
        self.assertIn((self.program / 'skills' / '00全流程SKILL').as_posix(), body)
        self.assertNotIn('../00全流程SKILL/', body)
        before = target.stat().st_mtime_ns
        self.assertEqual(self.run_sync()['unchanged'], ['pipeline-script-preparation'])
        self.assertEqual(target.stat().st_mtime_ns, before)

    def test_orphan_is_recycled_not_deleted(self):
        self.run_sync()
        self.source.unlink()
        result = self.run_sync()
        self.assertEqual(result['recycled'], ['pipeline-script-preparation'])
        self.assertFalse((self.home / 'pipeline-script-preparation').exists())
        self.assertTrue(list(self.home.rglob('恢复位置.json')))

    def test_manual_skill_is_not_overwritten(self):
        target = self.home / 'pipeline-script-preparation' / 'SKILL.md'
        target.parent.mkdir(parents=True)
        target.write_text('hand written', encoding='utf-8')
        self.assertEqual(self.run_sync()['conflicts'], ['pipeline-script-preparation'])
        self.assertEqual(target.read_text(encoding='utf-8'), 'hand written')

    def test_modified_or_extra_files_protect_orphan(self):
        self.run_sync()
        directory = self.home / 'pipeline-script-preparation'
        (directory / 'notes.md').write_text('mine', encoding='utf-8')
        self.source.unlink()
        self.assertEqual(self.run_sync()['conflicts'], ['pipeline-script-preparation'])
        self.assertTrue(directory.exists())

    def test_changed_source_updates_but_user_edit_is_preserved(self):
        self.run_sync()
        target = self.home / 'pipeline-script-preparation' / 'SKILL.md'
        self.source.write_text(self.source.read_text(encoding='utf-8') + '\nnew body', encoding='utf-8')
        self.assertEqual(self.run_sync()['written'], ['pipeline-script-preparation'])
        self.assertIn('new body', target.read_text(encoding='utf-8'))
        target.write_text('user edit', encoding='utf-8')
        self.assertEqual(self.run_sync()['conflicts'], ['pipeline-script-preparation'])
        self.assertEqual(target.read_text(encoding='utf-8'), 'user edit')

    def test_codex_home_is_honored(self):
        with patch.dict(os.environ, {'CODEX_HOME': str(self.home.parent)}):
            self.assertEqual(sync.sync_codex_skills(self.program)['written'], ['pipeline-script-preparation'])

    def test_inventory_error_does_not_recycle(self):
        self.run_sync()
        self.source.unlink()
        broken = self.source.with_name('broken.skill.md')
        broken.write_text('---\nname: ../escape\n---\n', encoding='utf-8')
        result = self.run_sync()
        self.assertTrue(result['errors'])
        self.assertTrue((self.home / 'pipeline-script-preparation').exists())

    def test_later_registered_stage_is_not_truncated_to_twelve(self):
        write_skill(self.program / 'skills' / '13 质检交付SKILL', 'delivery-check', stage='质检交付')
        self.assertIn('delivery-check', self.run_sync()['written'])

    def test_different_installation_cannot_take_over_skill(self):
        self.run_sync()
        other = self.base / 'other'
        write_skill(other / 'skills' / '01 剧本准备SKILL', 'pipeline-script-preparation')
        self.assertEqual(sync.sync_codex_skills(other, self.home)['conflicts'],
                         ['pipeline-script-preparation'])

    def test_repair_missing_generated_file(self):
        self.run_sync()
        (self.home / 'pipeline-script-preparation' / 'SKILL.md').unlink()
        self.assertEqual(self.run_sync()['written'], ['pipeline-script-preparation'])

    def test_startup_is_background_and_dispatch_sync_precedes_prompt(self):
        with patch.object(sync.threading, 'Thread') as thread:
            sync.start_codex_skill_sync(self.program)
            self.assertIs(thread.call_args.kwargs['target'], sync.sync_codex_skills)
            thread.return_value.start.assert_called_once()
        tree = ast.parse(desktop_text())
        # open_flow_agent 已改写成 _FlowAgentLaunch，工作线程里的构建步骤是 prepare；
        # 改写后 prompt_with_settings 以 self.prompt_with_settings 调用，属性调用一并收集。
        dispatch = next(n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)
                        and n.name == '_FlowAgentLaunch')
        build = next(n for n in ast.walk(dispatch) if isinstance(n, ast.FunctionDef) and n.name == 'prepare')
        calls = [(n.func.id if isinstance(n.func, ast.Name) else n.func.attr, n.lineno) for n in ast.walk(build)
                 if isinstance(n, ast.Call) and isinstance(n.func, (ast.Name, ast.Attribute))]
        self.assertTrue(any(name == 'prompt_with_settings' for name, _ in calls))
        sync_line = next(line for name, line in calls if name == 'sync_codex_skills')
        self.assertTrue(all(line > sync_line for name, line in calls if name == 'prompt_with_settings'))


if __name__ == '__main__':
    unittest.main()

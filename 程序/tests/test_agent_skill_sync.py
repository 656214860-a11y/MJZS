"""Agent 技能同步的幂等、所有权和引用契约（只使用临时安装目录）。"""
from tests.architecture._scan import desktop_text  # R1490：Desktop 方法分布在 desktop.py 与迁出的 Mixin 模块
import json
import os
import ast
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from orchestrator import agent_skill_sync as sync
from orchestrator import codex_skill_sync as codex_sync
from test_skills import write_skill


class AgentSkillSyncTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.program = self.base / 'program'
        self.source = write_skill(self.program / 'skills' / '01 剧本准备SKILL', 'pipeline-script-preparation')

    def home(self, target):
        return self.base / target / 'skills'

    def run_sync(self, target='codex', home=None):
        return sync.sync_agent_skills(self.program, target, home or self.home(target))

    def test_materializes_only_agent_frontmatter_and_rewrites_reference(self):
        for target in sync.TARGETS:
            with self.subTest(target=target):
                home = self.home(target)
                with self.source.open('a', encoding='utf-8') as stream:
                    stream.write('\n[规则](../00全流程SKILL/reference.md)\n')
                result = self.run_sync(target, home)
                self.assertEqual(result['written'], ['pipeline-script-preparation'])
                target_file = home / 'pipeline-script-preparation' / 'SKILL.md'
                meta, body = sync.parse(target_file.read_text(encoding='utf-8'))
                self.assertEqual(set(meta), {'name', 'description'})
                self.assertIn((self.program / 'skills' / '00全流程SKILL').as_posix(), body)
                self.assertNotIn('../00全流程SKILL/', body)
                marker = json.loads((home / 'pipeline-script-preparation' / sync._MARKER
                                     ).read_text(encoding='utf-8'))
                self.assertEqual(marker['target'], target)
                before = target_file.stat().st_mtime_ns
                self.assertEqual(self.run_sync(target, home)['unchanged'],
                                 ['pipeline-script-preparation'])
                self.assertEqual(target_file.stat().st_mtime_ns, before)

    def test_orphan_is_recycled_not_deleted(self):
        for target in sync.TARGETS:
            with self.subTest(target=target):
                home = self.home(target)
                self.run_sync(target, home)
                directory = home / 'pipeline-script-preparation'
                self.source.unlink()
                result = self.run_sync(target, home)
                self.assertEqual(result['recycled'], ['pipeline-script-preparation'])
                self.assertFalse(directory.exists())
                self.assertTrue(list(home.rglob('恢复位置.json')))
                self.source = write_skill(self.program / 'skills' / '01 剧本准备SKILL',
                                          'pipeline-script-preparation')

    def test_manual_skill_is_not_overwritten(self):
        home = self.home('claude')
        target_file = home / 'pipeline-script-preparation' / 'SKILL.md'
        target_file.parent.mkdir(parents=True)
        target_file.write_text('hand written', encoding='utf-8')
        self.assertEqual(self.run_sync('claude', home)['conflicts'],
                         ['pipeline-script-preparation'])
        self.assertEqual(target_file.read_text(encoding='utf-8'), 'hand written')

    def test_modified_or_extra_files_protect_orphan(self):
        home = self.home('agents')
        self.run_sync('agents', home)
        directory = home / 'pipeline-script-preparation'
        (directory / 'notes.md').write_text('mine', encoding='utf-8')
        self.source.unlink()
        self.assertEqual(self.run_sync('agents', home)['conflicts'],
                         ['pipeline-script-preparation'])
        self.assertTrue(directory.exists())

    def test_changed_source_updates_but_user_edit_is_preserved(self):
        home = self.home('codex')
        self.run_sync('codex', home)
        target_file = home / 'pipeline-script-preparation' / 'SKILL.md'
        self.source.write_text(self.source.read_text(encoding='utf-8') + '\nnew body',
                               encoding='utf-8')
        self.assertEqual(self.run_sync('codex', home)['written'],
                         ['pipeline-script-preparation'])
        self.assertIn('new body', target_file.read_text(encoding='utf-8'))
        target_file.write_text('user edit', encoding='utf-8')
        self.assertEqual(self.run_sync('codex', home)['conflicts'],
                         ['pipeline-script-preparation'])
        self.assertEqual(target_file.read_text(encoding='utf-8'), 'user edit')

    def test_targets_are_isolated_same_skill_home(self):
        # 同一目标目录被两个 target 指向时，marker target 字段互不接管：
        # codex 写入的目录对 agents 目标是「非本目标所有」，报冲突而不被回收。
        home = self.home('shared')
        self.assertEqual(self.run_sync('codex', home)['written'],
                         ['pipeline-script-preparation'])
        result = self.run_sync('agents', home)
        self.assertEqual(result['conflicts'], ['pipeline-script-preparation'])
        self.assertTrue((home / 'pipeline-script-preparation' / 'SKILL.md').is_file())

    def test_legacy_marker_without_target_belongs_to_codex(self):
        home = self.home('codex')
        self.run_sync('codex', home)
        marker = home / 'pipeline-script-preparation' / sync._MARKER
        data = json.loads(marker.read_text(encoding='utf-8'))
        data.pop('target')
        marker.write_text(json.dumps(data), encoding='utf-8')
        # 旧 marker 仍视为 codex 所有：首次同步补写 target 字段，之后幂等；
        # 对 agents 目标同目录则冲突。
        self.assertEqual(self.run_sync('codex', home)['written'],
                         ['pipeline-script-preparation'])
        self.assertEqual(json.loads(marker.read_text(encoding='utf-8'))['target'], 'codex')
        self.assertEqual(self.run_sync('codex', home)['unchanged'],
                         ['pipeline-script-preparation'])
        self.assertEqual(self.run_sync('agents', home)['conflicts'],
                         ['pipeline-script-preparation'])

    def test_codex_home_is_honored(self):
        with patch.dict(os.environ, {'CODEX_HOME': str(self.home('codex').parent)}):
            self.assertEqual(sync.sync_agent_skills(self.program, 'codex')['written'],
                             ['pipeline-script-preparation'])

    def test_default_home_resolution(self):
        self.assertEqual(sync._default_home('codex'),
                         Path(os.environ.get('CODEX_HOME') or Path.home() / '.codex') / 'skills')
        self.assertEqual(sync._default_home('claude'), Path.home() / '.claude' / 'skills')
        self.assertEqual(sync._default_home('agents'), Path.home() / '.agents' / 'skills')

    def test_engine_targets_cover_launch_engines(self):
        self.assertEqual(sync.ENGINE_TARGETS['codex'], ('codex', 'agents'))
        self.assertEqual(sync.ENGINE_TARGETS['claude'], ('claude',))
        self.assertNotIn('qwen', sync.ENGINE_TARGETS)

    def test_sync_all_isolates_target_failures(self):
        homes = {'codex': self.home('codex'), 'claude': self.home('claude'),
                 'agents': self.home('agents')}
        reports = sync.sync_all_agent_skills(self.program, homes)
        for target in sync.TARGETS:
            self.assertEqual(reports[target]['written'], ['pipeline-script-preparation'])
        # claude 目标目录是普通文件 → mkdir 失败只进该目标 errors，agents 照常写入。
        blocked = self.base / 'blocked'
        blocked.write_text('not a dir', encoding='utf-8')
        reports = sync.sync_all_agent_skills(
            self.program, {'codex': self.home('codex'), 'claude': blocked / 'skills',
                           'agents': self.home('agents')},
            targets=('claude', 'agents'))
        self.assertTrue(reports['claude']['errors'])
        self.assertEqual(reports['agents']['unchanged'], ['pipeline-script-preparation'])

    def test_inventory_error_does_not_recycle(self):
        home = self.home('claude')
        self.run_sync('claude', home)
        self.source.unlink()
        broken = self.source.with_name('broken.skill.md')
        broken.write_text('---\nname: ../escape\n---\n', encoding='utf-8')
        result = self.run_sync('claude', home)
        self.assertTrue(result['errors'])
        self.assertTrue((home / 'pipeline-script-preparation').exists())

    def test_later_registered_stage_is_not_truncated_to_twelve(self):
        write_skill(self.program / 'skills' / '13 质检交付SKILL', 'delivery-check', stage='质检交付')
        self.assertIn('delivery-check', self.run_sync('agents', self.home('agents'))['written'])

    def test_different_installation_cannot_take_over_skill(self):
        home = self.home('codex')
        self.run_sync('codex', home)
        other = self.base / 'other'
        write_skill(other / 'skills' / '01 剧本准备SKILL', 'pipeline-script-preparation')
        self.assertEqual(sync.sync_agent_skills(other, 'codex', home)['conflicts'],
                         ['pipeline-script-preparation'])

    def test_repair_missing_generated_file(self):
        home = self.home('agents')
        self.run_sync('agents', home)
        (home / 'pipeline-script-preparation' / 'SKILL.md').unlink()
        self.assertEqual(self.run_sync('agents', home)['written'],
                         ['pipeline-script-preparation'])

    def test_startup_is_background_and_dispatch_sync_precedes_prompt(self):
        with patch.object(sync.threading, 'Thread') as thread:
            sync.start_agent_skill_sync(self.program)
            self.assertIs(thread.call_args.kwargs['target'], sync._all_entry)
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
        sync_line = next(line for name, line in calls if name == 'sync_agent_skills')
        self.assertTrue(all(line > sync_line for name, line in calls if name == 'prompt_with_settings'))


class CodexCompatTests(unittest.TestCase):
    """codex_skill_sync 兼容层：旧签名与 patch 面保持不变。"""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.program = self.base / 'program'
        self.home = self.base / 'codex' / 'skills'
        self.source = write_skill(self.program / 'skills' / '01 剧本准备SKILL',
                                  'pipeline-script-preparation')

    def test_sync_codex_skills_delegates_to_codex_target(self):
        result = codex_sync.sync_codex_skills(self.program, self.home)
        self.assertEqual(result['written'], ['pipeline-script-preparation'])
        marker = json.loads((self.home / 'pipeline-script-preparation' / sync._MARKER
                             ).read_text(encoding='utf-8'))
        self.assertEqual(marker['target'], 'codex')

    def test_start_codex_skill_sync_runs_before_then_sync(self):
        calls = []
        with unittest.mock.patch.object(codex_sync.threading, 'Thread') as thread, \
                unittest.mock.patch.object(codex_sync, 'sync_codex_skills',
                                           side_effect=lambda **kw: calls.append('sync')):
            codex_sync.start_codex_skill_sync(self.program, before=lambda: calls.append('migrate'))
            kwargs = thread.call_args.kwargs
            kwargs['target'](**kwargs['kwargs'])
        self.assertEqual(calls, ['migrate', 'sync'])


if __name__ == '__main__':
    unittest.main()

# -*- coding: utf-8 -*-
"""统筹迁移工具只读报告与幂等回写的回归。"""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock


HERE = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('workflow_migration', HERE / 'scripts' / 'migrate_workflow_presets.py')
migration = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(migration)


class WorkflowMigrationTests(unittest.TestCase):
    def test_path_based_legacy_skill_is_resolved_and_apply_is_idempotent(self):
        with tempfile.TemporaryDirectory() as folder:
            project = Path(folder)
            legacy_path = project / 'legacy' / 'pipeline.md'
            legacy_path.parent.mkdir()
            legacy_path.write_text('x', encoding='utf-8')
            (project / '工作流任务').mkdir()
            (project / '工作流任务' / '工作流调用设置.json').write_text(
                json.dumps({'flows': {'writing': {'profiles': {'codex': {'skills': [str(legacy_path)]}}}}}),
                encoding='utf-8')
            (project / 'skill_config.json').write_text(json.dumps({
                'custom': {'untouched': True},
                'script': {'model': 'auto', 'skills': []},
                'storyboard': {'model': 'auto', 'skills': ['user-choice']},
            }), encoding='utf-8')

            class Skill:
                name = 'pipeline-script-preparation'
                path = legacy_path
                deprecated = False
            class Registry:
                def getAll(self): return [Skill()]
                def getById(self, value): return Skill() if value == Skill.name else None
                def canonical_id(self, value): return value
                def getByStage(self, stage): return []

            with mock.patch('skill_registry.default_registry', return_value=Registry()):
                self.assertEqual(migration.legacy_skill_ids(project), {Skill.name})
                self.assertEqual(migration.candidate(project)[:2], ('AIGC全流程', 1))
                self.assertTrue(migration.apply(project))
                saved = json.loads((project / 'skill_config.json').read_text(encoding='utf-8'))
                self.assertEqual(saved['custom'], {'untouched': True})
                self.assertIn(Skill.name, saved['script']['skills'])
                self.assertEqual(saved['storyboard']['skills'], ['user-choice'])
                self.assertEqual(saved['workflow']['name'], 'AIGC全流程')
                timestamp = (project / 'skill_config.json').stat().st_mtime_ns
                self.assertFalse(migration.apply(project))
                self.assertEqual((project / 'skill_config.json').stat().st_mtime_ns, timestamp)

    def test_markdown_report_contains_required_fields(self):
        text = migration.markdown_report([{'project': 'P', 'candidate': 'AIGC全流程', 'coverage': '1/2',
                                           'differences': {'script': {'current': [], 'suggested': ['a']}},
                                           'missing_locks': ['画幅']}])
        for value in ('推断统筹候选', '阶段勾选与展开表差异', '锁值缺项', '本报告只读'):
            self.assertIn(value, text)

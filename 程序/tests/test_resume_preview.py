# -*- coding: utf-8 -*-
"""O43 恢复预览自检：检查点版本／项目／步骤摘要核对、工具完成与成果完成分开、只读。

运行：python run_selftests.py -k resume_preview
"""
import json, os, sys, tempfile, unittest
from pathlib import Path
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
PROGRAM = os.path.dirname(HERE)
sys.path.insert(0, PROGRAM)
sys.path.insert(0, HERE)
os.chdir(PROGRAM)

import skill_orchestrator


def orchestrator(case):
    holder = tempfile.TemporaryDirectory()
    case.addCleanup(holder.cleanup)
    return skill_orchestrator.default_orchestrator(project=holder.name)


def steps_of(orch, stage_id):
    return list(orch._template_steps(stage_id) or orch.registry.getByStage(stage_id))


def step_name_at(orch, stage_id, index):
    item = steps_of(orch, stage_id)[index - 1]
    return str(getattr(item, 'name', None) or getattr(item, 'displayName', '') or '')


def seed(case, orch, stage_id, index, skills=None):
    """按现在的模板／注册表写一份「对得上」的检查点，返回步骤名。"""
    name = step_name_at(orch, stage_id, index)
    stage = type('Stage', (), {'id': stage_id})()
    step = type('Step', (), {'index': index, 'name': name})()
    orch.before_step(stage, step, skills)
    return name


class ResumePreviewTests(unittest.TestCase):
    def test_no_checkpoint_means_a_fresh_start(self):
        orch = orchestrator(self)
        preview = orch.resume_preview()
        self.assertFalse(preview['found'])
        self.assertEqual(preview['steps'], [])
        self.assertIn('从头开始', preview['text'])

    def test_fresh_checkpoint_continues_and_separates_tools_from_artifacts(self):
        orch = orchestrator(self)
        seed(self, orch, 'assets', 3, ['asset-visual-rank', 'asset-dedupe'])
        preview = orch.resume_preview()
        self.assertTrue(preview['found'])
        self.assertEqual(preview['stage'], 'assets')
        self.assertEqual(preview['step'], 3)
        self.assertTrue(preview['version_ok'])
        self.assertTrue(preview['project_ok'])
        self.assertTrue(preview['digest_ok'])
        self.assertEqual(preview['skills'], ['asset-visual-rank', 'asset-dedupe'])
        self.assertEqual(preview['tools_done'], [1, 2])
        self.assertFalse(preview['artifact_verified'])
        self.assertIn('工具调用完成，不等于成果已采用', preview['steps'][0]['reason'])
        self.assertEqual(preview['steps'][2]['verdict'], 'continue')
        self.assertIn('尚未确认阶段成果', preview['text'])
        self.assertEqual(preview['continue_count'] + preview['skip_count'] + preview['verify_count'],
                         preview['total_steps'])

    def test_old_format_checkpoint_needs_human_verification(self):
        orch = orchestrator(self)
        orch.status['checkpoint'] = {'stage': 'assets', 'step': 3, 'step_name': step_name_at(orch, 'assets', 3)}
        preview = orch.resume_preview()
        self.assertFalse(preview['version_ok'])
        self.assertIsNone(preview['version'])
        self.assertEqual(preview['steps'][2]['verdict'], 'verify')
        self.assertIn('旧版格式', preview['text'])
        self.assertEqual(preview['verify_count'], 1)

    def test_checkpoint_from_another_project_needs_human_verification(self):
        orch = orchestrator(self)
        name = step_name_at(orch, 'assets', 3)
        orch.status['checkpoint'] = {
            'stage': 'assets', 'step': 3, 'step_name': name,
            'version': skill_orchestrator.CHECKPOINT_VERSION, 'project': '/另一个/项目',
            'digest': skill_orchestrator.checkpoint_digest('assets', 3, name)}
        preview = orch.resume_preview()
        self.assertTrue(preview['version_ok'])
        self.assertFalse(preview['project_ok'])
        self.assertEqual(preview['steps'][2]['verdict'], 'verify')
        self.assertIn('不一致', preview['text'])

    def test_changed_step_identity_needs_human_verification(self):
        orch = orchestrator(self)
        name = step_name_at(orch, 'assets', 3)
        orch.status['checkpoint'] = {
            'stage': 'assets', 'step': 3, 'step_name': name,
            'version': skill_orchestrator.CHECKPOINT_VERSION, 'project': str(orch.project),
            'digest': 'deadbeef'}
        preview = orch.resume_preview()
        self.assertTrue(preview['version_ok'])
        self.assertTrue(preview['project_ok'])
        self.assertFalse(preview['digest_ok'])
        self.assertEqual(preview['steps'][2]['verdict'], 'verify')
        self.assertIn('对不上', preview['text'])

    def test_out_of_range_step_needs_human_verification(self):
        orch = orchestrator(self)
        orch.status['checkpoint'] = {'stage': 'assets', 'step': 99, 'step_name': '不存在的一步',
                                     'version': skill_orchestrator.CHECKPOINT_VERSION,
                                     'project': str(orch.project), 'digest': 'x'}
        preview = orch.resume_preview()
        self.assertFalse(preview['scope_ok'])
        self.assertGreaterEqual(preview['verify_count'], 1)

    def test_verified_artifact_skips_the_rest_without_repaying(self):
        orch = orchestrator(self)
        seed(self, orch, 'assets', 3)
        with mock.patch('skill_orchestrator.verified_stage_output', return_value=True):
            preview = orch.resume_preview()
        self.assertTrue(preview['artifact_verified'])
        self.assertEqual(preview['steps'][2]['verdict'], 'skip')
        self.assertEqual(preview['steps'][3]['verdict'], 'skip')
        self.assertIn('不重复付费、不重复发布', preview['text'])
        self.assertIn('阶段成果完成', preview['text'])

    def test_paid_steps_are_listed_and_only_continue_is_resubmitted(self):
        orch = orchestrator(self)
        paid = next(item for item in orch.registry.getAll() if getattr(item, 'paid', False))
        seed(self, orch, paid.stage, 1)
        preview = orch.resume_preview()
        self.assertIn(paid.name, preview['paid'])
        self.assertIn('付费步骤', preview['text'])
        self.assertIn('只有标「续做」的才会重新提交', preview['text'])

    def test_preview_is_read_only(self):
        orch = orchestrator(self)
        seed(self, orch, 'assets', 3)
        path = Path(orch.project) / 'sanhu_project_status.json'
        before_status = json.loads(path.read_text(encoding='utf-8'))
        before_bytes = path.read_bytes()
        orch.resume_preview()
        self.assertEqual(orch.status['checkpoint'], before_status['checkpoint'])
        self.assertEqual(path.read_bytes(), before_bytes)

    def test_checkpoint_failure_blocks_the_paid_action(self):
        orch = orchestrator(self)
        paid = next(item for item in orch.registry.getAll() if getattr(item, 'paid', False))
        spent = []
        with mock.patch.object(orch.budget, 'check', return_value=(True, '')), \
             mock.patch.object(orch.budget, 'spend', side_effect=lambda *a, **k: spent.append(a)), \
             mock.patch('skill_orchestrator.save_project_status', side_effect=OSError('磁盘满')):
            row = orch.execute(paid.name, {'project': orch.project, 'confirm': True})
        self.assertEqual(row['status'], 'failed')
        self.assertIn('检查点写入失败', row['detail'])
        self.assertEqual(spent, [])
        self.assertNotIn('checkpoint', orch.status)

    def test_checkpoint_records_version_project_skills_and_digest(self):
        orch = orchestrator(self)
        name = step_name_at(orch, 'assets', 3)
        stage = type('Stage', (), {'id': 'assets'})()
        step = type('Step', (), {'index': 3, 'name': name})()
        checkpoint = orch.before_step(stage, step, ['a', 'b'])
        self.assertEqual(checkpoint['version'], skill_orchestrator.CHECKPOINT_VERSION)
        self.assertEqual(checkpoint['project'], str(orch.project))
        self.assertEqual(checkpoint['skills'], ['a', 'b'])
        self.assertEqual(checkpoint['digest'],
                         skill_orchestrator.checkpoint_digest('assets', 3, name))
        saved = json.loads((Path(orch.project) / 'sanhu_project_status.json').read_text(encoding='utf-8'))
        self.assertEqual(saved['checkpoint'], checkpoint)

    def test_digest_depends_on_stage_step_and_name(self):
        base = skill_orchestrator.checkpoint_digest('assets', 3, '生成缺失的正典板')
        self.assertEqual(base, skill_orchestrator.checkpoint_digest('assets', 3, '生成缺失的正典板'))
        self.assertNotEqual(base, skill_orchestrator.checkpoint_digest('assets', 3, '别的步骤'))
        self.assertNotEqual(base, skill_orchestrator.checkpoint_digest('assets', 4, '生成缺失的正典板'))
        self.assertNotEqual(base, skill_orchestrator.checkpoint_digest('keyframe', 3, '生成缺失的正典板'))


if __name__ == '__main__':
    unittest.main()

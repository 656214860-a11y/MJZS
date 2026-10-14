"""R1433：总控清单、指纹自动同步（保留用户勾选）、体检与手动／自动共用门禁。"""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import master_skill
import stage_config
import stage_handler_registry
import workflow_settings

NAME = 'AIGC全流程'


class ManifestTests(unittest.TestCase):
    def load(self, payload):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / '总控.json'
            if payload is not None:
                path.write_text(payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False),
                                encoding='utf-8')
            saved = (dict(workflow_settings.WORKFLOW_PRESETS), list(workflow_settings.MASTER_MANIFEST_PROBLEMS))
            self.addCleanup(lambda: workflow_settings.refresh_workflow_presets(force=True))
            with mock.patch.object(workflow_settings, 'MASTER_MANIFEST', path):
                presets = dict(workflow_settings.refresh_workflow_presets(force=True))
                problems = list(workflow_settings.MASTER_MANIFEST_PROBLEMS)
        return presets, problems

    def test_shipped_manifest_equals_the_builtin_table(self):
        workflow_settings.refresh_workflow_presets(force=True)
        self.assertEqual(workflow_settings.MASTER_MANIFEST_PROBLEMS, [])
        self.assertEqual(workflow_settings.WORKFLOW_PRESETS, workflow_settings.BUILTIN_WORKFLOW_PRESETS)

    def test_manifest_drives_presets_and_lock_keys_become_definitions(self):
        presets, problems = self.load({'presets': {'自定义': {
            'package': 'skills/x/SKILL.md', 'stage_skills': {'script': ['a', 'b']},
            'locks': ['aspect_ratio', 'nope']}}})
        self.assertEqual(list(presets), ['自定义'])
        self.assertEqual(presets['自定义']['stage_skills'], {'script': ['a', 'b']})
        self.assertEqual([item['key'] for item in presets['自定义']['locks']], ['aspect_ratio'])
        self.assertIn('未登记的制作锁：nope', problems[0])

    def test_missing_or_broken_manifest_falls_back_to_builtin_and_says_so(self):
        for payload in (None, '{不是 JSON', {'presets': {}}):
            with self.subTest(payload=payload):
                presets, problems = self.load(payload)
                self.assertEqual(presets, workflow_settings.BUILTIN_WORKFLOW_PRESETS)
                self.assertTrue(problems[-1].startswith('已改用出厂内置总控'))


class MergeTests(unittest.TestCase):
    def test_replaces_only_master_items_and_keeps_user_choices(self):
        self.assertEqual(master_skill._merge(['m1', 'mine'], ['m1'], ['m2']), ['mine', 'm2'])

    def test_user_unchecked_master_item_is_not_rechecked(self):
        self.assertEqual(master_skill._merge(['m1', 'mine'], ['m1', 'm2'], ['m1', 'm2', 'm3']), ['m1', 'mine', 'm3'])
        self.assertEqual(master_skill._merge(['m1'], ['m1', 'm2'], ['m1', 'm2']), ['m1'])

    def test_stage_that_dropped_all_master_items_is_left_alone(self):
        self.assertEqual(master_skill._merge(['mine'], ['m1'], ['m2']), ['mine'])


class SyncTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.project = Path(temp.name)
        stage_config.put_workflow(self.project, {'name': NAME, 'skill_ref': 'x', 'lock': {}})
        self.presets = copy.deepcopy(workflow_settings.WORKFLOW_PRESETS)
        patcher = mock.patch.dict(workflow_settings.WORKFLOW_PRESETS, self.presets, clear=True)
        patcher.start(); self.addCleanup(patcher.stop)
        refresh = mock.patch.object(workflow_settings, 'refresh_workflow_presets',
                                    return_value=workflow_settings.WORKFLOW_PRESETS)
        refresh.start(); self.addCleanup(refresh.stop)

    def test_first_check_records_a_baseline_without_touching_stages(self):
        before = stage_config.get(self.project, 'script')['skills']
        result = master_skill.sync(self.project)
        self.assertFalse(result['updated'])
        self.assertEqual(stage_config.get(self.project, 'script')['skills'], before)
        applied = stage_config.current_workflow(self.project)['applied']
        self.assertEqual(applied['name'], NAME)
        self.assertEqual(len(applied['fingerprint']), 64)
        self.assertEqual(master_skill.sync(self.project)['message'], '', '指纹没变就什么都不做')

    def test_manifest_change_resyncs_master_items_and_keeps_user_extras(self):
        stage_config.put(self.project, 'script', skills=['pipeline-script-preparation', '短剧编剧搭子'])
        master_skill.sync(self.project)
        workflow_settings.WORKFLOW_PRESETS[NAME]['stage_skills']['script'] = ['script-forging']
        result = master_skill.sync(self.project)
        self.assertTrue(result['updated'])
        self.assertEqual(result['stages'], ['script'])
        self.assertIn('已同步 1 个阶段', result['message'])
        self.assertEqual(stage_config.get(self.project, 'script')['skills'], ['短剧编剧搭子', 'script-forging'])

    def test_content_change_of_a_referenced_file_is_detected(self):
        fake = Path(self.project) / 'skill.skill.md'
        ref = Path(self.project) / 'rule.md'
        ref.write_text('v1', encoding='utf-8')
        fake.write_text('---\nname: x\n---\n# x\n[规则](rule.md)\n', encoding='utf-8')
        registry = SimpleNamespace(getById=lambda sid: SimpleNamespace(path=fake), scan=lambda: None)
        preset = {'package': 'missing', 'stage_skills': {'script': ['x']}}
        first = master_skill.fingerprint(preset, registry)
        ref.write_text('v2', encoding='utf-8')
        self.assertNotEqual(master_skill.fingerprint(preset, registry), first)
        self.assertIn(ref.resolve(), master_skill.watched_files(preset, registry))

    def test_health_reports_unregistered_skill_and_missing_package(self):
        problems = master_skill.health({'package': 'nope/SKILL.md', 'stage_skills': {'video': ['没有这个']}})
        self.assertTrue(any('全流程包入口不存在' in item for item in problems))
        self.assertTrue(any('不在注册表里' in item for item in problems))

    def test_oversized_skill_is_reported_as_inline_only_limit(self):
        with tempfile.TemporaryDirectory() as folder:
            big = Path(folder) / 'big.skill.md'
            big.write_text('---\nname: big\n---\n# 大\n' + '字' * (workflow_settings.REQUEST_CONTEXT_MAX_CHARS + 1000), encoding='utf-8')
            registry = SimpleNamespace(getById=lambda sid: SimpleNamespace(path=big))
            problems = master_skill.health({'package': 'nope', 'stage_skills': {'video': ['big']}}, registry)
        row = next(item for item in problems if 'big' in item)
        self.assertIn('超过内联上限', row)
        self.assertIn('命令行 Agent 不受影响', row)

    def test_no_master_mode_is_a_no_op(self):
        stage_config.clear_workflow(self.project)
        self.assertEqual(master_skill.sync(self.project)['message'], '')
        self.assertNotIn('applied', stage_config.current_workflow(self.project))


class GateTests(unittest.TestCase):
    def config(self, **extra):
        return {'workflow_name': NAME, 'stage': 'keyframe', 'workflow_lock': {}, 'stage_skills': [], **extra}

    def test_missing_stage_locks_block_manual_and_auto_alike(self):
        message = master_skill.gate(self.config())
        self.assertIn('总控门禁已阻断', message)
        for label in ('画幅', '视频模型版本', '交付形态'):
            self.assertIn(label, message)
        full = {'aspect_ratio': '9:16', 'video_model_version': 'Seedance 2.5', 'delivery_format': '两者都交付'}
        self.assertEqual(master_skill.gate(self.config(workflow_lock=full)), '')

    def test_script_intake_is_not_blocked_by_locks(self):
        self.assertEqual(master_skill.gate(self.config(stage='writing')), '')

    def test_without_master_mode_nothing_is_blocked(self):
        self.assertEqual(master_skill.gate({'stage': 'keyframe', 'workflow_lock': {}}), '')

    def test_checked_skill_with_missing_reference_blocks(self):
        with tempfile.TemporaryDirectory() as folder:
            skill = Path(folder) / 'broken.skill.md'
            skill.write_text('---\nname: broken\n---\n# 正文\n[规则](gone.md)\n', encoding='utf-8')
            message = master_skill.gate(self.config(stage='writing', stage_skills=[str(skill)]))
        self.assertIn('引用缺失', message)

    def test_agent_prompt_and_frozen_send_both_enforce_the_gate(self):
        import workflow_engines
        with self.assertRaisesRegex(ValueError, '总控门禁已阻断'):
            workflow_engines.prompt_with_settings('任务', self.config())
        with self.assertRaisesRegex(ValueError, '总控门禁已阻断'):
            workflow_settings.freeze_skills(self.config())

    def test_stage_start_blocks_manual_trigger_with_a_readable_reason(self):
        with tempfile.TemporaryDirectory() as folder:
            project = Path(folder)
            stage_config.put_workflow(project, {'name': NAME, 'skill_ref': 'x', 'lock': {}})
            host = SimpleNamespace(root=project, pet=None)
            result = stage_handler_registry.start(host, 'keyframe', 'manual', lambda *args: 'started')
        self.assertIn('请先在 01 剧本准备', result)
        self.assertIn('画幅', result)


if __name__ == '__main__':
    unittest.main()

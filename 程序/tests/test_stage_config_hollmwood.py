# -*- coding: utf-8 -*-
"""HOLLMWOOD 项目级阶段配置的回归测试。"""
import tempfile
import unittest

import stage_config


class HollmwoodStageConfigTests(unittest.TestCase):
    def test_project_rules_survive_model_and_skill_save(self):
        with tempfile.TemporaryDirectory() as project:
            stage_config.put(project, 'script',
                             hollmwood_rhythm_template='自定义节奏',
                             hollmwood_director_rules='自定义导演规则')
            stage_config.put(project, 'script', model='任意模型', skills=[])
            self.assertEqual(stage_config.hollmwood_rules(project), ('自定义节奏', '自定义导演规则'))

    def test_non_hollmwood_stage_does_not_persist_role_fields(self):
        with tempfile.TemporaryDirectory() as project:
            entry = stage_config.put(project, 'storyboard', hollmwood_director_rules='无效规则')
            self.assertNotIn(stage_config.HOLLMWOOD_DIRECTOR, entry)

    def test_hollmwood_switch_defaults_to_true_and_persists_false(self):
        with tempfile.TemporaryDirectory() as project:
            self.assertTrue(stage_config.hollmwood_enabled(project))
            entry = stage_config.put(project, 'script', hollmwood_enabled=False)
            self.assertFalse(entry[stage_config.HOLLMWOOD_ENABLED])
            self.assertFalse(stage_config.hollmwood_enabled(project))
            self.assertFalse(stage_config.get(project, 'script')[stage_config.HOLLMWOOD_ENABLED])

    def test_workflow_projection_is_namespaced_and_clearable(self):
        with tempfile.TemporaryDirectory() as project:
            workflow = {'name': 'AIGC全流程', 'skill_ref': 'package/SKILL.md',
                        'lock': {'旧统筹': {'aspect_ratio': '1:1'},
                                 'AIGC全流程': {'aspect_ratio': '9:16'}}}
            stage_config.put_workflow(project, workflow)
            self.assertEqual(stage_config.workflow_lock(project)['aspect_ratio'], '9:16')
            stage_config.clear_workflow(project)
            self.assertEqual(stage_config.current_workflow(project), {})
            self.assertEqual(stage_config.get(project, 'script')['model'], 'auto')

    def test_workflow_apply_only_fills_explicitly_empty_stages(self):
        with tempfile.TemporaryDirectory() as project:
            stage_config.put(project, 'script', skills=[])
            stage_config.put(project, 'storyboard', skills=['pipeline-storyboard-draft'])
            preset = {
                'package': 'skills/AIGC/SKILL.md',
                'stage_skills': {
                    'script': ['pipeline-script-preparation'],
                    'storyboard': ['pipeline-storyboard'],
                },
            }
            stage_config.apply_workflow_empty_stages(
                project, {'name': 'AIGC全流程', 'skill_ref': preset['package'], 'lock': {}}, preset)
            self.assertEqual(stage_config.get(project, 'script')['skills'],
                             ['pipeline-script-preparation'])
            self.assertEqual(stage_config.get(project, 'storyboard')['skills'], ['pipeline-storyboard-draft'])
            self.assertEqual(stage_config.workflow_deviation_count(project, preset), 1)


if __name__ == '__main__':
    unittest.main()

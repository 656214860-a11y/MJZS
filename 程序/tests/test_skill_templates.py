"""三虎阶段模板的加载、门禁和检查点回归。"""
import json
import tempfile
import unittest
from pathlib import Path

import pet_bus
import skill_templates
from skill_orchestrator import Orchestrator


class StageTemplateExecutionTests(unittest.TestCase):
    def test_every_registered_stage_has_one_loadable_template(self):
        templates = [skill_templates.load_template(stage) for stage in pet_bus.STAGES]
        self.assertEqual([template.stage_id for template in templates], list(pet_bus.STAGES))
        self.assertTrue(all(template.steps for template in templates))

    def test_asset_template_runs_four_actions_and_writes_template_checkpoint(self):
        with tempfile.TemporaryDirectory() as folder:
            actions, messages = [], []
            orch = Orchestrator(project=folder)

            def execute(action, context):
                actions.append((action, context['_template_step'].index))
                return {'ok': True, 'summary': action + ' 完成'}

            run = orch.run_stage_with_template(
                'assets', mode='manual', wait_for_user=lambda question: '需要',
                broadcast=messages.append, execute_action=execute,
            )
            self.assertTrue(run['ok'])
            self.assertEqual([row[0] for row in actions], [
                'scan_assets', 'check_canonical_boards', 'generate_canonical_boards', 'write_asset_manifest',
            ])
            self.assertNotIn('checkpoint', orch.status)
            saved = json.loads((Path(folder) / 'sanhu_project_status.json').read_text(encoding='utf-8'))
            self.assertNotIn('checkpoint', saved)
            self.assertTrue(all(text.startswith('【') for text in messages))
            self.assertIn('【阶段 5/13】资产处理', messages)
            self.assertIn('【门禁】检测到 0 个角色缺少正典板，是否生成？', messages)

    def test_template_recovery_uses_template_step_count(self):
        with tempfile.TemporaryDirectory() as folder:
            status = {'checkpoint': {'stage': 'assets', 'step': 3, 'step_name': '生成缺失的正典板'}}
            orch = Orchestrator(project=folder, status=status)
            messages = []
            self.assertEqual(orch.recover_from_checkpoint(lambda text: '继续', messages.append), 3)
            self.assertIn('【恢复】阶段：资产管理，步骤 3/4：生成缺失的正典板', messages)


if __name__ == '__main__':
    unittest.main()

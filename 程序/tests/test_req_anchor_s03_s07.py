# -*- coding: utf-8 -*-
"""REQ-S03-52／REQ-S07-54：03 接入决策引擎选型，07 只做追溯核对。

只读阶段 SKILL，核对本地方法定义、03 镜头与初稿追溯字段、07 不重做选型且保留追溯列。
总控退役后不再断言外部包必须存在。
"""
import unittest
from pathlib import Path


PROGRAM = Path(__file__).resolve().parents[1]
SKILLS = PROGRAM / 'skills'


class DecisionEngineStageLinksTests(unittest.TestCase):
    def test_req_s03_52_links_decision_engine_and_reference_anchors(self):
        """REQ-S03-52：03 内置 pipeline SKILL 已清理，目录保留为空壳且阶段契约不再引用旧总控。"""
        import workflow_settings
        from orchestrator.skill_project_layer import RETIRED_BUILTIN_SKILL_IDS
        self.assertTrue((SKILLS / '03初步分镜SKILL').is_dir())
        self.assertFalse((SKILLS / '03初步分镜SKILL' / 'pipeline-storyboard-draft.skill.md').exists())
        self.assertIn('pipeline-storyboard-draft', RETIRED_BUILTIN_SKILL_IDS)
        contract = workflow_settings.stage_output_contract('storyboard')
        self.assertIn('镜头三元组', contract)
        self.assertNotIn('00全流程SKILL', contract)

    def test_req_s07_54_keeps_traceability_without_reselecting(self):
        """REQ-S07-54：07 内置 pipeline SKILL 已清理，目录保留为空壳且批次/追溯契约仍在代码侧。"""
        from contract import shot_batches
        from orchestrator.skill_project_layer import RETIRED_BUILTIN_SKILL_IDS
        self.assertTrue((SKILLS / '07分镜定稿SKILL').is_dir())
        self.assertFalse((SKILLS / '07分镜定稿SKILL' / 'pipeline-storyboard-final.skill.md').exists())
        self.assertIn('pipeline-storyboard-final', RETIRED_BUILTIN_SKILL_IDS)
        self.assertTrue(callable(shot_batches.check_batches))


if __name__ == '__main__':
    unittest.main()

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
        """REQ-S03-52：03 以节拍表为输入，逐节拍选 E-ID、分权重、查雷区并写入追溯字段。"""
        skill = SKILLS / '03初步分镜SKILL' / 'pipeline-storyboard-draft.skill.md'
        text = skill.read_text(encoding='utf-8')
        for phrase in ('本集节拍表', '不重新切分节拍', '禁止编造',
                       'E01', 'E15', 'EX01', '80/15/5是设计权重', '六列表',
                       'beat_no', 'context_id', 'forbidden_limits', 'emotion_anchor_table',
                       'shot_count_decision', 'beat_source', 'forbidden_zone_report'):
            self.assertIn(phrase, text)
        self.assertNotIn('../00全流程SKILL/', text)

    def test_req_s07_54_keeps_traceability_without_reselecting(self):
        """REQ-S07-54：07 不重做镜头选型，只在资产对齐清单保留节拍／E-ID 追溯列。"""
        skill = SKILLS / '07分镜定稿SKILL' / 'pipeline-storyboard-final.skill.md'
        text = skill.read_text(encoding='utf-8')
        for phrase in ('不重做镜头选型', 'beat_no', 'context_id', 'forbidden_limits',
                       '对齐清单', '名称编号对照', '资产编号'):
            self.assertIn(phrase, text)
        self.assertNotIn('../00全流程SKILL/', text)
        self.assertIn('in_state', text)
        self.assertIn('out_state', text)


if __name__ == '__main__':
    unittest.main()

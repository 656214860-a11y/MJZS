# -*- coding: utf-8 -*-
"""REQ-S03-52／REQ-S07-54：03 接入决策引擎选型，07 只做追溯核对。

只读阶段 SKILL 与外部包 reference，钉住三件事：
1. 03 链接决策引擎总入口与三份 reference，且链接锚点真实存在；
2. 03 把节拍／E-ID／雷区限制写成镜头级与初稿级追溯字段；
3. 07 不重做选型，只链接自己用得到的判定与格式章节，并保留追溯列。
"""
import re
import unittest
from pathlib import Path


PROGRAM = Path(__file__).resolve().parents[1]
SKILLS = PROGRAM / 'skills'
DECISION = '../00全流程SKILL/AIGC创作全流程/sd-decision-engine'


def _slug(heading):
    text = heading.strip().lower()
    text = re.sub(r'[^\w\s-]', '', text, flags=re.UNICODE)
    return re.sub(r'\s+', '-', text).strip('-')


def _anchors(path):
    found = set()
    for line in path.read_text(encoding='utf-8-sig').splitlines():
        match = re.match(r'^#{1,6}\s+(.+?)\s*#*\s*$', line)
        if match:
            found.add(_slug(match.group(1)))
    return found


def _links(text):
    return re.findall(r'\[[^\]]*\]\(([^)]+)\)', text)


class DecisionEngineStageLinksTests(unittest.TestCase):
    def _assert_links(self, skill, links):
        for target in links:
            path_text, _, fragment = target.partition('#')
            self.assertTrue(path_text, target)
            path = (skill.parent / path_text).resolve()
            self.assertTrue(path.is_file(), target)
            self.assertIn(fragment, _anchors(path), target)

    def test_req_s03_52_links_decision_engine_and_reference_anchors(self):
        """REQ-S03-52：03 以节拍表为输入，逐节拍选 E-ID、分权重、查雷区并写入追溯字段。"""
        skill = SKILLS / '03初步分镜SKILL' / 'pipeline-storyboard-draft.skill.md'
        text = skill.read_text(encoding='utf-8')
        required = (
            DECISION + '/SKILL.md#四工作流程',
            DECISION + '/references/context-mapping.md#六选-id-的优先级流程',
            DECISION + '/references/context-mapping.md#一80155-权重机制核心',
            DECISION + '/references/forbidden-zone-whitelist.md#六雷区自查流程生成完每个大分镜后过',
            DECISION + '/references/emotion-anchor-table.md#一标准格式6-列',
        )
        for target in required:
            self.assertIn(target, _links(text))
        for phrase in ('本集节拍表', '不重新切分节拍', '禁止编造', 'EX01', '80/15/5',
                       'beat_no', 'context_id', 'forbidden_limits',
                       'emotion_anchor_table', 'shot_count_decision',
                       'forbidden_zone_report'):
            self.assertIn(phrase, text)
        self._assert_links(skill, required)

    def test_req_s07_54_keeps_traceability_without_reselecting(self):
        """REQ-S07-54：07 不重做镜头选型，只在资产对齐清单保留节拍／E-ID 追溯列。"""
        skill = SKILLS / '07分镜定稿SKILL' / 'pipeline-storyboard-final.skill.md'
        text = skill.read_text(encoding='utf-8')
        required = (
            DECISION + '/references/forbidden-zone-whitelist.md#六雷区自查流程生成完每个大分镜后过',
            DECISION + '/references/emotion-anchor-table.md#一标准格式6-列',
        )
        for target in required:
            self.assertIn(target, _links(text))
        for phrase in ('不重做镜头选型', 'beat_no', 'context_id', 'forbidden_limits',
                       '对齐清单', '名称编号对照', '资产编号'):
            self.assertIn(phrase, text)
        self.assertNotIn(DECISION + '/references/context-mapping.md', text)
        self._assert_links(skill, required)


if __name__ == '__main__':
    unittest.main()

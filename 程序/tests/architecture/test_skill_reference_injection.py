"""D1：阶段 SKILL 只能定向引用 00 包的必要章节。"""
from pathlib import Path
import unittest


PROGRAM = Path(__file__).resolve().parents[2]
SKILLS = PROGRAM / 'skills'


class SkillReferenceInjectionTests(unittest.TestCase):
    def test_script_stages_name_only_their_approved_00_references(self):
        expected = {
            '01 剧本准备SKILL/pipeline-script-preparation.skill.md': (
                'production-workflow.md#the-loop',),
            '02 剧本整理SKILL/pipeline-script-structure.skill.md': (
                'production-workflow.md#the-loop', 'cinematic-language.md#shot-functions'),
        }
        for relative, fragments in expected.items():
            text = (SKILLS / relative).read_text(encoding='utf-8')
            self.assertIn('## 定向注入（00 包）', text, relative)
            self.assertIn('不得加载 00 包全文', text, relative)
            for fragment in fragments:
                self.assertIn(fragment, text, '%s 缺定向章节 %s' % (relative, fragment))

    def test_emotion_curve_uses_the_12_beat_source_not_the_old_scene_jump_rule(self):
        text = (SKILLS / '01 剧本准备SKILL/script-emotion-curve.skill.md').read_text(encoding='utf-8')
        self.assertIn('emotion-beat-curve.md#一-12-关键节拍点量化模型010-分', text)
        self.assertIn('12 个关键节拍', text)
        self.assertIn('第 9 节拍须为全片最高峰且不低于 9.5', text)
        self.assertNotIn('相邻两场强度不许跳两级以上', text)

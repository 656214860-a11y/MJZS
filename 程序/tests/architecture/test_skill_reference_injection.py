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

    def test_storyboard_and_final_stages_keep_precheck_and_d_lock_separate(self):
        expected = {
            '03初步分镜SKILL/pipeline-storyboard-draft.skill.md': (
                'blocking-and-staging.md#blocking-notation',
                'cinematic-language.md#shot-functions',
                '这里只做段缝风险预检',
            ),
            '06分镜定稿SKILL/pipeline-storyboard-final.skill.md': (
                'cinematic-language.md#shot-functions',
                'prompt-lexicon.md#the-conversion-procedure',
                'continuity-bible.md#shot-to-shot-continuity-schema',
                'D 锁只在本阶段放行',
                '`in_state`、`out_state`、`cut_type`、`audio_bridge` 与 `owner`',
            ),
        }
        for relative, fragments in expected.items():
            text = (SKILLS / relative).read_text(encoding='utf-8')
            self.assertIn('## 定向注入（00 包）', text, relative)
            self.assertIn('不得加载 00 包全文', text, relative)
            for fragment in fragments:
                self.assertIn(fragment, text, '%s 缺定向章节或门控 %s' % (relative, fragment))

        draft = (SKILLS / '03初步分镜SKILL/pipeline-storyboard-draft.skill.md').read_text(encoding='utf-8')
        self.assertNotIn('D 锁只在本阶段放行', draft)

    def test_storyboard_cluster_reference_anchors_exist_in_the_00_package(self):
        references = {
            'cinematic-director/references/blocking-and-staging.md': (
                '#blocking-notation', '#blocking-for-ai-video'),
            'cinematic-director/references/cinematic-language.md': (
                '#shot-functions', '#continuity-geometry'),
            'cinematic-director/references/prompt-lexicon.md': (
                '#the-conversion-procedure', '#the-one-dominant-move-rule'),
            'cinematic-director/references/continuity-bible.md': (
                '#shot-to-shot-continuity-schema', '#state-change-ledger'),
        }
        for relative, anchors in references.items():
            source = SKILLS / '00全流程SKILL' / relative
            text = source.read_text(encoding='utf-8')
            headings = {
                '#' + line.lstrip('#').strip().lower().replace(' ', '-').replace('–', '-')
                for line in text.splitlines() if line.startswith('#')
            }
            for anchor in anchors:
                self.assertIn(anchor, headings, '%s 缺目标章节 %s' % (relative, anchor))

    def test_emotion_curve_uses_the_12_beat_source_not_the_old_scene_jump_rule(self):
        text = (SKILLS / '01 剧本准备SKILL/script-emotion-curve.skill.md').read_text(encoding='utf-8')
        self.assertIn('emotion-beat-curve.md#一-12-关键节拍点量化模型010-分', text)
        self.assertIn('12 个关键节拍', text)
        self.assertIn('第 9 节拍须为全片最高峰且不低于 9.5', text)
        self.assertNotIn('相邻两场强度不许跳两级以上', text)

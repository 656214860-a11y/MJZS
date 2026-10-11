"""D1：阶段 SKILL 只能定向引用 00 包的必要章节。"""
from pathlib import Path
import unittest


PROGRAM = Path(__file__).resolve().parents[2]
SKILLS = PROGRAM / 'skills'


class SkillReferenceInjectionTests(unittest.TestCase):
    def test_script_stages_name_only_their_approved_00_references(self):
        expected = {
            '01 剧本准备SKILL/pipeline-script-preparation.skill.md': (
                'AIGC创作全流程/short-drama-director/references/screenplay-gate-engine.md',
                '完整遵循五阶门控', 'Premise→Structure→Beat→Entity→Page', '不裁剪 Gate'),
            '02 剧本整理SKILL/pipeline-script-structure.skill.md': (
                'production-workflow.md#the-loop', 'cinematic-language.md#shot-functions'),
        }
        self.assertTrue((SKILLS / '00全流程SKILL/AIGC创作全流程/short-drama-director/references/screenplay-gate-engine.md').is_file())
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
            '07分镜定稿SKILL/pipeline-storyboard-final.skill.md': (
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

    def test_asset_and_continuity_stages_keep_canon_and_audit_separate(self):
        expected = {
            '05资产管理SKILL/pipeline-assets.skill.md': (
                'continuity-bible.md#the-identity-string-contract',
                'image-model-adapters.md#4-character-consistency-playbook-cheapest-first',
                '不得进入正典',
                '不能把它们伪装为本阶段已验证规则',
            ),
            '06连贯性SKILL/pipeline-continuity.skill.md': (
                'continuity-bible.md#the-continuity-axes',
                'failure-modes.md#f7-continuity-break-across-shots',
                '未解决冲突必须保留到 `repairList`',
                '不取得 D 锁的段缝放行权',
            ),
        }
        for relative, fragments in expected.items():
            text = (SKILLS / relative).read_text(encoding='utf-8')
            self.assertIn('## 定向注入（00 包）', text, relative)
            self.assertIn('不得加载 00 包全文', text, relative)
            for fragment in fragments:
                self.assertIn(fragment, text, '%s 缺定向章节或门控 %s' % (relative, fragment))

    def test_asset_and_continuity_sources_contain_the_named_sections(self):
        expected = {
            'cinematic-director/references/continuity-bible.md': (
                '## The continuity axes', '## The identity string contract',
                '## Character schema', '## Asset naming convention',
                '## Shot-to-shot continuity schema', '## State-change ledger'),
            'cinematic-director/references/image-model-adapters.md': (
                '## 4. Character consistency playbook, cheapest first',),
            'cinematic-director/references/failure-modes.md': (
                '### F7 — Continuity break across shots',
                '### F19 — Object permanence break（对象消失）'),
        }
        for relative, headings in expected.items():
            text = (SKILLS / '00全流程SKILL' / relative).read_text(encoding='utf-8')
            for heading in headings:
                self.assertIn(heading, text, '%s 缺目标章节 %s' % (relative, heading))

    def test_keyframe_previs_video_stages_keep_media_handoffs_explicit(self):
        expected = {
            '08首帧管理SKILL/pipeline-keyframe.skill.md': (
                'image-model-adapters.md#3-keyframe-prompt-anatomy-nine-slots-then-constraints',
                'lighting-and-color.md#lighting-continuity-for-ai-video',
                '不得发布 `keyframeManifest`',
            ),
            '09白模预演SKILL/pipeline-previs.skill.md': (
                'blocking-and-staging.md#blocking-for-ai-video',
                'production-workflow.md#shot-difficulty-rubric',
                '不得进入视频生成',
            ),
            '10视频生成SKILL/pipeline-video-generation.skill.md': (
                'ai-video-tool-adapters.md#the-capability-first-rule',
                'failure-modes.md#60-second-triage-tree',
                '先读取所选工具的控制面，再选择 S1／S2／S3／S4',
                '不能作为已验证规则写入本阶段',
            ),
        }
        for relative, fragments in expected.items():
            text = (SKILLS / relative).read_text(encoding='utf-8')
            self.assertIn('## 定向注入（00 包）', text, relative)
            self.assertIn('不得加载 00 包全文', text, relative)
            for fragment in fragments:
                self.assertIn(fragment, text, '%s 缺定向章节或门控 %s' % (relative, fragment))

    def test_audio_edit_delivery_stages_keep_timeline_and_quality_gates_explicit(self):
        expected = {
            '11配音字幕SKILL/pipeline-audio-subtitle.skill.md': (
                'sound-and-dialogue.md#duration-budgeting',
                'sound-and-dialogue.md#the-one-speaker-per-clip-rule',
                '不得发布 `audioManifest`',
            ),
            '12后期剪辑SKILL/pipeline-editing.skill.md': (
                'editing-and-assembly.md#the-assembly-spec',
                'editing-and-assembly.md#fix-in-the-edit-regenerate-or-cover-it',
                '不得发布 `previewMaster` 或 `editManifest`',
            ),
            '13质检交付SKILL/pipeline-delivery.skill.md': (
                'failure-modes.md#failure-taxonomy-f1f19',
                'continuity-bible.md#seed-and-reference-registry',
                '不得标记交付完成',
            ),
        }
        for relative, fragments in expected.items():
            text = (SKILLS / relative).read_text(encoding='utf-8')
            self.assertIn('## 定向注入（00 包）', text, relative)
            self.assertIn('不得加载 00 包全文', text, relative)
            for fragment in fragments:
                self.assertIn(fragment, text, '%s 缺定向章节或门控 %s' % (relative, fragment))

    def test_audio_edit_delivery_sources_contain_the_named_sections(self):
        expected = {
            'cinematic-director/references/sound-and-dialogue.md': (
                '## Dialogue for AI video', '### Duration budgeting',
                '### The one-speaker-per-clip rule', '## Voice-over'),
            'cinematic-director/references/editing-and-assembly.md': (
                '## Pacing math', '## Cut motivation taxonomy',
                '### The hard-cut agreement checklist', '## The assembly spec',
                '## Fix in the edit, regenerate, or cover it'),
            'cinematic-director/references/failure-modes.md': (
                '## 60-second triage tree', '## The cost ladder',
                '## Failure taxonomy F1–F19'),
            'cinematic-director/references/continuity-bible.md': (
                '## Seed and reference registry',),
        }
        for relative, headings in expected.items():
            text = (SKILLS / '00全流程SKILL' / relative).read_text(encoding='utf-8')
            for heading in headings:
                self.assertIn(heading, text, '%s 缺目标章节 %s' % (relative, heading))

    def test_emotion_curve_uses_the_12_beat_source_not_the_old_scene_jump_rule(self):
        text = (SKILLS / '01 剧本准备SKILL/pipeline-script-preparation.skill.md').read_text(encoding='utf-8')
        self.assertIn('emotion-beat-curve.md#一-12-关键节拍点量化模型010-分', text)
        self.assertIn('12 个关键节拍', text)
        self.assertIn('第 9 节拍须为全片最高峰且不低于 9.5', text)
        self.assertNotIn('相邻两场强度不许跳两级以上', text)

"""阶段方法自包含：退役内建总控不产生断链或丢失有效交付职责。"""
from pathlib import Path
import unittest

PROGRAM = Path(__file__).resolve().parents[2]
SKILLS = PROGRAM / 'skills'


class SkillReferenceInjectionTests(unittest.TestCase):
    def stage_text(self, prefix):
        matches = sorted(SKILLS.glob(prefix + '*/pipeline*.skill.md'))
        self.assertEqual(len(matches), 1)
        text = matches[0].read_text(encoding='utf-8')
        self.assertNotIn('../00全流程SKILL/', text)
        if prefix != '04':
            self.assertIn('不默认加载外部包、风格库或示例库', text)
        return text

    def test_script_stages_keep_local_method_definitions(self):
        text = self.stage_text('01')
        for phrase in ('完整遵循五阶门控', 'Premise→Structure→Beat→Entity→Page',
                       '不裁剪 Gate', 'Premise：明确主角', '台词七维：角色辨识度',
                       '语速五步：拆句'):
            self.assertIn(phrase, text)
        text = self.stage_text('02')
        self.assertIn('不重开剧本创作和分集选择', text)
        self.assertIn('计划证据不足时退回剧本准备', text)

    def test_every_stage_remains_self_contained_without_retired_links(self):
        from orchestrator.skill_registry import reference_targets, resolve_reference
        for number in range(1, 14):
            text = self.stage_text('%02d' % number)
            path = next(SKILLS.glob('%02d*/pipeline*.skill.md' % number))
            for entry in reference_targets(text):
                if entry.get('path') is not None:
                    self.assertTrue(resolve_reference(path, entry['path']).is_file(), entry['raw'])

    def test_draft_assets_continuity_and_final_keep_release_boundaries(self):
        self.assertNotIn('D 锁只在本阶段放行', self.stage_text('03'))
        expected = {
            '03': ('这里只做段缝风险预检', '不越权生成最终提示词或采用分镜', '轴线', 'E01', 'E15', '六列表'),
            '05': ('不得进入正典', '不能把它们伪装为本阶段已验证规则', '身份锚点', '版本'),
            '06': ('未解决冲突必须保留到 `repairList`', '不取得 D 锁的段缝放行权',
                   '不执行分镜定稿放行', 'continuity_ledger'),
            '07': ('D 锁只在本阶段放行', 'in_state', 'out_state', 'cut_type', 'audio_bridge', 'owner'),
        }
        for stage, phrases in expected.items():
            text = self.stage_text(stage)
            for phrase in phrases:
                self.assertIn(phrase, text)

    def test_keyframe_previs_and_video_keep_real_evidence_gates(self):
        expected = {
            '08': ('不得发布 `keyframeManifest`', '已入库 M2', '不以空文件'),
            '09': ('不可播放', '运动预算', '不得进入视频生成'),
            '10': ('先读取所选工具的控制面，再选择 S1／S2／S3／S4',
                   'S1 图生视频', 'S2 文生视频', 'S3 首尾帧', 'S4 时间戳多镜头',
                   '不能作为已验证规则写入本阶段'),
        }
        for stage, phrases in expected.items():
            text = self.stage_text(stage)
            for phrase in phrases:
                self.assertIn(phrase, text)

    def test_audio_edit_delivery_keep_timeline_and_quality_gates(self):
        expected = {
            '11': ('不得发布 `audioManifest`', '逐条核对字幕文本、入点、出点、说话人及音轨来源'),
            '12': ('不得发布 `previewMaster` 或 `editManifest`', '时间码和修复/切换依据'),
            '13': ('不得标记交付完成', 'qualityReport', 'F1身份漂移', 'F19既有对象消失'),
        }
        for stage, phrases in expected.items():
            text = self.stage_text(stage)
            for phrase in phrases:
                self.assertIn(phrase, text)

    def test_emotion_curve_keeps_scoped_12_beat_method(self):
        text = self.stage_text('01')
        self.assertIn('12 个关键节拍', text)
        self.assertIn('第 9 节拍须为全片最高峰且不低于 9.5', text)
        self.assertIn('标准三分钟短剧', text)
        self.assertIn('反击反杀9.5–9.8', text)
        self.assertNotIn('相邻两场强度不许跳两级以上', text)

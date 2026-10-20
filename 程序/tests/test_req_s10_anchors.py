"""REQ-S10 测试锚定：视频阶段的数据依赖、门禁与 SKILL 页面文字。"""
import unittest
from pathlib import Path

import pet_bus
import skill_tools
import stage_flow
import stage_parallel

ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / 'skills' / '10视频生成SKILL'


class ReqS10AnchorTests(unittest.TestCase):
    def test_req_s10_03_video_depends_on_keyframe_and_previs_is_only_sg05(self):
        """REQ-S10-03：视频依赖表只列 keyframe；需要预演的业务前置由 SG-05 表达。"""
        self.assertEqual(stage_flow.DEPENDS['video'], ('keyframe',))
        gates = {row['id']: row for row in stage_parallel.GATES}
        self.assertEqual((gates['SG-05']['from'], gates['SG-05']['to'], gates['SG-05']['check']),
                         ('previs', 'video', 'previs_ready'))

    def test_req_s10_32_skill_page_locations_use_current_stage_label(self):
        """REQ-S10-32：视频 SKILL 不再写旧阶段号，页面动作仍只登记在页面上执行。"""
        expected = pet_bus.stage_label('video')
        texts = {path.name: path.read_text(encoding='utf-8') for path in SKILL_DIR.glob('*.skill.md')}
        self.assertEqual(len(texts), 5)
        for name, text in texts.items():
            self.assertNotIn('08 视频生成', text, name)
        page_lines = [line for text in texts.values() for line in text.splitlines()
                      if 'video.' in line and '→' in line and '视频生成' in line]
        self.assertTrue(page_lines)
        for line in page_lines:
            self.assertIn(expected, line)
        for tool in ('video.batchSubmit', 'video.retry', 'video.pause', 'video.resume'):
            self.assertIn(tool, skill_tools.PAGES)
            self.assertNotIn(tool, skill_tools.READY)


if __name__ == '__main__':
    unittest.main(verbosity=2)

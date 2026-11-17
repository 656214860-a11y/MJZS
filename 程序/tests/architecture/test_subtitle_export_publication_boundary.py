"""字幕文本发布必须由 L3 装配，L2 不可反向依赖基础设施。"""
from pathlib import Path
import unittest

from tests.architecture._scan import entity_file


ROOT = Path(__file__).resolve().parents[2]


class SubtitleExportPublicationBoundaryTests(unittest.TestCase):
    def test_l2_requires_injected_text_publisher(self):
        source = (ROOT / 'domain/subtitle_export_service.py').read_text(encoding='utf-8')
        self.assertIn('def publish_srt_text(target, text, *, publish=None):', source)
        self.assertNotIn('import line_endings', source)
        self.assertIn("TypeError('字幕文本发布需要 L3 注入发布器')", source)

    def test_l3_controller_owns_writer_injection(self):
        source = (ROOT / 'orchestrator/subtitle_export_controller.py').read_text(encoding='utf-8')
        self.assertIn('def subtitle_export_gateway():', source)
        self.assertIn('line_endings.write_text', source)
        self.assertIn('def publish_stage_srt_text(target, text):', source)

    def test_skill_tool_calls_l3_controller_only(self):
        source = entity_file('skill_tools').read_text(encoding='utf-8')
        self.assertIn('subtitle_export_controller import publish_stage_srt_text', source)
        self.assertNotIn('subtitle_export_service import publish_srt_text', source)


if __name__ == '__main__':
    unittest.main()

"""字幕阶段成果必须经 L3 注入发布器的架构门禁。"""
import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class SubtitleExportPublicationBoundaryTests(unittest.TestCase):
    def test_l2_exports_accept_a_publisher_and_do_not_write_directly(self):
        tree = ast.parse((ROOT / 'subtitle_export_service.py').read_text(encoding='utf-8'))
        exports = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)
                   and node.name in {'export_srt', 'export_dialogue_script'}}
        self.assertEqual(set(exports), {'export_srt', 'export_dialogue_script'})
        for node in exports.values():
            self.assertIn('publish', [arg.arg for arg in node.args.kwonlyargs])
            names = {child.id for child in ast.walk(node) if isinstance(child, ast.Name)}
            self.assertIn('publish', names)
            self.assertNotIn('save_text', names)

    def test_l3_injects_the_text_publisher_and_desktop_uses_l3(self):
        stage_source = (ROOT / 'stage_execution_service.py').read_text(encoding='utf-8')
        desktop_source = (ROOT / 'desktop.py').read_text(encoding='utf-8')
        self.assertIn('export_srt(project, episode, publish=publish_stage_text)', stage_source)
        self.assertIn('export_dialogue_script(project, episode, assets, publish=publish_stage_text)', stage_source)
        self.assertIn('from stage_execution_service import export_stage_srt', desktop_source)
        self.assertIn('from stage_execution_service import export_stage_dialogue_script', desktop_source)


if __name__ == '__main__':
    unittest.main()

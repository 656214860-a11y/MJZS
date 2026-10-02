import ast
import os
import unittest
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class LocalVideoSettingsBoundaryTests(unittest.TestCase):
    def test_settings_commit_delegates_publication_to_service(self):
        source = Path(ROOT, 'local_video.py').read_text(encoding='utf-8')
        tree = ast.parse(source)
        window = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'settings_window')
        commit = next(node for node in ast.walk(window) if isinstance(node, ast.FunctionDef) and node.name == 'commit')
        method = ast.get_source_segment(source, commit)
        self.assertIn("'publish_local_video_settings'", method)
        self.assertNotIn('copy2', method)
        self.assertNotIn('save(', method)

    def test_l2_requires_l3_gateway_without_direct_publishers(self):
        source = Path(ROOT, 'local_video_settings_service.py').read_text(encoding='utf-8')
        self.assertNotIn('from agent.core import file_hash, save,', source)
        self.assertIn("'publish_json', 'publish_bytes', 'copy_file', 'replace_file'", source)

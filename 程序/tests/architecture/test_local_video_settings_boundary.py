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
        calls = [node for node in ast.walk(commit) if isinstance(node, ast.Call) and getattr(node.func, 'id', '') == 'save_local_video_settings']
        self.assertEqual(len(calls), 1)
        self.assertNotIn('copy2', method)
        self.assertNotIn('save(', method)

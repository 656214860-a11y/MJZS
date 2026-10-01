import ast
import os
import unittest
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class CloudVideoSettingsBoundaryTests(unittest.TestCase):
    def test_settings_publication_delegates_to_service(self):
        source = Path(ROOT, 'cloud_video.py').read_text(encoding='utf-8')
        tree = ast.parse(source)
        methods = [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
                   and node.name in ('open_session', 'align_source', 'delete_model')]
        text = '\n'.join(ast.get_source_segment(source, method) for method in methods)
        self.assertEqual(text.count('publish_session_config('), 2)
        self.assertEqual(text.count('publish_workspace_preference('), 1)
        self.assertNotIn('save(', text)

    def test_studio_settings_delegate_to_service(self):
        source = Path(ROOT, 'app.py').read_text(encoding='utf-8')
        tree = ast.parse(source)
        methods = [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
                   and node.name == 'settings']
        text = '\n'.join(ast.get_source_segment(source, method) for method in methods)
        self.assertIn('publish_studio_config(', text)
        self.assertNotIn('save(', text)

    def test_desktop_workspace_selection_delegates_to_service(self):
        source = Path(ROOT, 'desktop.py').read_text(encoding='utf-8')
        tree = ast.parse(source)
        methods = [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
                   and node.name == 'set_video_workspace']
        text = '\n'.join(ast.get_source_segment(source, method) for method in methods)
        self.assertIn('publish_workspace_preference(', text)
        self.assertNotIn('save(', text)

    def test_desktop_video_mode_preference_delegates_to_service(self):
        source = Path(ROOT, 'desktop.py').read_text(encoding='utf-8')
        tree = ast.parse(source)
        methods = [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
                   and node.name == 'show']
        text = '\n'.join(ast.get_source_segment(source, method) for method in methods)
        self.assertIn('publish_workspace_preference(', text)
        self.assertNotIn('save(', text)

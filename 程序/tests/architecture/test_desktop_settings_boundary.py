import ast
import os
import unittest
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class DesktopSettingsBoundaryTests(unittest.TestCase):
    def test_desktop_preferences_delegate_all_mutations_to_service(self):
        source = Path(ROOT, 'desktop.py').read_text(encoding='utf-8')
        tree = ast.parse(source)
        methods = [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
                   and node.name in ('remember_daily_project_choice', '_sync_desktop_project_paths',
                                     'launch_comfy', 'find_editor')]
        text = '\n'.join(ast.get_source_segment(source, method) for method in methods)
        self.assertEqual(4, text.count('publish_desktop_preferences('))
        self.assertNotIn('publish_desktop_settings(', text)
        self.assertNotIn('save(self.settings_file', text)
        service = Path(ROOT, 'desktop_settings_service.py').read_text(encoding='utf-8')
        stage = Path(ROOT, 'stage_execution_service.py').read_text(encoding='utf-8')
        self.assertNotIn('from agent.core import save', service)
        self.assertIn('def desktop_settings_gateway()', stage)
        self.assertIn('def publish_desktop_preferences(', stage)

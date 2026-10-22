from tests.architecture._scan import desktop_text  # R1505：Desktop 方法分布在 desktop.py 与迁出的 Mixin 模块
import ast
import os
import unittest
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class CloudVideoSettingsBoundaryTests(unittest.TestCase):
    def test_l2_requires_l3_gateway_for_all_configuration_publication(self):
        source = Path(ROOT, 'cloud_video_service.py').read_text(encoding='utf-8')
        self.assertIn('def _require_gateway(gateway)', source)
        self.assertNotIn('from agent.core import read, save', source)
        service = Path(ROOT, 'stage_execution_service.py').read_text(encoding='utf-8')
        self.assertIn('def cloud_video_gateway()', service)

    def test_settings_publication_delegates_to_service(self):
        source = Path(ROOT, 'cloud_video.py').read_text(encoding='utf-8')
        tree = ast.parse(source)
        methods = [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
                   and node.name in ('open_session', 'align_source', 'delete_model')]
        text = '\n'.join(ast.get_source_segment(source, method) for method in methods)
        self.assertEqual(text.count('publish_cloud_video_session_config('), 2)
        self.assertEqual(text.count('publish_cloud_video_workspace_preference('), 1)
        self.assertNotIn('save(', text)

    def test_studio_settings_delegate_to_service(self):
        source = Path(ROOT, 'app.py').read_text(encoding='utf-8')
        tree = ast.parse(source)
        methods = [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
                   and node.name == 'settings']
        text = '\n'.join(ast.get_source_segment(source, method) for method in methods)
        self.assertIn('publish_cloud_video_studio_config(', text)
        self.assertNotIn('save(', text)

    def test_desktop_workspace_selection_delegates_to_service(self):
        source = desktop_text()
        tree = ast.parse(source)
        methods = [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
                   and node.name == 'set_video_workspace']
        text = '\n'.join(ast.get_source_segment(source, method) for method in methods)
        self.assertIn('publish_cloud_video_workspace_preference(', text)
        self.assertNotIn('save(', text)

    def test_desktop_video_mode_preference_delegates_to_service(self):
        source = desktop_text()
        tree = ast.parse(source)
        methods = [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
                   and node.name in ('show', '_show_reset_page')]  # R1809：show 的换页前置段切到 _show_reset_page，断言不变
        text = '\n'.join(ast.get_source_segment(source, method) for method in methods)
        self.assertIn('publish_cloud_video_workspace_preference(', text)
        self.assertNotIn('save(', text)

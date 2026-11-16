import ast
import unittest

from tests.architecture._scan import ROOT


class VideoDeleteBoundaryTests(unittest.TestCase):
    def test_app_delegates_video_delete_publication_to_lifecycle_service(self):
        tree = ast.parse((ROOT / 'app.py').read_text(encoding='utf-8'))
        app = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'App')
        method = next(node for node in app.body if isinstance(node, ast.FunctionDef)
                      and node.name == 'delete_video_shot')
        calls = [node for node in ast.walk(method) if isinstance(node, ast.Call)]
        self.assertEqual(1, sum(isinstance(node.func, ast.Name)
                                and node.func.id == 'mark_stage_video_deleted' for node in calls))
        prohibited = {'read', 'save', 'save_bytes', 'write_text', 'write_bytes', 'copy2',
                      'remove_temporary_file'}
        self.assertFalse(any(isinstance(node.func, ast.Name) and node.func.id in prohibited
                             for node in calls))

    def test_lifecycle_service_requires_l3_gateway_for_publication(self):
        source = (ROOT / 'domain/video_lifecycle_service.py').read_text(encoding='utf-8')
        self.assertIn('def _require_gateway', source)
        self.assertNotIn('from agent.core import read, save', source)

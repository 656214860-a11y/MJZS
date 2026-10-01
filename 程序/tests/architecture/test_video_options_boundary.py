import ast
import unittest

from tests.architecture._scan import ROOT


class VideoOptionsBoundaryTests(unittest.TestCase):
    def test_app_delegates_video_options_publication_to_lifecycle_service(self):
        tree = ast.parse((ROOT / 'app.py').read_text(encoding='utf-8'))
        app = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'App')
        method = next(node for node in app.body if isinstance(node, ast.FunctionDef)
                      and node.name == 'save_options')
        calls = [node for node in ast.walk(method) if isinstance(node, ast.Call)]
        self.assertEqual(2, sum(isinstance(node.func, ast.Name)
                                and node.func.id == 'save_video_options' for node in calls))
        prohibited = {'read', 'save', 'save_bytes', 'write_text', 'write_bytes', 'copy2',
                      'remove_temporary_file'}
        self.assertFalse(any(isinstance(node.func, ast.Name) and node.func.id in prohibited
                             for node in calls))

    def test_app_delegates_white_model_upload_choice_to_lifecycle_service(self):
        tree = ast.parse((ROOT / 'app.py').read_text(encoding='utf-8'))
        app = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'App')
        method = next(node for node in app.body if isinstance(node, ast.FunctionDef)
                      and node.name == 'set_white_upload')
        calls = [node for node in ast.walk(method) if isinstance(node, ast.Call)]
        self.assertEqual(1, sum(isinstance(node.func, ast.Name)
                                and node.func.id == 'save_white_model_upload' for node in calls))
        prohibited = {'read', 'save', 'save_bytes', 'write_text', 'write_bytes', 'copy2',
                      'remove_temporary_file'}
        self.assertFalse(any(isinstance(node.func, ast.Name) and node.func.id in prohibited
                             for node in calls))

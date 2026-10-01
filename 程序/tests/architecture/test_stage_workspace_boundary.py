"""Stage pages delegate user-visible directory initialization to a no-Tk service."""
import ast
import unittest

from tests.architecture._scan import ROOT


class StageWorkspaceBoundaryTests(unittest.TestCase):
    def test_audio_editing_and_delivery_pages_delegate_workspace_initialization(self):
        tree = ast.parse((ROOT / 'desktop.py').read_text(encoding='utf-8'))
        desktop = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'Desktop')
        expected = {
            'audio': 'ensure_audio_workspace',
            'import_audio': 'ensure_audio_workspace',
            'editing': 'ensure_editing_workspace',
            'delivery': 'ensure_delivery_workspace',
            'final_import': 'ensure_delivery_workspace',
        }
        for method_name, service_name in expected.items():
            method = next(node for node in desktop.body
                          if isinstance(node, ast.FunctionDef) and node.name == method_name)
            calls = [node.func.id for node in ast.walk(method) if isinstance(node, ast.Call)
                     and isinstance(node.func, ast.Name)]
            self.assertIn(service_name, calls, method_name)
            direct_mkdir = [node.lineno for node in ast.walk(method) if isinstance(node, ast.Call)
                            and isinstance(node.func, ast.Attribute) and node.func.attr == 'mkdir']
            self.assertEqual([], direct_mkdir, method_name + ' 不得直接创建阶段目录: ' + str(direct_mkdir))

    def test_asset_page_delegates_category_directory_initialization(self):
        tree = ast.parse((ROOT / 'desktop.py').read_text(encoding='utf-8'))
        desktop = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'Desktop')
        assets = next(node for node in desktop.body if isinstance(node, ast.FunctionDef) and node.name == 'assets')
        calls = [node.func.id for node in ast.walk(assets) if isinstance(node, ast.Call)
                 and isinstance(node.func, ast.Name)]
        self.assertIn('ensure_browser_directory', calls)
        direct_mkdir = [node.lineno for node in ast.walk(assets) if isinstance(node, ast.Call)
                        and isinstance(node.func, ast.Attribute) and node.func.attr == 'mkdir']
        self.assertEqual([], direct_mkdir, '资产页不得直接创建分类目录: ' + str(direct_mkdir))

    def test_storyboard_import_delegates_workspace_initialization_when_project_is_open(self):
        tree = ast.parse((ROOT / 'desktop.py').read_text(encoding='utf-8'))
        desktop = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'Desktop')
        importer = next(node for node in desktop.body if isinstance(node, ast.FunctionDef) and node.name == 'import_json')
        calls = [node.func.id for node in ast.walk(importer) if isinstance(node, ast.Call)
                 and isinstance(node.func, ast.Name)]
        self.assertIn('ensure_storyboard_workspace', calls)

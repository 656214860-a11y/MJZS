"""The writing page delegates script-rename persistence to its service."""
import ast
import unittest

from tests.architecture._scan import ROOT


class ScriptRenameBoundaryTests(unittest.TestCase):
    def test_writing_delegates_workspace_initialization_to_service(self):
        tree = ast.parse((ROOT / 'desktop.py').read_text(encoding='utf-8'))
        desktop = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'Desktop')
        writing = next(node for node in desktop.body if isinstance(node, ast.FunctionDef) and node.name == 'writing')
        names = [node.func.id for node in ast.walk(writing) if isinstance(node, ast.Call)
                 and isinstance(node.func, ast.Name)]
        self.assertIn('ensure_script_workspace', names)

    def test_writing_rename_uses_workspace_service_not_path_rename(self):
        tree = ast.parse((ROOT / 'desktop.py').read_text(encoding='utf-8'))
        desktop = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'Desktop')
        writing = next(node for node in desktop.body if isinstance(node, ast.FunctionDef) and node.name == 'writing')
        rename = next(node for node in ast.walk(writing)
                      if isinstance(node, ast.FunctionDef) and node.name == 'rename_script')
        names = [node.func.id for node in ast.walk(rename) if isinstance(node, ast.Call)
                 and isinstance(node.func, ast.Name)]
        self.assertIn('rename_script_document', names)
        direct = [node.lineno for node in ast.walk(rename) if isinstance(node, ast.Call)
                  and isinstance(node.func, ast.Attribute) and node.func.attr == 'rename']
        self.assertEqual([], direct, '剧本重命名不得由桌面页直接执行: ' + str(direct))

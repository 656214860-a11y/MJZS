"""The writing page delegates script-rename persistence to its service."""
import ast
import unittest

from tests.architecture._scan import ROOT, parse_desktop


class ScriptRenameBoundaryTests(unittest.TestCase):
    def test_writing_delegates_workspace_initialization_to_service(self):
        tree = parse_desktop()
        desktop = ast.Module(body=[member for cls in tree.body if isinstance(cls, ast.ClassDef) for member in cls.body], type_ignores=[])  # R1499：Desktop 方法分布在 desktop.py 与迁出的 Mixin 类里
        # R1817：writing 的闭包改写成了 _WritingPage 类，页面构造代码现在在类里；薄方法和新类两处都扫
        scopes = [node for node in desktop.body if isinstance(node, ast.FunctionDef) and node.name == 'writing'] + [cls for cls in tree.body if isinstance(cls, ast.ClassDef) and cls.name == '_WritingPage']
        self.assertEqual(len(scopes), 2)
        names = [node.func.id for writing in scopes for node in ast.walk(writing) if isinstance(node, ast.Call)
                 and isinstance(node.func, ast.Name)]
        self.assertIn('ensure_script_workspace', names)

    def test_writing_rename_uses_workspace_service_not_path_rename(self):
        tree = parse_desktop()
        desktop = ast.Module(body=[member for cls in tree.body if isinstance(cls, ast.ClassDef) for member in cls.body], type_ignores=[])  # R1499：Desktop 方法分布在 desktop.py 与迁出的 Mixin 类里
        # R1817：writing 的闭包改写成了 _WritingPage 类，页面构造代码现在在类里；薄方法和新类两处都扫
        scopes = [node for node in desktop.body if isinstance(node, ast.FunctionDef) and node.name == 'writing'] + [cls for cls in tree.body if isinstance(cls, ast.ClassDef) and cls.name == '_WritingPage']
        self.assertEqual(len(scopes), 2)
        rename = next(node for writing in scopes for node in ast.walk(writing)
                      if isinstance(node, ast.FunctionDef) and node.name == 'rename_script')
        names = [node.func.id for node in ast.walk(rename) if isinstance(node, ast.Call)
                 and isinstance(node.func, ast.Name)]
        self.assertIn('rename_script_document', names)
        direct = [node.lineno for node in ast.walk(rename) if isinstance(node, ast.Call)
                  and isinstance(node.func, ast.Attribute) and node.func.attr == 'rename']
        self.assertEqual([], direct, '剧本重命名不得由桌面页直接执行: ' + str(direct))

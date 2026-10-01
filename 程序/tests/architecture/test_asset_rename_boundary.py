"""The asset page delegates rename persistence to the asset service."""
import ast
import unittest

from tests.architecture._scan import ROOT


class AssetRenameBoundaryTests(unittest.TestCase):
    def test_desktop_rename_delegates_both_document_writes(self):
        tree = ast.parse((ROOT / 'desktop.py').read_text(encoding='utf-8'))
        rename = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'Desktop')
        method = next(node for node in rename.body if isinstance(node, ast.FunctionDef) and node.name == 'rename_asset')
        calls = [node for node in ast.walk(method) if isinstance(node, ast.Call)
                 and isinstance(node.func, ast.Name) and node.func.id == '_rename_asset']
        self.assertEqual(len(calls), 1)
        direct = [node.lineno for node in ast.walk(method) if isinstance(node, ast.Call)
                  and isinstance(node.func, ast.Name) and node.func.id == 'save']
        self.assertEqual(direct, [], '资产重命名不得由桌面页直接保存: ' + str(direct))

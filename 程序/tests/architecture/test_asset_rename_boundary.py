"""The asset page delegates rename persistence to the asset service."""
from tests.architecture._scan import parse_desktop  # R1505：Desktop 方法分布在 desktop.py 与迁出的 Mixin 模块
import ast
import unittest

from tests.architecture._scan import ROOT


class AssetRenameBoundaryTests(unittest.TestCase):
    def test_desktop_rename_delegates_both_document_writes(self):
        tree = parse_desktop()
        rename = ast.Module(body=[member for cls in tree.body if isinstance(cls, ast.ClassDef) for member in cls.body], type_ignores=[])  # Desktop 方法分布在 desktop.py 与迁出的 Mixin 类里
        method = next(node for node in rename.body if isinstance(node, ast.FunctionDef) and node.name == 'rename_asset')
        calls = [node for node in ast.walk(method) if isinstance(node, ast.Call)
                 and isinstance(node.func, ast.Name) and node.func.id == '_rename_asset']
        self.assertEqual(len(calls), 1)
        direct = [node.lineno for node in ast.walk(method) if isinstance(node, ast.Call)
                  and isinstance(node.func, ast.Name) and node.func.id == 'save']
        self.assertEqual(direct, [], '资产重命名不得由桌面页直接保存: ' + str(direct))

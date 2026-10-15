"""The asset page delegates registered-image removal to its lifecycle service."""
from tests.architecture._scan import parse_desktop  # R1505：Desktop 方法分布在 desktop.py 与迁出的 Mixin 模块
import ast
import unittest

from tests.architecture._scan import ROOT


class AssetImageRemovalBoundaryTests(unittest.TestCase):
    def test_desktop_delegates_image_recycle_and_index_update(self):
        tree = parse_desktop()
        desktop = ast.Module(body=[member for cls in tree.body if isinstance(cls, ast.ClassDef) for member in cls.body], type_ignores=[])  # Desktop 方法分布在 desktop.py 与迁出的 Mixin 类里
        method = next(node for node in desktop.body if isinstance(node, ast.FunctionDef) and node.name == 'delete_asset_image')
        calls = [node for node in ast.walk(method) if isinstance(node, ast.Call)
                 and isinstance(node.func, ast.Name) and node.func.id == 'remove_asset_image']
        self.assertEqual(len(calls), 1)
        direct = [node.lineno for node in ast.walk(method) if isinstance(node, ast.Call)
                  and isinstance(node.func, ast.Name) and node.func.id == 'save']
        self.assertEqual(direct, [], '资产图片删除不得由桌面页直接保存索引: ' + str(direct))

"""The asset page delegates local image import publication to its service."""
from tests.architecture._scan import parse_desktop  # R1505：Desktop 方法分布在 desktop.py 与迁出的 Mixin 模块
import ast
import unittest

from tests.architecture._scan import ROOT


class AssetImageImportBoundaryTests(unittest.TestCase):
    def test_desktop_delegates_image_and_registry_publication(self):
        tree = parse_desktop()
        desktop = ast.Module(body=[member for cls in tree.body if isinstance(cls, ast.ClassDef) for member in cls.body], type_ignores=[])  # Desktop 方法分布在 desktop.py 与迁出的 Mixin 类里
        method = next(node for node in desktop.body if isinstance(node, ast.FunctionDef) and node.name == 'asset_import')
        calls = [node for node in ast.walk(method) if isinstance(node, ast.Call)
                 and isinstance(node.func, ast.Name) and node.func.id == 'import_asset_image']
        self.assertEqual(len(calls), 1)
        prohibited = {'read', 'save', 'save_bytes', 'write_text', 'write_bytes', 'copy2', 'remove_temporary_file'}
        direct = [node.lineno for node in ast.walk(method) if isinstance(node, ast.Call)
                  and isinstance(node.func, ast.Name) and node.func.id in prohibited]
        self.assertEqual(direct, [], '资产导入不得由桌面页直接发布: ' + str(direct))

import ast
import os
import unittest
from pathlib import Path


ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class ServiceReturnContractBoundaryTests(unittest.TestCase):
    def test_only_frozen_l2_adopters_import_service_contract(self):
        """第 1 项暂停期间，新增采用方必须显式解冻并更新本棘轮。"""
        from tests.architecture._layers import LAYERS
        adopters = set()
        for module, layer in LAYERS.items():
            if layer != 2:
                continue
            path = Path(ROOT) / f'{module}.py'
            if not path.is_file():
                continue  # 历史兼容逻辑名仍可登记为 L2，但不是可扫描源码模块。
            tree = ast.parse(path.read_text(encoding='utf-8'))
            if any(isinstance(node, ast.ImportFrom) and node.module == 'service_contract'
                   for node in ast.walk(tree)):
                adopters.add(module)
        self.assertEqual(adopters, {'delivery_import_service', 'keyframe_lifecycle_service'})

    def test_delivery_import_is_registered_l2_and_uses_result_contract(self):
        from tests.architecture._layers import LAYERS
        self.assertEqual(LAYERS['delivery_import_service'], 2)
        tree = ast.parse((Path(ROOT) / 'delivery_import_service.py').read_text(encoding='utf-8'))
        imports = {name.name for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
                   and node.module == 'service_contract' for name in node.names}
        self.assertEqual(imports, {'SystemError', 'UserError', 'success'})

    def test_keyframe_lifecycle_is_registered_l2_and_uses_result_contract(self):
        from tests.architecture._layers import LAYERS
        self.assertEqual(LAYERS['keyframe_lifecycle_service'], 2)
        tree = ast.parse((Path(ROOT) / 'keyframe_lifecycle_service.py').read_text(encoding='utf-8'))
        imports = {name.name for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
                   and node.module == 'service_contract' for name in node.names}
        self.assertEqual(imports, {'SystemError', 'UserError', 'success'})
        lifecycle = {'delete_keyframe', 'restore_keyframe', 'replace_keyframe'}
        decorators = {
            node.name: {item.id for item in node.decorator_list if isinstance(item, ast.Name)}
            for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in lifecycle
        }
        self.assertEqual(set(decorators), lifecycle)
        self.assertTrue(all('_lifecycle_result' in values for values in decorators.values()))

    def test_service_result_contract_is_l0(self):
        from tests.architecture._layers import LAYERS
        self.assertEqual(LAYERS['service_contract'], 0)

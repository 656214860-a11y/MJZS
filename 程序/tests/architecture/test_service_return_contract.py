import ast
import json
import os
import unittest
from pathlib import Path


ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class ServiceReturnContractBoundaryTests(unittest.TestCase):
    def test_every_registered_l2_module_has_a_scope_record(self):
        """未审计模块不能因旧清单遗漏而被误判为已经完成迁移。"""
        from tests.architecture._layers import LAYERS
        root = Path(ROOT)
        ledger = json.loads((root / '维护记录' / '架构统一基数.json').read_text(encoding='utf-8'))['第一项']
        groups = [ledger[key] for key in ('adopters', 'exempt_items', 'scope_audit_pending')]
        names = [name for group in groups for name in group]
        self.assertEqual(len(names), len(set(names)), '范围记录不得重复或跨组重叠')
        self.assertEqual(set(names), {name for name, layer in LAYERS.items() if layer == 2})
        missing = {name for name in names if not (root / f'{name}.py').is_file()
                   and not (root / name / '__init__.py').is_file()}
        historical = ledger['historical_name_audit_pending']
        self.assertEqual(len(historical), len(set(historical)))
        self.assertEqual(missing, set(historical), '旧逻辑名须追溯替代入口，不能直接算已迁移')

    def test_only_approved_l2_adopters_import_service_contract(self):
        """解冻后的每批迁移仍必须显式更新采用方棘轮。"""
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
        self.assertEqual(adopters, {'asset_batch_settings_service', 'audio_import_service', 'delivery_import_service', 'desktop_settings_service', 'keyframe_lifecycle_service',
                                    'script_workspace_service', 'storyboard_edit_service', 'subtitle_export_service'})
        ledger = json.loads((Path(ROOT) / '维护记录' / '架构统一基数.json').read_text(encoding='utf-8'))['第一项']
        self.assertEqual(adopters, set(ledger['adopters']))
        self.assertFalse(adopters & set(ledger['exempt_items']))
        self.assertEqual(ledger['exempt_count'], len(ledger['exempt_items']))

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

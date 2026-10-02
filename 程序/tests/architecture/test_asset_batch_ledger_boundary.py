"""资产批次台账只能由状态服务持久化。"""
import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class AssetBatchLedgerBoundaryTests(unittest.TestCase):
    def test_executor_uses_state_service_not_direct_ledger_persistence(self):
        tree = ast.parse((ROOT / 'asset_batch_execution.py').read_text(encoding='utf-8'))
        imported = {name.name for node in tree.body if isinstance(node, ast.ImportFrom)
                    and node.module == 'asset_batch_state_service' for name in node.names}
        self.assertTrue({'read_ledger', 'save_ledger'} <= imported)
        forbidden = [node.lineno for node in ast.walk(tree) if isinstance(node, ast.Call)
                     and isinstance(node.func, ast.Name) and node.func.id == 'save']
        self.assertEqual(forbidden, [], '执行器不得直接持久化资产批次台账: ' + str(forbidden))

    def test_state_service_requires_l3_publisher_for_ledger_write(self):
        tree = ast.parse((ROOT / 'asset_batch_state_service.py').read_text(encoding='utf-8'))
        direct_core_saves = [name.name for node in tree.body if isinstance(node, ast.ImportFrom)
                             and node.module == 'agent.core' for name in node.names if name.name == 'save']
        self.assertEqual(direct_core_saves, [], 'L2 台账服务不得直接导入正式发布器')
        function = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                        and node.name == 'save_ledger')
        self.assertIn('publish', {arg.arg for arg in function.args.kwonlyargs})

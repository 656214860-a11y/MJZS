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

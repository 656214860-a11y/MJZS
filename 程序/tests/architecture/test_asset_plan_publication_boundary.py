"""资产计划同步只能委托同一发布包，避免四份清单部分落盘。"""
from __future__ import annotations

import ast
import unittest

from tests.architecture._scan import ROOT, parse


class AssetPlanPublicationBoundaryTests(unittest.TestCase):
    def test_sync_plan_delegates_all_output_to_bundle_publisher(self) -> None:
        tree = parse(ROOT / 'asset_plan.py')
        sync = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'sync_plan')
        calls = [node for node in ast.walk(sync) if isinstance(node, ast.Call)
                 and isinstance(node.func, ast.Name)]
        self.assertIn('publish_plan_bundle', [node.func.id for node in calls])
        direct_writers = [node.lineno for node in calls
                          if node.func.id in {'save', 'save_bytes', 'save_text', 'write_text', 'write_bytes'}]
        self.assertEqual(direct_writers, [], 'sync_plan 只能经 publish_plan_bundle 发布：' + str(direct_writers))

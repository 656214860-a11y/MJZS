"""资产计划同步只能委托同一发布包，避免四份清单部分落盘。"""
from __future__ import annotations

import ast
import unittest

from tests.architecture._scan import ROOT, entity_file, parse


class AssetPlanPublicationBoundaryTests(unittest.TestCase):
    def test_sync_plan_delegates_all_output_to_bundle_publisher(self) -> None:
        tree = parse(entity_file('asset_plan'))
        sync = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == '_sync_plan')
        calls = [node for node in ast.walk(sync) if isinstance(node, ast.Call)
                 and isinstance(node.func, ast.Name)]
        self.assertIn('_publish_plan_bundle', [node.func.id for node in calls])
        direct_writers = [node.lineno for node in calls
                          if node.func.id in {'save', 'save_bytes', 'save_text', 'write_text', 'write_bytes'}]
        self.assertEqual(direct_writers, [], 'sync_plan 只能经 publish_plan_bundle 发布：' + str(direct_writers))

        public = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'sync_plan')
        self.assertIn('_asset_plan_result', [item.id for item in public.decorator_list if isinstance(item, ast.Name)])

    def test_l2_requires_injected_publishers_and_l3_owns_their_assembly(self) -> None:
        plan = parse(entity_file('asset_plan'))
        resume = parse(entity_file('asset_resume'))
        stage = parse(ROOT / 'orchestrator/stage_asset_gateways.py')
        plan_imports = [name.name for node in plan.body if isinstance(node, ast.ImportFrom)
                        and node.module == 'agent.core' for name in node.names]
        resume_imports = [name.name for node in resume.body if isinstance(node, ast.ImportFrom)
                          and node.module == 'agent.core' for name in node.names]
        self.assertNotIn('save', plan_imports)
        self.assertNotIn('save_bytes', plan_imports)
        self.assertNotIn('save_text', plan_imports)
        self.assertNotIn('save', resume_imports)
        functions = {node.name: node for node in plan.body if isinstance(node, ast.FunctionDef)}
        for name in ('publish_plan_bundle', 'update_planned'):
            self.assertIn('gateway', [arg.arg for arg in functions[name].args.kwonlyargs])
        resume_note = next(node for node in resume.body
                           if isinstance(node, ast.FunctionDef) and node.name == 'note_round')
        self.assertIn('publish', [arg.arg for arg in resume_note.args.kwonlyargs])
        stage_functions = {node.name for node in stage.body if isinstance(node, ast.FunctionDef)}
        self.assertTrue({'asset_plan_gateway', 'sync_asset_plan', 'update_asset_plan_fields',
                         'apply_asset_plan_gate_choice', 'note_asset_resume_round'} <= stage_functions)

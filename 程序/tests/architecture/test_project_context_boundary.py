import ast
import os
import unittest

from tests.architecture._layers import LAYERS

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _tree(name):
    with open(os.path.join(ROOT, name), encoding='utf-8') as handle:
        return ast.parse(handle.read())


class ProjectContextBoundaryTests(unittest.TestCase):
    def test_context_contract_is_l0_and_constructed_only_by_l3(self):
        self.assertEqual(LAYERS['project_context'], 0)
        delivery = _tree('delivery_import_service.py')
        calls = [node for node in ast.walk(delivery) if isinstance(node, ast.Call)
                 and getattr(node.func, 'id', '') == 'ProjectContext']
        self.assertEqual(calls, [], 'L2 只可消费 ProjectContext，不得自行构造')
        orchestrator = _tree('stage_execution_service.py')
        constructors = [node for node in ast.walk(orchestrator) if isinstance(node, ast.Call)
                        and isinstance(node.func, ast.Attribute)
                        and node.func.attr == 'snapshot'
                        and isinstance(node.func.value, ast.Name)
                        and node.func.value.id == 'ProjectContext']
        self.assertEqual(len(constructors), 1, '项目上下文必须由 L3 统一构造')

    def test_l2_uses_injected_stage_resolver_without_project_path_join(self):
        delivery = _tree('delivery_import_service.py')
        source = open(os.path.join(ROOT, 'delivery_import_service.py'), encoding='utf-8').read()
        self.assertIn("context.stage_resolver('delivery')", source)
        self.assertNotIn('project_stages', source)
        self.assertNotIn('os.path.join', source)

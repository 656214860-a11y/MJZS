import ast
import json
import os
import unittest
from pathlib import Path

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
        source = Path(ROOT, 'delivery_import_service.py').read_text(encoding='utf-8')
        self.assertIn("context.stage_resolver('delivery')", source)
        self.assertNotIn('project_stages', source)
        self.assertNotIn('os.path.join', source)

    def test_asset_domain_services_consume_but_do_not_construct_context(self):
        for name in ('asset_context.py', 'asset_batch_lifecycle.py',
                     'asset_batch_state_service.py', 'asset_batch_service.py',
                     'asset_detail_service.py', 'asset_generated_import_service.py'):
            tree = _tree(name)
            constructors = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
                            and getattr(node.func, 'id', '') == 'ProjectContext']
            self.assertEqual(constructors, [], name + ' 不得自行构造 ProjectContext')
            source = Path(ROOT, name).read_text(encoding='utf-8')
            self.assertIn('ProjectContext', source)

    def test_confirmation_service_consumes_context_and_l3_injects_it(self):
        source = Path(ROOT, 'confirm_gates.py').read_text(encoding='utf-8')
        self.assertIn('ProjectContext', source)
        self.assertIn("context.stage_resolver('continuity')", source)
        tree = _tree('confirm_gates.py')
        constructors = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
                        and getattr(node.func, 'id', '') == 'ProjectContext']
        self.assertEqual(constructors, [])
        orchestrator = Path(ROOT, 'stage_execution_service.py').read_text(encoding='utf-8')
        self.assertIn('def run_stage_confirmation_gate(', orchestrator)
        self.assertIn('context=project_context(project)', orchestrator)

    def test_second_roadmap_scope_is_a_complete_migration_ratchet(self):
        ledger = json.loads(Path(ROOT, '维护记录', '架构统一基数.json').read_text(encoding='utf-8'))
        item = ledger['第二项']
        adopters = set(item['adopters'])
        pending = set(item['pending'])
        exempt = set(item['exempt_items'])
        historical = set(item['historical_name_audit_pending'])
        self.assertFalse((adopters & pending) | (adopters & exempt) | (adopters & historical))
        self.assertFalse((pending & exempt) | (pending & historical) | (exempt & historical))
        self.assertEqual(len(adopters | pending | exempt | historical), 37)
        self.assertEqual(item['exempt_count'], len(exempt))
        reasons = item['exempt_reasons']
        self.assertEqual(set(reasons), exempt)
        for name, reason in reasons.items():
            self.assertRegex(reason, r'^R\d+：')
            source = Path(ROOT, name + '.py').read_text(encoding='utf-8')
            self.assertNotIn('ProjectContext', source,
                             name + ' 是经审计的纯计算服务，不应伪造上下文消费')
        missing = {name for name in historical
                   if not (Path(ROOT, name + '.py').is_file()
                           or Path(ROOT, name, '__init__.py').is_file())}
        self.assertEqual(missing, historical,
                         '历史名称必须单独追溯，不得伪装成已迁移或现行待办')

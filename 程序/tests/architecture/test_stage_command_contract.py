"""L4 阶段命令只能交给 L3 阶段命令登记表。"""
from __future__ import annotations

import ast
import unittest

from tests.architecture._layers import LAYERS
from tests.architecture._scan import ROOT, module_name, parse


_L4_COMMAND_MODULES = frozenset({'desktop', 'app', 'pet_ui'})
_DIRECT_STAGE_IMPLEMENTATIONS = frozenset({
    'stage_exec', 'stage_execution_service', 'stage_parallel', 'skill_orchestrator',
    'workflow', 'workflow_tasks',
})


def _dotted_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _dotted_name(node.value)
        return f'{parent}.{node.attr}' if parent else None
    return None


class StageCommandContractTests(unittest.TestCase):
    def test_l4_stage_command_callers_use_registry_entrypoint(self) -> None:
        """L4 不得绕过 start() 调用具体阶段实现。"""
        violations = []
        registry_calls = []
        for name in sorted(_L4_COMMAND_MODULES):
            path = ROOT / f'{name}.py'
            if not path.is_file():
                continue
            self.assertEqual(LAYERS.get(module_name(path)), 4, path.name)
            for node in ast.walk(parse(path)):
                if not isinstance(node, ast.Call):
                    continue
                called = _dotted_name(node.func)
                if called == 'stage_handler_registry.start':
                    registry_calls.append(f'{path.name}:{node.lineno}')
                elif called and called.split('.', 1)[0] in _DIRECT_STAGE_IMPLEMENTATIONS:
                    violations.append(f'{path.name}:{node.lineno} {called}')
        self.assertTrue(registry_calls, '未找到 L4 到 stage_handler_registry.start() 的阶段命令入口')
        self.assertEqual(
            violations, [],
            'L4 阶段启动必须经 stage_handler_registry.start():\n' + '\n'.join(violations),
        )

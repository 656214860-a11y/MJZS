"""阶段完成事件必须由产物核验服务把关。"""
from __future__ import annotations

import ast
import unittest

from tests.architecture._layers import LAYERS
from tests.architecture._scan import module_name, parse, production_files


_COMPLETION_EVENT = 'stage.completed'


def _dotted_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _dotted_name(node.value)
        return f'{parent}.{node.attr}' if parent else None
    return None


def _is_completion_emit(node: ast.Call) -> bool:
    return (
        bool(node.args)
        and isinstance(node.args[0], ast.Constant)
        and node.args[0].value == _COMPLETION_EVENT
        and _dotted_name(node.func) in {'pet_bus.emit_safe', 'self._emit', 'pet._emit'}
    )


def _imports_completion_service(tree: ast.Module) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.Import) and any(alias.name == 'stage_completion_service' for alias in node.names):
            return True
        if isinstance(node, ast.ImportFrom) and node.module == 'stage_completion_service':
            return True
    return False


class CompletionGateTests(unittest.TestCase):
    def test_completion_events_are_not_emitted_by_ui_or_agent_modules(self) -> None:
        """UI/Agent 不能以文字或页面提示直接宣告阶段完成。"""
        violations = []
        for path in production_files():
            tree = parse(path)
            if LAYERS.get(module_name(path)) != 4 and not module_name(path).startswith('agent'):
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and _is_completion_emit(node):
                    violations.append(f'{path.name}:{node.lineno} stage.completed')
        self.assertEqual(
            violations, [],
            'UI 或 Agent 不得直接发送 stage.completed，必须经 stage_completion_service:\n'
            + '\n'.join(violations),
        )

    def test_completion_event_senders_depend_on_completion_service(self) -> None:
        """任何发送者须显式依赖产物核验服务，而非模型文字。"""
        violations = []
        for path in production_files():
            tree = parse(path)
            if any(isinstance(node, ast.Call) and _is_completion_emit(node) for node in ast.walk(tree)):
                if module_name(path) != 'stage_completion_service' and not _imports_completion_service(tree):
                    violations.append(f'{path.name}: stage_completion_service import missing')
        self.assertEqual(
            violations, [],
            'stage.completed 发送前必须调用 stage_completion_service:\n' + '\n'.join(violations),
        )

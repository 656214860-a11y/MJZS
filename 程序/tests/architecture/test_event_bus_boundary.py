"""跨模块状态只能经 pet_bus 的安全发送器，播报日志不是状态总线。"""
from __future__ import annotations

import ast
import unittest
from pathlib import Path

from tests.architecture._scan import parse, production_files_recursive


_ROOT = Path(__file__).resolve().parents[2]
_TRUSTED_TRANSPORT = 'pet_bus.py'
_WRAPPERS = {
    'pet_agent.py': 'emit_safe',
    'pet_ui.py': 'pet_bus.emit_safe',
}
_BROADCAST_CALLERS = {'desktop.py', 'pet_ui.py'}


def _dotted_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _dotted_name(node.value)
        return f'{parent}.{node.attr}' if parent else None
    return None


def _function(tree: ast.Module, name: str) -> ast.FunctionDef | None:
    return next((node for node in ast.walk(tree)
                 if isinstance(node, ast.FunctionDef) and node.name == name), None)


def _direct_bus_emits(tree: ast.Module) -> list[int]:
    """只识别项目持有的总线变量，避免把任意第三方 emit 误判为状态事件。"""
    return [node.lineno for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and _dotted_name(node.func) in {'bus.emit', 'self.bus.emit'}]


def _broadcaster_calls(tree: ast.Module) -> list[int]:
    return [node.lineno for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and (_dotted_name(node.func) == 'self.broadcaster.broadcast'
                 or _dotted_name(node.func) == 'broadcaster.broadcast'
                 or (isinstance(node.func, ast.Attribute) and node.func.attr == 'broadcast'
                     and isinstance(node.func.value, ast.Call)
                     and _dotted_name(node.func.value.func) == 'Broadcaster'))]


class EventBusBoundaryTests(unittest.TestCase):
    def test_only_pet_bus_implements_direct_bus_emit(self) -> None:
        violations = []
        for path in production_files_recursive():
            if path.name == _TRUSTED_TRANSPORT:
                continue
            violations.extend(f'{path.name}:{line}' for line in _direct_bus_emits(parse(path)))
        self.assertEqual(
            violations, [],
            '跨模块状态不得直调 Bus.emit，必须经 pet_bus.emit_safe 或受控 _emit 包装器：\n'
            + '\n'.join(violations),
        )

    def test_only_declared_wrappers_are_allowed(self) -> None:
        actual = {}
        for path in production_files_recursive():
            function = _function(parse(path), '_emit')
            if function is not None:
                actual[path.name] = function
        self.assertEqual(set(actual), set(_WRAPPERS), '新增 _emit 包装器必须先登记事件总线边界')
        for filename, expected in _WRAPPERS.items():
            calls = {_dotted_name(node.func) for node in ast.walk(actual[filename])
                     if isinstance(node, ast.Call)}
            self.assertIn(expected, calls, f'{filename}._emit 必须委托 pet_bus.emit_safe')
            self.assertFalse(calls & {'bus.emit', 'self.bus.emit'},
                             f'{filename}._emit 不得绕过安全发送器')

    def test_broadcaster_is_text_log_not_cross_module_state_bus(self) -> None:
        violations = []
        for path in production_files_recursive():
            if path.name in _BROADCAST_CALLERS:
                continue
            violations.extend(f'{path.name}:{line}' for line in _broadcaster_calls(parse(path)))
        self.assertEqual(
            violations, [],
            'Broadcaster 只可用于 desktop/pet_ui 的用户可见文本日志，状态通知必须走 pet_bus：\n'
            + '\n'.join(violations),
        )

    def test_scanners_reject_bypass_canaries(self) -> None:
        self.assertEqual(_direct_bus_emits(ast.parse('bus.emit("stage.started", stage="script")')), [1])
        self.assertEqual(_direct_bus_emits(ast.parse('self.bus.emit("stage.started", stage="script")')), [1])
        self.assertEqual(_broadcaster_calls(ast.parse('broadcaster.broadcast("【完成】x")')), [1])

"""业务右键菜单必须经 ContextMenu，保证定位与 grab 释放行为一致。"""
from __future__ import annotations

import ast
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]


def _direct_menu_calls(tree):
    calls = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr != 'Menu':
            continue
        owner = node.func.value
        if isinstance(owner, ast.Name) and owner.id == 'tk':
            calls.append(node.lineno)
    return calls


class ContextMenuBoundaryTests(unittest.TestCase):
    def test_business_modules_do_not_construct_tk_menus(self):
        actual = {}
        for path in ROOT.glob('*.py'):
            if path.name == 'ui_widgets.py':
                continue
            lines = _direct_menu_calls(ast.parse(path.read_text(encoding='utf-8')))
            if lines:
                actual[path.name] = lines
        self.assertEqual(actual, {},
                         '业务菜单必须经 ContextMenu 创建：' + str(actual))


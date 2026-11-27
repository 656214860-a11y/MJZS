"""业务右键菜单必须经 ContextMenu，保证定位与 grab 释放行为一致。"""
from __future__ import annotations

import ast
import unittest

from tests.architecture._scan import EXCLUDED_PARTS, ROOT


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

    def test_all_production_modules_do_not_construct_tk_menus(self):
        actual = {}
        for path in ROOT.rglob('*.py'):
            relative = path.relative_to(ROOT)
            if (path.name == 'ui_widgets.py' or path.name.startswith('test')
                    or EXCLUDED_PARTS.intersection(relative.parts)):
                continue
            lines = _direct_menu_calls(ast.parse(path.read_text(encoding='utf-8')))
            if lines:
                actual[str(relative)] = lines
        self.assertEqual(actual, {},
                         '生产菜单必须经 ContextMenu 创建：' + str(actual))

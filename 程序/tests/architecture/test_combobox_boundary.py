"""下拉框视觉只允许由 ui_widgets.setup_styles 统一定义。"""
from __future__ import annotations

import ast
import unittest

from tests.architecture._scan import ROOT, parse


class ComboboxBoundaryTests(unittest.TestCase):
    def test_desktop_initializes_global_combobox_styles(self):
        tree = parse(ROOT / 'desktop.py')
        calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
                 and isinstance(node.func, ast.Name) and node.func.id == 'setup_styles']
        self.assertTrue(calls, '桌面根窗口必须初始化统一 TCombobox 样式')

    def test_business_pages_do_not_define_private_combobox_styles(self):
        violations = []
        for path in ROOT.rglob('*.py'):
            relative = path.relative_to(ROOT)
            if (path.name in {'ui_widgets.py', 'ui_theme.py'} or path.name.startswith('test')
                    or 'tests' in relative.parts or 'tasks_round' in relative.parts
                    or '维护记录' in relative.parts):
                continue
            for node in ast.walk(parse(path)):
                if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                        and node.func.attr in {'configure', 'map'}):
                    continue
                values = [arg.value for arg in node.args if isinstance(arg, ast.Constant)
                          and isinstance(arg.value, str)]
                if any('Combobox' in value for value in values):
                    violations.append(f'{relative}:{node.lineno}')
        self.assertEqual(violations, [],
                         '业务页不得覆盖 TCombobox 视觉，统一由 setup_styles 定义：'
                         + '; '.join(violations))

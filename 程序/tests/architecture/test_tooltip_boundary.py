"""首迁 SKILL 全文提示不得退回页面内手写 Tooltip。"""
from __future__ import annotations

import ast
import unittest

from tests.architecture._scan import EXCLUDED_PARTS, ROOT


class TooltipBoundaryTests(unittest.TestCase):
    def test_skill_name_tip_uses_the_unified_component(self):
        tree = ast.parse((ROOT / "ui" / "skill_panel.py").read_text(encoding="utf-8"))
        panel = next(node for node in tree.body if isinstance(node, ast.ClassDef)
                     and node.name == "Panel")
        method = next(node for node in panel.body if isinstance(node, ast.FunctionDef)
                      and node.name == "add_skill_control")
        calls = [node for node in ast.walk(method) if isinstance(node, ast.Call)]
        self.assertIn("Tooltip", [node.func.id for node in calls
                                   if isinstance(node.func, ast.Name)])
        self.assertNotIn("show_skill_tip", [node.func.attr for node in calls
                                             if isinstance(node.func, ast.Attribute)])

    def test_production_modules_do_not_construct_tooltip_toplevels(self):
        violations = {}
        for path in ROOT.rglob('*.py'):
            relative = path.relative_to(ROOT)
            if (path.name in {'ui_widgets.py', 'ui_tooltip.py', 'ui_theme.py'} or path.name.startswith('test')
                    or EXCLUDED_PARTS.intersection(relative.parts)):
                continue
            tree = ast.parse(path.read_text(encoding='utf-8'))
            lines = [node.lineno for node in ast.walk(tree) if isinstance(node, ast.Call)
                     and isinstance(node.func, ast.Attribute)
                     and isinstance(node.func.value, ast.Name)
                     and node.func.value.id == 'tk' and node.func.attr == 'Toplevel']
            if lines:
                violations[str(relative)] = lines
        self.assertEqual(violations, {},
                         '业务提示窗口必须经 Tooltip 或 BaseDialog：' + str(violations))

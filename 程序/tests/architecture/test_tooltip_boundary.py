"""首迁 SKILL 全文提示不得退回页面内手写 Tooltip。"""
from __future__ import annotations

import ast
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]


class TooltipBoundaryTests(unittest.TestCase):
    def test_skill_name_tip_uses_the_unified_component(self):
        tree = ast.parse((ROOT / "skill_panel.py").read_text(encoding="utf-8"))
        panel = next(node for node in tree.body if isinstance(node, ast.ClassDef)
                     and node.name == "Panel")
        method = next(node for node in panel.body if isinstance(node, ast.FunctionDef)
                      and node.name == "add_skill_control")
        calls = [node for node in ast.walk(method) if isinstance(node, ast.Call)]
        self.assertIn("Tooltip", [node.func.id for node in calls
                                   if isinstance(node.func, ast.Name)])
        self.assertNotIn("show_skill_tip", [node.func.attr for node in calls
                                             if isinstance(node.func, ast.Attribute)])

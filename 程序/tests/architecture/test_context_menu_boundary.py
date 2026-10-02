"""首迁右键菜单不得退回页面内裸建 ``tk.Menu``。"""
from __future__ import annotations

import ast
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]


def _call_name(node: ast.Call) -> str:
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
        return f"{func.value.id}.{func.attr}"
    return ""


class ContextMenuBoundaryTests(unittest.TestCase):
    def test_chat_bubble_menu_uses_the_unified_component(self):
        tree = ast.parse((ROOT / "desktop.py").read_text(encoding="utf-8"))
        desktop = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "Desktop")
        method = next(node for node in desktop.body if isinstance(node, ast.FunctionDef) and node.name == "open_bubble_menu")
        calls = [_call_name(node) for node in ast.walk(method) if isinstance(node, ast.Call)]
        self.assertIn("ContextMenu", calls)
        self.assertNotIn("tk.Menu", calls)


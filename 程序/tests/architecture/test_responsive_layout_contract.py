"""P2：主要桌面页面必须复用统一的响应式布局原语。"""
from __future__ import annotations

import ast
import unittest
from pathlib import Path

from tests.architecture._scan import entity_file


ROOT = Path(__file__).resolve().parents[2]
PAGES = frozenset({'desktop.py', 'app.py', 'storyboard_files.py', 'asset_batch.py'})


def _imports_flow_bar(path: Path) -> bool:
    tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
    return any(
        isinstance(node, ast.ImportFrom)
        and node.module == 'responsive_ui'
        and any(alias.name == 'FlowBar' for alias in node.names)
        for node in ast.walk(tree)
    )


class ResponsiveLayoutContractTests(unittest.TestCase):
    def test_primary_desktop_pages_use_the_shared_wrapping_action_bar(self) -> None:
        missing = sorted(name for name in PAGES if not _imports_flow_bar(entity_file(name[:-3])))
        self.assertEqual(
            missing, [],
            '主页面的操作栏请复用 responsive_ui.FlowBar：' + ', '.join(missing),
        )

    def test_flow_bar_preserves_requested_button_width_and_wraps(self) -> None:
        tree = ast.parse((ROOT / 'responsive_ui.py').read_text(encoding='utf-8'))
        flow_bar = next(
            node for node in tree.body
            if isinstance(node, ast.ClassDef) and node.name == 'FlowBar'
        )
        layout = next(
            node for node in flow_bar.body
            if isinstance(node, ast.FunctionDef) and node.name == 'layout'
        )
        source = ast.unparse(layout)
        self.assertIn('child.winfo_reqwidth()', source)
        self.assertIn('x + width > available', source)
        self.assertIn('child.place(', source)

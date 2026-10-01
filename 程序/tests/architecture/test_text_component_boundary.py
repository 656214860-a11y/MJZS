"""文字层级组件的页面边界：视觉参数只能留在 ui_widgets。"""
from __future__ import annotations

import ast
import unittest

from tests.architecture._scan import ROOT, parse


TEXT_PAGE_MODULES = ("skill_panel.py",)
FORBIDDEN_OPTIONS = frozenset({"font", "foreground", "fg"})


def _is_label_call(node: ast.Call) -> bool:
    func = node.func
    return (isinstance(func, ast.Attribute) and func.attr == "Label"
            and isinstance(func.value, ast.Name) and func.value.id in {"ttk", "tk"})


class TextComponentBoundaryTests(unittest.TestCase):
    def test_stage_panel_does_not_hand_style_raw_labels(self):
        """阶段配置页的提示/说明/进度必须经文字组件，不得退回局部样式。"""
        violations = []
        for filename in TEXT_PAGE_MODULES:
            tree = parse(ROOT / filename)
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call) or not _is_label_call(node):
                    continue
                options = {keyword.arg for keyword in node.keywords if keyword.arg}
                invalid = sorted(options & FORBIDDEN_OPTIONS)
                if invalid:
                    violations.append(f"{filename}:{node.lineno} {', '.join(invalid)}")
        self.assertEqual(violations, [],
                         "页面文字须用 HintLabel/DescriptionBlock/ProgressLabel："
                         + "; ".join(violations))

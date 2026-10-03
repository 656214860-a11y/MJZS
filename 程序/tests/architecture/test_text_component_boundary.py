"""文字层级组件的页面边界：视觉参数只能留在 ui_widgets。"""
from __future__ import annotations

import ast
import unittest

from tests.architecture._scan import ROOT, parse


TEXT_PAGE_COMPONENTS = {
    "skill_panel.py": ("HintLabel", "DescriptionBlock", "ProgressLabel"),
    "agent/prompt_optimizer.py": ("DescriptionBlock",),
    "seedream_settings.py": ("DescriptionBlock", "ProgressLabel"),
    "qwen_setup.py": ("DescriptionBlock", "ProgressLabel"),
    "tts_settings.py": ("DescriptionBlock", "ProgressLabel"),
}
FORBIDDEN_OPTIONS = frozenset({"font", "foreground", "fg"})


def _is_label_call(node: ast.Call) -> bool:
    func = node.func
    return (isinstance(func, ast.Attribute) and func.attr == "Label"
            and isinstance(func.value, ast.Name) and func.value.id in {"ttk", "tk"})


class TextComponentBoundaryTests(unittest.TestCase):
    def test_migrated_pages_import_their_text_components(self):
        """已迁移页面必须继续经 ui_widgets 的文字语义组件。"""
        for filename, expected in TEXT_PAGE_COMPONENTS.items():
            tree = parse(ROOT / filename)
            imported = {
                alias.name
                for node in ast.walk(tree)
                if isinstance(node, ast.ImportFrom) and node.module == "ui_widgets"
                for alias in node.names
            }
            self.assertTrue(set(expected) <= imported,
                            f"{filename} 应导入：{', '.join(expected)}")

    def test_migrated_pages_do_not_hand_style_raw_labels(self):
        """迁移页面的提示/说明/进度不得退回局部文字样式。"""
        violations = []
        for filename in TEXT_PAGE_COMPONENTS:
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

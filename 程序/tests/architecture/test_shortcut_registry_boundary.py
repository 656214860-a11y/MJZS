"""首迁聊天记录快捷键不得退回页面内直接绑定。"""
from __future__ import annotations

import ast
from pathlib import Path
import unittest

from tests.architecture._scan import desktop_text

ROOT = Path(__file__).resolve().parents[2]
EXCLUDED_PARTS = {"tests", "tasks_round", "维护记录", ".git", "__pycache__"}


def _raw_accelerator_bindings(path: Path) -> list[str]:
    """Find direct Ctrl/Command command bindings outside the registry itself."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    violations = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == "bind" and node.args):
            continue
        sequence = node.args[0]
        if not (isinstance(sequence, ast.Constant) and isinstance(sequence.value, str)):
            continue
        if sequence.value.lower().startswith(("<control-", "<command-")):
            violations.append(f"{path.relative_to(ROOT)}:{node.lineno} {sequence.value}")
    return violations


class ShortcutRegistryBoundaryTests(unittest.TestCase):
    def test_ctrl_and_command_accelerators_are_registered_recursively(self):
        """业务页面不得绕过登记表直接绑定跨平台命令快捷键。"""
        violations = []
        for path in ROOT.rglob("*.py"):
            if path.name == "ui_shortcuts.py" or any(part in EXCLUDED_PARTS for part in path.parts):
                continue
            violations.extend(_raw_accelerator_bindings(path))
        self.assertEqual(violations, [], "快捷键须经 ShortcutRegistry：" + "; ".join(violations))

    def test_chat_bubble_copy_is_registered_through_the_unified_registry(self):
        text = desktop_text()  # R1499：Desktop 源码分布在 desktop.py 与迁出的 Mixin 模块
        self.assertIn('self.shortcuts.bind(box,', text)
        self.assertNotIn("box.bind('<Control-c>'", text)
        self.assertNotIn("box.bind('<Control-C>'", text)
        ast.parse(text)

    def test_existing_accelerator_pages_keep_registry_calls(self):
        for filename, marker in {
            "app.py": "self.shortcuts.bind(self.prompt,",
            "desktop.py": "self.shortcuts.bind(box,",
            "storyboard_table_ui.py": "ShortcutRegistry().bind(tree,",
        }.items():
            source = desktop_text() if filename == "desktop.py" else (ROOT / filename).read_text(encoding="utf-8")
            self.assertIn(marker, source, filename)

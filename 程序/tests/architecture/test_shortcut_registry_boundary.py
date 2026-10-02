"""首迁聊天记录快捷键不得退回页面内直接绑定。"""
from __future__ import annotations

import ast
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]


class ShortcutRegistryBoundaryTests(unittest.TestCase):
    def test_chat_bubble_copy_is_registered_through_the_unified_registry(self):
        text = (ROOT / 'desktop.py').read_text(encoding='utf-8')
        self.assertIn('self.shortcuts.bind(box,', text)
        self.assertNotIn("box.bind('<Control-c>'", text)
        self.assertNotIn("box.bind('<Control-C>'", text)
        ast.parse(text)

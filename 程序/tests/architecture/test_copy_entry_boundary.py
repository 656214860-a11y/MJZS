# -*- coding: utf-8 -*-
"""文本复制必须集中到可锁定、可反馈、可脱敏的唯一入口。"""
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
EXCLUDED_PARTS = {"tests", "tasks_round", "维护记录", "skills", ".git", "__pycache__"}


class CopyEntryBoundaryTests(unittest.TestCase):
    def test_clipboard_writes_only_live_in_the_shared_copy_entry(self):
        offenders = []
        for path in ROOT.rglob('*.py'):
            if (path.name == 'prompt_window.py'
                    or any(part in EXCLUDED_PARTS for part in path.parts)):
                continue
            if 'clipboard_append' in path.read_text(encoding='utf-8'):
                offenders.append(path.relative_to(ROOT).as_posix())
        self.assertEqual(offenders, [])

    def test_shared_entry_locks_writes_and_masks_status_preview(self):
        source = (ROOT / 'prompt_window.py').read_text(encoding='utf-8')
        self.assertIn('with hold_clipboard()', source)
        self.assertIn('def copy_preview(', source)
        self.assertIn('_SECRET_VALUE', source)

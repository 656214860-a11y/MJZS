"""Codex diagnostic transport and non-dispatch contract."""
import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import codex_paste


class CodexPasteDiagnosticsTests(unittest.TestCase):
    def test_deadline_and_diagnostics_round_trip(self):
        diagnostics = {'window_count': 1, 'windows': [{'index': 1, 'categories': ['editor-count'], 'editor_count': 0}]}
        receipt = {'ok': False, 'reason': '未找到输入框', 'send_dispatched': False, 'diagnostics': diagnostics}
        def run(args, **kwargs):
            payload = json.loads(Path(args[args.index('-PayloadFile') + 1]).read_text(encoding='utf-8'))
            self.assertEqual(payload['deadline'], 45)
            self.assertTrue(payload['diagnostic'])
            self.assertGreaterEqual(kwargs['timeout'], 85)
            return SimpleNamespace(stdout=json.dumps(receipt), stderr='', returncode=0)
        with patch.object(codex_paste.subprocess, 'run', side_effect=run):
            self.assertEqual(codex_paste.paste_existing('title', 'private prompt', diagnostic=True, deadline_seconds=45), receipt)

    def test_default_deadline_and_legacy_receipt(self):
        receipt = {'ok': True, 'reason': '已填入', 'send_dispatched': False}
        def run(args, **kwargs):
            payload = json.loads(Path(args[-1]).read_text(encoding='utf-8'))
            self.assertEqual(payload['deadline'], 15)
            self.assertEqual(kwargs['timeout'], 55)
            return SimpleNamespace(stdout=json.dumps(receipt), stderr='', returncode=0)
        with patch.object(codex_paste.subprocess, 'run', side_effect=run):
            self.assertEqual(codex_paste.paste_existing('title', 'prompt'), receipt)

    def test_diagnostic_collector_has_no_input_dispatch(self):
        source = Path(codex_paste.__file__).with_suffix('.ps1').read_text(encoding='utf-8-sig')
        collector = source.split('function Get-Diagnostics{', 1)[1].split('function Target-Window{', 1)[0]
        for forbidden in ('SendWait', '.Invoke(', 'Complete-Task', 'SetFocus(', 'SetText(', 'SetForegroundWindow('):
            self.assertNotIn(forbidden, collector)
        self.assertIn('Get-Diagnostics', source)
        branch = source.split('if($diagnostic){Finish $true', 1)[1].split('\n', 1)[0]
        self.assertNotIn('SendWait', branch)
        self.assertNotIn('Invoke', branch)
        self.assertLess(source.index('if($diagnostic){Finish $true'), source.index('$edit.SetFocus()'))
        for category in ('header-not-found', 'editor-count', 'editor-name-mismatch', 'process-path-mismatch', 'handle-zero', 'stable-too-low'):
            self.assertIn(category, collector)

    def test_new_task_uses_longer_deadline(self):
        source = Path(codex_paste.__file__).with_name('desktop.py').read_text(encoding='utf-8')
        self.assertTrue("deadline_seconds=45 if result.get('mode')=='new' else 15" in source)


if __name__ == '__main__':
    unittest.main()

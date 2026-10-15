"""Desktop paste transport and manual-send contract."""
from tests.architecture._scan import desktop_text  # R1490：Desktop 方法分布在 desktop.py 与迁出的 Mixin 模块
import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import codex_paste


class CodexManualPasteTests(unittest.TestCase):
    def test_claude_targets_configured_program_and_preserves_manual_send(self):
        def run(args, **kwargs):
            payload = json.loads(Path(args[-1]).read_text(encoding='utf-8'))
            self.assertEqual(payload['program'], 'C:/Apps/Claude.exe')
            self.assertEqual(payload['prompt'], '请读取任务文件')
            self.assertNotIn('auto_send', payload)
            return SimpleNamespace(stdout='{"ok":true,"send_dispatched":false}', stderr='', returncode=0)
        with patch.object(codex_paste.subprocess, 'run', side_effect=run):
            result = codex_paste.paste_existing('任务', '请读取任务文件', program='C:/Apps/Claude.exe')
        self.assertTrue(result['ok'])
        self.assertFalse(result['send_dispatched'])

    def test_claude_timeout_identifies_the_correct_app(self):
        with patch.object(codex_paste.subprocess, 'run', side_effect=codex_paste.subprocess.TimeoutExpired('powershell', 55)):
            result = codex_paste.paste_existing('title', 'path', program='C:/Apps/Claude.exe')
        self.assertIn('Claude Desktop', result['reason'])
        self.assertFalse(result['send_dispatched'])

    def test_deadline_and_paste_only_payload(self):
        diagnostics = {'window_count': 1, 'windows': [{'index': 1, 'categories': ['editor-count'], 'editor_count': 0}]}
        receipt = {'ok': False, 'reason': '未找到输入框', 'send_dispatched': False, 'diagnostics': diagnostics}
        def run(args, **kwargs):
            payload = json.loads(Path(args[args.index('-PayloadFile') + 1]).read_text(encoding='utf-8'))
            self.assertEqual(payload['deadline'], 45)
            self.assertNotIn('auto_send', payload)
            self.assertNotIn('diagnostic', payload)
            self.assertGreaterEqual(kwargs['timeout'], 85)
            return SimpleNamespace(stdout=json.dumps(receipt), stderr='', returncode=0)
        with patch.object(codex_paste.subprocess, 'run', side_effect=run):
            self.assertEqual(codex_paste.paste_existing('title', 'private prompt', deadline_seconds=45), receipt)

    def test_default_deadline_and_legacy_receipt(self):
        receipt = {'ok': True, 'reason': '已填入', 'send_dispatched': False}
        def run(args, **kwargs):
            payload = json.loads(Path(args[-1]).read_text(encoding='utf-8'))
            self.assertEqual(payload['deadline'], 15)
            self.assertEqual(kwargs['timeout'], 55)
            return SimpleNamespace(stdout=json.dumps(receipt), stderr='', returncode=0)
        with patch.object(codex_paste.subprocess, 'run', side_effect=run):
            self.assertEqual(codex_paste.paste_existing('title', 'prompt'), receipt)

    def test_manual_paste_has_no_send_or_content_detection(self):
        source = Path(codex_paste.__file__).with_suffix('.ps1').read_text(encoding='utf-8-sig')
        for forbidden in ('Complete-Task', 'Get-Diagnostics', 'Test-SendContent', 'InvokePattern', '{ENTER}', 'auto_send'):
            self.assertNotIn(forbidden, source)
        self.assertIn('SendWait', source)
        desktop = desktop_text()
        self.assertNotIn('confirm_existing', desktop)
        self.assertNotIn('auto_send=True', desktop)
        self.assertIn("'prepared' if result['ok'] else 'failed'", desktop)

    def test_timeout_never_claims_a_send(self):
        with patch.object(codex_paste.subprocess, 'run', side_effect=codex_paste.subprocess.TimeoutExpired('powershell', 55)):
            result = codex_paste.paste_existing('title', 'prompt')
        self.assertFalse(result['ok'])
        self.assertFalse(result['send_dispatched'])
        self.assertIn('手动发送', result['reason'])

    def test_new_task_uses_longer_deadline(self):
        source = desktop_text()
        self.assertTrue("deadline_seconds=45 if result.get('mode')=='new' else 15" in source)


if __name__ == '__main__':
    unittest.main()

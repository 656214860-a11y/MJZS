# -*- coding: utf-8 -*-
"""远端 pre-receive 的 gitleaks 增强层：未装不阻断、干净放行、命中上报、故障不升级。"""
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

PROGRAM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROGRAM))
spec = importlib.util.spec_from_file_location(
    'remote_pre_receive', PROGRAM / '维护记录' / '基准脚本' / 'remote_pre_receive.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class GitleaksScanTests(unittest.TestCase):
    def _binary(self, folder):
        binary = Path(folder) / 'gitleaks'
        binary.write_text('#!/bin/sh\n', encoding='utf-8')
        return str(binary)

    def test_binary_missing_is_noop(self):
        with mock.patch.object(mod, 'GITLEAKS_BIN', '/不存在的/gitleaks'):
            self.assertEqual(mod.gitleaks_scan('old', 'new'), [])

    def test_clean_scan_returns_nothing(self):
        with tempfile.TemporaryDirectory() as folder:
            done = subprocess.CompletedProcess([], 0, '', '')
            with mock.patch.object(mod, 'GITLEAKS_BIN', self._binary(folder)), \
                 mock.patch.object(mod, '_gitleaks_config', return_value=('cfg', None)), \
                 mock.patch.object(mod.subprocess, 'run', return_value=done):
                self.assertEqual(mod.gitleaks_scan('old', 'new'), [])

    def test_findings_are_reported(self):
        with tempfile.TemporaryDirectory() as folder:
            def fake_run(args, **_kw):
                report = args[args.index('--report-path') + 1]
                Path(report).write_text(
                    json.dumps([{'RuleID': 'github-token', 'File': '程序/x.py', 'StartLine': 3}]),
                    encoding='utf-8')
                return subprocess.CompletedProcess(args, 1, '', '')
            with mock.patch.object(mod, 'GITLEAKS_BIN', self._binary(folder)), \
                 mock.patch.object(mod, '_gitleaks_config', return_value=('cfg', None)), \
                 mock.patch.object(mod.subprocess, 'run', side_effect=fake_run):
                self.assertEqual(mod.gitleaks_scan('old', 'new'),
                                 ['gitleaks:github-token 程序/x.py:3'])

    def test_scanner_failure_does_not_block(self):
        with tempfile.TemporaryDirectory() as folder:
            done = subprocess.CompletedProcess([], 128, '', 'boom')
            with mock.patch.object(mod, 'GITLEAKS_BIN', self._binary(folder)), \
                 mock.patch.object(mod, '_gitleaks_config', return_value=('cfg', None)), \
                 mock.patch.object(mod.subprocess, 'run', return_value=done):
                self.assertEqual(mod.gitleaks_scan('old', 'new'), [])




class RemotePreReceiveTests(unittest.TestCase):
    def test_secret_patterns_catch_high_confidence_shapes(self):
        diff = ('+++ b/程序/leak.py\n'
                '@@ -0,0 +1,3 @@\n'
                '+key = ' + 'ghp_' + 'a' * 36 + '\n'
                '+aws = ' + 'AKIA' + 'B' * 16 + '\n'
                '+slack = ' + 'xoxb-' + '1' * 20 + '\n'
                '+g = ' + 'AIza' + 'c' * 35 + '\n'
                '+pem = ' + '-----BEGIN ' + 'RSA ' + 'PRIVATE KEY-----' + '\n'
                '+ok = "normal line"\n')
        hits = mod.scan_added_lines(diff)
        rules = {hit.split(':')[-1] for hit in hits}
        self.assertEqual(rules, {'github-token', 'aws-access-key', 'slack-token',
                                 'google-api-key', 'private-key'})
        self.assertEqual(len(hits), 5)

    def test_clean_diff_has_no_hits(self):
        diff = '+++ b/程序/good.py\n@@ -0,0 +1 @@\n+x = 1\n'
        self.assertEqual(mod.scan_added_lines(diff), [])

    def test_hook_is_executable_python_and_covers_program_prefix(self):
        source = Path(mod.__file__).read_text(encoding='utf-8')
        compile(source, mod.__file__, 'exec')
        self.assertIn("PROGRAM_PREFIX = '程序/'", source)
        self.assertIn('core.quotepath=false', source)



if __name__ == '__main__':
    unittest.main()

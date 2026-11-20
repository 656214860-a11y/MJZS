# -*- coding: utf-8 -*-
"""远端 pre-receive 的 gitleaks 增强层与 master/main 证据门禁：未装不阻断、干净放行、命中上报、故障不升级。"""
import importlib.machinery
import importlib.util
import json
import os
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

loader = importlib.machinery.SourceFileLoader(
    'server_pre_receive_spec', str(PROGRAM / '维护记录' / '基准脚本' / 'server_hooks' / 'pre-receive'))
spec_hook = importlib.util.spec_from_loader(loader.name, loader)
spec_hook_mod = importlib.util.module_from_spec(spec_hook)
sys.modules[spec_hook.name] = spec_hook_mod
loader.exec_module(spec_hook_mod)


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


GREEN = {'credential_scan': {'ran': True, 'hits': []},
         'targeted': {'cmd': 'x', 'exit': 0, 'passed': 3, 'failed': 0}}
EVIDENCE_SAMPLES = (
    GREEN,
    {'credential_scan': {'ran': True, 'hits': ['a.py:1:openai-style-key']},
     'targeted': GREEN['targeted']},
    {'credential_scan': {'ran': False, 'hits': []}, 'targeted': GREEN['targeted']},
    {'credential_scan': GREEN['credential_scan'],
     'targeted': {'cmd': 'x', 'exit': 1, 'passed': 3, 'failed': 1}},
    {'credential_scan': GREEN['credential_scan'],
     'targeted': {'cmd': '', 'exit': 0, 'passed': 0, 'failed': 0, 'skipped': 'docs-only'}},
    {'credential_scan': GREEN['credential_scan'],
     'targeted': {'cmd': '', 'exit': 0, 'passed': 0, 'failed': 0, 'skipped': 'trust-me'}},
    {'credential_scan': GREEN['credential_scan'], 'targeted': {}},
    'not-json',
)


def _git(root, *args):
    env = dict(os.environ, GIT_AUTHOR_NAME='t', GIT_AUTHOR_EMAIL='t@t',
               GIT_COMMITTER_NAME='t', GIT_COMMITTER_EMAIL='t@t')
    done = subprocess.run(['git', *args], cwd=root, env=env,
                          capture_output=True, text=True, encoding='utf-8')
    assert done.returncode == 0, done.stderr
    return done.stdout.strip()


def _commit(root, subject, files):
    for name, text in files.items():
        path = Path(root) / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')
        _git(root, 'add', name)
    _git(root, 'commit', '-q', '-m', subject)
    return _git(root, 'rev-parse', 'HEAD')


class EvidenceGateTests(unittest.TestCase):
    """master/main 证据门禁：与 server_hooks/pre-receive 同口径。"""

    def test_round_of_parses_only_round_subjects(self):
        self.assertEqual(mod.round_of('R2527: 改代码'), 2527)
        self.assertIsNone(mod.round_of('R2527-FAIL: 诊断'))
        self.assertIsNone(mod.round_of('merge whatever'))
        self.assertIsNone(mod.round_of('R2527 改代码'))

    def test_evidence_problem_verdicts(self):
        for sample in EVIDENCE_SAMPLES:
            raw = sample if isinstance(sample, str) else json.dumps(sample)
            self.assertEqual(mod.evidence_problem(raw) == '',
                             spec_hook_mod.evidence_problem(raw) == '',
                             '与 server_hooks/pre-receive 判定不一致: %r' % (sample,))

    def test_check_push_guards_only_protected_refs(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            _git(root, 'init', '-q', '-b', 'master')
            base = _commit(root, 'R2526: 基线', {'程序/a.py': 'x = 1\n'})
            sha = _commit(root, 'R2527: 改代码', {'程序/a.py': 'x = 2\n'})
            repo = str(root / '.git')
            self.assertTrue(any('缺少' in p for p in mod.check_push(base, sha, 'refs/heads/master', repo=repo)))
            self.assertEqual(mod.check_push(base, sha, 'refs/heads/codex/work', repo=repo), [])
            self.assertEqual(mod.check_push(sha, mod.ZERO, 'refs/heads/master', repo=repo),
                             ['不允许删除 refs/heads/master'])
            self.assertEqual(mod.check_push(mod.ZERO, sha, 'refs/heads/master', repo=repo), [])

    def test_check_push_rejects_non_fast_forward(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            _git(root, 'init', '-q', '-b', 'master')
            base = _commit(root, 'R2526: 基线', {'程序/a.py': 'x = 1\n'})
            old = _commit(root, 'R2527: 旧尖端', {'程序/a.py': 'x = 2\n'})
            _git(root, 'reset', '--hard', base)
            new = _commit(root, 'R2528: 改写', {'程序/a.py': 'x = 3\n'})
            repo = str(root / '.git')
            reason = ['拒绝非快进更新 refs/heads/master：禁止强推改写主干']
            self.assertEqual(mod.check_push(old, new, 'refs/heads/master', repo=repo), reason)
            self.assertEqual(spec_hook_mod.check_push(old, new, 'refs/heads/master', repo=repo), reason)
            self.assertEqual(mod.check_push(old, new, 'refs/heads/codex/work', repo=repo), [])
            self.assertTrue(any('缺少' in item for item in mod.check_push(base, new, 'refs/heads/master', repo=repo)))

    def test_check_push_passes_with_green_evidence(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            _git(root, 'init', '-q', '-b', 'master')
            base = _commit(root, 'R2526: 基线', {'程序/a.py': 'x = 1\n'})
            sha = _commit(root, 'R2527: 改代码',
                          {'程序/a.py': 'x = 2\n',
                           '程序/tasks_round/evidence/R2527.json': json.dumps(GREEN)})
            self.assertEqual(mod.check_push(base, sha, 'refs/heads/master',
                                            repo=str(root / '.git')), [])


if __name__ == '__main__':
    unittest.main()

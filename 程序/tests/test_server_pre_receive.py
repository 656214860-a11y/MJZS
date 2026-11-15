"""服务器端 pre-receive 的判据：R2527 起的源码轮次提交必须带绿色证据，与 round_evidence.judge 同口径（对应 G5）。"""
from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PROGRAM = Path(__file__).resolve().parent.parent
HOOK = PROGRAM / '维护记录' / '基准脚本' / 'server_hooks' / 'pre-receive'
loader = importlib.machinery.SourceFileLoader('pre_receive_for_tests', str(HOOK))
spec = importlib.util.spec_from_loader(loader.name, loader)
hook = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = hook
loader.exec_module(hook)

spec2 = importlib.util.spec_from_file_location('round_evidence_for_prereceive',
                                               PROGRAM / '维护记录' / '基准脚本' / 'round_evidence.py')
evidence = importlib.util.module_from_spec(spec2)
sys.modules[spec2.name] = evidence
spec2.loader.exec_module(evidence)

GREEN = {'credential_scan': {'ran': True, 'hits': []}, 'targeted': {'cmd': 'x', 'exit': 0, 'passed': 3, 'failed': 0}}
SAMPLES = (
    GREEN,
    {'credential_scan': {'ran': True, 'hits': ['a.py:1:openai-style-key']}, 'targeted': GREEN['targeted']},
    {'credential_scan': {'ran': False, 'hits': []}, 'targeted': GREEN['targeted']},
    {'credential_scan': GREEN['credential_scan'], 'targeted': {'cmd': 'x', 'exit': 1, 'passed': 3, 'failed': 1}},
    {'credential_scan': GREEN['credential_scan'], 'targeted': {'cmd': '', 'exit': 0, 'passed': 0, 'failed': 0, 'skipped': 'docs-only'}},
    {'credential_scan': GREEN['credential_scan'], 'targeted': {'cmd': '', 'exit': 0, 'passed': 0, 'failed': 0, 'skipped': 'trust-me'}},
    {'credential_scan': GREEN['credential_scan'], 'targeted': {}},
)


def git(root, *args):
    env = dict(os.environ, GIT_AUTHOR_NAME='t', GIT_AUTHOR_EMAIL='t@t', GIT_COMMITTER_NAME='t', GIT_COMMITTER_EMAIL='t@t')
    done = subprocess.run(['git', *args], cwd=root, env=env, capture_output=True, text=True, encoding='utf-8')
    assert done.returncode == 0, done.stderr
    return done.stdout.strip()


def commit(root, subject, files):
    for name, text in files.items():
        path = Path(root) / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')
        git(root, 'add', name)
    git(root, 'commit', '-q', '-m', subject)
    return git(root, 'rev-parse', 'HEAD')


class ServerPreReceiveTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        git(self.root, 'init', '-q', '-b', 'master')
        self.base = commit(self.root, 'R2526: 基线', {'程序/a.py': 'x = 1\n'})

    def push(self, sha, ref='refs/heads/master'):
        return hook.check_push(self.base, sha, ref, repo=str(self.root / '.git'))

    def test_verdict_matches_round_evidence_judge_on_every_sample(self):
        with tempfile.TemporaryDirectory() as folder:
            for index, sample in enumerate(SAMPLES):
                with self.subTest(sample=index):
                    Path(folder, 'R9999.json').write_text(json.dumps(sample), encoding='utf-8')
                    scan_ok, tests_ok, _ = evidence.judge(9999, Path(folder))
                    self.assertEqual(hook.evidence_problem(json.dumps(sample)) == '', scan_ok and tests_ok)

    def test_source_round_without_evidence_is_rejected(self):
        sha = commit(self.root, 'R2527: 改代码', {'程序/a.py': 'x = 2\n'})
        self.assertIn('缺少', self.push(sha)[0])

    def test_source_round_with_green_evidence_passes(self):
        sha = commit(self.root, 'R2527: 改代码', {'程序/a.py': 'x = 2\n',
                                                '程序/tasks_round/evidence/R2527.json': json.dumps(GREEN)})
        self.assertEqual(self.push(sha), [])

    def test_red_evidence_is_rejected(self):
        red = dict(GREEN, targeted={'cmd': 'x', 'exit': 1, 'passed': 1, 'failed': 1})
        sha = commit(self.root, 'R2527: 改代码', {'程序/a.py': 'x = 2\n',
                                                '程序/tasks_round/evidence/R2527.json': json.dumps(red)})
        self.assertIn('未通过', self.push(sha)[0])

    def test_docs_commits_old_rounds_fail_checkpoints_and_other_refs_pass_without_evidence(self):
        self.assertEqual(self.push(commit(self.root, 'R2527: 文档', {'程序/说明.md': '文档\n'})), [])
        self.assertEqual(self.push(commit(self.root, 'R2100: 老轮次', {'程序/a.py': 'x = 3\n'})), [])
        self.assertEqual(self.push(commit(self.root, 'R2530-FAIL: 诊断', {'程序/a.py': 'x = 4\n'})), [])
        sha = commit(self.root, 'R2531: 改代码', {'程序/a.py': 'x = 5\n'})
        self.assertEqual(self.push(sha, ref='refs/heads/codex/work'), [])

    def test_deleting_master_is_rejected(self):
        self.assertEqual(hook.check_push(self.base, hook.ZERO, 'refs/heads/master', repo=str(self.root / '.git')),
                         ['不允许删除 refs/heads/master'])


if __name__ == '__main__':
    unittest.main()

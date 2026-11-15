"""DORA 类指标报告：用临时 git 仓库构造提交序列，断言各指标算对（对应 O1／O3／O4／O5）。"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PROGRAM = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('dora_report_for_tests', PROGRAM / 'scripts' / 'dora_report.py')
dora = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = dora
spec.loader.exec_module(dora)

DAY = 86400
BASE = 1_700_000_000


def git(root, *args, when=None):
    env = dict(os.environ, GIT_AUTHOR_NAME='t', GIT_AUTHOR_EMAIL='t@t', GIT_COMMITTER_NAME='t',
               GIT_COMMITTER_EMAIL='t@t')
    if when is not None:
        env['GIT_AUTHOR_DATE'] = env['GIT_COMMITTER_DATE'] = '%d +0000' % when
    done = subprocess.run(['git', *args], cwd=root, env=env, capture_output=True, text=True, encoding='utf-8')
    assert done.returncode == 0, done.stderr
    return done.stdout


def commit(root, subject, files, when, body=''):
    for name in files:
        path = Path(root) / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(path.read_text(encoding='utf-8') + 'x\n' if path.exists() else 'x\n', encoding='utf-8')
        git(root, 'add', name)
    git(root, 'commit', '-q', '-m', subject + ('\n\n' + body if body else ''), when=when)


class DoraReportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        git(self.root, 'init', '-q', '-b', 'master')

    def test_rework_counts_only_rounds_followed_by_a_fix_to_the_same_module(self):
        commit(self.root, 'R1: 加 a', ['程序/a.py'], BASE)
        commit(self.root, 'R2: 修复 a 的空指针', ['程序/a.py'], BASE + 2 * DAY)
        commit(self.root, 'R3: 加 b', ['程序/b.py'], BASE + 3 * DAY)
        commits = dora.collect(self.root)
        count, considered, hot = dora.reworked(commits)
        self.assertEqual((count, considered), (1, 2))
        self.assertEqual(hot['a'], 1)

    def test_fix_after_seven_days_does_not_count(self):
        commit(self.root, 'R1: 加 a', ['程序/a.py'], BASE)
        commit(self.root, 'R2: 修复 a', ['程序/a.py'], BASE + 8 * DAY)
        self.assertEqual(dora.reworked(dora.collect(self.root))[:2], (0, 1))

    def test_fail_checkpoints_and_agent_grouping(self):
        commit(self.root, 'R1: 好', ['程序/a.py'], BASE, body='Agent: swe-2')
        commit(self.root, 'R2-FAIL: 坏', ['程序/b.py'], BASE + 60, body='Agent: swe-2')
        commit(self.root, 'R3: 无标注', ['程序/c.py'], BASE + 120)
        groups = dora.by_agent(dora.collect(self.root))
        self.assertEqual(groups, {'swe-2': (2, 1), '未标注': (1, 0)})

    def test_lead_time_runs_from_first_branch_commit_to_the_merge(self):
        commit(self.root, 'R1: 起点', ['程序/a.py'], BASE)
        git(self.root, 'checkout', '-q', '-b', 'codex/wip-R2')
        commit(self.root, 'R2: 分支提交', ['程序/b.py'], BASE + 3600)
        git(self.root, 'checkout', '-q', 'master')
        commit(self.root, 'R9: 主干上的另一个提交', ['程序/c.py'], BASE + 4000)
        git(self.root, 'merge', '-q', '--no-ff', 'codex/wip-R2', '-m', 'R3: 合入 codex/wip-R2 到 master（合并轮）：x',
            when=BASE + 7200)
        commits = dora.collect(self.root)
        self.assertEqual(dora.lead_times(self.root, commits), [7200 - 3600])

    def test_red_dwell_pairs_first_red_with_the_next_green(self):
        history = self.root / 'h.jsonl'
        rows = [{'at': '2026-01-01T10:00:00', 'ok': True}, {'at': '2026-01-01T11:00:00', 'ok': False},
                {'at': '2026-01-01T12:00:00', 'ok': False}, {'at': '2026-01-01T15:00:00', 'ok': True}]
        history.write_text('\n'.join(json.dumps(row) for row in rows) + '\n', encoding='utf-8')
        self.assertEqual(dora.red_dwell(history), [4 * 3600])

    def test_missing_history_means_insufficient_data(self):
        self.assertIsNone(dora.red_dwell(self.root / 'none.jsonl'))
        commit(self.root, 'R1: x', ['程序/a.py'], BASE)
        report = dora.render(self.root, None, self.root / 'none.jsonl')
        self.assertIn('数据不足', report)
        self.assertIn('启发式', report)

    def test_modules_ignore_tests_docs_and_records(self):
        files = {'程序/a.py', '程序/tests/test_a.py', '程序/docs/x.md', '程序/维护记录/y.json', '程序/agent/core.py'}
        self.assertEqual(dora.modules_of(files), {'a', 'agent'})


if __name__ == '__main__':
    unittest.main()

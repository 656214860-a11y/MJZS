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
A, B, C, D = ('a' * 40, 'b' * 40, 'c' * 40, 'd' * 40)
SAMPLE = 'abcdef1234'  # 早期自检写进真实历史的样例行用的 head，不是完整提交号


def full_run(clock, head, failed=None, seconds=600):
    """一行全量记录：``failed`` 为 None 是绿，列表是红（空列表＝红了但没留下失败文件名）。"""
    return {'at': '2026-01-01T%s:00' % clock, 'head': head, 'ok': failed is None, 'seconds': seconds,
            'failed_files': list(failed or [])}


def write_history(path, rows):
    path.write_text('\n'.join(row if isinstance(row, str) else json.dumps(row) for row in rows) + '\n', encoding='utf-8')
    return path


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
        rows = [{'at': '2026-01-01T10:00:00', 'ok': True, 'head': A}, {'at': '2026-01-01T11:00:00', 'ok': False, 'head': B},
                {'at': '2026-01-01T12:00:00', 'ok': False, 'head': C}, {'at': '2026-01-01T15:00:00', 'ok': True, 'head': D}]
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

    def test_report_separates_flaky_files_from_persistent_ones(self):
        commit(self.root, 'R1: x', ['程序/a.py'], BASE)
        history = write_history(self.root / 'h.jsonl', [
            full_run('09:00', A, ['test_perf']), full_run('09:20', A),
            full_run('10:00', B, ['test_broken']), full_run('10:20', B, ['test_broken']),
            full_run('11:00', C, ['test_broken']), full_run('12:00', D), full_run('12:30', SAMPLE, ['test_alpha'])])
        report = dora.render(self.root, None, history)
        self.assertIn('有效全量 6 次（绿 2／红 4）', report)
        self.assertIn('另有 1 行无效记录未计入', report)
        self.assertIn('最近 6 次（从旧到新）：红绿红红红绿。', report)
        self.assertIn('| 只有偶发、疑似偶发的文件 | 1 | 25.0% |', report)
        self.assertIn('| 含持续红的文件（连续 3 次及以上） | 3 | 75.0% |', report)
        self.assertIn('| test_perf | 偶发 | 1 | 1 | 1 | 1 | 2026-01-01T09:00:00 |', report)
        self.assertIn('| test_broken | 3 | 1 | 3 | 2026-01-01T11:00:00 |', report)
        self.assertNotIn('test_alpha', report)


class RedBreakdownTests(unittest.TestCase):
    """全量红灯归因：偶发看「同一个提交红绿不一」，持续红看「连续 3 次完整全量都红」。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.history = Path(self.tmp.name) / 'h.jsonl'

    def breakdown(self, rows):
        valid, _dropped = dora.history_rows(write_history(self.history, rows))
        return dora.red_breakdown(valid)

    def test_sample_rows_do_not_bend_the_red_dwell(self):
        write_history(self.history, [full_run('10:00', A), full_run('10:30', SAMPLE, ['test_alpha']),
                                     full_run('10:40', SAMPLE), full_run('11:00', B, ['test_x']), full_run('13:00', C)])
        self.assertEqual(dora.red_dwell(self.history), [2 * 3600])

    def test_rows_without_a_full_commit_id_or_a_readable_time_are_dropped_and_counted(self):
        rows = [full_run('10:00', A), full_run('10:30', SAMPLE, ['test_alpha']), '{"at": "2026-01-01T10:35',
                dict(full_run('10:40', B), at='昨天'), full_run('11:00', C)]
        valid, dropped = dora.history_rows(write_history(self.history, rows))
        self.assertEqual([row['head'] for row in valid], [A, C])
        self.assertEqual(dropped, 3)
        self.assertEqual(dora.history_rows(self.history.with_name('none.jsonl')), (None, 0))

    def test_window_keeps_only_rows_from_since_onwards(self):
        rows = [full_run('10:00', SAMPLE, ['test_alpha']), full_run('10:30', A), full_run('11:00', B), full_run('12:00', C)]
        everything, _dropped = dora.history_rows(write_history(self.history, rows))
        valid, dropped = dora.history_rows(self.history, since=everything[1]['stamp'])
        self.assertEqual([row['head'] for row in valid], [B, C])
        self.assertEqual(dropped, 0, '统计窗之前的行不保留也不计数，哪怕它本身无效')

    def test_same_commit_red_then_green_marks_the_file_flaky(self):
        runs, files = self.breakdown([full_run('10:00', A, ['test_perf']), full_run('10:20', A),
                                      full_run('11:00', B, ['test_perf']), full_run('12:00', C)])
        info = files['test_perf']
        self.assertEqual((info['kind'], info['reds'], info['flips'], info['streaks']), ('偶发', 2, 1, [1, 1]))
        self.assertEqual(runs, {'偶发': [2, 1200], '持续红': [0, 0], '未定': [0, 0], '没有失败文件名': [0, 0]})

    def test_three_reds_in_a_row_are_persistent_and_own_the_run(self):
        runs, files = self.breakdown([full_run('10:00', A, ['test_broken', 'test_perf']), full_run('10:20', A, ['test_broken']),
                                      full_run('11:00', B, ['test_broken']), full_run('12:00', C)])
        info = files['test_broken']
        self.assertEqual((info['kind'], info['streaks'], info['flips']), ('持续红', [3], 0))
        self.assertEqual(files['test_perf']['kind'], '偶发', '同一提交上另一次完整的红没有红它，也算红绿不一')
        self.assertEqual(runs['持续红'], [3, 1800], '有文件正处在持续红里，这次红就不能记到偶发头上')
        self.assertEqual(runs['偶发'], [0, 0])

    def test_a_red_without_file_names_is_listed_apart_and_proves_nothing(self):
        runs, files = self.breakdown([full_run('10:00', A, ['test_x']), full_run('10:10', A, [], seconds=1),
                                      full_run('10:30', A, ['test_x']), full_run('11:00', B)])
        info = files['test_x']
        self.assertEqual((info['kind'], info['flips'], info['streaks']), ('未定', 0, [2]))
        self.assertEqual(runs['没有失败文件名'], [1, 1])
        self.assertEqual(runs['未定'], [2, 1200])

    def test_repeated_short_reds_without_proof_are_only_suspected(self):
        runs, files = self.breakdown([full_run('10:00', A, ['test_y']), full_run('11:00', B),
                                      full_run('12:00', C, ['test_y']), full_run('13:00', D)])
        info = files['test_y']
        self.assertEqual((info['kind'], info['flips'], info['streaks']), ('疑似偶发', 0, [1, 1]))
        self.assertEqual(runs['偶发'], [2, 1200])


if __name__ == '__main__':
    unittest.main()

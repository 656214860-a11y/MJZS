"""U12：观察期失败占比与连续失败告警；样本不足不判回滚。"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import release_watch  # noqa: E402

NOW = 1_000_000.0


def rows(states, step=60):
    return [{'created': NOW - 3600 + index * step, 'state': state} for index, state in enumerate(states)]


class ReleaseWatchTests(unittest.TestCase):
    def test_too_few_samples_never_roll_back(self):
        report = release_watch.assess(rows(['failed'] * 4), NOW, baseline=0.0)
        self.assertFalse(report['rollback'])
        self.assertTrue(any('不足' in alert for alert in report['alerts']))

    def test_share_above_double_baseline_rolls_back(self):
        report = release_watch.assess(rows(['failed', 'failed', 'succeeded', 'succeeded', 'succeeded']), NOW, baseline=0.1)
        self.assertTrue(report['rollback'])
        self.assertEqual(report['share'], 0.4)

    def test_without_baseline_only_reports(self):
        report = release_watch.assess(rows(['failed'] * 6), NOW)
        self.assertFalse(report['rollback'])
        self.assertEqual(report['streak'], 6)
        self.assertTrue(any('连续失败' in alert for alert in report['alerts']))

    def test_old_and_running_rows_are_ignored(self):
        old = [{'created': NOW - 48 * 3600, 'state': 'failed'}]
        running = [{'created': NOW - 10, 'state': 'running'}]
        self.assertEqual(release_watch.assess(old + running, NOW)['samples'], 0)

    def test_since_cuts_off_earlier_runs(self):
        report = release_watch.assess(rows(['failed'] * 6), NOW, since=NOW - 3600 + 4 * 60)
        self.assertEqual(report['samples'], 2)


if __name__ == '__main__':
    unittest.main()

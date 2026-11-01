"""U12：发布后观察的失败占比上限（用户裁定 20%）与连续失败告警。"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import release_watch as watch

NOW = 1_000_000.0


def rows(states):
    return [{'created': NOW - 100 + index, 'state': state} for index, state in enumerate(states)]


class ReleaseWatchTests(unittest.TestCase):
    def test_share_over_twenty_percent_recommends_rollback(self):
        report = watch.assess(rows(['succeeded'] * 7 + ['failed'] * 3), now=NOW)
        self.assertEqual(report['samples'], 10)
        self.assertTrue(report['rollback'])
        self.assertTrue(any('超过上限 20%' in alert for alert in report['alerts']))

    def test_share_at_or_under_limit_does_not(self):
        report = watch.assess(rows(['succeeded'] * 4 + ['failed']), now=NOW)
        self.assertEqual(report['share'], 0.2)
        self.assertFalse(report['rollback'])

    def test_too_few_samples_never_roll_back(self):
        report = watch.assess(rows(['failed'] * 4), now=NOW)
        self.assertFalse(report['rollback'])
        self.assertEqual(report['streak'], 4)

    def test_baseline_rule_still_applies(self):
        states = ['succeeded'] * 9 + ['failed']
        self.assertFalse(watch.assess(rows(states), now=NOW)['rollback'])
        self.assertTrue(watch.assess(rows(states), now=NOW, baseline=0.04)['rollback'])


if __name__ == '__main__':
    unittest.main()

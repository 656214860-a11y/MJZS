# -*- coding: utf-8 -*-
"""usage_snapshot／usage_history：今日与项目累计、Decimal 金额、跨天归档、明细上限、重启恢复。"""
import calendar
import json
import tempfile
import time
import unittest
from pathlib import Path

from infra import usage_history
from infra.usage_snapshot import DETAIL_LIMIT, UsageSnapshot


def _at(day_stamp):
    """把北京时间 'YYYY-MM-DD HH:MM:SS' 转成 epoch（pet_llm.beijing 口径）。"""
    return calendar.timegm(time.strptime(day_stamp, '%Y-%m-%d %H:%M:%S')) - 8 * 3600


class UsageSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.project = Path(self.tmp.name)

    def test_record_call_grows_today_and_project_total(self):
        snap = UsageSnapshot(self.project)
        snap.record_call('script', 'gpt-x', 1200, cost='0.82', currency='CNY', request_id='r1')
        data = snap.current()
        self.assertEqual(data['today']['token_used'], 1200)
        self.assertEqual(data['today']['calls'], 1)
        self.assertEqual(data['project_total']['token_used'], 1200)
        self.assertEqual(data['project_total']['total_calls'], 1)
        self.assertEqual(data['today']['money_spent'], '0.82')
        self.assertEqual(data['project_total']['money_spent'], '0.82')
        self.assertEqual(len(data['today']['details']), 1)
        self.assertEqual(data['today']['details'][0]['tokens'], 1200)
        self.assertTrue((self.project / 'usage_summary.json').is_file())

    def test_money_uses_decimal_not_float(self):
        snap = UsageSnapshot(self.project)
        snap.record_call('a', 'm', 1, cost='0.1')
        snap.record_call('a', 'm', 1, cost='0.2')
        # float 0.1+0.2 会得到 0.30000000000000004；Decimal 必须精确为 0.3
        self.assertEqual(snap.current()['today']['money_spent'], '0.3')
        self.assertEqual(snap.current()['project_total']['money_spent'], '0.3')

    def test_day_rollover_archives_and_resets(self):
        clock = {'t': _at('2025-06-10 12:00:00')}
        snap = UsageSnapshot(self.project, clock=lambda: clock['t'])
        snap.record_call('a', 'm', 100, cost='1.5', currency='CNY')
        clock['t'] = _at('2025-06-11 09:00:00')
        snap.record_call('a', 'm', 50)
        data = snap.current()
        self.assertEqual(data['today']['token_used'], 50)
        self.assertEqual(data['today']['calls'], 1)
        self.assertEqual(data['project_total']['token_used'], 150)
        archived = json.loads((self.project / 'usage_history' / '2025-06.json')
                              .read_text(encoding='utf-8'))
        self.assertEqual(archived['days']['2025-06-10'],
                         {'tokens': 100, 'cost': '1.5', 'calls': 1})

    def test_details_capped_at_limit_dropping_oldest(self):
        snap = UsageSnapshot(self.project)
        for i in range(DETAIL_LIMIT + 5):
            snap.record_call('a', 'm', i)
        details = snap.current()['today']['details']
        self.assertEqual(len(details), DETAIL_LIMIT)
        self.assertEqual(details[0]['tokens'], 5)
        self.assertEqual(snap.current()['today']['token_used'],
                         sum(range(DETAIL_LIMIT + 5)))

    def test_project_total_survives_restart(self):
        snap = UsageSnapshot(self.project)
        snap.record_call('a', 'm', 700, cost='0.5', currency='CNY')
        snap.record_call('a', 'm', 300)
        again = UsageSnapshot(self.project)
        total = again.current()['project_total']
        self.assertEqual(total['token_used'], 1000)
        self.assertEqual(total['total_calls'], 2)
        self.assertEqual(total['money_spent'], '0.5')

    def test_missing_or_bad_summary_starts_from_zero(self):
        fresh = UsageSnapshot(self.project)
        total = fresh.current()['project_total']
        self.assertEqual(total['token_used'], 0)
        self.assertEqual(total['money_spent'], '0')
        (self.project / 'usage_summary.json').write_text('{bad json', encoding='utf-8')
        corrupt = UsageSnapshot(self.project)
        total = corrupt.current()['project_total']
        self.assertEqual(total['token_used'], 0)
        self.assertEqual(total['money_spent'], '0')

    def test_no_price_table_keeps_money_at_zero_not_fake(self):
        snap = UsageSnapshot(self.project)
        snap.record_call('a', 'm', 500)
        data = snap.current()
        self.assertEqual(data['today']['money_spent'], '0')
        self.assertEqual(data['currency'], '')


class UsageHistoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.project = Path(self.tmp.name)

    def test_this_month_missing_returns_empty_days(self):
        self.assertEqual(usage_history.this_month(self.project), {'days': {}})

    def test_record_today_overwrites_same_day(self):
        usage_history.record_today(self.project, '2025-06-10', 100, '1.5', 2, currency='CNY')
        usage_history.record_today(self.project, '2025-06-10', 120, '1.8', 3, currency='CNY')
        usage_history.record_today(self.project, '2025-06-11', 7, '0.1', 1)
        raw = json.loads((self.project / 'usage_history' / '2025-06.json')
                         .read_text(encoding='utf-8'))
        self.assertEqual(raw['days']['2025-06-10'], {'tokens': 120, 'cost': '1.8', 'calls': 3})
        self.assertEqual(raw['days']['2025-06-11'], {'tokens': 7, 'cost': '0.1', 'calls': 1})
        self.assertEqual(raw['currency'], 'CNY')


if __name__ == '__main__':
    unittest.main()

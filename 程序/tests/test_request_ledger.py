# -*- coding: utf-8 -*-
"""O29：请求级可对账台账——重试不重复结算、同一远端任务唯一账单、缺量记未知、取消不伪造退款。"""
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import model_pool
from pet_llm import RequestLedger, request_ledger_path


class RequestLedgerTests(unittest.TestCase):
    def test_invalid_usage_and_rates_do_not_produce_money(self):
        for value in (-1, float('nan'), float('inf'), True):
            with self.subTest(value=value), self.assertRaises(ValueError):
                RequestLedger().reserve('bad', 'seconds', value)
        ledger = RequestLedger(); ledger.settle('ok', kind='seconds', amount=2)
        for value in (-1, float('nan'), float('inf'), True):
            with self.subTest(rate=value), self.assertRaises(ValueError):
                ledger.report({'rates': {'seconds': value}})

    def test_money_separates_reservations_and_unknown_cost(self):
        ledger = RequestLedger()
        ledger.settle('done', kind='seconds', amount=3)
        ledger.reserve('pending', 'seconds', 2)
        ledger.mark_unknown('lost')
        money = ledger.report({'rates': {'seconds': 0.1}})['money']
        self.assertEqual(money['settled_amount'], 0.3)
        self.assertEqual(money['reserved_amount'], 0.2)
        self.assertFalse(money['complete'])
        self.assertEqual(money['unknown_requests'], 1)

    def test_reserve_is_idempotent_per_request_and_kind(self):
        ledger = RequestLedger()
        first = ledger.reserve('REQ-1', 'seconds', 5)
        again = ledger.reserve('REQ-1', 'seconds', 5)
        self.assertIs(first, again)
        self.assertEqual(len(ledger.entries), 1)
        self.assertEqual(first['state'], 'reserved')
        self.assertEqual(first['mode'], 'estimated')

    def test_settle_never_double_counts_on_retry(self):
        ledger = RequestLedger()
        ledger.reserve('REQ-1', 'tokens', 100)
        ledger.settle('REQ-1', amount=120)
        ledger.settle('REQ-1', amount=120)          # 重试/重复回调
        report = ledger.report()
        self.assertEqual(report['kinds']['tokens']['settled'], 120)
        self.assertEqual(len(ledger.entries), 1)

    def test_settle_reads_usage_totals_and_missing_usage_becomes_unknown(self):
        ledger = RequestLedger()
        ledger.settle('REQ-A', usage={'prompt_tokens': 10, 'completion_tokens': 4})
        self.assertEqual(ledger.entries[-1]['amount'], 14)
        self.assertEqual(ledger.entries[-1]['state'], 'settled')
        # 缺 usage：明确记未知，不记 0（0 会被当成免费）。
        entry = ledger.settle('REQ-B')
        self.assertEqual(entry['state'], 'unknown')
        self.assertIsNone(entry['amount'])
        report = ledger.report()
        self.assertEqual(report['kinds']['requests']['unknown'], 1)
        self.assertIn('REQ-B', report['unknown_ids'])

    def test_missing_usage_does_not_show_as_free(self):
        ledger = RequestLedger()
        ledger.settle('REQ-B')
        report = ledger.report()
        self.assertNotIn('money', report)
        self.assertEqual(report['kinds']['requests']['settled'], 0)

    def test_same_remote_task_links_to_one_bill(self):
        ledger = RequestLedger()
        ledger.reserve('REQ-1', 'seconds', 5, remote_task_id='task-9')
        ledger.reserve('REQ-2', 'seconds', 5)
        ledger.link('REQ-2', 'task-9')
        self.assertEqual(ledger.entries[0]['remote_task_id'], 'task-9')
        self.assertEqual(ledger.entries[1]['state'], 'duplicate')
        report = ledger.report()
        self.assertEqual(report['duplicate_ids'], ['REQ-2'])
        self.assertEqual(report['kinds']['seconds']['reserved'], 5)
        self.assertEqual(report['requests'], 1)

    def test_cancel_keeps_reported_usage_and_never_fakes_a_refund(self):
        ledger = RequestLedger()
        ledger.reserve('REQ-1', 'seconds', 5)
        ledger.settle('REQ-1', amount=6)
        ledger.cancel('REQ-1', reason='用户取消')
        entry = ledger.entries[0]
        self.assertEqual(entry['state'], 'cancelled')
        self.assertEqual(entry['mode'], 'reported')
        self.assertEqual(entry['amount'], 6)        # 已实报的用量不减，不伪造退款
        report = ledger.report()
        self.assertEqual(report['kinds']['seconds']['settled'], 6)
        self.assertIn('REQ-1', report['cancelled_ids'])

    def test_cancel_of_reserved_request_is_unknown_not_zero(self):
        ledger = RequestLedger()
        ledger.reserve('REQ-1', 'seconds', 5)
        ledger.cancel('REQ-1')
        entry = ledger.entries[0]
        self.assertEqual(entry['state'], 'cancelled')
        self.assertEqual(entry['mode'], 'unknown')
        self.assertIsNone(entry['amount'])

    def test_report_lists_kinds_separately(self):
        ledger = RequestLedger()
        ledger.reserve('T1', 'tokens', 100)
        ledger.settle('T1', amount=120)
        ledger.reserve('S1', 'seconds', 5)
        ledger.settle('S1', amount=6)
        ledger.reserve('I1', 'images', 2)
        report = ledger.report()
        self.assertEqual(report['kinds']['tokens']['settled'], 120)
        self.assertEqual(report['kinds']['seconds']['settled'], 6)
        self.assertEqual(report['kinds']['images']['reserved'], 2)
        self.assertNotIn('money', report)           # 没配价格表不猜金额

    def test_price_table_is_optional_dated_and_reports_missing_rates(self):
        ledger = RequestLedger()
        ledger.settle('T1', kind='tokens', amount=1000)
        ledger.settle('S1', kind='seconds', amount=10)
        priced = ledger.report({'version': '2026-10-12', 'at': '2026-10-12',
                                'rates': {'tokens': 0.001}})
        self.assertEqual(priced['money']['amount'], 1.0)
        self.assertEqual(priced['money']['table_version'], '2026-10-12')
        self.assertIn('seconds', priced['money']['missing_rates'])

    def test_save_and_load_round_trip(self):
        with tempfile.TemporaryDirectory() as td:
            ledger = RequestLedger(td)
            ledger.reserve('REQ-1', 'seconds', 5, remote_task_id='task-9')
            path = ledger.save()
            self.assertEqual(path, request_ledger_path(td))
            data = json.loads(path.read_text(encoding='utf-8'))
            self.assertEqual(data['entries'][0]['id'], 'REQ-1')
            restored = RequestLedger(td).load()
            self.assertEqual(restored.entries[0]['remote_task_id'], 'task-9')


class ProbeUsageNoteTests(unittest.TestCase):
    def test_probe_marks_possible_usage_and_records_unknown(self):
        record = model_pool.record({'model': 'm', 'base_url': 'https://x.test/v1',
                                    'wire_api': 'openai', 'key_env': 'TEST_KEY'})
        ledger = RequestLedger()

        def send(url, body, headers, timeout):
            return {'ok': True, 'status': 200, 'data': {'choices': [{'message': {'content': 'pong'}}]}}

        with (
            mock.patch.object(model_pool, 'status', lambda item, program=None: (True, '')),
            mock.patch.object(model_pool, 'key_of', lambda item, program=None: 'test-key'),
        ):
            result = model_pool.probe(record, send, None, ledger=ledger)
        self.assertTrue(result['ok'])
        self.assertEqual(result['usage_note'], model_pool.PROBE_USAGE_NOTE)
        self.assertIn('可能产生用量', model_pool.PROBE_USAGE_NOTE)
        self.assertEqual(len(ledger.entries), 1)
        self.assertEqual(ledger.entries[0]['state'], 'unknown')

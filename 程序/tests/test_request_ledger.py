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


class ModelMoneyBudgetTests(unittest.TestCase):
    def test_legacy_session_ledger_blocks_budget_without_mutating_history(self):
        with tempfile.TemporaryDirectory() as td:
            self.policy(td)
            old = RequestLedger(Path(td) / 'cloud_video' / 'old')
            old.settle('old-request', kind='seconds', amount=5)
            path = old.save()
            before = path.read_bytes()
            with self.assertRaisesRegex(ValueError, '旧视频会话费用'):
                RequestLedger(td).authorize_model('new', 'm', 'script', 1, 1)
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(RequestLedger(td).load().entries, [])

    def test_unaccounted_legacy_tasks_block_including_rejected_remote_requests(self):
        from agent.core import save
        for state in ('unknown', 'queued', 'downloaded', 'rejected'):
            with self.subTest(state=state), tempfile.TemporaryDirectory() as td:
                self.policy(td)
                save(Path(td) / 'cloud_video/old/data/state.json',
                     {'shots': {'shot': [{'state': state, 'charged': False}]}})
                with self.assertRaisesRegex(ValueError, '旧视频任务费用'):
                    RequestLedger(td).authorize_model('new', 'm', 'script', 1, 1)

    def test_preflight_rejections_and_accounted_tasks_do_not_block_budget(self):
        from agent.core import save
        with tempfile.TemporaryDirectory() as td:
            self.policy(td)
            ledger = RequestLedger(td)
            ledger.authorize_model('old', 'm', 'script', 1, 1)
            save(Path(td) / 'cloud_video/old/data/state.json', {'shots': {'shot': [
                {'money_request_id': 'old', 'state': 'unknown'},
                {'not_submitted': True, 'state': 'rejected'}]}})
            ledger.authorize_model('new', 'm', 'script', 1, 1)
            self.assertEqual(len(ledger.load().entries), 2)

    def test_corrupt_legacy_state_blocks_only_when_amount_cap_enabled(self):
        from agent.core import save
        with tempfile.TemporaryDirectory() as td:
            self.policy(td)
            save(Path(td) / 'cloud_video/old/data/state.json', {'shots': []})
            with self.assertRaisesRegex(ValueError, '旧视频任务状态损坏'):
                RequestLedger(td).authorize_model('new', 'm', 'script', 1, 1)
            self.policy(td, None)
            RequestLedger(td).authorize_model('new', 'm', 'script', 1, 1)

    def policy(self, folder, cap='1'):
        path = Path(folder) / 'cost_profile.json'
        path.write_text(json.dumps({'budget_amount': cap, 'price_table': {
            'currency': 'CNY', 'version': 'test-v1', 'model_rates': {
                'm': {'prompt_tokens': '0.01', 'completion_tokens': '0.02'}}}}), encoding='utf-8')
        return path

    def test_async_duplicate_receipt_is_counted_once_and_success_not_downgraded(self):
        with tempfile.TemporaryDirectory() as td:
            path = self.policy(td, '10')
            data = json.loads(path.read_text(encoding='utf-8'))
            data['price_table']['model_rates']['video'] = {'seconds': '0.1'}
            path.write_text(json.dumps(data), encoding='utf-8')
            ledger = RequestLedger(td)
            for rid in ('first', 'duplicate'):
                ledger.authorize_units(rid, 'video', 'video', 'videos', {'seconds': 5}, amount=1)
                ledger.settle_units(rid, amount=1, remote_task_id='same-remote-task')
            ledger.settle_units('first')
            self.assertEqual(ledger.load()._find('first')['money_state'], 'estimated')
            self.assertEqual(ledger._find('duplicate')['state'], 'duplicate')
            report = ledger.report(data['price_table'])
            self.assertEqual(report['money']['amount'], 0.5)
            self.assertEqual(report['model_costs']['CNY']['estimated_spent'], '0.5')
            self.assertEqual(report['model_costs']['CNY']['held'], '0')

    def test_image_and_text_share_budget_and_keep_unknown_cost(self):
        from pet_llm import BudgetRejected
        with tempfile.TemporaryDirectory() as td:
            path = self.policy(td, '0.8')
            data = json.loads(path.read_text(encoding='utf-8'))
            data['price_table']['model_rates']['image-m'] = {'images': '0.5'}
            path.write_text(json.dumps(data), encoding='utf-8')
            ledger = RequestLedger(td)
            with ledger.metered_units('image1', 'image-m', 'assets', 'images', 1):
                pass
            ledger.authorize_model('text1', 'm', 'script', 10, 10)
            with self.assertRaises(BudgetRejected):
                with ledger.metered_units('image2', 'image-m', 'keyframe', 'images', 1):
                    self.fail('must not send')
            self.assertEqual(len(ledger.load().entries), 2)
            report = ledger.report(data['price_table'])
            self.assertEqual(report['money']['amount'], 0.8)
            self.assertEqual(report['kinds']['images']['settled'], 1)
            # A timeout preserves the image reservation across restart.
            data['budget_amount'] = '1.3'
            path.write_text(json.dumps(data), encoding='utf-8')
            with self.assertRaises(TimeoutError):
                with ledger.metered_units('image3', 'image-m', 'assets', 'images', 1):
                    raise TimeoutError('test')
            restarted = RequestLedger(td).load()
            self.assertEqual(restarted._find('image3')['money_state'], 'unknown')
            self.assertEqual(restarted._find('image3')['budget_cost'], '0.5')
            with self.assertRaises(BudgetRejected):
                with restarted.metered_units('image4', 'image-m', 'assets', 'images', 1):
                    self.fail('must not send')

    def test_unknown_reservation_survives_restart_and_explicit_raise(self):
        with tempfile.TemporaryDirectory() as td:
            path = self.policy(td)
            first = RequestLedger(td)
            first.authorize_model('a', 'm', 'script', 20, 20)
            first.settle_model('a', {})
            restarted = RequestLedger(td)
            with self.assertRaisesRegex(ValueError, '超过项目金额预算'):
                restarted.authorize_model('b', 'm', 'script', 20, 20)
            self.policy(td, '2')
            restarted.authorize_model('b', 'm', 'script', 20, 20)
            self.assertEqual(restarted.entries[0]['budget_cost'], '0.60')
            self.assertEqual(restarted.entries[0]['money_state'], 'unknown')
            self.assertTrue(path.exists())

    def test_settlement_freezes_price_and_does_not_duplicate(self):
        with tempfile.TemporaryDirectory() as td:
            path = self.policy(td)
            ledger = RequestLedger(td)
            ledger.authorize_model('a', 'm', 'assistant', 20, 20)
            config = json.loads(path.read_text(encoding='utf-8'))
            config['price_table']['model_rates']['m']['prompt_tokens'] = '99'
            path.write_text(json.dumps(config), encoding='utf-8')
            ledger.settle_model('a', {'prompt_tokens': 10, 'completion_tokens': 5})
            ledger.settle_model('a', {'prompt_tokens': 10, 'completion_tokens': 5})
            self.assertEqual(ledger.entries[0]['budget_cost'], '0.20')
            self.assertEqual(ledger.entries[0]['price_version'], 'test-v1')
            self.assertEqual(len(ledger.entries), 1)
            money = ledger.report({'currency': 'CNY', 'rates': {'tokens': 99}})['money']
            self.assertEqual(money['settled_amount'], 0.2, '冻结模型费率不得再叠加通用Token费率')
            self.assertTrue(money['complete'])
            from usage_overview import cost_per_minute
            cost = cost_per_minute(td, 60, {'currency': 'CNY', 'rates': {'tokens': 99}},
                                   {'gpu': 0, 'storage': 0, 'bandwidth': 0, 'human': 0})
            self.assertEqual(cost['known_per_minute'], 0.2)
            ledger.settle_model('a', {})
            self.assertEqual(ledger.entries[0]['money_state'], 'estimated')
            with self.assertRaisesRegex(ValueError, '不能重复发送'):
                ledger.authorize_model('a', 'm', 'assistant', 1, 1)

    def test_concurrent_requests_share_one_ceiling(self):
        from concurrent.futures import ThreadPoolExecutor
        with tempfile.TemporaryDirectory() as td:
            self.policy(td, '0.60')
            def reserve(index):
                try:
                    RequestLedger(td).authorize_model(str(index), 'm', 'script', 20, 20)
                    return True
                except ValueError:
                    return False
            with ThreadPoolExecutor(max_workers=4) as pool:
                self.assertEqual(sum(pool.map(reserve, range(4))), 1)
            self.assertEqual(len(RequestLedger(td).load().entries), 1)

    def test_actual_overestimate_stops_next_request_without_erasing_spend(self):
        with tempfile.TemporaryDirectory() as td:
            self.policy(td)
            ledger = RequestLedger(td)
            ledger.authorize_model('a', 'm', 'script', 1, 1)
            ledger.settle_model('a', {'prompt_tokens': 200, 'completion_tokens': 10})
            with self.assertRaisesRegex(ValueError, '超过项目金额预算'):
                RequestLedger(td).authorize_model('b', 'm', 'script', 1, 1)
            self.assertEqual(RequestLedger(td).load().entries[0]['budget_cost'], '2.20')

    def test_invalid_policy_unpriced_history_and_corrupt_ledger_block(self):
        with tempfile.TemporaryDirectory() as td:
            self.policy(td)
            ledger = RequestLedger(td)
            with self.assertRaisesRegex(ValueError, '模型费率'):
                ledger.authorize_model('a', 'missing', 'script', 1, 1)
            ledger.reserve('old', 'seconds', 1)
            ledger.save()
            with self.assertRaisesRegex(ValueError, '未计价'):
                ledger.authorize_model('a', 'm', 'script', 1, 1)
            request_ledger_path(td).write_text('{broken', encoding='utf-8')
            with self.assertRaises(ValueError):
                ledger.authorize_model('a', 'm', 'script', 1, 1)
            self.assertEqual(request_ledger_path(td).read_text(encoding='utf-8'), '{broken')

    def test_concurrent_legacy_recording_keeps_all_entries(self):
        from concurrent.futures import ThreadPoolExecutor
        from pet_llm import record_request
        with tempfile.TemporaryDirectory() as td:
            with ThreadPoolExecutor(max_workers=4) as pool:
                results = list(pool.map(lambda n: record_request(td, str(n), 'images', 1), range(12)))
            self.assertTrue(all(results))
            self.assertEqual(len(RequestLedger(td).load().entries), 12)

    def test_other_process_cannot_enter_locked_ledger(self):
        import subprocess
        import sys
        import pet_llm
        with tempfile.TemporaryDirectory() as td:
            self.policy(td)
            script = ("import sys; sys.path.insert(0, sys.argv[1]); from pet_llm import RequestLedger\n"
                      "with RequestLedger(sys.argv[2]).transaction():\n"
                      " print('locked', flush=True)\n input()\n")
            child = subprocess.Popen([sys.executable, '-c', script, str(Path(pet_llm.__file__).parent), td],
                                     stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                     text=True, creationflags=subprocess.CREATE_NO_WINDOW)
            try:
                self.assertEqual(child.stdout.readline().strip(), 'locked')
                with self.assertRaisesRegex(ValueError, '正在更新'):
                    RequestLedger(td).authorize_model('a', 'm', 'script', 1, 1)
            finally:
                child.communicate('\n', timeout=10)
            self.assertEqual(child.returncode, 0)
            RequestLedger(td).authorize_model('a', 'm', 'script', 1, 1)


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

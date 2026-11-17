# -*- coding: utf-8 -*-
"""R3248：L1 可靠性止血——限流时钟注入与锁外分片睡眠、凭据分桶、Retry-After 60 秒上限、
结算兜底不丢付费结果、陈旧本地预留清扫、传输重放与降级链共用尝试预算。"""
import tempfile
import unittest
from unittest import mock

import infra.api_endpoints as api_endpoints
import infra.request_ledger as request_ledger_module
from infra.model_metering import REPLAYABLE_RETRY_STATUS, metered, replayable_retry
from infra.pet_llm import RequestLedger, request_ledger_path


class _Clock:
    def __init__(self, now=1000.0):
        self.now = now

    def __call__(self):
        return self.now


class _Ledger:
    def __init__(self, settle_error=None):
        self.calls = []
        self.settle_error = settle_error

    def authorize_model(self, *args):
        self.calls.append(('authorize', args))

    def settle_model(self, request_id, usage):
        self.calls.append(('settle', request_id, usage))
        if self.settle_error is not None:
            raise self.settle_error


class RetryDelayTests(unittest.TestCase):
    def test_retry_after_capped_at_60_seconds(self):
        self.assertEqual(api_endpoints._retry_delay(1, retry_after=3600), 60.0)
        self.assertEqual(api_endpoints._retry_delay(1, retry_after=30), 30.0)
        self.assertEqual(api_endpoints._retry_delay(1, retry_after=0), 0.0)

    def test_backoff_uses_real_random_jitter_and_can_be_disabled(self):
        deterministic = api_endpoints._retry_delay(2, jitter=False)
        self.assertAlmostEqual(deterministic, 0.5)
        samples = {round(api_endpoints._retry_delay(2), 4) for _ in range(40)}
        self.assertGreater(len(samples), 1)
        for value in samples:
            self.assertTrue(0.7 <= value <= 1.3, value)

    def test_status_zero_is_not_replayable(self):
        self.assertNotIn(0, REPLAYABLE_RETRY_STATUS)
        self.assertFalse(replayable_retry(0))
        for status in (408, 429, 500, 503):
            self.assertTrue(replayable_retry(status), status)


class RateLimitTests(unittest.TestCase):
    def test_wait_for_rpm_sleeps_in_slices_with_checkpoint(self):
        slept, checkpoints = [], []
        clock = _Clock()
        control = mock.Mock()
        control.checkpoint.side_effect = lambda: checkpoints.append(1)
        host = 'slice-rpm.test'
        with mock.patch.object(api_endpoints, '_CLOCK', clock), \
                mock.patch.object(api_endpoints, '_SLEEP', slept.append):
            api_endpoints.wait_for_rpm('https://' + host + '/v1', 60, control)
            api_endpoints.wait_for_rpm('https://' + host + '/v1', 60, control)
        self.assertEqual(slept, [0.5, 0.5])
        self.assertEqual(len(checkpoints), 2)

    def test_credential_separates_buckets_and_never_stores_plaintext(self):
        slept = []
        clock = _Clock()
        url = 'https://cred-rpm.test/v1'
        with mock.patch.object(api_endpoints, '_CLOCK', clock), \
                mock.patch.object(api_endpoints, '_SLEEP', slept.append):
            api_endpoints.wait_for_rpm(url, 60, credential='ENV_A')
            api_endpoints.wait_for_rpm(url, 60, credential='ENV_A')
            api_endpoints.wait_for_rpm(url, 60, credential='ENV_B')
            api_endpoints.wait_for_rpm(url, 60)
        self.assertEqual(slept, [0.5, 0.5])
        for key in api_endpoints._HOST_RATE_LIMITS:
            self.assertNotIn('ENV_A', key)
            self.assertNotIn('ENV_B', key)

    def test_rpm_change_updates_interval_without_resetting_schedule(self):
        slept = []
        clock = _Clock()
        url = 'https://retune-rpm.test/v1'
        with mock.patch.object(api_endpoints, '_CLOCK', clock), \
                mock.patch.object(api_endpoints, '_SLEEP', slept.append):
            api_endpoints.wait_for_rpm(url, 60, credential='K')
            api_endpoints.wait_for_rpm(url, 60, credential='K')
            clock.now = 1002.0
            api_endpoints.wait_for_rpm(url, 30, credential='K')
            clock.now = 1002.5
            api_endpoints.wait_for_rpm(url, 30, credential='K')
        bucket = api_endpoints._HOST_RATE_LIMITS[api_endpoints._bucket_key('retune-rpm.test', 'K')]
        self.assertAlmostEqual(bucket.interval, 2.0)
        # next=1004 保留：1002.5 时预约等待 1.5 秒（若重置为新桶则等待为 0）
        self.assertEqual(slept, [0.5, 0.5, 0.5, 0.5, 0.5])


    def test_rpm_ten_spaces_requests_by_six_seconds(self):
        slept = []
        clock = _Clock()
        with mock.patch.object(api_endpoints, '_CLOCK', clock), \
                mock.patch.object(api_endpoints, '_SLEEP', slept.append):
            api_endpoints.wait_for_rpm('https://ten-rpm.test/v1', 10)
            api_endpoints.wait_for_rpm('https://ten-rpm.test/v1', 10)
        self.assertGreaterEqual(sum(slept), 6.0)
        self.assertAlmostEqual(sum(slept), 6.0, places=3)

    def test_concurrent_callers_get_positive_wait_for_second(self):
        import threading
        clock = _Clock()
        barrier = threading.Barrier(2)
        local = threading.local()
        totals = []

        def fake_sleep(seconds):
            local.total = getattr(local, 'total', 0.0) + seconds

        def call():
            barrier.wait()
            api_endpoints.wait_for_rpm('https://conc-rpm.test/v1', 60)
            totals.append(getattr(local, 'total', 0.0))

        with mock.patch.object(api_endpoints, '_CLOCK', clock), \
                mock.patch.object(api_endpoints, '_SLEEP', fake_sleep):
            threads = [threading.Thread(target=call) for _ in range(2)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(10)
        self.assertFalse(any(thread.is_alive() for thread in threads))
        self.assertEqual(sorted(totals), [0.0, 1.0])

    def test_cancelled_wait_raises_within_half_second(self):
        import time as real_time
        slept = []
        clock = _Clock()
        control = mock.Mock()
        control.checkpoint.side_effect = [None, RuntimeError('cancelled')]
        with mock.patch.object(api_endpoints, '_CLOCK', clock), \
                mock.patch.object(api_endpoints, '_SLEEP', slept.append):
            api_endpoints.wait_for_rpm('https://cancel-rpm.test/v1', 60)
            start = real_time.monotonic()
            with self.assertRaises(RuntimeError):
                api_endpoints.wait_for_rpm('https://cancel-rpm.test/v1', 60, control)
            elapsed = real_time.monotonic() - start
        self.assertLess(elapsed, 0.5)
        self.assertEqual(slept, [0.5])


class _Opener:
    """每次 open 抛出一个新的 HTTP 500（真实链路里 5xx 走 HTTPError 分支）。"""

    def __init__(self):
        self.opens = 0

    def open(self, request, timeout=None):
        import io
        import urllib.error
        self.opens += 1
        raise urllib.error.HTTPError(str(request.full_url), 500, 'server error', {},
                                     io.BytesIO(b'{"error": "boom"}'))


class MeteredSettlementTests(unittest.TestCase):
    def test_settle_runs_when_usage_of_raises(self):
        ledger = _Ledger()

        def boom(_result):
            raise RuntimeError('usage parse failed')

        with self.assertRaises(RuntimeError):
            metered(ledger, ('r1', 'm', 's', 1, 1), lambda: {'ok': True}, boom)
        self.assertIn(('settle', 'r1', {}), ledger.calls)

    def test_settle_failure_still_returns_paid_result(self):
        ledger = _Ledger(settle_error=OSError('lock timeout'))
        with mock.patch('infra.diagnostic_capture.record_degradation') as degrade:
            result, usage, rejected = metered(
                ledger, ('r2', 'm', 's', 1, 1), lambda: {'ok': True, 'status': 200},
                lambda r: {'prompt_tokens': 5})
        self.assertIsNone(rejected)
        self.assertEqual(result['status'], 200)
        self.assertEqual(usage, {'prompt_tokens': 5})
        degrade.assert_called_once()

    def test_on_result_error_is_logged_not_raised_and_settle_still_runs(self):
        ledger = _Ledger()

        def bad_callback(_result, _usage):
            raise ValueError('diagnostic write failed')

        result, usage, rejected = metered(
            ledger, ('r3', 'm', 's', 1, 1), lambda: {'ok': True}, dict, on_result=bad_callback)
        self.assertIsNone(rejected)
        self.assertTrue(ledger.calls[-1][0] == 'settle')

    def test_settle_inner_diagnostic_failure_is_swallowed(self):
        ledger = _Ledger(settle_error=OSError('lock timeout'))
        with mock.patch('infra.diagnostic_capture.record_degradation',
                        side_effect=RuntimeError('diag down')):
            result, _usage, rejected = metered(
                ledger, ('r6', 'm', 's', 1, 1), lambda: {'ok': True}, dict)
        self.assertIsNone(rejected)
        self.assertTrue(result['ok'])

    def test_attempt_record_failure_is_logged_not_raised(self):
        class FoundLedger(_Ledger):
            def _find(self, request_id, kind=None):
                return {'id': request_id}

        ledger = FoundLedger()
        with mock.patch('infra.request_ledger.record_request_attempt',
                        side_effect=OSError('io error')):
            result, _usage, rejected = metered(
                ledger, ('r7', 'm', 's', 1, 1), lambda: {'ok': True, 'status': 200},
                lambda r: {'prompt_tokens': 1})
        self.assertIsNone(rejected)
        self.assertEqual(result['status'], 200)

    def test_non_dict_result_still_settles(self):
        ledger = _Ledger()
        result, usage, rejected = metered(
            ledger, ('r8', 'm', 's', 1, 1), lambda: 'raw', lambda r: {})
        self.assertEqual(result, 'raw')
        self.assertIsNone(rejected)
        self.assertIn(('settle', 'r8', {}), ledger.calls)


class StaleReservationTests(unittest.TestCase):
    def test_stale_local_reserved_becomes_unknown_remote_and_fresh_untouched(self):
        with tempfile.TemporaryDirectory() as td:
            ledger = RequestLedger(td, clock=lambda: 10000.0)
            ledger.entries = [
                {'id': 'old', 'kind': 'tokens', 'state': 'reserved', 'at': 2000.0,
                 'remote_task_id': None, 'amount': 1, 'money_state': 'reserved'},
                {'id': 'fresh', 'kind': 'tokens', 'state': 'reserved', 'at': 9900.0,
                 'remote_task_id': None, 'amount': 1},
                {'id': 'remote', 'kind': 'videos', 'state': 'reserved', 'at': 100.0,
                 'remote_task_id': 'task-1', 'amount': 1},
            ]
            ledger.save()
            restored = RequestLedger(td, clock=lambda: 10000.0).load()
        states = {entry['id']: entry['state'] for entry in restored.entries}
        self.assertEqual(states, {'old': 'unknown', 'fresh': 'reserved', 'remote': 'reserved'})
        old = next(entry for entry in restored.entries if entry['id'] == 'old')
        self.assertEqual(old['money_state'], 'unknown')


class TransactionLockTests(unittest.TestCase):
    def test_lock_wait_is_bounded_and_reports_busy(self):
        import msvcrt
        with tempfile.TemporaryDirectory() as td:
            ledger = RequestLedger(td)
            lock_path = request_ledger_path(td).with_suffix('.lock')
            lock_path.parent.mkdir(parents=True, exist_ok=True)
            stream = lock_path.open('a+b')
            try:
                if not lock_path.stat().st_size:
                    stream.write(b'0')
                    stream.flush()
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                with mock.patch.object(request_ledger_module, 'REQUEST_LOCK_WAIT_SECONDS', 0.3), \
                        mock.patch.object(request_ledger_module, 'REQUEST_LOCK_POLL_SECONDS', 0.05):
                    with self.assertRaises(ValueError):
                        with ledger.transaction():
                            pass
            finally:
                try:
                    stream.seek(0)
                    msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
                except OSError:
                    pass
                stream.close()

    def test_lock_wait_calls_checkpoint_between_polls(self):
        import msvcrt
        with tempfile.TemporaryDirectory() as td:
            ledger = RequestLedger(td)
            lock_path = request_ledger_path(td).with_suffix('.lock')
            lock_path.parent.mkdir(parents=True, exist_ok=True)
            stream = lock_path.open('a+b')
            try:
                if not lock_path.stat().st_size:
                    stream.write(b'0')
                    stream.flush()
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                control = mock.Mock()
                with mock.patch('contract.platform_tools.current_execution', return_value=control), \
                        mock.patch.object(request_ledger_module, 'REQUEST_LOCK_WAIT_SECONDS', 0.15), \
                        mock.patch.object(request_ledger_module, 'REQUEST_LOCK_POLL_SECONDS', 0.05):
                    with self.assertRaises(ValueError):
                        with ledger.transaction():
                            pass
            finally:
                try:
                    stream.seek(0)
                    msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
                except OSError:
                    pass
                stream.close()
            self.assertTrue(control.checkpoint.called)

    def test_transaction_roundtrip_still_saves(self):
        with tempfile.TemporaryDirectory() as td:
            ledger = RequestLedger(td)
            with ledger.transaction():
                ledger.entries.append({'id': 'x', 'kind': 'tokens', 'state': 'reserved',
                                       'at': ledger.clock(), 'amount': 1})
            restored = RequestLedger(td).load()
            self.assertEqual(restored.entries[0]['id'], 'x')

    def test_two_processes_authorize_and_settle_without_value_error(self):
        import subprocess
        import sys
        from pathlib import Path
        script = (
            "import sys\n"
            "sys.path.insert(0, sys.argv[1])\n"
            "from infra.request_ledger import RequestLedger\n"
            "ledger = RequestLedger(sys.argv[2])\n"
            "prefix = sys.argv[3]\n"
            "for i in range(20):\n"
            "    rid = prefix + '-' + str(i)\n"
            "    ledger.authorize_model(rid, 'm', 'script', 1, 1)\n"
            "    ledger.settle_model(rid, {'prompt_tokens': 1, 'completion_tokens': 1})\n"
            "print('done', flush=True)\n"
        )
        program = str(Path(__file__).resolve().parents[1])
        with tempfile.TemporaryDirectory() as td:
            procs = [subprocess.Popen([sys.executable, '-c', script, program, td, 'p%d' % n],
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                      creationflags=subprocess.CREATE_NO_WINDOW)
                     for n in range(2)]
            for proc in procs:
                _out, err = proc.communicate(timeout=180)
                self.assertEqual(proc.returncode, 0, err)
            ledger = RequestLedger(td).load()
        self.assertEqual(len(ledger.entries), 40)
        self.assertTrue(all(entry.get('state') == 'settled' for entry in ledger.entries))


class SettleLockTimeoutTests(unittest.TestCase):
    def test_settle_lock_timeout_degrades_without_raising(self):
        import msvcrt
        with tempfile.TemporaryDirectory() as td:
            ledger = RequestLedger(td)
            with ledger.transaction():
                ledger.entries.append({'id': 'r', 'kind': 'tokens', 'state': 'reserved',
                                       'at': ledger.clock(), 'amount': 5, 'money_state': 'reserved'})
            ledger2 = RequestLedger(td)
            ledger2.load()
            lock_path = request_ledger_path(td).with_suffix('.lock')
            stream = lock_path.open('a+b')
            try:
                if not lock_path.stat().st_size:
                    stream.write(b'0')
                    stream.flush()
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                with mock.patch.object(request_ledger_module, 'REQUEST_LOCK_WAIT_SECONDS', 0.2), \
                        mock.patch.object(request_ledger_module, 'REQUEST_LOCK_POLL_SECONDS', 0.02), \
                        mock.patch('infra.diagnostic_capture.record_degradation') as degrade:
                    ledger2.settle_units('r', amount=3)
                    ledger2.settle_model('r', {'prompt_tokens': 1, 'completion_tokens': 1})
            finally:
                try:
                    stream.seek(0)
                    msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
                except OSError:
                    pass
                stream.close()
            entry = ledger2._find('r')
            self.assertEqual(entry['state'], 'unknown')
            self.assertEqual(entry['money_state'], 'unknown')
            self.assertEqual(degrade.call_count, 2)

    def test_settle_lock_timeout_inner_failures_are_swallowed(self):
        with tempfile.TemporaryDirectory() as td:
            ledger = RequestLedger(td)
            ledger.entries = [{'id': 'r', 'kind': 'tokens', 'state': 'reserved',
                               'at': ledger.clock(), 'amount': 5}]
            exc = request_ledger_module.LedgerLockTimeout('busy')
            with mock.patch('infra.diagnostic_capture.record_degradation',
                            side_effect=RuntimeError('diag down')):
                request_ledger_module._settle_lock_timeout(ledger, 'r', exc)
            entry = ledger._find('r')
            self.assertEqual(entry['state'], 'unknown')
            self.assertNotIn('money_state', entry)
            with mock.patch.object(ledger, '_find', side_effect=RuntimeError('find down')):
                request_ledger_module._settle_lock_timeout(ledger, 'r', exc)

    def test_settle_missing_request_raises_value_error(self):
        with tempfile.TemporaryDirectory() as td:
            ledger = RequestLedger(td)
            with self.assertRaises(ValueError):
                ledger.settle_units('missing')
            with self.assertRaises(ValueError):
                ledger.settle_model('missing', {'prompt_tokens': 1, 'completion_tokens': 1})

    def test_attempt_record_edges(self):
        import infra.request_ledger as rl
        with tempfile.TemporaryDirectory() as td:
            ledger = RequestLedger(td)
            self.assertIsNone(rl.record_request_attempt(ledger, 'missing'))
            ledger.entries = [{'id': 'r', 'kind': 'tokens', 'state': 'settled',
                               'at': ledger.clock(), 'amount': 1, 'attempts': 'corrupt'}]
            entry = rl.record_request_attempt(ledger, 'r', status=500, error_class='http',
                                              retry_after=1.5, wire_api='chat', retry_count=2)
            self.assertEqual(len(entry['attempts']), 1)
            self.assertEqual(entry['attempts'][0]['status'], 500)
            self.assertEqual(entry['attempts'][0]['retry_count'], 2)


class AttemptBudgetTests(unittest.TestCase):
    def test_budget_is_shared_across_replays_and_exhausts(self):
        opener = _Opener()
        budget = [2]
        with mock.patch.object(api_endpoints, '_SLEEP', lambda _s: None):
            first = api_endpoints._http_transport('https://budget.test/v1', {'a': 1}, {}, 5,
                                                 opener=lambda: opener, attempt_budget=budget)
            self.assertFalse(first['ok'])
            self.assertEqual(first['status'], 500)
            self.assertEqual(opener.opens, 2)
            self.assertEqual(budget[0], 0)
            second = api_endpoints._http_transport('https://budget.test/v1', {'a': 1}, {}, 5,
                                                  opener=lambda: opener, attempt_budget=budget)
        self.assertEqual(opener.opens, 2)
        self.assertEqual(second['status'], 0)
        self.assertIn('上限', second['error'])

    def test_paid_posts_stay_within_three_for_default_chain(self):
        import io
        import urllib.error
        from pathlib import Path
        from infra.pet_llm import Client

        def env_dir(base):
            (Path(base) / '.env').write_text('DEEPSEEK_API_KEY=sk-test-123456\n', encoding='utf-8')
            return Path(base)

        with tempfile.TemporaryDirectory() as td:
            program = env_dir(td)
            opens = []

            def fail_open(self, request, timeout=None):
                opens.append(1)
                raise urllib.error.HTTPError(str(request.full_url), 500, 'err', {},
                                             io.BytesIO(b'{}'))

            with mock.patch('urllib.request.OpenerDirector.open', fail_open), \
                    mock.patch.object(api_endpoints, '_SLEEP', lambda _s: None):
                result = Client(program=program).ask('writing.breakdown', 'split')
        self.assertFalse(result['ok'])
        self.assertEqual(len(opens), 3)

    def test_default_replay_limit_unchanged_without_budget(self):
        opener = _Opener()
        with mock.patch.object(api_endpoints, '_SLEEP', lambda _s: None):
            result = api_endpoints._http_transport('https://budget2.test/v1', {'a': 1}, {}, 5,
                                                  opener=lambda: opener)
        self.assertEqual(opener.opens, api_endpoints.MAX_REPLAY_ATTEMPTS)
        self.assertFalse(result['ok'])


if __name__ == '__main__':
    unittest.main()

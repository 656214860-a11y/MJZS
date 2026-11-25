"""I10 命名执行器测试：有界队列 QuotaError、取消语义、供应商闸门、限时关闭。"""
import threading
import time
import unittest

import infra.executors as executors
from contract.infra_errors import ConfigError, QuotaError


class ExecutorCase(unittest.TestCase):
    def tearDown(self):
        try:
            executors.shutdown(wait=0.2)
        except Exception:
            pass
        executors._POOLS.clear()
        executors._VENDOR_GATES.clear()


class SubmitTests(ExecutorCase):
    def test_submit_runs_and_returns_future(self):
        future = executors.submit('io', lambda: 40 + 2, label='t-add')
        self.assertEqual(future.result(timeout=5), 42)
        self.assertTrue(future.done())

    def test_unknown_pool_and_bad_fn_rejected(self):
        with self.assertRaises(ConfigError):
            executors.submit('nope', lambda: None)
        with self.assertRaises(ConfigError):
            executors.submit('io', 'not-callable')

    def test_full_queue_raises_quota_error(self):
        saved = executors.QUEUE_LIMIT
        executors.QUEUE_LIMIT = 4
        try:
            gate = threading.Event()
            executors.submit('gpu', gate.wait, label='blocker')
            submitted = 0
            with self.assertRaises(QuotaError) as ctx:
                for index in range(64):
                    executors.submit('gpu', lambda: index, label='filler-%d' % index)
                    submitted += 1
            self.assertEqual(ctx.exception.code, 'E-QUOTA-EXCEEDED')
            self.assertLessEqual(submitted, 8)   # 1 worker 取走 + 4 槽，其余即满
        finally:
            executors.QUEUE_LIMIT = saved
            gate.set()

    def test_cancelled_before_start_never_runs(self):
        flag = executors.CancelFlag()
        flag.cancel()
        ran = []
        future = executors.submit('io', lambda: ran.append(1), cancel=flag)
        deadline = time.monotonic() + 5
        while not future.done() and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertTrue(future.cancelled())
        self.assertEqual(ran, [])

    def test_running_task_reads_cancel_marker(self):
        flag = executors.CancelFlag()
        started = threading.Event()
        seen = []

        def work():
            started.set()
            time.sleep(0.05)
            seen.append(flag.is_set())
            return 'ok'

        future = executors.submit('io', work, cancel=flag)
        self.assertTrue(started.wait(timeout=5))
        flag.cancel()
        self.assertEqual(future.result(timeout=5), 'ok')
        self.assertEqual(seen, [True])

    def test_task_exception_goes_to_future(self):
        def boom():
            raise ValueError('boom')
        future = executors.submit('io', boom)
        with self.assertRaises(ValueError):
            future.result(timeout=5)


class VendorGateTests(ExecutorCase):
    def test_vendor_limit_caps_concurrency(self):
        executors.set_vendor_limit('testvendor', 1)
        in_flight = {'now': 0, 'peak': 0}
        lock = threading.Lock()

        def work():
            with lock:
                in_flight['now'] += 1
                in_flight['peak'] = max(in_flight['peak'], in_flight['now'])
            time.sleep(0.05)
            with lock:
                in_flight['now'] -= 1
            return True

        futures = [executors.submit('network', work, vendor='testvendor',
                                    label='v%d' % i) for i in range(4)]
        for future in futures:
            self.assertTrue(future.result(timeout=10))
        self.assertEqual(in_flight['peak'], 1)
        status = executors.vendor_status()
        self.assertEqual(status['testvendor']['limit'], 1)
        self.assertEqual(status['testvendor']['in_flight'], 0)

    def test_network_workers_scale_with_vendor_limits(self):
        executors.set_vendor_limit('v-a', 2)
        executors.set_vendor_limit('v-b', 3)
        executors.submit('network', lambda: None, vendor='v-a')
        status = executors.pool_status()
        self.assertGreaterEqual(status['network']['workers'], 4)

    def test_set_vendor_limit_validates(self):
        with self.assertRaises(ConfigError):
            executors.set_vendor_limit('', 2)
        with self.assertRaises(ConfigError):
            executors.set_vendor_limit('x', 'abc')
        self.assertEqual(executors.set_vendor_limit('x', 0), 0)
        self.assertNotIn('x', executors.vendor_status())


class StreamPoolTests(ExecutorCase):
    def test_stream_runs_task_on_dedicated_thread(self):
        seen = []

        def work():
            seen.append(threading.current_thread().name)
            return 'done'

        future = executors.submit('stream', work, label='reader')
        self.assertEqual(future.result(timeout=5), 'done')
        self.assertEqual(seen, ['executor-stream'])
        status = executors.pool_status()
        self.assertIn('stream', status)

    def test_stream_cancelled_before_run_never_executes(self):
        flag = executors.CancelFlag()
        flag.cancel()
        ran = []
        future = executors.submit('stream', lambda: ran.append(1), cancel=flag)
        deadline = time.monotonic() + 5
        while not future.done() and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertTrue(future.cancelled())
        self.assertEqual(ran, [])

    def test_stream_shutdown_waits_bounded_and_logs(self):
        started = threading.Event()
        release = threading.Event()

        def work():
            started.set()
            release.wait(timeout=30)

        executors.submit('stream', work, label='straggler')
        self.assertTrue(started.wait(timeout=5))
        begin = time.monotonic()
        with self.assertLogs('executors', level='WARNING') as logs:
            executors.shutdown(wait=0.05)
        self.assertLess(time.monotonic() - begin, 3.0)
        self.assertTrue(any('stream' in line for line in logs.output))
        release.set()


class ShutdownTests(ExecutorCase):
    def test_shutdown_cancels_queued_tasks(self):
        gate = threading.Event()
        executors.submit('gpu', gate.wait, label='blocker')
        time.sleep(0.05)   # 等 gpu 唯一 worker 取走 blocker
        queued = [executors.submit('gpu', lambda i=i: i, label='q%d' % i)
                  for i in range(3)]
        started = time.monotonic()
        executors.shutdown(wait=0.2)
        self.assertLess(time.monotonic() - started, 3.0)
        for future in queued:
            self.assertTrue(future.cancelled())
        gate.set()

    def test_shutdown_waits_for_running_up_to_limit(self):
        started = threading.Event()
        release = threading.Event()
        done = []

        def work():
            started.set()
            release.wait(timeout=30)
            done.append(1)
            return 'finished'

        future = executors.submit('io', work, label='slow')
        self.assertTrue(started.wait(timeout=5))
        begin = time.monotonic()
        executors.shutdown(wait=0.2)
        self.assertLess(time.monotonic() - begin, 3.0)
        self.assertFalse(future.done())
        release.set()
        deadline = time.monotonic() + 5
        while not future.done() and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertEqual(done, [1])

    def test_submit_after_shutdown_rejected(self):
        executors.submit('io', lambda: 1)
        executors.shutdown(wait=0.2)
        with self.assertRaises(RuntimeError):
            executors.submit('io', lambda: 2)

    def test_shutdown_logs_stragglers(self):
        started = threading.Event()
        release = threading.Event()

        def work():
            started.set()
            release.wait(timeout=30)

        executors.submit('io', work, label='straggler')
        self.assertTrue(started.wait(timeout=5))
        with self.assertLogs('executors', level='WARNING') as logs:
            executors.shutdown(wait=0.05)
        self.assertTrue(any('关闭超时' in line for line in logs.output))
        release.set()


class ConcurrencyRobustnessTests(ExecutorCase):
    """REF-L1-1 回归：闸门等待期取消、拆闸唤醒等待者、关闭后不再扩容。"""

    def _hold_gate(self, vendor):
        started = threading.Event()
        release = threading.Event()

        def blocker():
            started.set()
            release.wait(timeout=30)

        held = executors.submit('network', blocker, vendor=vendor)
        self.assertTrue(started.wait(timeout=5))
        return held, release

    def _wait_until_blocked(self, future):
        # 旧实现出队后 running() 变 True；修复后等闸时停在 PENDING。
        # 1 秒兜底足够让 worker 出队并进入 gate.acquire 等待。
        deadline = time.monotonic() + 1
        while not (future.running() or future.done()) \
                and time.monotonic() < deadline:
            time.sleep(0.01)

    def test_cancel_during_gate_wait_cancels_future(self):
        executors.set_vendor_limit('cancel-vendor', 1)
        held, release = self._hold_gate('cancel-vendor')
        try:
            flag = executors.CancelFlag()
            waiting = executors.submit('network', lambda: 'never', cancel=flag,
                                       vendor='cancel-vendor')
            self._wait_until_blocked(waiting)
            flag.cancel()
            deadline = time.monotonic() + 5
            while not waiting.done() and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertTrue(waiting.done())
            self.assertTrue(waiting.cancelled())
        finally:
            release.set()
        held.result(timeout=5)

    def test_vendor_limit_removal_wakes_waiters(self):
        executors.set_vendor_limit('wake-vendor', 1)
        held, release = self._hold_gate('wake-vendor')
        try:
            waiter = executors.submit('network', lambda: 'ran',
                                      vendor='wake-vendor')
            self._wait_until_blocked(waiter)
            executors.set_vendor_limit('wake-vendor', 0)
            self.assertEqual(waiter.result(timeout=5), 'ran')
        finally:
            release.set()
        held.result(timeout=5)

    def test_scale_workers_after_closing_spawns_none(self):
        executors.set_vendor_limit('scale-vendor', 1)
        pool = executors._pool('network')
        executors.shutdown(wait=0.2)
        self.assertTrue(pool._closing)
        before = len(pool._workers)
        executors.set_vendor_limit('scale-vendor', before + 4)
        self.assertEqual(len(pool._workers), before)


if __name__ == '__main__':
    unittest.main()

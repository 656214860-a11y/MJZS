"""桌面后台任务：任务失败时，诊断记录自己出错也必须先把失败结果交回界面（R1777 审计）。"""
import queue
import unittest
from types import SimpleNamespace
from unittest import mock

from desktop_async_tasks import AsyncTasksMixin


class _Host(AsyncTasksMixin):
    def __init__(self):
        self._async_ticket = 0
        self.worker = False
        self.page_index = 0
        self.root = ''
        self.q = queue.Queue()
        self.busy_state = SimpleNamespace(set_busy=lambda *args, **kwargs: None)
        self.background_tasks = SimpleNamespace(submit=lambda ticket, **_kw: ticket,
                                                run=self._run)

    def _run(self, ticket, fn):
        return fn()

    def _schedule_async_result_poll(self, ticket):
        return None


class AsyncFailureDeliveryTests(unittest.TestCase):
    def test_failure_result_is_delivered_even_if_diagnostics_raise(self):
        host = _Host()

        def boom():
            raise RuntimeError('task failed')

        with mock.patch('diagnostic_capture.record_degradation', side_effect=OSError('disk full')):
            host.async_(boom)
            ticket, ok, message, done = host.q.get(timeout=5)
        self.assertFalse(ok)
        self.assertEqual(message, 'task failed')
        self.assertIsNone(done)


if __name__ == '__main__':
    unittest.main()

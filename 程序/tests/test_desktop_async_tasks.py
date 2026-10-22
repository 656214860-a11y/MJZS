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


class TickResultTests(unittest.TestCase):
    def host(self, *, accepts=True, finished=True):
        host = _Host()
        host._async_ticket = 7
        host.worker = True
        host.shutting_down = False
        host._brief_load_results = queue.Queue()
        host.status = mock.Mock()
        host.notifier = mock.Mock()
        host._start_next_queued = mock.Mock()
        host.update_script_interrupt_button = mock.Mock()
        host.clear_thinking = mock.Mock()
        host.background_tasks = SimpleNamespace(accepts=lambda ticket: accepts,
                                                finish=lambda ticket, **_kw: finished)
        return host

    def test_abandoned_current_ticket_frees_the_worker_and_moves_on(self):
        host = self.host(accepts=True, finished=False)
        host.q.put((7, True, 'late', None))
        host._tick_async_result()
        self.assertFalse(host.worker)
        host.status.set.assert_called_once_with('本机已停止等待；在途任务与迟到结果可在运行状况核对。')
        host._start_next_queued.assert_called_once_with()

    def test_failed_idea_request_unlocks_the_send_button(self):
        host = self.host()
        host._idea_requesting = True
        host.idea_chat_controller = mock.Mock()
        host.idea_send = mock.Mock(winfo_exists=lambda: True)
        host.q.put((7, False, '断线', None))
        host._tick_async_result()
        host.idea_chat_controller.cancel_request.assert_called_once_with()
        host.idea_send.state.assert_called_once_with(['!disabled'])
        host.notifier.error.assert_called_once_with('断线', title='操作未完成')
        self.assertFalse(host.worker)

    def test_pending_structure_retry_reports_a_refused_restart(self):
        host = self.host()
        host._auto_structure_retry = True
        host.pet_start = mock.Mock(side_effect=ValueError('门禁未过'))
        done = mock.Mock()
        host.q.put((7, True, 'ok', done))
        host._tick_async_result()
        done.assert_called_once_with('ok')
        host.pet_start.assert_called_once_with('script_structure')
        self.assertFalse(host._auto_structure_retry)
        host.status.set.assert_called_once_with('自动恢复结构剧本暂缓：门禁未过')
        host._start_next_queued.assert_called_once_with()


if __name__ == '__main__':
    unittest.main()

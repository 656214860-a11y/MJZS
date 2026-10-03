"""无 Tk 桌面自动流程调度器回归。"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from desktop_automation_service import BackgroundTaskLifecycle, DesktopAutomationScheduler


class DesktopAutomationSchedulerTests(unittest.TestCase):
    def make_scheduler(self):
        self.pending = []
        self.cancelled = []
        self.stopping = False
        self.handles = []
        self.next_handle = 0
        def schedule(delay, callback):
            handle = 'timer-'+str(self.next_handle)
            self.next_handle += 1
            self.pending.append((handle, delay, callback))
            return handle
        return DesktopAutomationScheduler(
            schedule_after=schedule, cancel_scheduled=self.cancelled.append,
            is_stopping=lambda:self.stopping)

    def test_recurring_callback_recovers_and_cancels(self):
        scheduler = self.make_scheduler()
        errors = []
        scheduler.start('main', 150, lambda:(_ for _ in ()).throw(ValueError('boom')),
                        on_error=errors.append, remember_timer=self.handles.append)
        handle, delay, callback = self.pending.pop(0)
        self.assertEqual((handle, delay), ('timer-0', 150))
        callback()
        self.assertEqual(str(errors[0]), 'boom')
        self.assertEqual(self.handles[-1], 'timer-1')
        scheduler.cancel_all()
        self.assertEqual(self.cancelled, ['timer-1'])
        self.assertIsNone(self.handles[-1])

    def test_due_poll_advances_before_failure_and_respects_guards(self):
        scheduler = self.make_scheduler()
        state = {'due': 0, 'ready': True}
        errors = []
        ran = scheduler.run_due(
            now=10, due_at=lambda:state['due'], delay_seconds=30,
            allowed=lambda:state['ready'], set_due=lambda value:state.__setitem__('due', value),
            poll=lambda:(_ for _ in ()).throw(OSError('offline')), on_error=errors.append,
            handled_exceptions=(OSError,))
        self.assertFalse(ran)
        self.assertEqual(state['due'], 40)
        self.assertEqual(str(errors[0]), 'offline')
        state['ready'] = False
        self.assertFalse(scheduler.run_due(
            now=40, due_at=lambda:state['due'], delay_seconds=30,
            allowed=lambda:state['ready'], set_due=lambda value:state.__setitem__('due', value),
            poll=lambda:None, on_error=errors.append, handled_exceptions=(OSError,)))
        self.assertEqual(state['due'], 40)


class BackgroundTaskLifecycleTests(unittest.TestCase):
    def test_cancelled_or_superseded_result_is_never_accepted(self):
        lifecycle = BackgroundTaskLifecycle()
        lifecycle.submit(7)
        self.assertTrue(lifecycle.cancel())
        self.assertFalse(lifecycle.finish(7, succeeded=True))
        self.assertEqual(lifecycle.snapshot(), {'ticket': 7, 'state': 'cancelled'})

        lifecycle.submit(8)
        lifecycle.submit(9)
        self.assertFalse(lifecycle.accepts(8))
        self.assertTrue(lifecycle.finish(9, succeeded=False))
        self.assertEqual(lifecycle.snapshot(), {'ticket': 9, 'state': 'failed'})


if __name__ == '__main__':
    unittest.main(verbosity=2)

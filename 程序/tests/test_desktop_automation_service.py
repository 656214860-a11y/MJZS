"""无 Tk 桌面自动流程调度器回归。"""
import os
import queue
import sys
import unittest
from types import SimpleNamespace

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from desktop_automation_service import (BACKGROUND_TASK_MIGRATION,
                                        BackgroundTaskLifecycle, DesktopAutomationScheduler)


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

    def test_progress_and_result_share_the_same_delivery_ticket(self):
        """连续进度与最终结果都必须由同一个仍有效的代次交付。"""
        lifecycle = BackgroundTaskLifecycle()
        old_ticket = lifecycle.submit(1)
        current_ticket = lifecycle.submit(2)
        self.assertFalse(lifecycle.accepts(old_ticket))
        self.assertTrue(lifecycle.accepts(current_ticket))
        self.assertFalse(lifecycle.finish(old_ticket, succeeded=True))
        self.assertTrue(lifecycle.finish(current_ticket, succeeded=True))
        self.assertFalse(lifecycle.accepts(current_ticket))


class BackgroundTaskMigrationManifestTests(unittest.TestCase):
    def test_progress_delivery_entries_are_migrated(self):
        records = {record['entry']: record for record in BACKGROUND_TASK_MIGRATION}
        self.assertEqual(records['auto_video'], {
            'entry': 'auto_video', 'category': 'progress-and-result', 'state': 'migrated'})
        self.assertEqual(records['auto_asset']['state'], 'migrated')
        self.assertEqual(records['auto_keyframe']['state'], 'migrated')
        self.assertEqual(records['previs_jobs']['state'], 'migrated')
        self.assertEqual(records['cloud_monitor']['state'], 'migrated')


class AutoVideoLifecycleDeliveryTests(unittest.TestCase):
    def test_stale_progress_and_result_cannot_refresh_the_desktop(self):
        """自动视频被替换后，旧 worker 的日志和结果均不得触达状态栏或下游。"""
        from desktop import Desktop
        lifecycle = BackgroundTaskLifecycle()
        lifecycle.submit(1)
        lifecycle.submit(2)
        status = SimpleNamespace(values=[], set=lambda value: status.values.append(value))
        desktop = SimpleNamespace(
            auto_video_tasks=lifecycle,
            auto_video_messages=queue.Queue(),
            auto_video_queue=queue.Queue(),
            auto_video_busy=True,
            auto_video_signature=None,
            auto_video_due=0,
            auto_video_last='',
            auto_video_error='',
            status=status,
            _poll_auto_due=lambda *args, **kwargs: self.fail('过期结果不得继续轮询'),
        )
        desktop.auto_video_messages.put((1, '旧进度'))
        desktop.auto_video_queue.put((1, True, '旧结果', ('SH001',)))
        Desktop._tick_auto_video(desktop)
        self.assertEqual(status.values, [])
        self.assertTrue(desktop.auto_video_busy)
        self.assertIsNone(desktop.auto_video_signature)


class AutoAssetLifecycleDeliveryTests(unittest.TestCase):
    def test_stale_progress_and_result_cannot_refresh_the_desktop(self):
        """自动资产被替换后，旧 worker 的消息和结果均不得触达 UI 或续跑台账。"""
        from desktop import Desktop
        lifecycle = BackgroundTaskLifecycle()
        lifecycle.submit(1)
        lifecycle.submit(2)
        status = SimpleNamespace(values=[], set=lambda value: status.values.append(value))
        desktop = SimpleNamespace(
            auto_asset_tasks=lifecycle,
            auto_asset_messages=queue.Queue(),
            auto_asset_queue=queue.Queue(),
            auto_asset_busy=True,
            auto_asset_signature=None,
            status=status,
            _poll_auto_due=lambda *args, **kwargs: None,
        )
        desktop.auto_asset_messages.put((1, '旧进度'))
        desktop.auto_asset_queue.put((1, True, '旧结果', ('asset-1',)))
        Desktop._tick_auto_asset(desktop)
        self.assertEqual(status.values, [])
        self.assertTrue(desktop.auto_asset_busy)
        self.assertIsNone(desktop.auto_asset_signature)


class AutoKeyframeLifecycleDeliveryTests(unittest.TestCase):
    def test_stale_progress_and_result_cannot_refresh_the_desktop(self):
        """自动首帧被替换后，旧 worker 的消息和结果均不得触达 UI 或推进阶段。"""
        from desktop import Desktop
        lifecycle = BackgroundTaskLifecycle()
        lifecycle.submit(1)
        lifecycle.submit(2)
        status = SimpleNamespace(values=[], set=lambda value: status.values.append(value))
        desktop = SimpleNamespace(
            auto_keyframe_tasks=lifecycle,
            auto_keyframe_messages=queue.Queue(),
            auto_keyframe_queue=queue.Queue(),
            auto_keyframe_busy=True,
            auto_keyframe_signature=None,
            status=status,
            _poll_auto_due=lambda *args, **kwargs: None,
        )
        desktop.auto_keyframe_messages.put((1, '旧进度'))
        desktop.auto_keyframe_queue.put((1, True, '旧结果', ('SH001',)))
        Desktop._tick_auto_keyframe(desktop)
        self.assertEqual(status.values, [])
        self.assertTrue(desktop.auto_keyframe_busy)
        self.assertIsNone(desktop.auto_keyframe_signature)


class CloudMonitorLifecycleDeliveryTests(unittest.TestCase):
    def test_stale_result_cannot_refresh_schedule_or_status(self):
        """跨页云端查询被替换后，旧结果不得改变节流或写入状态栏。"""
        from desktop import Desktop
        lifecycle = BackgroundTaskLifecycle()
        lifecycle.submit(1)
        lifecycle.submit(2)
        status = SimpleNamespace(values=[], set=lambda value: status.values.append(value))
        desktop = SimpleNamespace(
            cloud_monitor_tasks=lifecycle,
            cloud_monitor_result=queue.Queue(),
            cloud_monitor_busy=True,
            cloud_monitor_due=0,
            root=object(),
            status=status,
        )
        desktop.cloud_monitor_result.put((1, False, '旧错误'))
        Desktop._tick_cloud_monitor(desktop)
        self.assertEqual(status.values, [])
        self.assertTrue(desktop.cloud_monitor_busy)
        self.assertEqual(desktop.cloud_monitor_due, 0)


class PrevisLifecycleDeliveryTests(unittest.TestCase):
    def test_stale_completion_announcement_cannot_reach_pet(self):
        """白模旧批次退出后不得再向桌宠或主界面交付完成播报。"""
        from desktop import Desktop
        lifecycle = BackgroundTaskLifecycle()
        lifecycle.submit(1)
        lifecycle.submit(2)
        reports = []
        desktop = SimpleNamespace(
            auto_previs_tasks=lifecycle,
            previs_jobs={'news': queue.Queue()},
            _poll_auto_due=lambda *args, **kwargs: None,
            poll_auto_previs=lambda: None,
            auto_previs_error='',
            pet_report=lambda *args, **kwargs: reports.append((args, kwargs)),
        )
        desktop.previs_jobs['news'].put((1, True, '旧批次完成'))
        Desktop._tick_auto_previs(desktop)
        self.assertEqual(reports, [])
        self.assertTrue(lifecycle.accepts(2))


class BackgroundDeliveryMatrixTests(unittest.TestCase):
    """逐项调用真实桌面收尾方法，不创建窗口或启动线程。"""

    ENTRIES = {
        'Desktop.async_': ('background_tasks', 'q', '_tick_async_result'),
        'auto_edit': ('auto_edit_tasks', 'auto_edit_queue', '_drain_auto_edit_result'),
        'auto_handoff': ('auto_handoff_tasks', 'auto_handoff_queue', '_drain_auto_handoff_result'),
        'auto_video': ('auto_video_tasks', 'auto_video_queue', '_tick_auto_video'),
        'auto_asset': ('auto_asset_tasks', 'auto_asset_queue', '_tick_auto_asset'),
        'auto_keyframe': ('auto_keyframe_tasks', 'auto_keyframe_queue', '_tick_auto_keyframe'),
        'previs_jobs': ('auto_previs_tasks', 'previs_news', '_tick_auto_previs'),
        'cloud_monitor': ('cloud_monitor_tasks', 'cloud_monitor_result', '_tick_cloud_monitor'),
    }

    def make_desktop(self, entry):
        effects = []
        record = lambda *args, **kwargs: effects.append((args, kwargs))
        desktop = SimpleNamespace(
            win=SimpleNamespace(after_cancel=record), cancel_resize=lambda: None,
            idea_chat_controller=SimpleNamespace(cancel_request=lambda: None),
            _async_ticket=1, _brief_load_results=queue.Queue(), worker=True,
            busy_state=SimpleNamespace(set_busy=record), status=SimpleNamespace(set=record),
            notifier=SimpleNamespace(error=record), update_script_interrupt_button=record,
            clear_thinking=record, _poll_auto_due=lambda *args, **kwargs: False,
            kick_unattended=record, pet_report=record, show=record, page_index=None,
            root=object(), pet=SimpleNamespace(auto=SimpleNamespace(active=None)),
            keyframe_batch_state=lambda **kwargs: (object(), [], '', ''),
            asset_pending_ids=lambda: [], clear_asset_resume=record,
            auto_asset_attempt=0, cloud_monitor_busy=True, cloud_monitor_due=0,
            auto_video_last='', auto_previs_error='',
        )
        for name, (owner, result, _) in self.ENTRIES.items():
            lifecycle = BackgroundTaskLifecycle()
            lifecycle.submit(1)
            setattr(desktop, owner, lifecycle)
            setattr(desktop, result, queue.Queue())
            setattr(desktop, name + '_busy', True)
            setattr(desktop, name + '_signature', None)
            setattr(desktop, name + '_due', 0)
            setattr(desktop, name + '_error', '')
            setattr(desktop, 'poll_' + name, lambda: None)
        desktop.poll_auto_previs = lambda: None
        desktop._start_next_queued = lambda: None  # R1470：结果收尾后启动排队任务；本测试不涉及排队
        from desktop import Desktop
        desktop._async_failed = lambda value: Desktop._async_failed(desktop, value)  # R1822：失败收尾抽成了方法，照样跑真的
        desktop.previs_jobs = {'news': desktop.previs_news}
        for name in ('auto_video', 'auto_asset', 'auto_keyframe'):
            setattr(desktop, name + '_messages', queue.Queue())
        return desktop, effects

    def enqueue(self, desktop, entry, succeeded, ticket=1):
        _, result, _ = self.ENTRIES[entry]
        row = (ticket, succeeded, '完成' if succeeded else '失败')
        if entry == 'Desktop.async_':
            row += (None,)
        elif entry in ('auto_handoff', 'auto_video', 'auto_asset', 'auto_keyframe'):
            row += (('signature',),)
        getattr(desktop, result).put(row)

    def drain(self, desktop, entry):
        from desktop import Desktop
        getattr(Desktop, self.ENTRIES[entry][2])(desktop)

    def test_manifest_has_exactly_the_exercised_entries(self):
        names = [item['entry'] for item in BACKGROUND_TASK_MIGRATION]
        self.assertEqual(len(names), len(set(names)))
        self.assertEqual(set(names), set(self.ENTRIES))
        self.assertTrue(all(item['state'] == 'migrated' for item in BACKGROUND_TASK_MIGRATION))

    def test_cancel_replace_and_window_close_reject_all_late_deliveries(self):
        from desktop import Desktop
        for entry, (owner, _, _) in self.ENTRIES.items():
            for mode in ('cancel', 'replace', 'close'):
                for succeeded in (True, False):
                    with self.subTest(entry=entry, mode=mode, succeeded=succeeded):
                        desktop, effects = self.make_desktop(entry)
                        lifecycle = getattr(desktop, owner)
                        if mode == 'replace':
                            lifecycle.submit(2)
                        elif mode == 'close':
                            Desktop.cancel_timers(desktop)
                            self.assertTrue(desktop.shutting_down)
                        else:
                            self.assertTrue(lifecycle.cancel(1))
                        before = lifecycle.snapshot()
                        effects.clear()
                        if entry in ('auto_video', 'auto_asset', 'auto_keyframe'):
                            getattr(desktop, entry + '_messages').put((1, '迟到进度'))
                        self.enqueue(desktop, entry, succeeded)
                        self.drain(desktop, entry)
                        self.assertEqual(effects, [])
                        self.assertEqual(lifecycle.snapshot(), before)
                        self.assertEqual(lifecycle.accepts(2), mode == 'replace')

    def test_current_success_and_failure_finish_once(self):
        for entry, (owner, _, _) in self.ENTRIES.items():
            for succeeded in (True, False):
                with self.subTest(entry=entry, succeeded=succeeded):
                    desktop, effects = self.make_desktop(entry)
                    self.enqueue(desktop, entry, succeeded)
                    self.drain(desktop, entry)
                    self.assertEqual(getattr(desktop, owner).snapshot(), {
                        'ticket': 1, 'state': 'succeeded' if succeeded else 'failed'})
                    if entry != 'cloud_monitor' or not succeeded:
                        self.assertTrue(effects)
                    effects.clear()
                    self.enqueue(desktop, entry, succeeded)
                    self.drain(desktop, entry)
                    self.assertEqual(effects, [], '同一结果不得重复交付')

    def test_current_progress_and_result_share_ticket(self):
        for entry in ('auto_video', 'auto_asset', 'auto_keyframe'):
            with self.subTest(entry=entry):
                desktop, effects = self.make_desktop(entry)
                getattr(desktop, entry + '_messages').put((1, '当前进度'))
                self.enqueue(desktop, entry, True)
                self.drain(desktop, entry)
                self.assertIn('当前进度', effects[0][0][0])
                self.assertEqual(getattr(desktop, self.ENTRIES[entry][0]).snapshot()['state'], 'succeeded')


if __name__ == '__main__':
    unittest.main(verbosity=2)

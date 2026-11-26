# -*- coding: utf-8 -*-
"""R2985 P0：StatusBus 消息模型与总线行为（纯逻辑，无 Tk）。"""
import sys
import threading
import unittest
from pathlib import Path

HERE = str(Path(__file__).resolve().parents[1])
sys.path.insert(0, HERE)
sys.path.insert(0, str(Path(__file__).resolve().parent))

import infra.app_logging as app_logging
import ui.ui_status_bus as ui_status_bus
from contract.infra_errors import StorageError
from ui.ui_status_bus import (AUTO_DISMISS_MS, LEVELS, Message, StatusBus,
                              publish_unhandled_error, register_unhandled_bus,
                              unregister_unhandled_bus)


class MessageModelTests(unittest.TestCase):
    def test_make_gives_persistent_levels_no_ttl(self):
        for level in ('warning', 'error'):
            self.assertIsNone(Message.make(level, 'x').ttl)
        for level in ('info', 'success'):
            self.assertEqual(Message.make(level, 'x').ttl, AUTO_DISMISS_MS)

    def test_make_auto_false_is_persistent(self):
        self.assertIsNone(Message.make('info', 'x', auto=False).ttl)

    def test_unknown_level_rejected(self):
        with self.assertRaises(ValueError):
            Message.make('verbose', 'x')

    def test_negative_ttl_rejected(self):
        with self.assertRaises(ValueError):
            Message('info', 'x', -1)


class StatusBusTests(unittest.TestCase):
    def setUp(self):
        self.bus = StatusBus(history_limit=5)

    def test_publish_rejects_non_message(self):
        with self.assertRaises(TypeError):
            self.bus.publish('文本')

    def test_pump_delivers_current_event(self):
        events = []
        self.bus.subscribe(events.append)
        msg = Message.make('success', '完成')
        self.bus.publish(msg)
        self.assertEqual(self.bus.pump(), 1)
        self.assertEqual(events, [('current', msg, None)])
        self.assertIs(self.bus.current, msg)

    def test_worker_thread_publish_is_delivered_in_order(self):
        order = []
        self.bus.subscribe(lambda e: order.append(e[1].text) if e[0] == 'current' else None)

        def _producer(start):
            for i in range(20):
                self.bus.publish(Message.make('info', '第%d条' % (start + i)))

        threads = [threading.Thread(target=_producer, args=(0,)),
                   threading.Thread(target=_producer, args=(100,))]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(self.bus.pump(), 40)
        self.assertEqual(len(order), 40)

    def test_duplicate_within_window_is_merged(self):
        events = []
        self.bus.subscribe(events.append)
        first = Message.make('error', '失败')
        self.bus.publish(first)
        self.bus.pump()
        self.bus.publish(Message.make('error', '失败'))
        self.bus.pump()
        self.assertEqual([e[0] for e in events], ['current'])
        self.assertEqual(self.bus.history(), [])

    def test_expire_moves_transient_to_history(self):
        events = []
        self.bus.subscribe(events.append)
        msg = Message.make('info', '临时提示')
        self.bus.publish(msg)
        self.bus.pump()
        self.assertTrue(self.bus.expire_current())
        self.assertIsNone(self.bus.current)
        self.assertEqual(self.bus.history(), [msg])
        self.assertEqual(events[-1], ('expired', None, None))

    def test_expire_ignores_persistent(self):
        self.bus.publish(Message.make('error', '常驻'))
        self.bus.pump()
        self.assertFalse(self.bus.expire_current())
        self.assertIsNotNone(self.bus.current)

    def test_dismiss_moves_persistent_to_history(self):
        msg = Message.make('error', '常驻')
        self.bus.publish(msg)
        self.bus.pump()
        self.assertTrue(self.bus.dismiss())
        self.assertIsNone(self.bus.current)
        self.assertEqual(self.bus.history(), [msg])

    def test_history_is_capped(self):
        for i in range(8):
            self.bus.publish(Message.make('info', 'm%d' % i))
            self.bus.pump()
            self.bus.expire_current()
        self.assertEqual(len(self.bus.history()), 5)
        self.assertEqual(self.bus.history()[-1].text, 'm7')

    def test_unsubscribe_stops_events(self):
        events = []
        unsub = self.bus.subscribe(events.append)
        unsub()
        self.bus.publish(Message.make('info', 'x'))
        self.bus.pump()
        self.assertEqual(events, [])

    def test_levels_contract(self):
        self.assertEqual(LEVELS, ('info', 'success', 'warning', 'error'))


class UnhandledErrorReportTests(unittest.TestCase):
    """L5-E2：未捕获异常经崩溃监听上屏——同码 60 秒限频，不同码互不抑制。"""

    def setUp(self):
        unregister_unhandled_bus()
        ui_status_bus._unhandled_seen.clear()
        self.bus = StatusBus()          # 构造即登记为未捕获异常上屏总线

    def tearDown(self):
        unregister_unhandled_bus()
        ui_status_bus._unhandled_seen.clear()

    def _deliver(self):
        self.bus.pump()
        return self.bus.current

    def test_same_code_is_suppressed_within_sixty_seconds(self):
        self.assertTrue(publish_unhandled_error('E-UNKNOWN', '【错误】甲', now=1000.0))
        self.assertFalse(publish_unhandled_error('E-UNKNOWN', '【错误】乙', now=1030.0))
        self.assertEqual(self._deliver().text, '【错误】甲')

    def test_different_codes_do_not_suppress_each_other(self):
        publish_unhandled_error('E-IO-WRITE', '【错误】甲', now=1000.0)
        publish_unhandled_error('E-UNKNOWN', '【错误】乙', now=1001.0)
        self.assertEqual(self._deliver().text, '【错误】乙')
        self.assertEqual(self.bus.history()[-1].text, '【错误】甲')

    def test_report_resumes_after_window_and_folds_suppressed_count(self):
        publish_unhandled_error('E-UNKNOWN', '【错误】甲', now=1000.0)
        publish_unhandled_error('E-UNKNOWN', '【错误】乙', now=1010.0)
        publish_unhandled_error('E-UNKNOWN', '【错误】丙', now=1020.0)
        publish_unhandled_error('E-UNKNOWN', '【错误】丁', now=1061.0)
        text = self._deliver().text
        self.assertTrue(text.startswith('【错误】丁'), text)
        self.assertIn('（近 1 分钟共 3 次）', text)

    def test_unregistered_bus_is_silent_and_never_raises(self):
        unregister_unhandled_bus()
        self.assertFalse(publish_unhandled_error('E-UNKNOWN', '【错误】甲', now=1000.0))
        self.assertIsNone(self._deliver())

    def test_crash_listener_forwards_to_status_bus(self):
        app_logging._crash('tk-callback', ValueError('不应上屏的原文'))
        message = self._deliver()
        self.assertIsNotNone(message)
        self.assertEqual(message.level, 'error')
        self.assertTrue(message.text.startswith('【错误】[E-UNKNOWN]'), message.text)
        self.assertNotIn('不应上屏的原文', message.text)

    def test_registered_error_code_is_shown(self):
        app_logging._crash('worker', StorageError('内部细节不上屏', code='E-IO-WRITE'))
        self.assertTrue(self._deliver().text.startswith('【错误】[E-IO-WRITE]'))

    def test_system_exit_and_keyboard_interrupt_are_not_reported(self):
        app_logging._crash('main', SystemExit(1))
        app_logging._crash('main', KeyboardInterrupt())
        self.assertIsNone(self._deliver())

    def test_register_unhandled_bus_returns_cancel_function(self):
        other = StatusBus()
        detach = register_unhandled_bus(other)
        detach()
        self.assertFalse(publish_unhandled_error('E-UNKNOWN', 'x', now=1.0))


if __name__ == '__main__':
    unittest.main()

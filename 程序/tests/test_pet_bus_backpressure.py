# -*- coding: utf-8 -*-
"""宠物事件总线背压自检：重复上报合并、水位降载、终态不丢、异常有界与持久、订阅释放。

运行：python run_selftests.py -k pet_bus
"""
import json, os, sys, tempfile, threading, unittest
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)
os.chdir(HERE)

import pet_bus


def watch(bus):
    """订阅全部事件，返回收件清单。"""
    seen = []
    bus.subscribe('*', seen.append)
    return seen


class BackpressureTests(unittest.TestCase):
    def test_repeated_report_does_not_grow_the_queue(self):
        """同一件事反复上报：队列里只留一条，其余记进幂等丢掉的条数（内存不再跟着涨）。"""
        bus = pet_bus.Bus()
        item = pet_bus.event('stage.started', stage='keyframe')
        for _ in range(5000):
            bus.publish(item)
        self.assertEqual(bus.queue.qsize(), 1)
        self.assertEqual(bus.pending, 1)
        self.assertEqual(bus.touched, 5000)
        self.assertEqual(bus.dropped, 4999)

    def test_repeated_report_delivers_once_then_clears_the_water(self):
        bus = pet_bus.Bus()
        seen = watch(bus)
        item = pet_bus.event('stage.completed', stage='assets')
        bus.publish(item)
        bus.publish(item)
        self.assertEqual(bus.pump(), 1)
        self.assertEqual(len(seen), 1)
        self.assertEqual(bus.dropped, 1)
        self.assertEqual(bus.pending, 0)

    def test_distinct_events_are_all_kept_below_the_water(self):
        bus = pet_bus.Bus()
        seen = watch(bus)
        for index in range(300):
            bus.emit('stage.completed', stage='assets', detail=str(index))
        self.assertEqual(bus.pump(limit=1000), 300)
        self.assertEqual(len(seen), 300)
        self.assertEqual(bus.shed, 0)

    def test_terminal_and_paused_events_never_shed_at_the_water(self):
        """到水位后：进度事件让路并计数，完成／失败／暂停（带并发号归还）照常入队。"""
        bus = pet_bus.Bus(pending_limit=3)
        seen = watch(bus)
        for index in range(3):
            bus.emit('stage.executing', stage='video', detail=str(index))
        self.assertEqual(bus.pending, 3)
        bus.emit('stage.executing', stage='video', detail='让路')
        bus.emit('stage.completed', stage='video')
        bus.emit('stage.failed', stage='video', error='超时')
        bus.emit('stage.paused', stage='video', reason='等待已验证的阶段成果')
        self.assertEqual(bus.shed, 1)
        bus.pump(limit=1000)
        kinds = [item['kind'] for item in seen]
        self.assertEqual(kinds.count('stage.executing'), 3)
        self.assertIn('stage.completed', kinds)
        self.assertIn('stage.failed', kinds)
        self.assertIn('stage.paused', kinds)

    def test_sheddable_kinds_are_declared_and_do_not_cover_terminals(self):
        self.assertTrue(pet_bus.is_sheddable('stage.executing'))
        self.assertTrue(pet_bus.is_sheddable('notify.aggregate'))
        for kind in ('stage.completed', 'stage.failed', 'stage.paused', 'script.completed',
                     'intent.command', 'budget.exceeded', 'delivery.ready'):
            self.assertFalse(pet_bus.is_sheddable(kind))
            self.assertNotIn(kind, pet_bus.SHEDDABLE_EVENTS)

    def test_water_and_stats_expose_the_pending_count(self):
        bus = pet_bus.Bus()
        for index in range(4):
            bus.emit('stage.started', stage='edit', detail=str(index))
        stats = bus.stats()
        self.assertEqual(stats['pending'], 4)
        self.assertEqual(stats['water'], 4)
        self.assertEqual(stats['touched'], 4)
        bus.pump(limit=1000)
        self.assertEqual(bus.pending, 0)
        self.assertEqual(bus.stats()['water'], 4)         # 历史最高水位只记不降

    def test_slow_subscriber_costs_pump_not_publish(self):
        """慢订阅者是 pump（界面线程）的代价：publish 只入队，不被订阅者拖住。"""
        bus = pet_bus.Bus()
        released = threading.Event()

        def slow(item):
            released.wait(2)

        bus.subscribe('*', slow)
        for index in range(200):
            bus.emit('stage.completed', stage='edit', detail=str(index))
        self.assertEqual(bus.pending, 200)                 # 还没 pump，队列照收
        self.assertEqual(bus.delivered, 0)                 # 入队不算送达
        released.set()
        self.assertEqual(bus.pump(limit=1000), 200)
        self.assertEqual(bus.pending, 0)
        self.assertEqual(bus.delivered, 200)

    def test_long_run_does_not_accumulate(self):
        """长时间任务：每轮 pump 掉，水位与历史都不随时间累积。"""
        bus = pet_bus.Bus()
        bus.subscribe('*', lambda item: None)
        peak = 0
        for index in range(2000):
            bus.emit('stage.executing', stage='video', detail=str(index))
            if index % 10 == 0:
                bus.pump(limit=1000)
            peak = max(peak, bus.queue.qsize())
        bus.pump(limit=1000)
        self.assertLessEqual(peak, 12)
        self.assertLessEqual(len(bus.history), pet_bus.HISTORY_LIMIT)
        self.assertEqual(bus.pending, 0)


class ErrorCapacityTests(unittest.TestCase):
    def test_errors_are_bounded_but_the_total_is_counted(self):
        bus = pet_bus.Bus(error_limit=3)

        def broken(item):
            raise RuntimeError('订阅者自己的问题')

        bus.subscribe('*', broken)
        for index in range(10):
            bus.emit('stage.completed', stage='edit', detail=str(index))
        bus.pump(limit=1000)
        self.assertEqual(bus.errors_total, 10)
        self.assertEqual(len(bus.errors), 3)
        self.assertTrue(all(kind == 'stage.completed' for kind, _ in bus.errors))
        self.assertEqual(bus.stats()['errors'], 10)

    def test_subscriber_error_is_persisted_to_the_journal(self):
        with tempfile.TemporaryDirectory() as td:
            journal = Path(td) / '宠物' / '事件日志.jsonl'
            bus = pet_bus.Bus(journal=journal, error_limit=4)

            def broken(item):
                raise RuntimeError('订阅者自己的问题')

            bus.subscribe('*', broken)
            bus.emit('stage.completed', stage='edit')
            bus.pump()
            rows = [json.loads(line) for line in journal.read_text(encoding='utf-8').splitlines()]
            self.assertEqual([row['kind'] for row in rows], ['stage.completed', 'bus.subscriber.error'])
            self.assertEqual(rows[1]['event'], 'stage.completed')
            self.assertEqual(rows[1]['error'], '订阅者自己的问题')

    def test_error_persistence_is_capped(self):
        limit = pet_bus.ERROR_PERSIST_LIMIT
        with tempfile.TemporaryDirectory() as td:
            journal = Path(td) / '事件日志.jsonl'
            bus = pet_bus.Bus(journal=journal, error_limit=4)

            def broken(item):
                raise RuntimeError('x')

            bus.subscribe('*', broken)
            for index in range(limit + 5):
                bus.emit('stage.completed', stage='edit', detail=str(index))
            bus.pump(limit=1000)
            rows = [json.loads(line) for line in journal.read_text(encoding='utf-8').splitlines()]
            persisted = [row for row in rows if row['kind'] == 'bus.subscriber.error']
            self.assertEqual(len(persisted), limit)
            self.assertEqual(bus.errors_total, limit + 5)

    def test_no_journal_means_no_diagnostic_file(self):
        with tempfile.TemporaryDirectory() as td:
            bus = pet_bus.Bus()

            def broken(item):
                raise RuntimeError('x')

            bus.subscribe('*', broken)
            bus.emit('stage.completed', stage='edit')
            bus.pump()
            self.assertEqual(bus.errors_total, 1)
            self.assertEqual(list(Path(td).iterdir()), [])


class SubscriptionReleaseTests(unittest.TestCase):
    def test_unsubscribe_stops_only_that_callback(self):
        bus = pet_bus.Bus()
        first, second = [], []
        handle = bus.subscribe('*', first.append)
        bus.subscribe('*', second.append)
        self.assertEqual(bus.unsubscribe('*', handle), 1)
        self.assertEqual(bus.unsubscribe('*', handle), 0)      # 再摘一次不再计数
        bus.emit('stage.completed', stage='edit')
        bus.pump()
        self.assertEqual(first, [])
        self.assertEqual(len(second), 1)

    def test_unsubscribe_without_callback_clears_the_whole_kind(self):
        bus = pet_bus.Bus()
        seen = []
        bus.subscribe('stage.completed', seen.append)
        bus.subscribe('stage.completed', seen.append)
        self.assertEqual(bus.unsubscribe('stage.completed'), 2)
        bus.emit('stage.completed', stage='edit')
        bus.pump()
        self.assertEqual(seen, [])

    def test_release_clears_every_subscription_on_reopen(self):
        """关页重开：release 之后旧订阅一条都不再收到事件，也不残留回调。"""
        bus = pet_bus.Bus()
        seen = []
        bus.subscribe('*', seen.append)
        bus.subscribe('stage.failed', seen.append)
        self.assertEqual(bus.release(), 2)
        self.assertEqual(bus.release(), 0)
        bus.emit('stage.failed', stage='edit', error='超时')
        bus.pump()
        self.assertEqual(seen, [])
        self.assertEqual(bus.delivered, 0)


if __name__ == '__main__':
    unittest.main()

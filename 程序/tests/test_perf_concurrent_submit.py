# -*- coding: utf-8 -*-
"""并发提交吞吐与队列 N 并发排队时延（阶段4 T6 余量）：只量我们自己代码的并发上限。

- 多个生产者线程并发 enqueue_descriptor，多个消费者线程并发 pop 并执行；断言正好一次（不丢不重）。
- 持久队列的入队与领取都在 agent.publication 的进程级 RLock 里串行，所以并发不提高吞吐、只排队；
  本条口径就是把这个上限量出来，并用观察值设退化报警线（不是性能承诺）。
- 供应商侧下单／轮询／下载耗时属外因，不入门槛。

按 test_perf 前缀自动进 run_selftests 的串行性能池。
"""
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
for folder in (str(HERE.parent), str(HERE)):
    if folder not in sys.path:
        sys.path.insert(0, folder)

from agent.core import read
from desktop_automation_service import PersistentBackgroundTaskQueue
from performance_contract import CONCURRENT_SUBMIT_ITEMS_PER_SECOND

TOTAL = 16
PRODUCERS = 4
CONSUMERS = 2


class ConcurrentSubmitThroughputTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'queue.json'
        self.done_numbers = []
        self.done_lock = threading.Lock()
        self.failures = []

        def handler(payload):
            with self.done_lock:
                self.done_numbers.append(payload['n'])
            return payload['n']

        self.queue = PersistentBackgroundTaskQueue(self.path, handlers={'noop': handler},
                                                   clock=lambda: 1000.0)
        self.producers_done = threading.Event()

    def _produce(self, numbers):
        try:
            for number in numbers:
                while True:
                    try:
                        self.queue.enqueue_descriptor('noop', {'n': number}, label='t%d' % number)
                        break
                    except ValueError:
                        # 满队列是文档化的背压；并发提交时必须退让重试，不能丢任务。
                        time.sleep(0.005)
        except Exception as exc:                      # pragma: no cover - 只在回归时命中
            self.failures.append(repr(exc))
        finally:
            pass

    def _consume(self):
        try:
            while True:
                item = self.queue.pop()
                if item is None:
                    if self.producers_done.is_set():
                        return
                    time.sleep(0.005)
                    continue
                item['fn']()
        except Exception as exc:                      # pragma: no cover - 只在回归时命中
            self.failures.append(repr(exc))

    def test_concurrent_submitters_never_lose_or_duplicate_tasks(self):
        chunks = [list(range(index, TOTAL, PRODUCERS)) for index in range(PRODUCERS)]
        producers = [threading.Thread(target=self._produce, args=(chunk,), daemon=True)
                     for chunk in chunks]
        consumers = [threading.Thread(target=self._consume, daemon=True) for _ in range(CONSUMERS)]
        for thread in consumers:
            thread.start()
        started = time.perf_counter()
        for thread in producers:
            thread.start()
        for thread in producers:
            thread.join()
        self.producers_done.set()
        for thread in consumers:
            thread.join()
        elapsed = time.perf_counter() - started

        self.assertEqual(self.failures, [], '并发提交／领取不得抛异常')
        self.assertEqual(sorted(self.done_numbers), list(range(TOTAL)), '每个任务必须正好执行一次')
        states = [row['state'] for row in read(self.path)['tasks']]
        # 领取先于执行：并发跑完不许留 claimed（遗留 claimed 会被当成在途任务，不再自动重提）。
        self.assertEqual(set(states), {'completed'}, '并发跑完不得残留 claimed／queued')
        self.assertEqual(len(states), TOTAL, '落盘的完成任务数必须等于提交数（TOTAL 小于 HISTORY_LIMIT，不会被裁剪）')
        throughput = TOTAL / elapsed
        self.assertGreaterEqual(
            throughput, CONCURRENT_SUBMIT_ITEMS_PER_SECOND,
            '%d 项并发提交实测 %.2f 项／秒（%.2f 秒）低于下限 %.2f' % (
                TOTAL, throughput, elapsed, CONCURRENT_SUBMIT_ITEMS_PER_SECOND))
        print('并发提交：%d 项／%d 生产者／%d 消费者，%.2f 秒，%.2f 项／秒'
              % (TOTAL, PRODUCERS, CONSUMERS, elapsed, throughput))


if __name__ == '__main__':
    unittest.main()
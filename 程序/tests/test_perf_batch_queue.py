# -*- coding: utf-8 -*-
"""批量与队列的本地口径（阶段4 T6）：只量我们自己代码的批量／排队成本。

- 批量首帧：量提交前的 `keyframe_batch.batch_plan` 规划成本（每镜一次文件状态＋尝试记录读取）。
  下单、轮询、下载的耗时由供应商决定，属外因，只登记不进门槛（见 docs/process/联调测试出口基线.md §6 T6）。
- 后台队列：量持久队列 `PersistentBackgroundTaskQueue` 的每项入队与领取成本，并按生产上限验证
  满队列拒绝与领取顺序（优先级降序、同级先到先领）。队列压力下 UI 响应需要实机 Tk，本文件不覆盖。

本文件按 `test_perf` 前缀自动进 run_selftests 的串行性能池（不与普通用例挤并行池）。
"""
import json
import statistics
import sys
import tempfile
import time
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
for folder in (str(HERE.parent), str(HERE)):
    if folder not in sys.path:
        sys.path.insert(0, folder)

import keyframe_batch as batch
from agent.core import read
from desktop_automation_service import QUEUE_LIMIT, PersistentBackgroundTaskQueue
from performance_contract import BATCH_PLAN_PER_SHOT_MS, QUEUE_ITEM_MS

BATCH_SIZES = (50, 200)
BATCH_REPEATS = 3


def build_episode(root, count):
    """一半镜头有首帧、一半缺失，保证规划真的按镜算，不是空转。"""
    base = Path(root) / 'episode'
    (base / 'frames').mkdir(parents=True, exist_ok=True)
    shots = []
    for index in range(1, count + 1):
        sid = 'SH%03d' % index
        shots.append({'id': sid, 'title': sid, 'duration': 5, 'frame': 'frames/%s.png' % sid,
                      'frame_prompt': sid, 'characters': ['CHAR_001'], 'location': 'LOC_001'})
        if index % 2 == 0:
            (base / 'frames' / (sid + '.png')).write_bytes(b'\x89PNG\r\n\x1a\n' + b'0' * 16)
    source = base / 'episode.json'
    source.write_text(json.dumps({'episode_id': 'EP001', 'title': 'T', 'shots': shots},
                                 ensure_ascii=False), encoding='utf-8')
    return source


class BatchPlanCostTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def test_planning_cost_per_shot_stays_within_the_recorded_budget(self):
        """每镜成本不随批量大小上升：50 镜与 200 镜都必须在上限内。"""
        observed = {}
        for size in BATCH_SIZES:
            source = build_episode(Path(self.tmp.name) / ('s%d' % size), size)
            batch.batch_plan(source)                      # 热身：首次读盘不算每镜成本
            runs = []
            for _ in range(BATCH_REPEATS):
                started = time.perf_counter()
                plan = batch.batch_plan(source)
                runs.append((time.perf_counter() - started) * 1000.0)
            self.assertEqual(plan['counts']['targets'], size // 2, '规划必须真的按镜算，否则口径失真')
            per_shot = statistics.median(runs) / size
            observed[size] = round(per_shot, 3)
            self.assertLessEqual(
                per_shot, BATCH_PLAN_PER_SHOT_MS,
                '%d 镜一次规划 %.3f ms/镜 超过上限 %.2f ms（逐档实测：%s）'
                % (size, per_shot, BATCH_PLAN_PER_SHOT_MS, observed))


class DurableQueueCostTests(unittest.TestCase):
    """持久队列入队与领取的本地成本（历次实测与耗时构成见 performance_contract 注释）。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'queue.json'

    def new_queue(self):
        return PersistentBackgroundTaskQueue(self.path, handlers={'noop': lambda payload: payload},
                                             clock=lambda: 1000.0)

    def build_queue(self, count):
        queue = self.new_queue()
        timings, created = [], []
        for index in range(count):
            started = time.perf_counter()
            created.append(queue.enqueue_descriptor('noop', {'n': index}, label='item%d' % index,
                                                    priority=(count - index) % 3))
            timings.append((time.perf_counter() - started) * 1000.0)
        return queue, timings, created

    def claim_one(self, queue):
        """领取一次并回读落盘状态得到本次领取的 id（pop 只返回可执行体，不返回 id）。"""
        before = {row['id'] for row in read(self.path)['tasks'] if row['state'] == 'claimed'}
        started = time.perf_counter()
        queue.pop()
        elapsed = (time.perf_counter() - started) * 1000.0
        fresh = [row['id'] for row in read(self.path)['tasks']
                 if row['state'] == 'claimed' and row['id'] not in before]
        self.assertEqual(len(fresh), 1, '一次 pop 必须恰好多一个已领取任务')
        return fresh[0], elapsed

    def test_enqueue_and_claim_cost_stay_within_the_recorded_budget(self):
        queue, enqueue_ms, created = self.build_queue(QUEUE_LIMIT)
        self.assertEqual([row['label'] for row in read(self.path)['tasks']],
                         ['item%d' % index for index in range(QUEUE_LIMIT)],
                         '落盘顺序必须就是入队顺序')
        with self.assertRaises(ValueError):
            queue.enqueue_descriptor('noop', {'n': 'overflow'}, label='overflow')
        claim_ms, order = [], []
        for _ in range(QUEUE_LIMIT):
            task_id, elapsed = self.claim_one(queue)
            order.append(task_id)
            claim_ms.append(elapsed)
        self.assertIsNone(queue.pop(), '领完之后不能再有可领任务')
        self.assertEqual(sorted(order), sorted(created), '每个入队任务必须恰好被领取一次')
        self.assertEqual(len(set(order)), QUEUE_LIMIT)
        for value in enqueue_ms + claim_ms:
            self.assertLessEqual(value, QUEUE_ITEM_MS,
                                 '队列单项 %.1f ms 超过上限 %.1f ms' % (value, QUEUE_ITEM_MS))

    def test_claim_order_is_priority_then_arrival(self):
        queue, _enqueue_ms, created = self.build_queue(QUEUE_LIMIT)
        expected = [row['id'] for row in sorted(read(self.path)['tasks'],
                                                key=lambda row: (-row['priority'], row['created']))]
        order = []
        for _ in range(QUEUE_LIMIT):
            order.append(self.claim_one(queue)[0])
        self.assertEqual(order, expected, '领取顺序＝优先级降序、同级先到先领')
        self.assertEqual(sorted(order), sorted(created))
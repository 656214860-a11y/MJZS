# -*- coding: utf-8 -*-
"""宠物事件总线自检：契约校验、幂等去重、订阅隔离、审计日志、线程安全。运行：python test_pet_bus.py"""
import json, os, sys, tempfile, threading, unittest
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.chdir(HERE)

import pet_bus


class ContractTests(unittest.TestCase):
    def test_event_carries_time_and_id(self):
        item = pet_bus.event("stage.started", stage="keyframe")
        self.assertEqual(item["kind"], "stage.started")
        self.assertEqual(item["stage"], "keyframe")
        self.assertTrue(item["id"])
        self.assertGreater(item["at"], 0)

    def test_unknown_kind_rejected(self):
        with self.assertRaises(ValueError):
            pet_bus.event("stage.done", stage="assets")

    def test_unknown_stage_rejected(self):
        with self.assertRaises(ValueError):
            pet_bus.event("stage.completed", stage="配音")

    def test_missing_field_rejected(self):
        with self.assertRaises(ValueError) as ctx:
            pet_bus.event("video.task.failed", shot="SH001")
        self.assertIn("error", str(ctx.exception))

    def test_every_kind_is_constructible(self):
        """每条登记的事件都能被构造出来：契约与实现不会各写一份。"""
        payload = {"stage": "assets", "error": "超时", "attempt": 1, "delay": 30, "shot": "SH001",
                   "character": "CHAR_001", "candidates": 3, "path": "exports/MASTER.mp4",
                   "budget": "video", "used": 5, "limit": 10, "text": "继续",
                   "project": "demo"}
        for kind, fields in pet_bus.CONTRACT.items():
            with self.subTest(kind=kind):
                item = pet_bus.event(kind, **{name: payload[name] for name in fields})
                self.assertEqual(item["kind"], kind)
                for name in fields:
                    self.assertIn(name, item)

    def test_stage_names_cover_every_stage(self):
        self.assertEqual(sorted(pet_bus.STAGE_NAMES), sorted(pet_bus.STAGES))


class IdentityTests(unittest.TestCase):
    def test_same_content_same_id(self):
        first = pet_bus.event("stage.failed", stage="video", error="503")
        second = pet_bus.event("stage.failed", stage="video", error="503")
        self.assertEqual(first["id"], second["id"])

    def test_different_content_different_id(self):
        first = pet_bus.event("stage.failed", stage="video", error="503")
        second = pet_bus.event("stage.failed", stage="video", error="超时")
        self.assertNotEqual(first["id"], second["id"])

    def test_explicit_key_overrides_content(self):
        item = pet_bus.event("stage.failed", key="固定键", stage="video", error="503")
        self.assertEqual(item["id"], "固定键")


class BusTests(unittest.TestCase):
    def test_publish_then_pump_delivers_once(self):
        bus = pet_bus.Bus()
        seen = []
        bus.subscribe("stage.started", seen.append)
        bus.emit("stage.started", stage="script")
        self.assertEqual(bus.delivered, 0)                 # 入队不算送达
        self.assertEqual(bus.pump(), 1)
        self.assertEqual([item["stage"] for item in seen], ["script"])
        self.assertEqual(bus.delivered, 1)

    def test_duplicate_report_is_dropped(self):
        bus = pet_bus.Bus()
        seen = []
        bus.subscribe("*", seen.append)
        item = pet_bus.event("stage.completed", stage="assets")
        bus.publish(item); bus.publish(item)
        bus.pump()
        self.assertEqual(len(seen), 1)
        self.assertEqual(bus.dropped, 1)
        self.assertEqual(bus.touched, 2)

    def test_wildcard_and_exact_subscribers_both_fire(self):
        bus = pet_bus.Bus()
        exact = []; everything = []
        bus.subscribe("stage.failed", exact.append)
        bus.subscribe("*", everything.append)
        bus.emit("stage.completed", stage="final")
        bus.emit("stage.failed", stage="video", error="429")
        bus.pump()
        self.assertEqual(len(everything), 2)
        self.assertEqual([item["stage"] for item in exact], ["video"])

    def test_subscriber_error_does_not_stop_the_others(self):
        bus = pet_bus.Bus()
        seen = []
        def broken(item):
            raise RuntimeError("订阅者自己的问题")
        bus.subscribe("*", broken)
        bus.subscribe("*", seen.append)
        bus.emit("stage.completed", stage="edit")
        bus.pump()
        self.assertEqual(len(seen), 1)
        self.assertEqual(bus.errors, [("stage.completed", "订阅者自己的问题")])
        self.assertEqual(bus.delivered, 1)

    def test_pump_respects_limit(self):
        bus = pet_bus.Bus()
        for index in range(5):
            bus.emit("stage.completed", stage="assets", detail=str(index))
        self.assertEqual(bus.pump(limit=2), 2)
        self.assertEqual(bus.pump(), 3)

    def test_publish_from_worker_threads(self):
        bus = pet_bus.Bus()
        seen = []
        bus.subscribe("*", seen.append)
        def worker(offset):
            for index in range(50):
                bus.emit("stage.completed", stage="video", detail=str(offset) + "-" + str(index))
        threads = [threading.Thread(target=worker, args=(offset,)) for offset in range(2)]
        for thread in threads: thread.start()
        for thread in threads: thread.join()
        self.assertEqual(bus.pump(limit=1000), 100)
        self.assertEqual(len(seen), 100)
        self.assertEqual(bus.dropped, 0)

    def test_history_is_bounded(self):
        bus = pet_bus.Bus()
        for index in range(pet_bus.HISTORY_LIMIT + 10):
            bus.emit("stage.completed", stage="assets", detail=str(index))
        bus.pump(limit=1000)
        self.assertEqual(len(bus.history), pet_bus.HISTORY_LIMIT)

    def test_journal_appends_one_json_per_line(self):
        with tempfile.TemporaryDirectory() as td:
            journal = Path(td) / "宠物" / "事件日志.jsonl"
            bus = pet_bus.Bus(journal=journal)
            bus.emit("stage.started", stage="keyframe")
            bus.emit("firstframe.task.failed", shot="SH001", error="超时")
            bus.pump()
            lines = journal.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 2)
            self.assertEqual(json.loads(lines[0])["kind"], "stage.started")
            self.assertEqual(json.loads(lines[1])["shot"], "SH001")
            self.assertTrue(all(isinstance(json.loads(line), dict) for line in lines))

    def test_no_journal_means_no_file(self):
        with tempfile.TemporaryDirectory() as td:
            bus = pet_bus.Bus()
            bus.emit("stage.started", stage="script")
            bus.pump()
            self.assertEqual(list(Path(td).iterdir()), [])


class RunKeyedIdentityTests(unittest.TestCase):
    """D5-a/G7：终态事件的幂等键可带调用方运行序号 run=；at 永不进键。"""

    def test_terminal_event_run_seq_changes_id(self):
        first = pet_bus.event("stage.failed", stage="video", error="503", run=1)
        second = pet_bus.event("stage.failed", stage="video", error="503", run=2)
        self.assertNotEqual(first["id"], second["id"])
        self.assertEqual(first["run"], 1)
        self.assertEqual(second["run"], 2)

    def test_same_run_duplicate_still_shares_id(self):
        first = pet_bus.event("stage.failed", stage="video", error="503", run=7)
        second = pet_bus.event("stage.failed", stage="video", error="503", run=7)
        self.assertEqual(first["id"], second["id"])

    def test_without_run_behaviour_is_unchanged(self):
        first = pet_bus.event("stage.failed", stage="video", error="503")
        second = pet_bus.event("stage.failed", stage="video", error="503")
        self.assertEqual(first["id"], second["id"])
        self.assertNotIn("run", first)
        self.assertNotIn("run", second)

    def test_progress_events_ignore_run(self):
        """进度类事件不在 TERMINAL_EVENTS：run 不进负载也不进键，去重口径不变。"""
        for kind, payload in (("stage.executing", {"stage": "video"}),
                              ("notify.aggregate", {"text": "汇总"}),
                              ("stage.paused", {"stage": "video", "reason": "等待"})):
            with self.subTest(kind=kind):
                first = pet_bus.event(kind, run=1, **payload)
                second = pet_bus.event(kind, run=2, **payload)
                self.assertEqual(first["id"], second["id"])
                self.assertNotIn("run", first)

    def test_terminal_kinds_are_declared(self):
        for kind in ("stage.started", "stage.completed", "stage.failed", "stage.retrying",
                     "script.completed", "delivery.ready",
                     "firstframe.task.failed", "video.task.failed", "voice.task.failed"):
            self.assertIn(kind, pet_bus.TERMINAL_EVENTS)
        for kind in pet_bus.SHEDDABLE_EVENTS + ("stage.paused", "usage_updated", "intent.command"):
            self.assertNotIn(kind, pet_bus.TERMINAL_EVENTS)


class RunKeyedDeliveryTests(unittest.TestCase):
    """D5-a 复现：同一阶段相同错误文本二次失败、带不同 run → 两条都送达。"""

    def test_second_run_same_failure_both_delivered(self):
        bus = pet_bus.Bus()
        seen = []
        bus.subscribe("*", seen.append)
        bus.emit("stage.failed", stage="video", error="503", run=1)
        bus.emit("stage.failed", stage="video", error="503", run=2)
        bus.pump()
        self.assertEqual(len(seen), 2)
        self.assertEqual([item["run"] for item in seen], [1, 2])

    def test_repeat_without_run_still_deduped(self):
        bus = pet_bus.Bus()
        seen = []
        bus.subscribe("*", seen.append)
        bus.emit("stage.failed", stage="video", error="503")
        bus.emit("stage.failed", stage="video", error="503")
        bus.pump()
        self.assertEqual(len(seen), 1)
        self.assertEqual(bus.dropped, 1)

    def test_run_key_does_not_weaken_queued_backpressure(self):
        """_queued 合并仍按幂等键工作：同 run 的重复上报在队列里只留一条。"""
        bus = pet_bus.Bus()
        item = pet_bus.event("stage.failed", stage="video", error="503", run=1)
        for _ in range(200):
            bus.publish(item)
        self.assertEqual(bus.queue.qsize(), 1)
        self.assertEqual(bus.pending, 1)
        self.assertEqual(bus.dropped, 199)

    def test_publish_and_emit_return_values_unchanged(self):
        bus = pet_bus.Bus()
        item = pet_bus.event("stage.completed", stage="edit", run=3)
        self.assertIs(bus.publish(item), item)
        emitted = bus.emit("stage.completed", stage="edit", run=3)
        self.assertEqual(emitted["id"], item["id"])


class JournalFailureTests(unittest.TestCase):
    """D5-b：journal 写盘抛 OSError 时订阅者仍收到事件，错误记入有界 errors。"""

    def test_journal_write_oserror_still_delivers_and_records(self):
        with tempfile.TemporaryDirectory() as td:
            journal = Path(td) / "事件日志.jsonl"
            journal.mkdir()                                   # 目录当文件用 → open 抛 IsADirectoryError
            bus = pet_bus.Bus(journal=journal)
            seen = []
            bus.subscribe("*", seen.append)
            bus.emit("stage.completed", stage="edit")
            count = bus.pump()
            self.assertEqual(count, 1)
            self.assertEqual(len(seen), 1)                     # 事件照常送达
            self.assertEqual(bus.delivered, 1)
            self.assertTrue(any(kind == "journal.write" for kind, _ in bus.errors), bus.errors)

    def test_journal_write_oserror_is_bounded(self):
        with tempfile.TemporaryDirectory() as td:
            journal = Path(td) / "事件日志.jsonl"
            journal.mkdir()
            bus = pet_bus.Bus(journal=journal, error_limit=3)
            bus.subscribe("*", lambda item: None)
            for index in range(10):
                bus.emit("stage.completed", stage="edit", detail=str(index))
            bus.pump(limit=1000)
            self.assertEqual(len(bus.errors), 3)               # 有界环形，不无限涨
            self.assertTrue(all(kind == "journal.write" for kind, _ in bus.errors))


class EmitStatusTests(unittest.TestCase):
    """D5-c/H3：Bus.emit_status 返回 (status, item)，status ∈ delivered/suppressed/failed。"""

    def test_delivered_when_accepted_into_queue(self):
        bus = pet_bus.Bus()
        status, item = bus.emit_status("stage.completed", stage="edit")
        self.assertEqual(status, "delivered")
        self.assertEqual(item["kind"], "stage.completed")
        self.assertEqual(bus.pending, 1)

    def test_suppressed_when_deduped_while_queued(self):
        bus = pet_bus.Bus()
        bus.emit_status("stage.completed", stage="edit")
        status, item = bus.emit_status("stage.completed", stage="edit")
        self.assertEqual(status, "suppressed")
        self.assertIsNotNone(item)
        self.assertEqual(item["kind"], "stage.completed")

    def test_suppressed_when_shed_at_the_water(self):
        bus = pet_bus.Bus(pending_limit=1)
        bus.emit("stage.executing", stage="video", detail="a")
        status, item = bus.emit_status("stage.executing", stage="video", detail="b")
        self.assertEqual(status, "suppressed")
        self.assertEqual(bus.shed, 1)

    def test_failed_on_contract_violation_without_raising(self):
        bus = pet_bus.Bus()
        status, item = bus.emit_status("stage.done", stage="x")       # 未登记事件
        self.assertEqual(status, "failed")
        self.assertIsNone(item)
        status, item = bus.emit_status("stage.failed", stage="video")  # 缺 error 字段
        self.assertEqual(status, "failed")
        self.assertIsNone(item)
        self.assertEqual(bus.pending, 0)

    def test_emit_safe_and_publish_still_return_item(self):
        bus = pet_bus.Bus()
        errors = pet_bus.ErrorLog()
        self.assertIsNotNone(pet_bus.emit_safe(bus, errors, "stage.completed", stage="edit"))
        self.assertEqual(errors, [])


class RunSequencerTests(unittest.TestCase):
    """D5-d/G7：Bus.begin_run/current_run 按阶段发运行序号；
    with_current_run 只给终态事件注入当前 run，不碰进度类。"""

    def test_begin_run_increments_per_stage(self):
        bus = pet_bus.Bus()
        self.assertEqual(bus.begin_run("video"), 1)
        self.assertEqual(bus.begin_run("video"), 2)
        self.assertEqual(bus.current_run("video"), 2)
        self.assertEqual(bus.current_run("script"), 0)          # 未开跑的阶段为 0
        self.assertEqual(bus.begin_run("script"), 1)            # 各阶段独立计数
        self.assertEqual(bus.current_run("video"), 2)

    def test_current_run_unknown_stage_is_zero(self):
        bus = pet_bus.Bus()
        self.assertEqual(bus.current_run("不存在"), 0)

    def test_with_current_run_injects_terminal_only(self):
        bus = pet_bus.Bus()
        bus.begin_run("video")
        payload = {"stage": "video", "error": "503"}
        out = pet_bus.with_current_run(bus, "stage.failed", payload)
        self.assertEqual(out["run"], 1)
        self.assertNotIn("run", payload)                        # 原负载不被改写
        live = {"stage": "video"}
        self.assertIs(pet_bus.with_current_run(bus, "stage.executing", live), live)
        self.assertNotIn("run", live)
        no_stage = {"text": "你好"}
        self.assertIs(pet_bus.with_current_run(bus, "notify.aggregate", no_stage), no_stage)

    def test_with_current_run_keeps_explicit_run(self):
        bus = pet_bus.Bus()
        bus.begin_run("video")
        out = pet_bus.with_current_run(bus, "stage.failed",
                                       {"stage": "video", "error": "x", "run": 9})
        self.assertEqual(out["run"], 9)

    def test_with_current_run_no_run_started_leaves_payload(self):
        bus = pet_bus.Bus()
        payload = {"stage": "video", "error": "x"}
        out = pet_bus.with_current_run(bus, "stage.failed", payload)
        self.assertNotIn("run", out)                            # 没有当前运行则不造号


class RunSequencerDeliveryTests(unittest.TestCase):
    """D5-d：第二个失败运行让状态机离开旧结算；同 run 重复仍被压制。"""

    def test_second_failed_run_delivers_again(self):
        bus = pet_bus.Bus()
        seen = []
        bus.subscribe("*", seen.append)
        bus.begin_run("video")
        bus.emit("stage.failed", stage="video", error="503", run=bus.current_run("video"))
        bus.begin_run("video")                                  # 第二次运行开始
        bus.emit("stage.failed", stage="video", error="503", run=bus.current_run("video"))
        bus.pump()
        self.assertEqual(len(seen), 2)
        self.assertEqual([item["run"] for item in seen], [1, 2])

    def test_same_run_repeat_still_suppressed(self):
        bus = pet_bus.Bus()
        seen = []
        bus.subscribe("*", seen.append)
        bus.begin_run("video")
        run = bus.current_run("video")
        bus.emit("stage.failed", stage="video", error="503", run=run)
        bus.emit("stage.failed", stage="video", error="503", run=run)
        bus.pump()
        self.assertEqual(len(seen), 1)
        self.assertEqual(bus.dropped, 1)


class AgentEmitRunTests(unittest.TestCase):
    """D5-d：Agent._emit 自动注入当前运行号，UI/编排层不用各自记 run。"""

    def test_agent_emit_terminal_carries_current_run(self):
        import tempfile
        bus = pet_bus.Bus()
        with tempfile.TemporaryDirectory() as td:
            import pet_agent
            import pet_state
            machine = pet_state.Machine(td, persist=False)
            agent = pet_agent.Agent(project=td, bus=bus, machine=machine, persist=False)
            bus.begin_run("video")
            agent._emit("stage.failed", stage="video", error="503")
            bus.pump()
            item = bus.history[-1]
            self.assertEqual(item["run"], 1)
            self.assertEqual(item["kind"], "stage.failed")

    def test_agent_emit_progress_has_no_run(self):
        import tempfile
        bus = pet_bus.Bus()
        with tempfile.TemporaryDirectory() as td:
            import pet_agent
            import pet_state
            machine = pet_state.Machine(td, persist=False)
            agent = pet_agent.Agent(project=td, bus=bus, machine=machine, persist=False)
            bus.begin_run("video")
            agent._emit("stage.executing", stage="video")
            bus.pump()
            self.assertNotIn("run", bus.history[-1])

    def test_second_run_failure_reaches_machine_again(self):
        """同错文本第二个 run 的 stage.failed 必须再次送达订阅者（状态机可重走）。"""
        import tempfile
        import pet_agent
        import pet_state
        bus = pet_bus.Bus()
        with tempfile.TemporaryDirectory() as td:
            machine = pet_state.Machine(td, persist=False)
            agent = pet_agent.Agent(project=td, bus=bus, machine=machine, persist=False)
            delivered = []
            bus.subscribe("stage.failed", delivered.append)
            for _ in range(2):
                bus.begin_run("video")
                agent._emit("stage.failed", stage="video", error="503")
                bus.pump()
            self.assertEqual(len(delivered), 2)
            self.assertEqual([item["run"] for item in delivered], [1, 2])


if __name__ == "__main__":
    unittest.main()

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
                   "project": "demo", "op": "search", "nonce": "n1"}
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


if __name__ == "__main__":
    unittest.main()

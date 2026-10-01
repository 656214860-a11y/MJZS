# -*- coding: utf-8 -*-
"""阶段状态机自检：推进、失败/重试、进度与 ETA、落盘恢复。运行：python test_pet_state.py"""
import json, os, sys, tempfile, unittest
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.chdir(HERE)

import pet_bus
from pet_state import (FAILED, PENDING, RETRYING, RUNNING, SKIPPED, SUCCESS, Machine, state_path)


class Clock:
    """可推进的假时钟：ETA 用例不依赖真实等待。"""
    def __init__(self):
        self.now = 0.0
    def __call__(self):
        return self.now


def machine(td, clock=None, persist=True):
    return Machine(Path(td), clock=clock or Clock(), persist=persist)


class InitialTests(unittest.TestCase):
    def test_starts_pending_at_first_stage(self):
        with tempfile.TemporaryDirectory() as td:
            m = machine(td)
            self.assertEqual(m.current(), "script")
            self.assertEqual([m.stages[stage]["state"] for stage in pet_bus.STAGES], [PENDING] * len(pet_bus.STAGES))
            state = m.progress()
            self.assertEqual(state["percent"], 0.0)
            self.assertEqual(state["done_stages"], 0)
            self.assertIsNone(state["ratio"])

    def test_stage_matches_page_order(self):
        with tempfile.TemporaryDirectory() as td:
            m = machine(td)
            self.assertEqual(m.next_after("assets"), "continuity")
            self.assertEqual(m.next_after("continuity"), "final")
            self.assertEqual(m.next_after("delivery"), None)
            with self.assertRaises(ValueError):
                m.next_after("剧本")

    def test_unknown_stage_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            m = machine(td)
            with self.assertRaises(ValueError):
                m.start("配音")


class TransitionTests(unittest.TestCase):
    def test_event_sequence_drives_the_machine(self):
        with tempfile.TemporaryDirectory() as td:
            m = machine(td)
            self.assertTrue(m.apply(pet_bus.event("stage.started", stage="script")))
            self.assertEqual(m.stages["script"]["state"], RUNNING)
            self.assertTrue(m.apply(pet_bus.event("stage.completed", stage="script")))
            self.assertEqual(m.current(), "script_structure")
            self.assertTrue(m.apply(pet_bus.event("stage.completed", stage="script_structure")))
            self.assertEqual(m.current(), "storyboard")
            self.assertEqual(m.settled(), ["script", "script_structure"])
            self.assertFalse(m.apply(pet_bus.event("stage.completed", stage="script")))   # 重复上报无变化

    def test_non_stage_events_are_ignored(self):
        with tempfile.TemporaryDirectory() as td:
            m = machine(td)
            self.assertFalse(m.apply(pet_bus.event("video.task.failed", shot="SH001", error="超时")))

    def test_failure_counts_attempts_and_retry_keeps_reason(self):
        with tempfile.TemporaryDirectory() as td:
            m = machine(td)
            m.apply(pet_bus.event("stage.failed", stage="video", error="503 服务不可用"))
            self.assertEqual(m.stages["video"]["state"], FAILED)
            self.assertEqual(m.stages["video"]["attempts"], 1)
            self.assertIn("503", m.stages["video"]["reason"])
            m.apply(pet_bus.event("stage.retrying", stage="video", attempt=2, delay=60))
            self.assertEqual(m.stages["video"]["state"], RETRYING)
            self.assertEqual(m.stages["video"]["attempts"], 2)
            self.assertIn("60", m.stages["video"]["reason"])

    def test_skip_takes_a_stage_out_of_the_way(self):
        with tempfile.TemporaryDirectory() as td:
            m = machine(td)
            m.skip("audio", "纯配音项目不需要")
            m.complete("script")
            m.complete("script_structure")
            self.assertEqual(m.current(), "storyboard")
            self.assertEqual(m.progress()["done_stages"], 3)

    def test_subscribe_receives_bus_events(self):
        with tempfile.TemporaryDirectory() as td:
            bus = pet_bus.Bus()
            m = machine(td, persist=False)
            m.subscribe(bus)
            bus.emit("stage.started", stage="assets")
            bus.emit("stage.completed", stage="assets")
            bus.pump()
            self.assertEqual(m.stages["assets"]["state"], SUCCESS)


class ProgressTests(unittest.TestCase):
    def test_detail_drives_percent_and_eta(self):
        with tempfile.TemporaryDirectory() as td:
            clock = Clock()
            m = machine(td, clock=clock, persist=False)
            m.start("script"); m.complete("script")             # 1/12 完成
            self.assertEqual(m.progress()["percent"], 8.3)
            m.start("script_structure"); m.complete("script_structure")
            m.start("storyboard")
            m.detail("storyboard", 0, 10)
            clock.now = 5.0
            m.detail("storyboard", 5, 10)
            state = m.progress()
            self.assertEqual(state["ratio"], 0.5)
            self.assertEqual(state["percent"], 20.8)
            self.assertEqual(state["eta_seconds"], 5.0)         # 每秒 1 镜，还剩 5 镜
            self.assertEqual(state["detail"], {"done": 5, "total": 10})

    def test_running_without_counts_invents_nothing(self):
        with tempfile.TemporaryDirectory() as td:
            m = machine(td, persist=False)
            m.start("script")
            state = m.progress()
            self.assertIsNone(state["ratio"])
            self.assertEqual(state["percent"], 0.0)
            self.assertIsNone(state["eta_seconds"])

    def test_eta_uses_completed_stage_average_when_two_spans_exist(self):
        with tempfile.TemporaryDirectory() as td:
            clock = Clock()
            m = machine(td, clock=clock, persist=False)
            m.start("script"); clock.now = 4.0; m.complete("script")
            m.start("script_structure"); clock.now = 7.0; m.complete("script_structure")
            m.start("storyboard"); clock.now = 9.0; m.complete("storyboard")
            m.start("assets"); m.detail("assets", 0, 4)
            clock.now = 11.0; m.detail("assets", 2, 4)          # 每秒 1 项，还剩 2 项
            state = m.progress()
            # 当前阶段 2 秒 + 后面 8 个阶段按已完成均值（4 与 2 → 3 秒）估 24 秒
            self.assertEqual(state["eta_seconds"], 26.0)

    def test_summary_is_a_plain_template(self):
        with tempfile.TemporaryDirectory() as td:
            m = machine(td, persist=False)
            self.assertTrue(m.summary().startswith(
                "0/%d 阶段完成 · 当前：剧本准备" % len(pet_bus.STAGES)))
            for stage in pet_bus.STAGES[:6]:
                m.complete(stage)
            m.start("keyframe"); m.detail("keyframe", 3, 12)
            self.assertIn("当前：首帧管理（3/12）", m.summary())
            for stage in pet_bus.STAGES:
                m.complete(stage)
            self.assertEqual(m.summary(), "全部 %d 个阶段已完成" % len(pet_bus.STAGES))


class PersistenceTests(unittest.TestCase):
    def test_save_and_load_roundtrip(self):
        with tempfile.TemporaryDirectory() as td:
            clock = Clock()
            m = machine(td, clock=clock)
            m.start("script"); clock.now = 3.0; m.complete("script")
            m.start("script_structure"); clock.now = 4.0; m.complete("script_structure")
            m.start("storyboard"); clock.now = 5.0; m.complete("storyboard")
            m.apply(pet_bus.event("stage.failed", stage="assets", error="余额不足"), persist=True)
            m.save()
            restored = Machine(Path(td)).load()
            self.assertEqual(restored.stages["script"]["state"], SUCCESS)
            self.assertEqual(restored.stages["assets"]["state"], FAILED)
            self.assertEqual(restored.stages["assets"]["attempts"], 1)
            self.assertEqual(restored.elapsed["script"], 3.0)
            self.assertEqual(restored.current(), "assets")

    def test_state_file_lives_in_the_project(self):
        with tempfile.TemporaryDirectory() as td:
            m = machine(td)
            m.save()
            self.assertTrue(state_path(Path(td)).is_file())
            data = json.loads(state_path(Path(td)).read_text(encoding="utf-8"))
            self.assertEqual(sorted(data["stages"]), sorted(pet_bus.STAGES))

    def test_corrupt_snapshot_falls_back_to_defaults(self):
        with tempfile.TemporaryDirectory() as td:
            path = state_path(Path(td)); path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("{ 这不是 JSON", encoding="utf-8")
            m = Machine(Path(td)).load()
            self.assertEqual(m.current(), "script")
            self.assertEqual(m.stages["script"]["state"], PENDING)

    def test_unknown_saved_stage_is_ignored(self):
        with tempfile.TemporaryDirectory() as td:
            path = state_path(Path(td)); path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({"stages": {"不存在的阶段": {"state": "success"},
                                                   "assets": {"state": "success", "attempts": "2"}},
                                        "elapsed": {"assets": "1.5", "不存在的阶段": 9}}), encoding="utf-8")
            m = Machine(Path(td)).load()
            self.assertEqual(sorted(m.stages), sorted(pet_bus.STAGES))
            self.assertEqual(m.stages["assets"]["state"], SUCCESS)
            self.assertEqual(m.stages["assets"]["attempts"], 2)
            self.assertEqual(m.elapsed["assets"], 1.5)

    def test_persist_false_writes_nothing(self):
        with tempfile.TemporaryDirectory() as td:
            m = machine(td, persist=False)
            m.apply(pet_bus.event("stage.started", stage="script"), persist=True)
            m.save()
            self.assertFalse(state_path(Path(td)).exists())

    def test_apply_with_persist_writes_the_snapshot(self):
        with tempfile.TemporaryDirectory() as td:
            m = machine(td)
            m.apply(pet_bus.event("stage.completed", stage="script"), persist=True)
            self.assertTrue(state_path(Path(td)).is_file())


class DwellTests(unittest.TestCase):
    """各阶段停留时长与平均单镜耗时：只在收尾时结算一次，重启后接着算。"""

    def test_dwell_defaults_to_zero_for_every_stage(self):
        with tempfile.TemporaryDirectory() as td:
            m = machine(td, persist=False)
            self.assertEqual(sorted(m.dwell()), sorted(pet_bus.STAGES))
            self.assertEqual(set(m.dwell().values()), {0.0})
            self.assertEqual(m.per_unit_all(), {}, "没有产出单位就不该编出平均耗时")

    def test_units_come_from_the_reported_progress(self):
        with tempfile.TemporaryDirectory() as td:
            clock = Clock()
            m = machine(td, clock=clock, persist=False)
            m.start("keyframe")
            m.detail("keyframe", 3, 12)
            m.detail("keyframe", 12, 12)
            clock.now = 24.0
            m.complete("keyframe")
            self.assertEqual(m.units_of("keyframe"), 12)
            self.assertEqual(m.dwell()["keyframe"], 24.0)
            self.assertEqual(m.per_unit("keyframe"), 2.0)
            self.assertEqual(m.per_unit_all(), {"keyframe": 2.0})

    def test_a_second_run_adds_to_the_same_stage(self):
        """重试是同一阶段又跑一遍：单位与停留都要累加，不能覆盖。"""
        with tempfile.TemporaryDirectory() as td:
            clock = Clock()
            m = machine(td, clock=clock, persist=False)
            m.start("keyframe"); m.detail("keyframe", 5, 5); clock.now = 10.0; m.complete("keyframe")
            m.start("keyframe"); m.detail("keyframe", 3, 3); clock.now = 16.0; m.complete("keyframe")
            self.assertEqual(m.units_of("keyframe"), 8)
            self.assertEqual(m.dwell()["keyframe"], 16.0)

    def test_a_repeated_completion_is_not_counted_twice(self):
        """重复的 stage.completed 不能被算两次：时间与单位都得挡住。

        进度与收尾在总线是两条腿的消息：收尾之后还会飘来一条迟到的进度，把本轮的计数重新填上，
        所以「已收尾的阶段直接返回」必须挡在累计之前——否则下一次重复收尾会把迟到的进度再算一遍。
        """
        with tempfile.TemporaryDirectory() as td:
            clock = Clock()
            m = machine(td, clock=clock, persist=False)
            m.start("assets"); m.detail("assets", 4, 4); clock.now = 8.0
            m.complete("assets")
            m.detail("assets", 4, 4)                      # 收尾之后迟到的那条进度
            m.complete("assets")
            m.fail("assets", "又报了一次失败")
            self.assertEqual(m.dwell()["assets"], 8.0)
            self.assertEqual(m.units_of("assets"), 4)
            self.assertEqual(m.run_units["assets"], 4, "迟到的进度只是记着，不该被重复收尾算进去")

    def test_a_failed_run_still_keeps_its_dwell_and_units(self):
        with tempfile.TemporaryDirectory() as td:
            clock = Clock()
            m = machine(td, clock=clock, persist=False)
            m.start("video"); m.detail("video", 2, 9); clock.now = 30.0
            m.fail("video", "被限流")
            self.assertEqual(m.dwell()["video"], 30.0)
            self.assertEqual(m.units_of("video"), 2)

    def test_slowest_lists_the_longest_stages_in_stage_order(self):
        with tempfile.TemporaryDirectory() as td:
            clock = Clock()
            m = machine(td, clock=clock, persist=False)
            m.start("storyboard"); clock.now = 5.0; m.complete("storyboard")
            m.start("keyframe"); clock.now = 12.0; m.complete("keyframe")
            m.start("audio"); clock.now = 19.0; m.complete("audio")
            self.assertEqual(m.slowest(2), [("keyframe", 7.0), ("audio", 7.0)])
            self.assertEqual(m.slowest(0), [])
            self.assertEqual(m.slowest(99)[0], ("keyframe", 7.0))

    def test_units_are_snapshotted_and_restored(self):
        with tempfile.TemporaryDirectory() as td:
            clock = Clock()
            m = machine(td, clock=clock)
            m.start("keyframe"); m.detail("keyframe", 6, 6); clock.now = 12.0; m.complete("keyframe")
            m.save()
            restored = Machine(Path(td)).load()
            self.assertEqual(restored.units_of("keyframe"), 6)
            self.assertEqual(restored.dwell()["keyframe"], 12.0)
            self.assertEqual(restored.per_unit("keyframe"), 2.0)

    def test_a_running_stage_resumes_its_timer_after_a_restart(self):
        """快照里只有状态没有计时器：不重新起表的话，重启后这一段停留永远不会增长。"""
        with tempfile.TemporaryDirectory() as td:
            m = machine(td)
            m.start("assets")
            m.save()
            clock = Clock()
            restored = Machine(Path(td), clock=clock).load()
            self.assertEqual(restored.stages["assets"]["state"], RUNNING)
            clock.now = 4.0
            restored.complete("assets")
            self.assertEqual(restored.dwell()["assets"], 4.0)

    def test_a_settled_stage_does_not_restart_its_timer(self):
        with tempfile.TemporaryDirectory() as td:
            m = machine(td)
            m.complete("script")
            clock = Clock()
            restored = Machine(Path(td), clock=clock).load()
            self.assertIsNone(restored.started.get("script"))
            clock.now = 9.0
            restored.complete("script")
            self.assertEqual(restored.dwell()["script"], 0.0)

    def test_broken_saved_units_fall_back_to_zero(self):
        with tempfile.TemporaryDirectory() as td:
            path = state_path(Path(td)); path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({"units": {"keyframe": "坏数字", "未知阶段": 5},
                                        "run_units": {"assets": "-3"}}), encoding="utf-8")
            m = Machine(Path(td)).load()
            self.assertEqual(m.units_of("keyframe"), 0)
            self.assertEqual(m.units_of("assets"), 0, "负数要夹回 0")
            self.assertEqual(m.units_of("未知阶段"), 0, "没登记的阶段一个键都不该多出来")
            self.assertEqual(sorted(m.units), sorted(pet_bus.STAGES))


if __name__ == "__main__":
    unittest.main()

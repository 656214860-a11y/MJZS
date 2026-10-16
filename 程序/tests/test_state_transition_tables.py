"""生命周期状态机全转移表测试（R1617／Q8）。

R1610 Q8 的事实：既有生命周期用例是场景式——挑几个状态试一下，没有用表枚举"允许／禁止转移"，
也没有"每个状态至少被覆盖一次"的断言。本文件把三处真实存在状态转移的地方写成显式表：

1. 后台可恢复任务队列 `desktop_automation_service.PersistentBackgroundTaskQueue`：
   `queued` → `claimed` → `completed`／失败仍留在途；`queued` → `expired`／`cancelled`；
   禁止"未领取直接完成""已领取被取消／被 clear 清掉"。
2. 本地视频删除前置门 `video_lifecycle_service.mark_video_deleted`：`UNCERTAIN_STATES` 内
   任一在途／结果不确定状态禁止标记删除。
3. 重试状态机 `pet_agent.classify` ＋ `retry_plan`：可重试类目退避、参数类立即重试、
   达次数上限或不可重试类目进入终态。

三条都断言状态空间全覆盖（表里每个状态都被真实驱动过），并断言终态不再自行转出。
第 2／3 条的表由模块公开常量（`UNCERTAIN_STATES`／`VERDICTS`／`PATTERNS`）派生，所以新增
状态会自动进入用例；若新增状态与既有转移规则冲突，本用例会红。

刻意不做：不重写既有场景用例（`test_persistent_task_queue`／`test_video_lifecycle_service`／
`test_pet_agent` 保留原样），本文件只补"全表枚举"这一层。
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pet_agent
import video_lifecycle_service as video_service
from agent.core import read, save
from desktop_automation_service import PersistentBackgroundTaskQueue

# 队列状态空间：五个状态都必须在本文件的场景里被真实观测到。
QUEUE_STATES = ("queued", "claimed", "completed", "expired", "cancelled")
# (操作序列, 该行最终状态)：既有允许转移，也含禁止转移的"不变"期望。
QUEUE_SCENARIOS = (
    (("enqueue",), "queued"),
    (("enqueue", "pop"), "claimed"),
    (("enqueue", "pop", "run_ok"), "completed"),
    (("enqueue", "advance", "pop"), "expired"),
    (("enqueue", "cancel"), "cancelled"),
    (("enqueue", "clear"), "cancelled"),
    (("enqueue", "pop", "run_fail"), "claimed"),
    (("enqueue", "pop", "cancel"), "claimed"),
    (("enqueue", "pop", "clear"), "claimed"),
    (("enqueue", "finish_direct"), "queued"),
)
# 在途／结果不确定状态词表的本地副本：必须与 video_lifecycle_service.UNCERTAIN_STATES 相等。
# 冻结成副本而不是直接引用，是为了让"有人把一个状态从集合里删掉"这件事必须两处同步——
# 否则门禁会跟着被改的常量一起放行，等于没测。
UNCERTAIN_VIDEO_STATES = ("queued", "running", "submitting", "unknown", "succeeded")
# "已结算"侧取样：这些状态不该拦住删除。
SETTLED_VIDEO_STATES = ("downloaded", "imported", "failed", "rejected", "cancelled", "")


def _probe_handler(payload):
    if payload.get("fail"):
        raise RuntimeError("probe failure")
    return "ok"


class QueueTransitionTableTests(unittest.TestCase):
    """后台队列：每条转移都由公开接口驱动，状态取自落盘台账（不是内存副本）。"""

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / "queue.json"
        self._sequence = 0

    def _fresh_path(self):
        # 每条场景用独立台账文件：靠时钟常量排序时遗留行会抢走 pop，污染下一条场景。
        self._sequence += 1
        return self.path.with_name("queue-%d.json" % self._sequence)

    def _run_scenario(self, ops, path=None):
        path = path or self._fresh_path()
        clock = {"now": 1000.0}
        queue = PersistentBackgroundTaskQueue(path, handlers={"probe": _probe_handler},
                                             clock=lambda: clock["now"])
        row = {"id": None, "handle": None}
        observed = set()

        def state_now():
            data = read(path) if path.exists() else {"tasks": []}
            match = next((item for item in data["tasks"] if item["id"] == row["id"]), None)
            current = match["state"] if match else None
            if current:
                observed.add(current)
            return current

        for op in ops:
            if op == "enqueue":
                row["id"] = queue.enqueue_descriptor(
                    "probe", {"fail": "run_fail" in ops}, label="probe", expires_at=clock["now"] + 5)
            elif op == "pop":
                row["handle"] = queue.pop()
            elif op == "advance":
                clock["now"] += 10
            elif op == "run_ok":
                self.assertEqual(row["handle"]["fn"](), "ok")
            elif op == "run_fail":
                with self.assertRaises(RuntimeError):
                    row["handle"]["fn"]()
            elif op == "cancel":
                queue.cancel(row["id"])
            elif op == "clear":
                queue.clear()
            elif op == "finish_direct":
                queue._finish(row["id"], "completed")   # 只有 claimed 才能收尾
            else:
                raise AssertionError("未知操作：" + op)
            state_now()
        return state_now(), observed

    def test_transition_table_states_match(self):
        for ops, expected in QUEUE_SCENARIOS:
            with self.subTest(ops=ops):
                final, _observed = self._run_scenario(ops)
                self.assertEqual(final, expected, "操作序列 " + "/".join(ops) + " 的终态不符")

    def test_every_queue_state_is_observed(self):
        observed = set()
        for ops, _expected in QUEUE_SCENARIOS:
            _final, seen = self._run_scenario(ops)
            observed |= seen
        self.assertEqual(set(QUEUE_STATES) - observed, set(), "有状态从未被驱动过")

    def test_forbidden_transitions_do_not_move_the_row(self):
        # 已领取的行不可被取消、不被 clear 清掉，未领取的行不得直接收尾。
        for ops in (("enqueue", "pop", "cancel"), ("enqueue", "pop", "clear")):
            with self.subTest(ops=ops):
                _final, seen = self._run_scenario(ops)
                self.assertIn("claimed", seen)
                self.assertNotIn("cancelled", seen)
        _final, seen = self._run_scenario(("enqueue", "finish_direct"))
        self.assertEqual(seen, {"queued"})

    def test_claimed_row_stays_durable_until_reopened(self):
        # 在途失败只登记不回滚：重开队列后仍能看见它，且不会被重放。
        path = self._fresh_path()
        queue = PersistentBackgroundTaskQueue(path, handlers={"probe": _probe_handler})
        task_id = queue.enqueue_descriptor("probe", {"fail": True}, label="probe")
        with self.assertRaises(RuntimeError):
            queue.pop()["fn"]()
        reopened = PersistentBackgroundTaskQueue(path, handlers={"probe": _probe_handler})
        self.assertEqual([row["id"] for row in reopened.unresolved()], [task_id])
        self.assertEqual(reopened.labels(), [])


class VideoDeletionGateTableTests(unittest.TestCase):
    """本地视频删除前置门：`UNCERTAIN_STATES` 内的状态一律拦下，其余放行。"""

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.source = Path(directory.name) / "episode.json"
        save(self.source, {"shots": [{"id": "SH001"}, {"id": "SH002"}]})

    def _attempt(self, sid, versions):
        return video_service.mark_video_deleted(self.source, sid, versions, gateway={"publish_json": save})

    def test_uncertain_vocabulary_matches_the_frozen_copy(self):
        self.assertEqual(set(video_service.UNCERTAIN_STATES), set(UNCERTAIN_VIDEO_STATES),
                         "在途状态词表变了：确认是有意改动后同步本文件的冻结副本")

    def test_uncertain_states_are_exactly_the_refused_ones(self):
        refused, allowed = set(), set()
        for state in UNCERTAIN_VIDEO_STATES + SETTLED_VIDEO_STATES:
            with self.subTest(state=state):
                result = self._attempt("SH001", [{"state": state}])
                if isinstance(result, video_service.UserError):
                    refused.add(state)
                else:
                    self.assertTrue(result, "已结算状态不该被拦住：" + repr(state))
                    allowed.add(state)
                save(self.source, {"shots": [{"id": "SH001"}, {"id": "SH002"}]})
        self.assertEqual(refused, set(UNCERTAIN_VIDEO_STATES))
        self.assertEqual(allowed, set(SETTLED_VIDEO_STATES))
        self.assertEqual(refused | allowed, set(UNCERTAIN_VIDEO_STATES) | set(SETTLED_VIDEO_STATES),
                         "有状态既不被拦也不被放行：状态空间没驱动完")

    def test_any_uncertain_version_blocks_the_whole_shot(self):
        for uncertain in video_service.UNCERTAIN_STATES:
            versions = [{"state": "downloaded"}, {"state": uncertain}]
            with self.subTest(uncertain=uncertain):
                self.assertIsInstance(self._attempt("SH002", versions), video_service.UserError)
                self.assertFalse(read(self.source)["shots"][1].get("video_deleted"))
        self.assertTrue(self._attempt("SH002", [{"state": "downloaded"}]).ok)

    def test_empty_version_list_is_settled(self):
        self.assertTrue(self._attempt("SH002", []).ok)
        self.assertTrue(self._attempt("SH002", None).ok)


class RetryStateMachineTableTests(unittest.TestCase):
    """重试状态机：判定表（VERDICTS）与转移结果（retry_plan）必须一致，终态不再转出。"""

    PROBES = {category: next(mark for mark in marks if not str(mark).isdigit())
              for category, marks in pet_agent.PATTERNS}
    PROBES["unknown"] = "完全没认出来的错误"

    def test_probes_land_in_their_own_category(self):
        self.assertEqual(set(self.PROBES), set(pet_agent.VERDICTS))
        self.assertEqual({category for category, _marks in pet_agent.PATTERNS} | {"unknown"},
                         set(pet_agent.VERDICTS))
        for category, probe in self.PROBES.items():
            with self.subTest(category=category):
                self.assertEqual(pet_agent.classify(probe)["category"], category)

    def test_transition_table_matches_declared_verdicts(self):
        for category, (retry, action, _hint) in pet_agent.VERDICTS.items():
            probe = self.PROBES[category]
            for attempt in (0, 1, pet_agent.MAX_ATTEMPTS - 1, pet_agent.MAX_ATTEMPTS,
                            pet_agent.MAX_ATTEMPTS + 3):
                with self.subTest(category=category, attempt=attempt):
                    plan = pet_agent.retry_plan(attempt, probe)
                    self.assertEqual(plan["action"], action)
                    expected_allow = retry and attempt < pet_agent.MAX_ATTEMPTS
                    self.assertEqual(plan["allow"], expected_allow)
                    if expected_allow:
                        self.assertEqual(plan["next_attempt"], attempt + 1)
                        expected_delay = 0.0 if action == "fix_params" else pet_agent.backoff(attempt + 1)
                        self.assertEqual(plan["delay"], expected_delay)
                    else:
                        self.assertEqual(plan["next_attempt"], attempt, "终态不得自行前进")
                        self.assertIsNone(plan["delay"], "终态不得给出退避")

    def test_terminal_states_never_leave(self):
        terminal_probes = [self.PROBES[category] for category, verdict in pet_agent.VERDICTS.items()
                           if not verdict[0]]
        self.assertTrue(terminal_probes, "判定表里应当存在不可重试类目")
        for probe in terminal_probes:
            for attempt in (0, 1, pet_agent.MAX_ATTEMPTS + 3):
                with self.subTest(probe=probe, attempt=attempt):
                    self.assertFalse(pet_agent.retry_plan(attempt, probe)["allow"])
        timeout = self.PROBES["timeout"]
        exhausted = pet_agent.retry_plan(pet_agent.MAX_ATTEMPTS, timeout)
        self.assertFalse(exhausted["allow"])
        self.assertIn("交给您确认", exhausted["hint"])
        # 上限是硬边界：再加次数也不会重新放行。
        self.assertFalse(pet_agent.retry_plan(pet_agent.MAX_ATTEMPTS + 1, timeout)["allow"])

    def test_backoff_sequence_is_monotonic_and_capped(self):
        delays = [pet_agent.retry_plan(attempt, self.PROBES["timeout"])["delay"]
                  for attempt in range(pet_agent.MAX_ATTEMPTS)]
        self.assertEqual(delays, [30.0, 60.0, 120.0, 120.0])
        self.assertEqual(delays, sorted(delays), "退避必须单调不减")
        self.assertEqual(delays[-1], float(pet_agent.pet_llm.RETRY_DELAYS[-1]), "最后一档固定不翻倍")


if __name__ == "__main__":
    unittest.main()
"""车道不阻塞的三道硬闸：改动重叠在提交时拒绝，出口 CI 在占主干之前，
全量不让别的会话把 GUI 等到整段结束。源码被改回旧顺序时本文件变红。"""
import unittest

from tests.architecture._scan import ROOT

SCOPE = ROOT / "维护记录" / "基准脚本" / "branch_scope.py"
MERGE = ROOT / "scripts" / "merge_round.py"
SCHEDULING = ROOT / "selftest_scheduling.py"
RUNNER = ROOT / "run_selftests.py"
ENV = ROOT / "selftest_env.py"
RUNBOOK = ROOT / "runbook.md"
ARCHITECTURE = ROOT / "architecture.md"
RELEASE_SPEC = ROOT / "docs" / "specs" / "03_安装签名与分发.md"
ADR = ROOT / "docs" / "adr" / "0015-lane-flow-does-not-block-sessions.md"


def _text(path):
    return path.read_text(encoding="utf-8")


class LaneFlowGateTests(unittest.TestCase):
    def test_commit_rejects_overlapping_paths_not_only_new_files(self):
        text = _text(SCOPE)
        self.assertIn("def staged_files(", text)
        self.assertIn("added_only=False", text)
        report = text.split("def commit_gate_report", 1)[1]
        self.assertIn("未合入改动重叠", report)

    def test_exit_ci_runs_before_master_is_occupied(self):
        text = _text(MERGE)
        main = text.split("def main(", 1)[1].split("\ndef _merge_locked", 1)[0]
        locked = text.split("def _merge_locked", 1)[1]
        self.assertIn("run_branch_exit_ci", main)
        self.assertNotIn('"--no-commit"', main)
        self.assertIn('"--no-commit"', locked)
        self.assertNotIn("run_exit_ci(", locked)
        reclaim = text.split("def reclaim_dead_owned_merge", 1)[1].split("\ndef ", 1)[0]
        self.assertIn('state != "stale"', reclaim)
        self.assertIn('"merge", "--abort"', reclaim)

    def test_full_suite_cannot_hold_gui_for_the_whole_run(self):
        self.assertIn("GUI_FULL_SUITE_WAIT_SECONDS", _text(ENV))
        scheduling = _text(SCHEDULING)
        self.assertIn("def foreign_full_suite(", scheduling)
        self.assertIn("GUI_FULL_SUITE_WAIT_SECONDS", scheduling)
        runner = _text(RUNNER)
        self.assertIn("yield_between=full_safe", runner)
        self.assertIn("归还 GUI 令牌", runner)

    def test_design_docs_carry_the_loop_into_later_rounds(self):
        runbook = _text(RUNBOOK)
        loop = runbook.split("**现行开发闭环", 1)[1].split("**领号与队列", 1)[0]
        for phrase in ("full-safe-runner.lock", "merge-lane.lock", "GUI_DEFERRED",
                       "出口 CI 在车道工作树", "只接受快进", "distribution_build.py",
                       "test_lane_flow_gates.py"):
            self.assertIn(phrase, loop, phrase)
        architecture = _text(ARCHITECTURE)
        self.assertIn("test_lane_flow_gates.py", architecture)
        self.assertIn("full-safe-runner.lock", architecture)
        spec = _text(RELEASE_SPEC)
        self.assertIn("### 1.1 现行发布闭环", spec)
        self.assertIn("仓库已推送", spec)
        decision = _text(ADR)
        self.assertIn("- 状态：已接受", decision)
        self.assertIn("full-safe-runner.lock", decision)
        self.assertIn("runbook.md", decision)
        checklist = _text(ROOT / "说明" / "发布检查单.md")
        self.assertIn("不覆盖旧发布目录", checklist)
        self.assertIn("新空目录", checklist)
        self.assertNotIn("手工解压覆盖", checklist)
        pits = _text(ROOT / "说明" / "已知坑与不可破坏契约.md")
        self.assertIn("full-safe-runner.lock", pits)
        self.assertIn("C20", pits)
        registry = _text(ROOT / "说明" / "工程文档登记表.md")
        self.assertIn("docs/review/安装更新与恢复方案_A15.md", registry)
        self.assertIn("0015-lane-flow-does-not-block-sessions.md", registry)
        self.assertIn("0015-lane-flow-does-not-block-sessions.md",
                      _text(ROOT / "文档导航.md"))


if __name__ == "__main__":
    unittest.main()

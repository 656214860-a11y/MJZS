"""覆盖率基线与度量工具门禁（R1616／Q7）。

R1610 Q7 的事实：本仓没有行／分支覆盖率度量，`测试分层基线.json` 只记用例计数与耗时，
"覆盖核心路径"只能靠"对应用例存在"推断。本仓零运行时依赖，且随附解释器
（Python 3.15.0a2）未随附标准库 `trace`，故不引入 coverage.py 也不依赖 trace，
而是新增 `scripts/coverage_report.py`：用 `sys.settrace` 对定向用例测量生产模块行覆盖，
把结果沉淀为 `维护记录/覆盖率基线.json`。

本门禁只做四件事，**不重跑测量**：
1. 基线结构自洽（百分比＝covered/total、计数与列表一致、来源必须是用例全通过的那次测量）。
2. 基线登记项在磁盘上都存在，且基线模块集合与生产运行时口径相等（防口径漂移）。
3. 核心路径（计费／状态机／发布／队列）设下限阈值，低于阈值即失败。
4. 子进程真跑一次工具（小目标），证明工具在随附解释器上可用且确实采到覆盖。

诚实边界：阈值只对"基线里记录的那次测量"成立。本轮**不重跑测量**、也不把覆盖率接进
每次提交的强制门禁，因此它不能发现"代码改了但没刷新基线"的退化；刷新基线必须重跑工具
（命令见工具 docstring），工具在目标用例失败时拒绝写基线。
"""
from __future__ import annotations

import ast
import json
import os
import re
import subprocess
import sys
import unittest
from pathlib import Path

from tests.architecture._scan import ROOT, production_runtime_files

BASELINE = ROOT / "维护记录" / "覆盖率基线.json"
TOOL = ROOT / "scripts" / "coverage_report.py"
# 核心路径下限：按 R1616 实测值约七成向下取整，只挡"刷新基线时的塌陷"，不是质量目标。
CORE_FLOORS = {
    "pet_llm.py": 50.0,  # 计费：RequestLedger 记账与金额不变量
    "usage_overview.py": 18.0,  # 计费：用量与成本汇总
    "keyframe_lifecycle_service.py": 65.0,  # 状态机：首帧生命周期
    "video_lifecycle_service.py": 75.0,  # 状态机：视频生命周期
    "asset_batch_lifecycle.py": 28.0,  # 状态机：资产批次生命周期
    "agent/publication.py": 70.0,  # 发布：原子发布
    "desktop_automation_service.py": 30.0,  # 队列：PersistentBackgroundTaskQueue
}
# 工具自检目标：取第一个存在的即可，避免某个用例改名后本门禁误红。
SMOKE_TARGETS = (
    "tests.test_money_invariants",
    "tests.test_artifact_schema",
    "tests.test_request_ledger",
)
_COVERED_LINE = re.compile(r"模块被覆盖：(\d+)/(\d+)")


def _has_statements(path: Path) -> bool:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except SyntaxError:
        return True  # 语法错误由语法用例报，这里不重复判定
    return any(isinstance(node, ast.stmt) for node in ast.walk(tree))


class CoverageBaselineTests(unittest.TestCase):
    def _baseline(self) -> dict:
        if not BASELINE.is_file():
            self.fail(f"缺少覆盖率基线 {BASELINE}；跑 scripts/coverage_report.py 生成")
        return json.loads(BASELINE.read_text(encoding="utf-8"))

    def test_baseline_is_self_consistent(self):
        data = self._baseline()
        for key in ("targets", "tests_ok", "modules", "modules_covered", "modules_total"):
            self.assertIn(key, data, f"基线缺少字段 {key}")
        self.assertTrue(data["tests_ok"], "基线必须来自目标用例全通过的一次测量")
        self.assertTrue(data["targets"], "基线未登记任何测量目标")
        rows = data["modules"]
        self.assertEqual(data["modules_total"], len(rows), "modules_total 与列表长度不一致")
        self.assertEqual(data["modules_covered"], sum(1 for row in rows if row["covered"] > 0),
                         "modules_covered 与逐行统计不一致")
        self.assertEqual(len({row["module"] for row in rows}), len(rows), "基线存在重复模块")
        for row in rows:
            self.assertGreater(row["total"], 0, f'{row["module"]} 可执行行数为 0，不应登记')
            self.assertLessEqual(row["covered"], row["total"], f'{row["module"]} 覆盖行数超过总行数')
            self.assertGreaterEqual(row["covered"], 0, f'{row["module"]} 覆盖行数为负')
            self.assertEqual(row["percent"], round(100.0 * row["covered"] / row["total"], 1),
                             f'{row["module"]} 百分比与 covered/total 不自洽')

    def test_baseline_modules_exist_and_keep_production_scope(self):
        data = self._baseline()
        registered = {row["module"] for row in data["modules"]}
        for name in sorted(registered):
            self.assertTrue((ROOT / name).is_file(), f"基线登记了不存在的模块 {name}")
        expected = {path.relative_to(ROOT).as_posix() for path in production_runtime_files()
                    if _has_statements(path)}
        self.assertEqual(registered, expected,
                         "基线模块集合与生产运行时口径不一致；新增／删除生产模块后须重跑工具刷新基线")

    def test_core_paths_meet_recorded_floor(self):
        rows = {row["module"]: row for row in self._baseline()["modules"]}
        for name, floor in CORE_FLOORS.items():
            self.assertIn(name, rows, f"核心模块 {name} 不在基线内（被改名／拆分？须重跑工具刷新基线）")
            self.assertGreaterEqual(rows[name]["percent"], floor,
                                    f"{name} 记录覆盖 {rows[name]['percent']}% 低于下限 {floor}%；"
                                    "若属真实退化须先补用例，不得为过门禁而调低下限")

    def test_coverage_tool_runs_on_bundled_interpreter(self):
        self.assertTrue(TOOL.is_file(), f"缺少覆盖率工具 {TOOL}")
        target = next((name for name in SMOKE_TARGETS if (ROOT / Path(*name.split(".")).with_suffix(".py")).is_file()), None)
        self.assertIsNotNone(target, f"覆盖率工具自检目标全部缺失：{SMOKE_TARGETS}")
        env = {key: value for key, value in os.environ.items() if key != "PYTHONPATH"}
        completed = subprocess.run(
            [sys.executable, "-B", str(TOOL), target, "--quiet"],
            cwd=str(ROOT), env=env, capture_output=True, text=True, timeout=180)
        self.assertEqual(completed.returncode, 0,
                         f"覆盖率工具退出码 {completed.returncode}：{completed.stderr.strip()[-400:]}")
        matched = _COVERED_LINE.search(completed.stdout)
        self.assertIsNotNone(matched, f"覆盖率工具未输出覆盖统计：{completed.stdout.strip()[-400:]}")
        self.assertGreaterEqual(int(matched.group(1)), 1,
                                f"工具在 {target} 上一条生产行都没采到，tracer 可能失效")
        self.assertEqual(int(matched.group(2)), len(self._baseline()["modules"]),
                         "工具与基线的模块口径不一致（一侧改了算法未刷新另一侧）")


if __name__ == "__main__":
    unittest.main()
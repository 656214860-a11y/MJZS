"""L0/L1 分支覆盖率棘轮门禁（SWE-2 T8.4）。

与 ``test_coverage_baseline.py`` 同一纪律：基线是**定向测量的快照**，本门禁
不重跑测量，只做四件事——

1. 基线结构自洽（百分比＝covered/points、计数与列表一致、来源必须是用例全通过的那次测量）。
2. 基线模块集合与 ``_layers.LAYERS`` 登记的 L0/L1 顶层模块相等（防口径漂移：
   新 L0/L1 模块或改名必须重跑 ``scripts/branch_coverage_report.py`` 刷新基线与下限表）。
3. 每个模块的实测分支覆盖不低于 ``维护记录/分支覆盖率下限.json`` 登记的棘轮下限；
   下限文件只许人工上调，工具重测不改写它，因此测量退化会在这里现形。
4. 子进程真跑一次工具（小目标），证明 tracer 在随附解释器上可用且确实采到决策点。

诚实边界：口径、排除项与「定向测量不是全量套件覆盖率」的声明见工具 docstring、
基线 JSON 的 ``metric``/``scope`` 字段与 runbook §11；单行复合语句、表达式短路、
``break`` 离开循环等在行粒度下不可分辨的分支不计入分母。
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tests.architecture._layers import LAYERS
from tests.architecture._scan import ROOT

BASELINE = ROOT / "维护记录" / "分支覆盖率基线.json"
FLOORS = ROOT / "维护记录" / "分支覆盖率下限.json"
TOOL = ROOT / "scripts" / "branch_coverage_report.py"
# 工具自检目标：取第一个存在的即可，避免某个用例改名后本门禁误红。
SMOKE_TARGETS = (
    "tests.test_artifact_schema",
    "tests.test_pet_bus",
    "tests.test_file_cache",
)
_COVERED_LINE = re.compile(r"模块：(\d+)；决策点：(\d+)/(\d+)")


def _l01_files() -> set[str]:
    expected = set()
    for name, layer in LAYERS.items():
        if layer not in (0, 1):
            continue
        path = ROOT / (name + ".py")
        if path.is_file():
            expected.add(name + ".py")
    return expected


class BranchCoverageFloorTests(unittest.TestCase):
    def _baseline(self) -> dict:
        if not BASELINE.is_file():
            self.fail(f"缺少分支覆盖率基线 {BASELINE}；跑 scripts/branch_coverage_report.py 生成")
        return json.loads(BASELINE.read_text(encoding="utf-8"))

    def _floors(self) -> dict:
        if not FLOORS.is_file():
            self.fail(f"缺少分支覆盖率下限表 {FLOORS}")
        return json.loads(FLOORS.read_text(encoding="utf-8"))

    def test_baseline_is_self_consistent(self):
        data = self._baseline()
        for key in ("targets", "tests_ok", "modules", "modules_total",
                    "points_total", "points_covered", "metric", "scope"):
            self.assertIn(key, data, f"基线缺少字段 {key}")
        self.assertTrue(data["tests_ok"], "基线必须来自目标用例全通过的一次测量")
        self.assertTrue(data["targets"], "基线未登记任何测量目标")
        self.assertIn("定向", data.get("scope", "") + data.get("metric", ""),
                      "基线必须声明定向测量口径")
        rows = data["modules"]
        self.assertEqual(data["modules_total"], len(rows), "modules_total 与列表长度不一致")
        self.assertEqual(len({row["module"] for row in rows}), len(rows), "基线存在重复模块")
        for row in rows:
            self.assertGreaterEqual(row["points"], 0, f'{row["module"]} 决策点数为负')
            self.assertLessEqual(row["covered"], row["points"],
                                 f'{row["module"]} 覆盖决策点数超过总数')
            expected = 100.0 if row["points"] == 0 else round(100.0 * row["covered"] / row["points"], 1)
            self.assertEqual(row["percent"], expected,
                             f'{row["module"]} 百分比与 covered/points 不自洽')
        self.assertEqual(data["points_total"], sum(r["points"] for r in rows),
                         "points_total 与逐行统计不一致")
        self.assertEqual(data["points_covered"], sum(r["covered"] for r in rows),
                         "points_covered 与逐行统计不一致")

    def test_module_set_matches_l01_registry(self):
        data = self._baseline()
        registered = {row["module"] for row in data["modules"]}
        for name in sorted(registered):
            self.assertTrue((ROOT / name).is_file(), f"基线登记了不存在的模块 {name}")
        self.assertEqual(registered, _l01_files(),
                         "基线模块集合与 _layers L0/L1 口径不一致；"
                         "新增／删除／改层 L0/L1 模块后须重跑工具刷新基线与下限表")

    def test_floors_cover_every_module_and_ratchet_holds(self):
        data = self._baseline()
        floors = self._floors().get("floors")
        self.assertIsInstance(floors, dict, "下限表缺少 floors 字段")
        rows = {row["module"]: row for row in data["modules"]}
        self.assertEqual(set(floors), set(rows),
                         "下限表与基线模块集合不一致；每个 L0/L1 模块都必须有棘轮下限")
        for name, floor in floors.items():
            self.assertIsInstance(floor, (int, float), f"{name} 下限不是数字")
            self.assertGreaterEqual(floor, 0.0, f"{name} 下限为负")
            self.assertLessEqual(floor, 100.0, f"{name} 下限超过 100")
            self.assertGreaterEqual(rows[name]["percent"], floor,
                                    f"{name} 实测 {rows[name]['percent']}% 低于棘轮下限 {floor}%；"
                                    "若属真实退化须先补用例，不得为过门禁而调低下限")

    def test_branch_coverage_tool_runs_on_bundled_interpreter(self):
        self.assertTrue(TOOL.is_file(), f"缺少分支覆盖率工具 {TOOL}")
        target = next((name for name in SMOKE_TARGETS
                       if (ROOT / Path(*name.split(".")).with_suffix(".py")).is_file()), None)
        self.assertIsNotNone(target, f"工具自检目标全部缺失：{SMOKE_TARGETS}")
        env = {key: value for key, value in os.environ.items() if key != "PYTHONPATH"}
        completed = subprocess.run(
            [sys.executable, "-B", str(TOOL), target, "--quiet"],
            cwd=str(ROOT), env=env, capture_output=True, text=True, timeout=600)
        self.assertEqual(completed.returncode, 0,
                         f"分支覆盖率工具退出码 {completed.returncode}：{completed.stderr.strip()[-400:]}")
        matched = _COVERED_LINE.search(completed.stdout)
        self.assertIsNotNone(matched, f"工具未输出覆盖统计：{completed.stdout.strip()[-400:]}")
        self.assertEqual(int(matched.group(1)), len(self._baseline()["modules"]),
                         "工具与基线的模块口径不一致（一侧改了算法未刷新另一侧）")
        self.assertGreater(int(matched.group(3)), 0,
                           "工具在 L0/L1 上一条决策点都没采到，tracer 可能失效")


if __name__ == "__main__":
    unittest.main()

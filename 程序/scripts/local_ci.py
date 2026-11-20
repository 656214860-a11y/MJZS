"""本地持续集成（R1428，路线图 G）：随附解释器依次跑默认冒烟、增量门禁与安全全量。

由 ``开发者工具/本地CI.cmd`` 调用；日志以 UTF-8 写入 ``程序/logs/ci_最近.log``，退出码非 0 即失败。
通知分发器在 ``DRAMA_SUPPRESS_MODAL=1`` 下不弹系统模态框，整轮可无人值守跑完。

模式（``开发者工具/本地CI.cmd <模式>``）：

- 默认：默认冒烟 → 安全全量自检（``run_selftests.py --all --safe``，含架构门禁），用时约 8 分钟；
- ``quick``：默认冒烟 → 增量门禁，改动少时的快跑；
- ``targets``：按 ``logs/ci_targets.txt`` 逐行定向复跑；
- ``release``（U2）：``exit`` 全部步骤再加分发副本自检，发布前跑，非 0 即不得发布；
- ``exit``（R1624／Q10）：**静态门禁 → 架构门禁 → 默认冒烟**，不跑安全全量。这是机器可判定的
  「CI 通过」出口——非 0 即失败，约 4 分钟，供提交前与流水线首段使用。静态门禁单列在前是为了
  快速失败（秒级命中无效转义、裸 ``print``、行数上限、静默异常等），不必等完 3 分钟的架构全跑。
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

PROGRAM = Path(__file__).resolve().parents[1]
LOG = PROGRAM / "logs" / "ci_最近.log"
STEPS = (
    ("默认冒烟", ["smoke_test.py"]),
    ("增量门禁", ["smoke_test.py", "--gate"]),
    ("安全全量自检", ["run_selftests.py", "--all", "--safe"]),
)
# 完整 CI 不走增量门禁：改动多时它会触到 900 秒上限而中止，安全全量已覆盖同一批用例。
FULL_STEPS = (
    STEPS[0],
    STEPS[2],
)
# R1624／Q10：静态门禁子集单列，先于架构全跑，命中即快速失败。
STATIC_GATE_TESTS = (
    "tests.architecture.test_static_hygiene",
    # R1624：静态名字检查（用了没定义的名字＝用户侧 NameError）也是静态门禁，别等架构全跑。
    "tests.test_static_names",
    "tests.architecture.test_print_ratchet",
    "tests.architecture.test_module_size_ratchet",
    "tests.architecture.test_function_size_ratchet",
    "tests.architecture.test_silent_exception_ratchet",
    "tests.architecture.test_todo_comment_snapshot",
    "tests.architecture.test_skip_hygiene",
    # R2-G2：文案规则（弹窗行数/按钮字数/命名统一）违规合入后才被全量发现，提进静态门禁拦在合入前。
    "tests.test_copy_rules",
)
# 机器可判定的「CI 通过」出口：静态门禁＋架构门禁＋默认冒烟，非 0 即失败。
EXIT_STEPS = (
    STEPS[0],
    ("静态门禁", ["-m", "unittest", *STATIC_GATE_TESTS]),
    ("架构门禁", ["smoke_test.py", "--architecture"]),
)

# U2：发布出口＝CI 出口＋分发副本自检（构建→校验→副本解释器导入入口模块）。
RELEASE_STEPS = (*EXIT_STEPS, ("分发自检", ["scripts/distribution_selfcheck.py"]))


def main(argv=None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if "release" in args:
        steps = RELEASE_STEPS
    elif "exit" in args:
        steps = EXIT_STEPS
    elif "quick" in args:
        steps = STEPS[:2]
    else:
        steps = FULL_STEPS
    targets = PROGRAM / "logs" / "ci_targets.txt"
    if "targets" in args and targets.is_file():
        # 定向复跑：ci_targets.txt 每行一个 unittest 目标（如 tests.test_idea_chat），逐个详细输出。
        names = [line.strip() for line in targets.read_text(encoding="utf-8").splitlines() if line.strip()]
        steps = tuple(("定向 " + name, ["-m", "unittest", "-v", name]) for name in names)
    env = dict(os.environ, DRAMA_SUPPRESS_MODAL="1", DRAMA_SUPPRESS_NETWORK="1", PYTHONIOENCODING="utf-8",
               PYTHONPATH=os.pathsep.join(filter(None, (str(PROGRAM / "tests"), str(PROGRAM),
                                                        os.environ.get("PYTHONPATH", "")))))
    LOG.parent.mkdir(parents=True, exist_ok=True)
    failed = False
    with LOG.open("w", encoding="utf-8") as log:
        log.write("[CI] 开始 %s\n" % time.strftime("%Y-%m-%d %H:%M:%S"))
        for index, (label, command) in enumerate(steps, 1):
            print("[CI] %d/%d %s..." % (index, len(steps), label), flush=True)
            log.write("\n[CI] === %s ===\n" % label)
            log.flush()
            started = time.perf_counter()
            result = subprocess.run([sys.executable, "-B", *command], cwd=PROGRAM, env=env,
                                    stdout=log, stderr=subprocess.STDOUT, check=False)
            log.write("[CI] %s 退出码 %d，用时 %.1f 秒\n" % (label, result.returncode,
                                                         time.perf_counter() - started))
            if result.returncode != 0 and "targets" in args:
                failed = True
                continue
            if result.returncode != 0:
                log.write("[CI] 失败\n")
                print("[CI] 失败：%s，日志 %s" % (label, LOG), flush=True)
                return result.returncode or 1
        if failed:
            log.write("[CI] 失败\n")
            return 1
        log.write("[CI] 通过\n")
        # T8.3：基准趋势只告警不阻断——在主步骤之后、with 块内写日志。
        trend = subprocess.run([sys.executable, "-B", "scripts/benchmark_trend.py"], cwd=PROGRAM,
                               capture_output=True, text=True, check=False,
                               encoding="utf-8", errors="replace")
        for line in (trend.stdout or "").splitlines():
            print(line, flush=True)
            log.write("%s\n" % line)
    print("[CI] 通过，日志 %s" % LOG, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

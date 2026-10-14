"""本地持续集成（R1428，路线图 G）：随附解释器依次跑默认冒烟、增量门禁与安全全量。

由根目录 ``本地CI.cmd`` 调用；日志以 UTF-8 写入 ``程序/logs/ci_最近.log``，退出码非 0 即失败。
通知分发器在 ``DRAMA_SUPPRESS_MODAL=1`` 下不弹系统模态框，整轮可无人值守跑完。
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


def main(argv=None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    steps = STEPS[:2] if "quick" in args else FULL_STEPS
    targets = PROGRAM / "logs" / "ci_targets.txt"
    if "targets" in args and targets.is_file():
        # 定向复跑：ci_targets.txt 每行一个 unittest 目标（如 tests.test_idea_chat），逐个详细输出。
        names = [line.strip() for line in targets.read_text(encoding="utf-8").splitlines() if line.strip()]
        steps = tuple(("定向 " + name, ["-m", "unittest", "-v", name]) for name in names)
    env = dict(os.environ, DRAMA_SUPPRESS_MODAL="1", PYTHONIOENCODING="utf-8",
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
    print("[CI] 通过，日志 %s" % LOG, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""一条命令完成合并轮：合入分支 → 领号 → 状态页抬头 → 结果文件 → 提交。

在主检出（master）的程序目录下运行，不要在 WIP 工作树里运行。合并先用 ``--no-commit`` 试做，冲突就
中止并还原，不浪费轮次号；成功才领号、改抬头、写结果文件，再交给 ``commit_round`` 提交（白名单取自暂存清单）。

用法::

    python -B scripts/dev.py merge codex/wip-R2300 -s "R2300（说明）合入 master，无冲突"

不跑测试、不推送；合并后的后台全量验收仍按 AGENTS.md 核对。
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

PROGRAM = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(PROGRAM), str(PROGRAM / "scripts"), str(PROGRAM / "维护记录" / "基准脚本")]
import commit_round  # noqa: E402
import round_claim  # noqa: E402

STATUS = PROGRAM / "project_status.md"
LOCAL_ONLY = (".claude/settings.local.json",)  # 缓存 TTL 钩子会改它，不属于待合并内容
HEADER_RE = re.compile(r"^更新：[\d-]+｜当前轮次：\d+（(?P<inner>.*?)）(?=｜|$)", re.M)


def bump_status(text: str, number: int, summary: str, today: date) -> str:
    """抬头改成「当前轮次：N+1」，上一轮只保留前一轮的首句，不让抬头越写越长。"""
    found = HEADER_RE.search(text)
    if not found:
        raise ValueError("project_status.md 找不到「更新：…｜当前轮次：N（…）」抬头")
    previous = found.group("inner").split("上一轮：")[0].strip().rstrip("。；")
    head = "更新：%s｜当前轮次：%d（R%d 合并轮：%s；断言未动；未跑全量。上一轮：%s。）" % (
        today.isoformat(), number + 1, number, summary.rstrip("。"), previous)
    return text[:found.start()] + head + text[found.end():]


def foreign_changes(porcelain: str) -> list[str]:
    """未提交的已跟踪改动里，去掉本机设置文件后剩下的。"""
    return [line for line in porcelain.splitlines() if line.strip() and not line[3:].strip('"').endswith(LOCAL_ONLY)]


def result_text(number: int, branch: str, summary: str) -> str:
    return ("# R%d 合并轮结果\n\n- 轮次类型：合并轮。\n- 合入：`%s` 到 master。\n- 说明：%s\n"
            "- 冲突：无（有冲突时本命令中止，不领号）。断言未动。未跑全量。\n" % (number, branch, summary))


def _git(*args: str) -> subprocess.CompletedProcess:
    return commit_round._git(*args)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("branch", help="要合入 master 的分支")
    parser.add_argument("-s", "--summary", required=True, help="一句话说明，写进状态页抬头和结果文件")
    args = parser.parse_args(argv)

    if _git("symbolic-ref", "--short", "HEAD").stdout.strip() != "master":
        print("必须在 master 检出里运行。", file=sys.stderr)
        return 2
    if foreign_changes(_git("status", "--porcelain", "--untracked-files=no").stdout):
        print("master 检出有未提交改动或他人暂存，先处理再合并。", file=sys.stderr)
        return 2
    # 先等全量验收锁再领号：等锁可能几十分钟，期间别的会话会领走下一个号，领早了提交就被钩子拒。
    if not commit_round.wait_for_lock(commit_round.common_dir(), 30 * 60):
        print("等全量验收锁超过 30 分钟，未合并。", file=sys.stderr)
        return 3
    merged = _git("merge", "--no-commit", "--no-ff", args.branch)
    if merged.returncode:
        _git("merge", "--abort")
        print("合并有冲突，已中止并还原，未领号：\n" + (merged.stdout + merged.stderr).strip(), file=sys.stderr)
        return 1
    number = round_claim.claim_next(common_dir=commit_round.common_dir(),
                                    tasks_round=PROGRAM / "tasks_round", root=round_claim.ROOT)
    STATUS.write_text(bump_status(STATUS.read_text(encoding="utf-8"), number, args.summary, date.today()),
                      encoding="utf-8", newline="")
    result = PROGRAM / "tasks_round" / ("tasks_round_%d_result.md" % number)
    result.write_text(result_text(number, args.branch, args.summary), encoding="utf-8", newline="\n")
    return commit_round.main(["-m", "R%d: 合入 %s 到 master（合并轮）：%s\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
                              % (number, args.branch, args.summary),
                              "project_status.md", str(result.relative_to(PROGRAM))])


if __name__ == "__main__":
    raise SystemExit(main())

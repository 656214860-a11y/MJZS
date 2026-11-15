"""一条命令完成合并轮：合入分支 → 领号 → 状态页抬头 → 结果文件 → 提交。

在主检出（master）的程序目录下运行，不要在 WIP 工作树里运行。合并先用 ``--no-commit`` 试做，冲突就
中止并还原，不浪费轮次号；成功才领号、改抬头、写结果文件，再交给 ``commit_round`` 提交（白名单取自暂存清单）。

用法::

    python -B scripts/dev.py merge codex/wip-R2300 -s "R2300（说明）合入 master，无冲突"

合并提交前跑 ``local_ci.py exit``（静态门禁→架构门禁→默认冒烟），非 0 则中止并还原，无跳过开关；不推送；
合并后的后台全量验收仍按 AGENTS.md 核对。
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


def merge_in_progress(cwd: Path = PROGRAM) -> bool:
    """MERGE_HEAD 存在＝有合并进行中，可能是其他会话的合并轮；此时绝不能 merge --abort。"""
    return commit_round._git("rev-parse", "-q", "--verify", "MERGE_HEAD", cwd=cwd).returncode == 0


def merge_head_is(branch: str, cwd: Path = PROGRAM) -> bool:
    """MERGE_HEAD 记录的被合入提交是否就是本次分支头；不等说明现场属于别人的合并。"""
    head = commit_round._git("rev-parse", "-q", "--verify", "MERGE_HEAD", cwd=cwd)
    want = commit_round._git("rev-parse", "-q", "--verify", branch, cwd=cwd)
    return (head.returncode == 0 and want.returncode == 0
            and head.stdout.strip() == want.stdout.strip())


def cleanup_failed_merge(branch: str, cwd: Path = PROGRAM) -> str:
    """合并失败后的现场处理：只有 MERGE_HEAD 确实是本分支的合并才 abort；
    否则是别的会话的合并现场，原样保留。返回 "conflict" 或 "foreign"。"""
    if merge_in_progress(cwd) and merge_head_is(branch, cwd):
        commit_round._git("merge", "--abort", cwd=cwd)
        return "conflict"
    return "foreign"


def run_exit_ci() -> int:
    """合入前的出口档（静态门禁→架构门禁→默认冒烟）；非 0 即不许合并，且没有跳过开关。"""
    return subprocess.call([sys.executable, "-B", str(PROGRAM / "scripts" / "local_ci.py"), "exit"], cwd=str(PROGRAM))


def abort_merge(result: Path) -> None:
    _git("merge", "--abort")
    result.unlink(missing_ok=True)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("branch", help="要合入 master 的分支")
    parser.add_argument("-s", "--summary", required=True, help="一句话说明，写进状态页抬头和结果文件")
    args = parser.parse_args(argv)

    if _git("symbolic-ref", "--short", "HEAD").stdout.strip() != "master":
        print("必须在 master 检出里运行。", file=sys.stderr)
        return 2
    if merge_in_progress():
        print("已有未完成的合并（MERGE_HEAD 存在），可能是其他会话的合并轮；"
              "待其提交或中止后再运行本命令。", file=sys.stderr)
        return 2
    if foreign_changes(_git("status", "--porcelain", "--untracked-files=no").stdout):
        print("master 检出有未提交改动或他人暂存，先处理再合并。", file=sys.stderr)
        return 2
    # 先等全量验收锁再合并：等锁可能几十分钟；轮次号在 --no-commit 成功后才领，
    # 避免冲突中止白白烧号。认领归属记入 round-claims.json，之后他车道领新号不再顶掉本合并提交。
    if not commit_round.wait_for_lock(commit_round.common_dir(), 30 * 60):
        print("等全量验收锁超过 30 分钟，未合并。", file=sys.stderr)
        return 3
    merged = _git("merge", "--no-commit", "--no-ff", args.branch)
    if merged.returncode:
        detail = (merged.stdout + merged.stderr).strip()
        if cleanup_failed_merge(args.branch) == "conflict":
            print("合并有冲突，已中止并还原，未领号：\n" + detail, file=sys.stderr)
        else:
            print("合并未能开始，或现场属于其他会话的合并（MERGE_HEAD 不匹配），未领号、未动现场：\n" + detail,
                  file=sys.stderr)
        return 1
    number = round_claim.claim_next(common_dir=commit_round.common_dir(),
                                    tasks_round=PROGRAM / "tasks_round", root=round_claim.ROOT)
    STATUS.write_text(bump_status(STATUS.read_text(encoding="utf-8"), number, args.summary, date.today()),
                      encoding="utf-8", newline="")
    result = PROGRAM / "tasks_round" / ("tasks_round_%d_result.md" % number)
    result.write_text(result_text(number, args.branch, args.summary), encoding="utf-8", newline="\n")
    code = run_exit_ci()
    if code:
        abort_merge(result)
        print("出口档 CI 未通过（退出码 %d），已中止合并并还原；轮次号 R%d 已被占用，下次领号会跳过。" % (code, number),
              file=sys.stderr)
        return code
    return commit_round.main(["-m", "R%d: 合入 %s 到 master（合并轮）：%s\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
                              % (number, args.branch, args.summary),
                              "project_status.md", str(result.relative_to(PROGRAM))])


if __name__ == "__main__":
    raise SystemExit(main())

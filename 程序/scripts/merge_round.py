"""一条命令完成合并轮：合入分支 → 领号 → 状态页抬头 → 结果文件 → 提交。

在主检出（master）的程序目录下运行，不要在 WIP 工作树里运行。合入前先把分支变基到当前
master：冲突就在该车道中止变基并退回，不占主干、不领号。变基干净后先在车道工作树跑出口 CI，
通过后才 ``--no-commit`` 占主干。失联合并道留下的 MERGE_HEAD，只有锁已静默且提交对得上才自动还原。
冲突就中止并还原，不领号；验收锁拿到后才领号改抬头写结果文件（CI 失败与等锁超时都不烧轮次号），再交给 ``commit_round`` 提交（白名单取自暂存清单）。

用法::

    python -B scripts/dev.py merge codex/wip-R2300 -s "R2300（说明）合入 master，无冲突"

合并提交前跑 ``local_ci.py exit``（静态门禁→架构门禁→默认冒烟），非 0 则中止并还原，无跳过开关；不推送；
合并后的后台全量验收仍按 AGENTS.md 核对。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import date
from pathlib import Path

PROGRAM = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(PROGRAM), str(PROGRAM / "scripts"), str(PROGRAM / "维护记录" / "基准脚本")]
import commit_round  # noqa: E402
import lock_lease  # noqa: E402
import round_claim  # noqa: E402

STATUS = PROGRAM / "project_status.md"
LOCAL_ONLY = (".claude/settings.local.json",)  # 缓存 TTL 钩子会改它，不属于待合并内容

# 变基冲突、车道不干净或变基现场已属于别人：退回该车道，不占主干、不领号。
REBASE_RETURNED = 5
MERGE_LANE_LOCK = "merge-lane.lock"
# MERGE_HEAD 超过该时长未结＝疑似僵死合并（等锁上限 30 分钟＋出口 CI 约 5 分钟＋提交余量）。
# 只报警不自动 abort：abort 别人的合并现场是破坏性操作，必须人工确认（R2564 事故）。
MERGE_HEAD_STALE_SECONDS = 45 * 60
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


RESULT_RE = re.compile(r"tasks_round_(\d+)_result\.md$")


def continuity_gap() -> int | None:
    """「当前轮次 == 最新结果轮次+1」的差值；0/None 为通过。合并候选 CI 期间本检查被跳过，
    领号写页后由这里复核——分支带更高结果号时在提交前拦下，不产生断档提交。"""
    nums = [int(m.group(1)) for path in (PROGRAM / "tasks_round").rglob("tasks_round_*_result.md")
            if (m := RESULT_RE.search(path.name))]
    if not nums:
        return None
    head = re.search(r"当前轮次：(\d+)", STATUS.read_text(encoding="utf-8"))
    return -1 if not head else int(head.group(1)) - (max(nums) + 1)


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


def merge_head_age_seconds(cwd: Path = PROGRAM):
    """MERGE_HEAD 文件龄期（秒）；无合并或取不到返回 None。用 git-path 解析，兼容工作树私有 gitdir。"""
    rel = commit_round._git("rev-parse", "--git-path", "MERGE_HEAD", cwd=cwd).stdout.strip()
    if not rel:
        return None
    path = Path(rel)
    if not path.is_absolute():
        path = (cwd / path).resolve()
    try:
        return time.time() - path.stat().st_mtime
    except OSError:
        return None


def worktree_for_branch(branch: str, cwd: Path = PROGRAM) -> Path | None:
    """分支当前检出的工作树；没有检出则返回 None。"""
    out = commit_round._git("worktree", "list", "--porcelain", cwd=cwd)
    current = None
    ref = "refs/heads/" + branch
    for line in out.stdout.splitlines():
        if line.startswith("worktree "):
            current = Path(line.split(" ", 1)[1])
        elif line == "branch " + ref:
            return current
    return None


def _git_path(name: str, cwd: Path) -> Path:
    rel = commit_round._git("rev-parse", "--git-path", name, cwd=cwd).stdout.strip()
    path = Path(rel)
    return path if path.is_absolute() else (cwd / path).resolve()


def rebase_in_progress(cwd: Path) -> bool:
    return _git_path("rebase-merge", cwd).exists() or _git_path("rebase-apply", cwd).exists()


def _rebase_in(wt: Path, upstream: str, branch: str) -> int:
    if rebase_in_progress(wt):
        print("车道 %s 已有未完成的变基，未动现场、未领号。" % branch, file=sys.stderr)
        return REBASE_RETURNED
    dirty = commit_round._git("status", "--porcelain", "--untracked-files=no", cwd=wt)
    if dirty.stdout.strip():
        print("分支 %s 的工作树有未提交改动，已退回车道，未领号。" % branch, file=sys.stderr)
        return REBASE_RETURNED
    done = commit_round._git("rebase", upstream, cwd=wt)
    if done.returncode == 0:
        return 0
    if rebase_in_progress(wt):
        commit_round._git("rebase", "--abort", cwd=wt)
    detail = ((done.stdout or "") + (done.stderr or "")).strip()
    print("变基到当前 master 发生冲突，已退回车道 %s，未占主干、未领号：\n%s" % (branch, detail),
          file=sys.stderr)
    return REBASE_RETURNED


def rebase_onto_master(branch: str, cwd: Path = PROGRAM) -> int:
    """把分支变基到当前 master。冲突则中止变基并退回该车道，不移动主干检出。"""
    master = commit_round._git("rev-parse", "master", cwd=cwd)
    if master.returncode:
        print("找不到 master，已退回车道 %s，未领号。" % branch, file=sys.stderr)
        return REBASE_RETURNED
    if commit_round._git("rev-parse", "-q", "--verify", branch, cwd=cwd).returncode:
        print("找不到分支 %s，已退回车道，未领号。" % branch, file=sys.stderr)
        return REBASE_RETURNED
    upstream = master.stdout.strip()
    if commit_round._git("merge-base", "--is-ancestor", upstream, branch, cwd=cwd).returncode == 0:
        return 0
    wt = worktree_for_branch(branch, cwd)
    if wt is not None and wt.resolve() == Path(cwd).resolve():
        print("分支 %s 正检出在当前主干工作树，已退回车道，未领号。" % branch, file=sys.stderr)
        return REBASE_RETURNED
    temporary = None
    if wt is None:
        temporary = Path(tempfile.mkdtemp(prefix="rebase-lane-"))
        added = commit_round._git("worktree", "add", "--quiet", str(temporary), branch, cwd=cwd)
        if added.returncode:
            shutil.rmtree(temporary, ignore_errors=True)
            detail = ((added.stdout or "") + (added.stderr or "")).strip()
            print("无法为 %s 准备变基工作树，已退回车道，未领号：\n%s" % (branch, detail),
                  file=sys.stderr)
            return REBASE_RETURNED
        wt = temporary
    try:
        return _rebase_in(wt, upstream, branch)
    finally:
        if temporary is not None:
            commit_round._git("worktree", "remove", "--force", str(temporary), cwd=cwd)
            shutil.rmtree(temporary, ignore_errors=True)


def cleanup_failed_merge(branch: str, cwd: Path = PROGRAM) -> str:
    """合并失败后的现场处理：只有 MERGE_HEAD 确实是本分支的合并才 abort；
    否则是别的会话的合并现场，原样保留。返回 "conflict" 或 "foreign"。"""
    if merge_in_progress(cwd) and merge_head_is(branch, cwd):
        commit_round._git("merge", "--abort", cwd=cwd)
        return "conflict"
    return "foreign"


def merge_lane_lock_path(cwd: Path = PROGRAM) -> Path:
    return commit_round.common_dir(cwd) / MERGE_LANE_LOCK


def reclaim_dead_owned_merge(cwd: Path = PROGRAM) -> bool:
    """合并道锁已静默，且 MERGE_HEAD 就是锁里记下的提交时，才中止这次合并。

    锁还活着、没有锁、或 MERGE_HEAD 对不上，一律不动现场。
    """
    if not merge_in_progress(cwd):
        return False
    path = merge_lane_lock_path(cwd)
    state, holder, _snapshot = lock_lease.inspect(str(path))
    if state != "stale":
        return False
    tip = str(holder.get("tip") or "")
    head = commit_round._git("rev-parse", "-q", "--verify", "MERGE_HEAD", cwd=cwd).stdout.strip()
    if not tip or tip != head:
        return False
    commit_round._git("merge", "--abort", cwd=cwd)
    lock_lease.reclaim(str(path))
    print("已还原失联合并道留下的 MERGE_HEAD（%s）。" % holder.get("branch", ""), file=sys.stderr)
    return True


def acquire_merge_lane(branch: str, tip: str, cwd: Path = PROGRAM) -> bool:
    """独占合并道。别人正持有则立即返回，不等。"""
    path = merge_lane_lock_path(cwd)
    payload = json.dumps(lock_lease.payload(os.getpid(), branch=branch, tip=tip), ensure_ascii=False)
    for _attempt in range(2):
        state, holder, _snapshot = lock_lease.inspect(str(path))
        if state == "live":
            print("合并道由 PID %s 持有（%s），本次未占主干、未领号。"
                  % (holder.get("pid"), holder.get("branch", "")), file=sys.stderr)
            return False
        if state == "stale":
            lock_lease.reclaim(str(path))
        try:
            descriptor = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            continue
        try:
            os.write(descriptor, payload.encode("utf-8"))
        finally:
            os.close(descriptor)
        lock_lease.arm(str(path))
        return True
    print("合并道锁未能独占，本次未占主干、未领号。", file=sys.stderr)
    return False


def release_merge_lane(cwd: Path = PROGRAM) -> None:
    path = merge_lane_lock_path(cwd)
    try:
        holder = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        holder = {}
    if holder.get("pid") not in (None, os.getpid()):
        return
    lock_lease.release(str(path))
    try:
        path.unlink()
    except OSError:
        pass


def lane_program(branch: str, cwd: Path = PROGRAM) -> Path | None:
    """分支工作树里的程序目录；没有出口 CI 脚本则不用。"""
    wt = worktree_for_branch(branch, cwd)
    if wt is None:
        return None
    program = wt / "程序"
    if (program / "scripts" / "local_ci.py").is_file():
        return program
    return None


def run_exit_ci(program: Path = PROGRAM) -> int:
    """合入前的出口档（静态门禁→架构门禁→默认冒烟）；非 0 即不许合并，且没有跳过开关。"""
    return subprocess.call(
        [sys.executable, "-B", str(program / "scripts" / "local_ci.py"), "exit"], cwd=str(program))


def run_branch_exit_ci(branch: str, cwd: Path = PROGRAM) -> int:
    """在分支自己的工作树里跑出口 CI。主干检出保持干净，失败不占主干、不领号。"""
    program = lane_program(branch, cwd)
    temporary = None
    if program is None:
        temporary = Path(tempfile.mkdtemp(prefix="merge-ci-"))
        added = commit_round._git("worktree", "add", "--quiet", str(temporary), branch, cwd=cwd)
        if added.returncode:
            shutil.rmtree(temporary, ignore_errors=True)
            detail = ((added.stdout or "") + (added.stderr or "")).strip()
            print("无法为 %s 准备出口 CI 工作树，未占主干、未领号：\n%s" % (branch, detail),
                  file=sys.stderr)
            return 1
        program = temporary / "程序"
        if not (program / "scripts" / "local_ci.py").is_file():
            commit_round._git("worktree", "remove", "--force", str(temporary), cwd=cwd)
            shutil.rmtree(temporary, ignore_errors=True)
            print("分支 %s 没有出口 CI 脚本，未占主干、未领号。" % branch, file=sys.stderr)
            return 1
    try:
        print("出口 CI 在车道工作树运行，主干检出保持干净：%s" % program, flush=True)
        return run_exit_ci(program)
    finally:
        if temporary is not None:
            commit_round._git("worktree", "remove", "--force", str(temporary), cwd=cwd)
            shutil.rmtree(temporary, ignore_errors=True)


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
    reclaim_dead_owned_merge()
    if merge_in_progress():
        age = merge_head_age_seconds()
        if age is not None and age > MERGE_HEAD_STALE_SECONDS:
            print("警告：MERGE_HEAD 已存在 %.0f 分钟，且不是失联合并道留下的现场。"
                  "请人工核实属主后决定提交或 git merge --abort；本命令不自动处理。"
                  % (age / 60), file=sys.stderr)
        print("已有未完成的合并（MERGE_HEAD 存在），可能是其他会话的合并轮；"
              "待其提交或中止后再运行本命令。", file=sys.stderr)
        return 2
    if foreign_changes(_git("status", "--porcelain", "--untracked-files=no").stdout):
        print("master 检出有未提交改动或他人暂存，先处理再合并。", file=sys.stderr)
        return 2
    aligned = rebase_onto_master(args.branch)
    if aligned:
        return aligned
    # 出口 CI 在车道工作树跑完再动主干。主干上只留合并、等锁、领号、提交。
    code = run_branch_exit_ci(args.branch)
    if code:
        print("出口档 CI 未通过（退出码 %d），未占主干、未领号。" % code, file=sys.stderr)
        return code
    tip = _git("rev-parse", args.branch).stdout.strip()
    if not acquire_merge_lane(args.branch, tip):
        return 2
    try:
        return _merge_locked(args)
    finally:
        release_merge_lane()


def _merge_locked(args) -> int:
    if merge_in_progress():
        print("已有未完成的合并（MERGE_HEAD 存在），未领号、未动现场。", file=sys.stderr)
        return 2
    merged = _git("merge", "--no-commit", "--no-ff", args.branch)
    if merged.returncode:
        detail = (merged.stdout + merged.stderr).strip()
        if cleanup_failed_merge(args.branch) == "conflict":
            print("合并有冲突，已中止并还原，未领号：\n" + detail, file=sys.stderr)
        else:
            print("合并未能开始，或现场属于其他会话的合并（MERGE_HEAD 不匹配），未领号、未动现场：\n" + detail,
                  file=sys.stderr)
        return 1
    # 出口 CI 已在占主干之前跑完。这里只等验收锁再领号。
    # CI 通过后才等锁再领号：等锁超时与提交失败都发生在领号之前，不再白白烧轮次号。
    if not commit_round.wait_for_lock(commit_round.common_dir(), 30 * 60):
        cleanup_failed_merge(args.branch)
        print("等全量验收锁超过 30 分钟，未合并、未领号。", file=sys.stderr)
        return 3
    number = round_claim.claim_next(common_dir=commit_round.common_dir(),
                                    tasks_round=PROGRAM / "tasks_round", root=round_claim.ROOT)
    STATUS.write_text(bump_status(STATUS.read_text(encoding="utf-8"), number, args.summary, date.today()),
                      encoding="utf-8", newline="")
    result = PROGRAM / "tasks_round" / ("tasks_round_%d_result.md" % number)
    result.write_text(result_text(number, args.branch, args.summary), encoding="utf-8", newline="\n")
    gap = continuity_gap()
    if gap:
        result.unlink(missing_ok=True)   # untracked 结果文件 merge --abort 不会带走，须显式删
        cleanup_failed_merge(args.branch)
        print("状态页轮次连续性自检失败（差 %d），已中止本分支合并还原；轮次号 R%d 已被占用。"
              % (gap, number), file=sys.stderr)
        return 4
    code = commit_round.main(["-m", "R%d: 合入 %s 到 master（合并轮）：%s\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
                              % (number, args.branch, args.summary),
                              "project_status.md", str(result.relative_to(PROGRAM))])
    if code and merge_in_progress() and merge_head_is(args.branch):
        # 提交没成但现场是本分支的：还原现场，避免 MERGE_HEAD 僵死阻塞后续合并（R2958 类事故）。
        abort_merge(result)
        print("合并提交未成功（退出码 %d），已中止本分支合并现场还原；轮次号 R%d 已被占用，下次领号会跳过。"
              % (code, number), file=sys.stderr)
    return code


if __name__ == "__main__":
    raise SystemExit(main())

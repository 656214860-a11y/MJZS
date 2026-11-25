"""一条命令完成「暂存 → 白名单 → 等全量验收锁 → 提交」。

pre-commit 钩子仅在 master/main/游离 HEAD 上、``full-safe-selftest.lock`` 存在时拒绝提交（工作分支不受锁限制，
直接提交，WIP 提交首行用 ``WIP: 说明``、免领轮次号，合入 master 前须整理成 R<轮次>）。超长 ``--all --safe``
只持有 ``full-safe-runner.lock``，不再创建这把提交锁，车道提交和合并不必等十几分钟。若仍有旧进程持着提交锁，
本脚本在 master 上把等待放进进程内：心跳静默满 3 分钟（旧锁则持有进程已不在）才回收，仍有效则静默轮询，直到释放或超时。
``git add`` / ``commit`` 撞上 index.lock 或其他 Git 锁时，按 0.2、0.4、0.8、1.6、3.2 秒再试 5 次。
钩子规则不变，不绕过。

用法（程序目录下）::

    python -B scripts/commit_round.py -m "R1931: 说明" [文件 ...]

不给文件就提交已暂存的内容；给了文件先 ``git add -- 文件``。白名单取自最终暂存清单，
不会用 ``git add -A``。领轮次号仍用 ``dev.py claim``（须在写结果文件前领，不能挪到提交时）。
"""
from __future__ import annotations

import argparse
import hashlib
import os
import re
import subprocess
import sys
import time
import tempfile
from pathlib import Path

PROGRAM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROGRAM))
import run_selftests  # noqa: E402

sys.path.insert(0, str(PROGRAM / "维护记录" / "基准脚本"))
import branch_scope  # noqa: E402
import round_evidence  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
import commit_retry
import test_move_audit  # noqa: E402
import taskbook_closure  # noqa: E402

POLL_SECONDS = 15
REPORT_SECONDS = 120
REJECT_MARK = "全量安全验收锁存在"
GIT_LOCK_DELAYS = (0.2, 0.4, 0.8, 1.6, 3.2)
ROUND_MESSAGE_RE = re.compile(r"^R(\d+):")


def with_agent_trailer(message: str, agent: str) -> str:
    """提交信息末尾加 ``Agent: <名称>`` 行（已有则不重复）；名称为空则原样返回。"""
    agent = (agent or "").strip()
    if not agent or any(line.startswith("Agent: ") for line in message.splitlines()):
        return message
    return message.rstrip("\n") + "\n\nAgent: " + agent


def check_test_move(message: str, root: Path) -> int:
    """提交信息首行以「R<n>: 测试搬家」开头时核对暂存区（规则 16）：只许移动测试与修 import；返回 0 放行，非 0 拒绝。"""
    if not test_move_audit.is_move_round(message):
        return 0
    problems = test_move_audit.audit_staged(root)
    for line in problems:
        print("拒绝提交：测试搬家轮 " + line, file=sys.stderr)
    return 5 if problems else 0


def check_scope_overlap(root: Path) -> int:
    """暂存内容与其他活跃车道的未合入改动有真实冲突、或双方新增了同名文件时拒绝；能自动合并的重叠只提示。

    合并提交（MERGE_HEAD）与主干分支不触发；被合入的源分支本就含同名新文件，
    属正常合并而非重复实现。"""
    if _git("rev-parse", "-q", "--verify", "MERGE_HEAD", cwd=root).returncode == 0:
        return 0
    branch = _git("symbolic-ref", "--quiet", "--short", "HEAD", cwd=root).stdout.strip()
    if branch in ("", "master", "main"):
        return 0
    report = branch_scope.commit_gate_report(root, exclude_branch=branch)
    for line in report["skipped"]:
        print("警告：" + line, file=sys.stderr)
    for line in report.get("notes", ()):
        print("提示：" + line, file=sys.stderr)
    for line in report["conflicts"]:
        print("拒绝提交：" + line, file=sys.stderr)
    return 5 if report["conflicts"] else 0


def check_taskbook_closure(message: str, root: Path) -> int:
    """声明「任务书收尾/完成」的提交必须通过闭环校验器（规则 35，R3039 决策 14）；返回 0 放行，5 拒绝。"""
    staged = [line for line in _git("diff", "--cached", "--name-only", cwd=root).stdout.splitlines() if line]
    if not taskbook_closure.declares_closure(message, staged):
        return 0
    problems = taskbook_closure.validate(tasks_round=root / "程序" / "tasks_round",
                                         completion_dir=root / "程序" / "tasks_round" / "任务完成")
    if problems:
        for line in problems:
            print("拒绝提交：" + line, file=sys.stderr)
        return 5
    return 0


def attach_evidence(message: str, keywords, root: Path, receipt=None) -> int:
    """R<N>（N 不早于证据制度起点）的提交必须带绿色证据文件：凭据扫描无命中，改了 .py 则定向测试须绿。

    返回 0 放行（证据已暂存），非 0 拒绝提交。"""
    matched = ROUND_MESSAGE_RE.match(message)
    if not matched or int(matched.group(1)) < round_evidence.EVIDENCE_REQUIRED_FROM:
        return 0
    number = int(matched.group(1))
    merging = _git("rev-parse", "-q", "--verify", "MERGE_HEAD", cwd=root).returncode == 0
    if receipt:
        with tempfile.TemporaryDirectory(dir=receipt.directory) as directory:
            temp = Path(directory)
            target = round_evidence.write_evidence(number, keywords, directory=temp, root=root)
            scan_ok, tests_ok, detail = round_evidence.judge(number, directory=temp)
            receipt.publish(receipt.evidence, target.read_bytes())
            result = PROGRAM / "tasks_round" / ("tasks_round_%d_result.md" % number)
            relative = result.relative_to(root).as_posix()
            if scan_ok and tests_ok and relative in staged_paths(*receipt.files):
                result_copy = temp / result.name
                result_copy.write_bytes(result.read_bytes())
                if round_evidence.stamp_result(result_copy, number, directory=temp):
                    receipt.publish(relative, result_copy.read_bytes())
    else:
        target = round_evidence.write_evidence(number, keywords, root=root, skip="merge-ci-exit" if merging else None)
        scan_ok, tests_ok, detail = round_evidence.judge(number)
        _git("add", "--", str(target), cwd=root).check_returncode()
        if scan_ok and tests_ok:
            result = PROGRAM / "tasks_round" / ("tasks_round_%d_result.md" % number)
            staged = _git("diff", "--cached", "--name-only", cwd=root).stdout.splitlines()
            if any(name.endswith(result.name) for name in staged) and round_evidence.stamp_result(result, number):
                _git("add", "--", str(result), cwd=root).check_returncode()
    if scan_ok and tests_ok:
        return 0
    print("拒绝提交：R%d 证据不通过（%s）。凭据命中先移除；改了 .py 须用 --tests <模块关键词> 跑定向测试且全绿。" % (number, detail),
          file=sys.stderr)
    return 4


def _git_lock_busy(text: str) -> bool:
    sample = (text or "").lower()
    if "another git process" in sample or "index.lock" in sample:
        return True
    return ".lock" in sample and "file exists" in sample


def _run_git(args, cwd, env=None) -> subprocess.CompletedProcess:
    """瞬时的 index.lock / ref 锁按指数退避再试 5 次，其它失败原样返回。"""
    command = ["git", "-c", "core.quotepath=false", *args]
    delays = iter(GIT_LOCK_DELAYS)
    while True:
        done = subprocess.run(command, cwd=cwd, env=env, capture_output=True,
                              text=True, encoding="utf-8", errors="replace")
        blob = (done.stderr or "") + (done.stdout or "")
        if done.returncode == 0 or not _git_lock_busy(blob):
            return done
        try:
            time.sleep(next(delays))
        except StopIteration:
            return done


def _git(*args: str, cwd: Path = PROGRAM) -> subprocess.CompletedProcess:
    return _run_git(args, cwd)


def staged_paths(*paths):
    result = _git("diff", "--cached", "--no-renames", "--name-only", "-z", "--", *paths)
    result.check_returncode()
    return set(filter(None, result.stdout.split("\0")))


def reject_other_paths(staged, allowed):
    unexpected = sorted(staged - allowed)
    if unexpected:
        print("显式提交遇到其他已暂存文件：" + "、".join(unexpected), file=sys.stderr)
    return bool(unexpected)


def common_dir(cwd: Path = PROGRAM) -> Path:
    path = Path(_git("rev-parse", "--git-common-dir", cwd=cwd).stdout.strip())
    return path if path.is_absolute() else (cwd / path).resolve()


def attach_codex_worktree(root: Path) -> int:
    """Codex 的临时工作树在首次提交前取得具名分支，保留原 HEAD 和暂存区。"""
    if (root.parent.parent != Path.home() / ".codex" / "worktrees"
            or not re.fullmatch("[0-9a-f]{4}", root.parent.name)):
        return 0
    head = _git("symbolic-ref", "--quiet", "HEAD", cwd=root)
    if head.returncode != 1:
        return head.returncode
    git_dir = _git("rev-parse", "--absolute-git-dir", cwd=root)
    if git_dir.returncode:
        return git_dir.returncode
    metadata = Path(git_dir.stdout.strip())
    if metadata == common_dir(root):
        return 0
    if any((metadata / name).exists() for name in
           ("rebase-merge", "rebase-apply", "MERGE_HEAD", "CHERRY_PICK_HEAD", "REVERT_HEAD", "BISECT_START", "sequencer")):
        print("工作树正在执行 Git 操作，请先完成该操作。", file=sys.stderr)
        return 1
    branch = "codex/worktree-" + root.parent.name
    attached = _git("switch", "-c", branch, cwd=root)
    print(attached.stderr.strip(), file=sys.stderr)
    return attached.returncode


def wait_for_lock(common: Path, timeout: float, *, poll: float = POLL_SECONDS,
                  report: float = REPORT_SECONDS, out=print) -> bool:
    """锁释放（或回收了失效锁）返回 True；超时返回 False。

    新锁以心跳为准：3 分钟内有心跳就继续等，打不开进程不算死亡。
    没有心跳的旧锁仍按持有进程是否还在。
    """
    lock = common / run_selftests.FULL_SAFE_LOCK_NAME
    deadline = time.monotonic() + timeout
    last_report = time.monotonic()
    while lock.exists():
        holder = run_selftests.lock_holder(str(lock))
        if run_selftests.reclaim_stale_lock(str(lock)):
            out("已回收失效验收锁（PID %s）" % holder.get("pid"))
            break
        if time.monotonic() >= deadline:
            return False
        if time.monotonic() - last_report >= report:
            out("等待全量验收锁：PID %s（R%s）仍在运行" % (holder.get("pid"), holder.get("round", "?")))
            last_report = time.monotonic()
        time.sleep(poll)
    return True


def _lock_wait_diagnosis(common: Path, waited_seconds: float) -> str:
    """等锁超时的诊断：锁持有者 PID、已等时长、心跳距今（字段缺失写未知）。"""
    holder = run_selftests.lock_holder(str(common / run_selftests.FULL_SAFE_LOCK_NAME))
    beat = holder.get("heartbeat_at")
    if beat is None:
        beat = holder.get("heartbeat")
    try:
        heartbeat = "%.0f 秒" % max(0.0, time.time() - float(beat))
    except (TypeError, ValueError):
        heartbeat = "未知"
    return "持有者 PID %s，已等 %.0f 秒，心跳距今 %s" % (holder.get("pid", "?"), waited_seconds, heartbeat)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("-m", "--message", required=True, help="提交说明，首行须为 R<轮次>: 说明")
    parser.add_argument("--tests", nargs="*", default=[], metavar="关键词",
                        help="定向测试的模块关键词（run_selftests.py -k），用于生成轮次证据")
    parser.add_argument("--agent", default="", help="本次改动的来源（模型／工具名），写入提交信息的 Agent: 行")
    parser.add_argument("--wait-minutes", type=float, default=5.0, help="最多等验收锁多少分钟")
    parser.add_argument("files", nargs="*", help="要暂存的 repo 内路径；省略则只提交已暂存内容")
    args = parser.parse_args(argv)

    if args.files and not _git("rev-parse", "-q", "--verify", "MERGE_HEAD").returncode:
        print("合并只能提交整个索引，请核对后使用无路径模式。", file=sys.stderr)
        return 1
    status = attach_codex_worktree(PROGRAM.parent)
    if status:
        return status
    if not args.files:
        return commit(args)
    number = re.match(r"^R(\d+)(?:-FAIL)?:", args.message)
    key = "R" + number.group(1) if number else hashlib.sha256(args.message.encode()).hexdigest()
    evidence = None
    if number and ROUND_MESSAGE_RE.match(args.message) and int(number.group(1)) >= round_evidence.EVIDENCE_REQUIRED_FROM:
        evidence = (PROGRAM / "tasks_round" / "evidence" / (key + ".json")).relative_to(PROGRAM.parent).as_posix()
    try:
        receipt = commit_retry.Receipt(_git, args.files, args.tests, args.message, key, evidence)
        with commit_retry.exclusive(receipt.worktree_lock), commit_retry.exclusive(receipt.round_lock):
            previous = receipt.open()
            if previous:
                print("已完成：" + previous)
                return 0
            return commit(args, receipt)
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as exc:
        print("显式提交停止：" + str(exc), file=sys.stderr)
        return 1


def commit(args, receipt=None):
    args.message = with_agent_trailer(args.message, args.agent)
    if receipt:
        allowed = staged_paths(*args.files)
        if receipt.evidence:
            if receipt.data:
                allowed.add(receipt.evidence)
            elif (receipt.root / receipt.evidence).exists():
                print("没有持久记录能证明已有证据的归属：" + receipt.evidence, file=sys.stderr)
                return 1
        if reject_other_paths(staged_paths(), allowed):
            return 1
        receipt.start()
        receipt.stage_inputs()
    if args.files or _git("diff", "--cached", "--name-only").stdout.strip():
        rejected = (check_test_move(args.message, PROGRAM.parent)
                    or check_scope_overlap(PROGRAM.parent)
                    or check_taskbook_closure(args.message, PROGRAM.parent))
        if rejected:
            return rejected
        if receipt:
            receipt.check()
        if receipt and receipt.evidence:
            rejected = attach_evidence(args.message, args.tests, PROGRAM.parent, receipt)
        else:
            rejected = attach_evidence(args.message, args.tests, PROGRAM.parent)
        if rejected:
            return rejected
    staged = [line for line in _git("diff", "--cached", "--name-only").stdout.splitlines() if line]
    if not staged:
        print("没有已暂存的改动，未提交。", file=sys.stderr)
        return 1
    env = dict(os.environ, CODEX_STAGE_ALLOWLIST=";".join(staged))
    commit_paths = []
    if receipt:
        permitted = staged_paths(*args.files)
        if receipt.evidence:
            permitted.add(receipt.evidence)
        selected = staged_paths()
        if reject_other_paths(selected, permitted):
            return 1
        commit_paths = ["--only", "--", *[":(top,literal)" + name for name in sorted(selected)]]
        args.message += "\n\nCommit-Attempt: " + receipt.data["id"]
        receipt.check()
        receipt.data["ready"] = True
        receipt.save()
    common = common_dir()
    deadline = time.monotonic() + args.wait_minutes * 60
    # 钩子只在 master/main/游离 HEAD 上拦验收锁；工作分支直接提交，不等锁。
    branch = _git("symbolic-ref", "--quiet", "--short", "HEAD").stdout.strip()
    lock_applies = branch in ("", "master", "main")
    while True:
        if lock_applies and not wait_for_lock(common, max(0.0, deadline - time.monotonic())):
            waited = args.wait_minutes * 60 - max(0.0, deadline - time.monotonic())
            print("等待全量验收锁超过 %.0f 分钟（%s），未提交；暂存区保留。"
                  % (args.wait_minutes, _lock_wait_diagnosis(common, waited)), file=sys.stderr)
            return 3
        if receipt:
            receipt.check()
            if _git("diff", "--quiet", "--", *commit_paths[2:]).returncode:
                raise commit_retry.RetryConflict("提交前工作区与已验收暂存内容不同")
        done = _run_git(["commit", "-q", "-m", args.message, *commit_paths], PROGRAM, env=env)
        text = (done.stdout + done.stderr).strip()
        if done.returncode and REJECT_MARK in text and time.monotonic() < deadline:
            continue  # 检查与提交之间被抢了锁，回头再等
        if text:
            print(text)
        if not done.returncode:
            print(receipt.find_commit() if receipt else _git("log", "--oneline", "-1").stdout.strip())
        return done.returncode


if __name__ == "__main__":
    raise SystemExit(main())

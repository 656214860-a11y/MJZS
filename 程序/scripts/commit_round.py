"""一条命令完成「暂存 → 白名单 → 等全量验收锁 → 提交」。

pre-commit 钩子仅在 master/main/游离 HEAD 上、``full-safe-selftest.lock`` 存在时拒绝提交（工作分支不受锁限制，
直接提交，WIP 提交首行用 ``WIP: 说明``、免领轮次号，合入 master 前须整理成 R<轮次>）。后台全量一跑十几分钟；
以前靠会话里 ``sleep 20`` 循环重试（最长 40 分钟）。本脚本在 master 上把等待放进进程内：
锁持有进程已死则回收，仍存活则静默轮询，直到释放或超时。钩子规则不变，不绕过。

用法（程序目录下）::

    python -B scripts/commit_round.py -m "R1931: 说明" [文件 ...]

不给文件就提交已暂存的内容；给了文件先 ``git add -- 文件``。白名单取自最终暂存清单，
不会用 ``git add -A``。领轮次号仍用 ``dev.py claim``（须在写结果文件前领，不能挪到提交时）。
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import time
from pathlib import Path

PROGRAM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROGRAM))
import run_selftests  # noqa: E402

sys.path.insert(0, str(PROGRAM / "维护记录" / "基准脚本"))
import round_evidence  # noqa: E402

POLL_SECONDS = 15
REPORT_SECONDS = 120
REJECT_MARK = "全量安全验收锁存在"
ROUND_MESSAGE_RE = re.compile(r"^R(\d+):")


def with_agent_trailer(message: str, agent: str) -> str:
    """提交信息末尾加 ``Agent: <名称>`` 行（已有则不重复）；名称为空则原样返回。"""
    agent = (agent or "").strip()
    if not agent or any(line.startswith("Agent: ") for line in message.splitlines()):
        return message
    return message.rstrip("\n") + "\n\nAgent: " + agent


def attach_evidence(message: str, keywords, root: Path) -> int:
    """R<N>（N 不早于证据制度起点）的提交必须带绿色证据文件：凭据扫描无命中，改了 .py 则定向测试须绿。

    返回 0 放行（证据已暂存），非 0 拒绝提交。"""
    matched = ROUND_MESSAGE_RE.match(message)
    if not matched or int(matched.group(1)) < round_evidence.EVIDENCE_REQUIRED_FROM:
        return 0
    number = int(matched.group(1))
    merging = _git("rev-parse", "-q", "--verify", "MERGE_HEAD", cwd=root).returncode == 0
    target = round_evidence.write_evidence(number, keywords, root=root, skip="merge-ci-exit" if merging else None)
    scan_ok, tests_ok, detail = round_evidence.judge(number)
    _git("add", "--", str(target), cwd=root)
    if scan_ok and tests_ok:
        result = PROGRAM / "tasks_round" / ("tasks_round_%d_result.md" % number)
        staged = _git("diff", "--cached", "--name-only", cwd=root).stdout.splitlines()
        if any(name.endswith(result.name) for name in staged) and round_evidence.stamp_result(result, number):
            _git("add", "--", str(result), cwd=root)
        return 0
    print("拒绝提交：R%d 证据不通过（%s）。凭据命中先移除；改了 .py 须用 --tests <模块关键词> 跑定向测试且全绿。" % (number, detail),
          file=sys.stderr)
    return 4


def _git(*args: str, cwd: Path = PROGRAM) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-c", "core.quotepath=false", *args], cwd=cwd,
                          capture_output=True, text=True, encoding="utf-8", errors="replace")


def common_dir(cwd: Path = PROGRAM) -> Path:
    path = Path(_git("rev-parse", "--git-common-dir", cwd=cwd).stdout.strip())
    return path if path.is_absolute() else (cwd / path).resolve()


def wait_for_lock(common: Path, timeout: float, *, poll: float = POLL_SECONDS,
                  report: float = REPORT_SECONDS, out=print) -> bool:
    """锁释放（或回收了失效锁）返回 True；超时返回 False。"""
    lock = common / run_selftests.FULL_SAFE_LOCK_NAME
    deadline = time.monotonic() + timeout
    last_report = time.monotonic()
    while lock.exists():
        holder = run_selftests.lock_holder(str(lock))
        if not run_selftests._pid_is_alive(holder.get("pid"), holder.get("started_at")):
            try:
                lock.unlink()
                out("已回收失效验收锁（持有进程 %s 已不存在）" % holder.get("pid"))
            except FileNotFoundError:
                pass
            break
        if time.monotonic() >= deadline:
            return False
        if time.monotonic() - last_report >= report:
            out("等待全量验收锁：PID %s（R%s）仍在运行" % (holder.get("pid"), holder.get("round", "?")))
            last_report = time.monotonic()
        time.sleep(poll)
    return True


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("-m", "--message", required=True, help="提交说明，首行须为 R<轮次>: 说明")
    parser.add_argument("--tests", nargs="*", default=[], metavar="关键词",
                        help="定向测试的模块关键词（run_selftests.py -k），用于生成轮次证据")
    parser.add_argument("--agent", default="", help="本次改动的来源（模型／工具名），写入提交信息的 Agent: 行")
    parser.add_argument("--wait-minutes", type=float, default=30.0, help="最多等验收锁多少分钟")
    parser.add_argument("files", nargs="*", help="要暂存的 repo 内路径；省略则只提交已暂存内容")
    args = parser.parse_args(argv)

    args.message = with_agent_trailer(args.message, args.agent)
    if args.files:
        added = _git("add", "--", *args.files)
        if added.returncode:
            print(added.stderr.strip(), file=sys.stderr)
            return added.returncode
    if args.files or _git("diff", "--cached", "--name-only").stdout.strip():
        rejected = attach_evidence(args.message, args.tests, PROGRAM.parent)
        if rejected:
            return rejected
    staged = [line for line in _git("diff", "--cached", "--name-only").stdout.splitlines() if line]
    if not staged:
        print("没有已暂存的改动，未提交。", file=sys.stderr)
        return 1
    env = dict(os.environ, CODEX_STAGE_ALLOWLIST=";".join(staged))
    common = common_dir()
    deadline = time.monotonic() + args.wait_minutes * 60
    # 钩子只在 master/main/游离 HEAD 上拦验收锁；工作分支直接提交，不等锁。
    branch = _git("symbolic-ref", "--quiet", "--short", "HEAD").stdout.strip()
    lock_applies = branch in ("", "master", "main")
    while True:
        if lock_applies and not wait_for_lock(common, max(0.0, deadline - time.monotonic())):
            print("等待全量验收锁超过 %.0f 分钟，未提交；暂存区保留。" % args.wait_minutes, file=sys.stderr)
            return 3
        done = subprocess.run(["git", "commit", "-q", "-m", args.message], cwd=PROGRAM, env=env,
                              capture_output=True, text=True, encoding="utf-8", errors="replace")
        text = (done.stdout + done.stderr).strip()
        if done.returncode and REJECT_MARK in text and time.monotonic() < deadline:
            continue  # 检查与提交之间被抢了锁，回头再等
        if text:
            print(text)
        if not done.returncode:
            print(_git("log", "--oneline", "-1").stdout.strip())
        return done.returncode


if __name__ == "__main__":
    raise SystemExit(main())

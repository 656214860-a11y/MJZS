# -*- coding: utf-8 -*-
"""主工作区同步：fetch 远端 → 仅 fast-forward，只拉不推。

「同步主工作区」的机械实现，供每轮开工前在**主工作区**（master/main 检出、
非链接工作树）运行。它只做三件事，绝不 push（AGENTS.md 规则 38 禁止 push）：

1. 校验调用位置：必须是主工作区、当前分支为 master/main、工作树干净；
   脏树或身处功能工作树一律拒绝，不静默替用户做任何分支切换。
2. ``git fetch <remote>`` 拉取最新引用。
3. 本地落后时 ``git merge --ff-only <remote>/<branch>`` 快进到最新；
   领先（ahead>0）时只报告，不回写、不 push、不 rebase。

用法（主工作区根目录，随附解释器）::

    python.exe -B 程序\\scripts\\sync_master.py            # 默认远端 backup，分支随当前 master/main
    python.exe -B 程序\\scripts\\sync_master.py --remote backup --branch master

退出码：0 已同步或已最新；2 前置校验失败（非主工作区／非 master／脏树）；3 合并冲突或网络失败。
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

PROGRAM = Path(__file__).resolve().parents[1]
ROOT = PROGRAM.parent
MAIN_BRANCHES = ("master", "main")


def git(*args: str, root: Path = ROOT) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(root), *args],
                          capture_output=True, text=True, encoding="utf-8", errors="replace")


def current_branch(root: Path = ROOT) -> str:
    result = git("symbolic-ref", "--quiet", "--short", "HEAD", root=root)
    return result.stdout.strip() if result.returncode == 0 else ""


def is_main_worktree(root: Path = ROOT) -> bool:
    """主工作树判定：git-dir == git-common-dir。链接工作树二者不同。"""
    gitdir = git("rev-parse", "--absolute-git-dir", root=root).stdout.strip()
    common = git("rev-parse", "--git-common-dir", root=root).stdout.strip()
    if not gitdir or not common:
        return False
    gitdir_path = Path(gitdir)
    common_path = Path(common) if Path(common).is_absolute() else (root / common).resolve()
    return gitdir_path.resolve() == common_path.resolve()


def divergence(root: Path, remote: str, branch: str) -> tuple[int, int]:
    """返回 (ahead, behind)：master 相对 remote/branch 领先与落后数。"""
    ahead = git("rev-list", "--count", "%s/%s..%s" % (remote, branch, branch), root=root)
    behind = git("rev-list", "--count", "%s..%s/%s" % (branch, remote, branch), root=root)
    return int(ahead.stdout.strip() or 0), int(behind.stdout.strip() or 0)


def require_clean(root: Path = ROOT) -> None:
    status = git("status", "--porcelain", root=root)
    dirty = [line for line in status.stdout.splitlines() if line.strip()]
    if dirty:
        raise RuntimeError("拒绝同步：主工作区有未提交改动，保持主树干净是工作流纪律。脏文件：%s"
                           % ", ".join(dirty))


def sync_master(*, root: Path = ROOT, remote: str = "backup", branch: str = "") -> dict:
    """校验前置条件，fetch 远端，仅 fast-forward 落后部分。返回报告字典。"""
    actual = current_branch(root)
    branch = branch or actual
    if branch != actual:
        raise RuntimeError("拒绝同步：当前检出分支 %s 与指定主干 %s 不一致，不会切换分支。"
                           % (actual or "(游离)", branch))
    if not is_main_worktree(root):
        raise RuntimeError("拒绝同步：当前不是主工作区（git-dir 与 common-dir 不同）。"
                           "同步只在主工作区执行，功能工作树用 rebase 而非同步。")
    if branch not in MAIN_BRANCHES:
        raise RuntimeError("拒绝同步：当前分支 %s 不是 %s。同步只作用于主工作区主干。"
                           % (branch, "/".join(MAIN_BRANCHES)))
    require_clean(root)

    fetched = git("fetch", remote, root=root)
    if fetched.returncode:
        raise RuntimeError("fetch %s 失败：%s" % (remote, (fetched.stderr or fetched.stdout).strip()))

    ahead, behind = divergence(root, remote, branch)
    report = {"remote": remote, "branch": branch, "ahead": ahead, "behind": behind,
              "action": "already-current", "pushed": False}
    if behind > 0:
        merged = git("merge", "--ff-only", "%s/%s" % (remote, branch), root=root)
        if merged.returncode:
            raise RuntimeError("快进失败（可能有分叉，未改动本地）：%s"
                               % (merged.stderr or merged.stdout).strip())
        report["action"] = "fast-forwarded"
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="主工作区同步：fetch 远端 → 仅 fast-forward，只拉不推")
    parser.add_argument("--remote", default="backup", help="远端名（默认 backup）")
    parser.add_argument("--branch", default="", help="主干名（默认自动取当前 master/main）")
    args = parser.parse_args(argv)
    try:
        report = sync_master(root=ROOT, remote=args.remote, branch=args.branch)
    except (RuntimeError, subprocess.CalledProcessError) as error:
        print(str(error), file=sys.stderr)
        return 2
    action = report["action"]
    if action == "fast-forwarded":
        print("已快进 %s 到 %s/%s（落后 %d 提交已补齐）" %
              (report["branch"], report["remote"], report["branch"], report["behind"]))
    else:
        print("已是最新：%s 相对 %s/%s 领先 %d、落后 %d，无需同步" %
              (report["branch"], report["remote"], report["branch"], report["ahead"], report["behind"]))
    if report["ahead"] > 0:
        print("提示：%s 领先远端 %d 个未推送提交。规则 38 禁止 push，保持不动，等待明确授权。"
              % (report["branch"], report["ahead"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

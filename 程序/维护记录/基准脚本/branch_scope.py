"""活跃车道范围扫描与新增文件撞名门禁。

两条并行车道各自实现同一需求时会「新增」同名文件，合入时变 add/add 冲突
（R2542 对 R2538 工程闸门批次4 的重复实现）。本模块提供两层防线：

- ``dev.py scope <路径>...``：开工前把计划触及的路径与各活跃工作树分支
  相对 master 的改动求交，重叠即提示，避免重复开工；
- ``dev.py commit`` 门禁（``commit_round.check_scope_overlap``）：暂存区新增
  文件与其他活跃分支的新增文件同名即拒绝提交，把 add/add 风险拦在提交点。

「活跃分支」口径：``git worktree list`` 中带分支引用的工作树，排除主干
（master/main）与调用方当前分支；无工作树的未合并分支视为停放或遗留，
不阻断提交，其风险由合并轮 CI 兜底。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import worktree_ledger  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
MAIN_BRANCHES = ("master", "main")


def git(root, *args):
    """worktree_ledger.git 加 ``core.quotepath=false``：中文路径不转义。"""
    return worktree_ledger.git(root, "-c", "core.quotepath=false", *args)


def lane_branches(root, exclude=()):
    """活跃工作树分支清单 ``[{branch, path}]``；exclude 为分支名集合。"""
    skip = set(exclude) | set(MAIN_BRANCHES)
    lanes = []
    for record in worktree_ledger.worktrees(root):
        ref = record.get("branch")
        if not isinstance(ref, str):
            continue  # detached 等无分支引用的工作树不算车道
        branch = ref.removeprefix("refs/heads/")
        if branch and branch not in skip:
            lanes.append({"branch": branch, "path": record.get("path", "")})
    return lanes


def changed_files(root, branch, added_only=False):
    """分支相对 master 合并基的改动文件集；added_only 时只算新增。"""
    flt = ("--diff-filter=A",) if added_only else ()
    out = git(root, "diff", "--name-only", *flt, "master..." + branch)
    return {line for line in out.splitlines() if line}


def scan(root, added_only=False, exclude=()):
    """逐分支扫描。返回 ``(found, errors)``：

    found = {branch: {"path": 工作树路径, "files": set}}（files 可为空）；
    errors = {branch: 读取失败原因}。
    """
    found, errors = {}, {}
    for lane in lane_branches(root, exclude=exclude):
        try:
            changed = changed_files(root, lane["branch"], added_only=added_only)
        except RuntimeError as error:
            errors[lane["branch"]] = str(error)
            continue
        found[lane["branch"]] = {"path": lane["path"], "files": changed}
    return found, errors


def _hit(path, query):
    query = query.replace("\\", "/").rstrip("/")
    return bool(query) and (path == query or path.startswith(query + "/"))


def scope_report(root, queries=(), *, added_only=False, exclude=()):
    """各活跃分支与查询路径的交集。

    返回 ``{"branches": {branch: {"path","matches","total"}}, "errors": {...},
    "scanned": 活跃分支数}``。queries 为空时 matches 为全部改动文件；
    给了 queries 时只保留有命中的分支。
    """
    found, errors = scan(root, added_only=added_only, exclude=exclude)
    branches = {}
    for branch, info in found.items():
        files = info["files"]
        if queries:
            matched = sorted(p for p in files if any(_hit(p, q) for q in queries))
            if not matched:
                continue
        else:
            matched = sorted(files)
        branches[branch] = {"path": info["path"], "matches": matched, "total": len(files)}
    return {"branches": branches, "errors": errors, "scanned": len(found) + len(errors)}


def staged_added_files(root):
    """暂存区相对 HEAD 的新增文件集。"""
    out = git(root, "diff", "--cached", "--diff-filter=A", "--name-only")
    return {line for line in out.splitlines() if line}


def commit_gate_report(root, exclude_branch):
    """提交门禁报告：``{"conflicts": [...], "skipped": [...]}``。

    暂存区新增文件与其他活跃分支新增文件同名即冲突（双方都按新文件添加，
    合入将成 add/add）；读取失败的分支只进 skipped 警告，不阻断提交。
    """
    staged = staged_added_files(root)
    if not staged:
        return {"conflicts": [], "skipped": []}
    found, errors = scan(root, added_only=True, exclude={exclude_branch})
    hits = {}
    for branch, info in found.items():
        for path in sorted(staged & info["files"]):
            hits.setdefault(path, []).append(branch)
    conflicts = [
        "新增文件 %s 与活跃分支 %s 撞名（双方均按新文件添加，合入将成 add/add 冲突；"
        "请改名、协调归属，或待对方合入后再提交）" % (path, "、".join(sorted(hits[path])))
        for path in sorted(hits)]
    skipped = ["活跃分支 %s 的新增文件清单读取失败，本次未纳入比对：%s" % (b, e)
               for b, e in sorted(errors.items())]
    return {"conflicts": conflicts, "skipped": skipped}


def _current_branch(root):
    try:
        return git(root, "symbolic-ref", "--quiet", "--short", "HEAD").strip()
    except RuntimeError:
        return ""


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--added", action="store_true",
                        help="只比对各分支新增文件（add/add 口径）")
    parser.add_argument("--json", action="store_true", help="机器可读输出")
    parser.add_argument("--root", type=Path, default=ROOT, help="仓库根（默认本仓库）")
    parser.add_argument("paths", nargs="*",
                        help="repo 相对路径或目录前缀；省略则只显示各分支改动数量")
    args = parser.parse_args(argv)
    root = args.root.resolve()
    current = _current_branch(root)
    exclude = {current} if current else set()
    report = scope_report(root, args.paths, added_only=args.added, exclude=exclude)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    mode = "仅新增文件" if args.added else "全部改动"
    print("车道范围扫描（基线 master，%s；当前分支 %s 已排除）" % (mode, current or "未知"))
    if args.paths:
        for branch in sorted(report["branches"]):
            info = report["branches"][branch]
            print("• %s — %d 个重叠" % (branch, len(info["matches"])))
            for path in info["matches"]:
                print("    " + path)
        clean = report["scanned"] - len(report["branches"]) - len(report["errors"])
        if clean:
            print("（另 %d 个活跃分支无重叠）" % clean)
    else:
        for branch in sorted(report["branches"]):
            info = report["branches"][branch]
            print("• %s — 改动 %d 个文件" % (branch, info["total"]))
        if not report["branches"]:
            print("没有其他活跃分支。")
    for branch, error in sorted(report["errors"].items()):
        print("警告：%s 读取失败已跳过：%s" % (branch, error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# -*- coding: utf-8 -*-
"""车道工作树子模块补种：把主工作树 .gitmodules 里各子模块的纯文件内容复制过去。

``git worktree add`` 新建的车道里子模块目录是空的（gitlink 只记提交号，不带
工作区文件），本机无网络时不能 ``git submodule update --init``，导致依赖子模块
内容的测试（如 ``test_script_contract`` 的剧本 SKILL 审计）在车道误红。本脚本
改为纯文件复制：读主工作树 ``.gitmodules``，把每个子模块路径下的普通文件逐个
复制到车道同路径；任何层级的 ``.git``（文件或目录）都不复制，不执行
``git submodule update``，不 add／commit，不改变 Git 状态。幂等：已存在且内容
一致的文件跳过（大小＋mtime 粗判，sha256 兜底），重复运行无操作。

用法（仓库根或任意目录，随附解释器）::

    python.exe -B 程序\\scripts\\seed_worktree_submodules.py <工作树路径>

目标必须是 ``git worktree list`` 里的工作树（允许主工作树本身，此时全部判为
已是最新）。每个子模块打印一行：复制 N 个文件／已是最新／源缺失。

退出码：0 完成（源缺失或为空只警告）；2 参数或目标校验失败。
"""
from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path, PurePosixPath

GIT = "git"


def _git(root, *args):
    """只读 git 调用；core.quotepath=false 防中文路径被转义。"""
    return subprocess.run([GIT, "-c", "core.quotepath=false", "-C", str(root), *args],
                          capture_output=True, text=True, encoding="utf-8", errors="replace")


def parse_gitmodules(text):
    """从 .gitmodules 文本提取各 submodule 节的 path 值，保持出现顺序、去重。"""
    paths = []
    in_submodule = False
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith(("#", ";")):
            continue
        if line.startswith("["):
            in_submodule = line.startswith("[submodule")
            continue
        if in_submodule and "=" in line:
            key, _, value = line.partition("=")
            if key.strip() != "path":
                continue
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] == '"':
                value = value[1:-1]
            if value and value not in paths:
                paths.append(value)
    return paths


def worktrees_of(target):
    """``git worktree list --porcelain`` 的全部工作树路径；首个即主工作树。失败返回 None。"""
    done = _git(target, "worktree", "list", "--porcelain")
    if done.returncode != 0:
        return None
    paths = []
    for line in done.stdout.splitlines():
        if line.startswith("worktree "):
            path = line[len("worktree "):].strip().strip('"')
            if path:
                paths.append(Path(path))
    return paths or None


def _same_path(a, b):
    return os.path.normcase(str(Path(a).resolve())) == os.path.normcase(str(Path(b).resolve()))


def _unsafe_rel(rel):
    """子模块路径必须是仓库内的相对路径：拒绝空、绝对路径、盘符与 ``..``。"""
    text = str(rel).strip()
    if not text:
        return True
    path = Path(text)
    posix = PurePosixPath(text)
    return (path.is_absolute() or posix.is_absolute() or bool(path.drive)
            or ".." in path.parts or ".." in posix.parts)


def _iter_files(root):
    """root 下全部普通文件的相对路径（排序）；任何层级的 .git 文件／目录都跳过。"""
    root = Path(root)
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [name for name in dirnames if name != ".git"]
        for name in filenames:
            if name == ".git":
                continue
            out.append(Path(dirpath, name).relative_to(root))
    return sorted(out)


def _sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _same_file(src, dst):
    """内容一致判定：非常规文件或尺寸不同直接不同；尺寸与 mtime 相同粗判一致，
    否则 sha256 兜底。"""
    try:
        src_stat = src.stat()
        dst_stat = dst.stat()
    except OSError:
        return False
    if not stat.S_ISREG(src_stat.st_mode) or not stat.S_ISREG(dst_stat.st_mode):
        return False
    if src_stat.st_size != dst_stat.st_size:
        return False
    if src_stat.st_mtime_ns == dst_stat.st_mtime_ns:
        return True
    try:
        return _sha256(src) == _sha256(dst)
    except OSError:
        return False


def _seed_one(target_root, source_root, rel):
    """复制单个子模块；返回 {path, status, copied, skipped, failed}。"""
    row = {"path": rel, "status": "", "copied": 0, "skipped": 0, "failed": 0}
    if _unsafe_rel(rel):
        row["status"] = "invalid"
        return row
    src_dir = Path(source_root) / rel
    dst_dir = Path(target_root) / rel
    if _same_path(src_dir, dst_dir):
        row["status"] = "same"
        return row
    if not src_dir.is_dir():
        row["status"] = "missing"
        return row
    files = _iter_files(src_dir)
    if not files:
        row["status"] = "empty"
        return row
    for rel_file in files:
        src = src_dir / rel_file
        dst = dst_dir / rel_file
        if _same_file(src, dst):
            row["skipped"] += 1
            continue
        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            row["copied"] += 1
        except OSError:
            row["failed"] += 1
    if row["copied"] == 0 and row["failed"] == 0:
        row["status"] = "uptodate"
    else:
        row["status"] = "copied" if row["copied"] else "failed"
    return row


def seed_worktree(target_root, source_root, modules=None):
    """把 source_root（主工作树）下 modules 各子模块复制到 target_root（车道）。

    modules 为 None 时读 source_root/.gitmodules；返回逐子模块结果列表。
    """
    target_root = Path(target_root)
    source_root = Path(source_root)
    if modules is None:
        gitmodules = source_root / ".gitmodules"
        modules = (parse_gitmodules(gitmodules.read_text(encoding="utf-8"))
                   if gitmodules.is_file() else [])
    return [_seed_one(target_root, source_root, rel) for rel in modules]


def _format_line(row):
    rel = row["path"]
    status = row["status"]
    if status == "missing":
        return "警告：%s 源缺失，已跳过" % rel
    if status == "empty":
        return "警告：%s 源目录为空，已跳过" % rel
    if status == "invalid":
        return "警告：%s 路径不安全，已跳过" % rel
    if status == "same":
        return "%s：已是最新（目标与源相同）" % rel
    if status == "uptodate":
        return "%s：已是最新" % rel
    if status == "copied":
        line = "%s：复制 %d 个文件" % (rel, row["copied"])
        if row["failed"]:
            line += "，失败 %d 个" % row["failed"]
        return line
    return "警告：%s 文件复制失败：%d 个" % (rel, row["failed"])


def run(target_root, source_root):
    """读 source_root/.gitmodules，逐子模块补种并逐行打印；恒返回 0。"""
    source_root = Path(source_root)
    gitmodules = source_root / ".gitmodules"
    if not gitmodules.is_file():
        print("警告：主工作树缺少 .gitmodules，没有可复制的子模块")
        return 0
    modules = parse_gitmodules(gitmodules.read_text(encoding="utf-8"))
    if not modules:
        print("主工作树 .gitmodules 中没有登记子模块")
        return 0
    for row in seed_worktree(target_root, source_root, modules):
        print(_format_line(row))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="把主工作树 .gitmodules 里各子模块的纯文件内容复制到指定车道工作树"
                    "（不复制 .git、不执行 submodule update、不改变 Git 状态）")
    parser.add_argument("worktree", help="git worktree list 中的工作树路径（允许主工作树）")
    args = parser.parse_args(argv)
    target = Path(args.worktree).expanduser()
    if not target.is_dir():
        print("错误：目标不是目录：%s" % args.worktree, file=sys.stderr)
        return 2
    target = target.resolve()
    trees = worktrees_of(target)
    if trees is None:
        print("错误：%s 不在 git 仓库中或 git 不可用" % target, file=sys.stderr)
        return 2
    if not any(_same_path(tree, target) for tree in trees):
        print("错误：%s 不是该仓库的 git worktree" % target, file=sys.stderr)
        return 2
    return run(target, trees[0])


if __name__ == "__main__":
    raise SystemExit(main())

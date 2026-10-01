#!/usr/bin/env python3
"""Safely remove disposable development artifacts from the assistant source tree.

Run with the bundled interpreter, preferably with ``-B``::

    D:\\漫剧制作助手\\运行环境\\Python\\python.exe -B scripts\\clean_dev.py --dry-run
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import shutil
import sys
import time
import zipfile

# Avoid creating a bytecode cache when this development-only script is launched
# without ``-B``.  The script itself imports no project module.
sys.dont_write_bytecode = True

PROGRAM = Path(__file__).resolve().parents[1]
DIST_ROOT = PROGRAM.parent
RUNTIME_PYTHON = DIST_ROOT / "运行环境" / "Python"
PROTECTED_DIRS = tuple(PROGRAM / name for name in ("skills", "tests", "配置", "assets"))
PROTECTED_FILES = (PROGRAM / "run_selftests.py", PROGRAM / "smoke_test.py")
RESULT_RE = re.compile(r"^tasks_round_(\d+)_result\.md$", re.IGNORECASE)


def _resolved(path: Path) -> Path:
    return path.resolve(strict=False)


def _inside(path: Path, root: Path) -> bool:
    try:
        _resolved(path).relative_to(_resolved(root))
        return True
    except ValueError:
        return False


def format_mib(size: int) -> str:
    return f"{size / 1024 / 1024:.2f} MiB"


def file_count_and_bytes(path: Path) -> tuple[int, int]:
    """Return logical file count/size without following directory links."""
    if not path.exists() and not path.is_symlink():
        return 0, 0
    if path.is_file() or path.is_symlink():
        try:
            return 1, path.lstat().st_size
        except OSError:
            return 0, 0
    count = total = 0
    for current, dirs, files in os.walk(path, followlinks=False):
        dirs[:] = [name for name in dirs if not (Path(current) / name).is_symlink()]
        for name in files:
            item = Path(current) / name
            try:
                total += item.lstat().st_size
                count += 1
            except OSError:
                pass
    return count, total


def protected_reason(
    path: Path, *, archive_source: bool = False, temporary_tree: bool = False
) -> str | None:
    """Return a rejection reason, or None when this particular path is deletable."""
    candidate = _resolved(path)
    if _inside(candidate, RUNTIME_PYTHON):
        return "运行环境/Python 属于受保护运行时"
    for root in PROTECTED_DIRS:
        if _inside(candidate, root):
            return f"{root.name}/ 属于受保护目录"
    if candidate in tuple(_resolved(item) for item in PROTECTED_FILES):
        return f"{candidate.name} 属于受保护启动/测试脚本"
    if candidate.suffix.lower() == ".py":
        return "程序 .py 源文件不可删除"
    if candidate.suffix.lower() == ".json" and _inside(candidate, PROGRAM / "配置"):
        return "配置 JSON 文件不可删除"
    if candidate.suffix.lower() == ".md" and not (
        (archive_source and _inside(candidate, PROGRAM / "tasks_round"))
        or (temporary_tree and (_inside(candidate, PROGRAM / ".selftmp") or _inside(candidate, DIST_ROOT / ".selftmp")))
    ):
        return "Markdown 文档不可删除（归档结果文件除外）"
    return None


def assert_tree_deletable(
    path: Path, *, archive_source: bool = False, temporary_tree: bool = False
) -> None:
    """Validate target and all descendants before a destructive operation."""
    reason = protected_reason(path, archive_source=archive_source, temporary_tree=temporary_tree)
    if reason:
        raise PermissionError(f"拒绝删除 {path}: {reason}")
    if not path.is_dir() or path.is_symlink():
        return
    for current, dirs, files in os.walk(path, followlinks=False):
        current_path = Path(current)
        for name in [*dirs, *files]:
            item = current_path / name
            reason = protected_reason(item, archive_source=archive_source, temporary_tree=temporary_tree)
            if reason:
                raise PermissionError(f"拒绝删除 {item}: {reason}")


def remove_path(
    path: Path, *, archive_source: bool = False, temporary_tree: bool = False
) -> tuple[int, int]:
    assert_tree_deletable(path, archive_source=archive_source, temporary_tree=temporary_tree)
    count, size = file_count_and_bytes(path)
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    else:
        os.remove(path)
    return count, size


def discover_pycache() -> tuple[list[Path], list[tuple[Path, str]]]:
    allowed: list[Path] = []
    refused: list[tuple[Path, str]] = []
    for current, dirs, _files in os.walk(PROGRAM, followlinks=False):
        for name in list(dirs):
            if name != "__pycache__":
                continue
            candidate = Path(current) / name
            reason = protected_reason(candidate)
            if reason:
                refused.append((candidate, reason))
            else:
                allowed.append(candidate)
            dirs.remove(name)
    return allowed, refused


def older_logs() -> list[Path]:
    cutoff = time.time() - 30 * 24 * 60 * 60
    found: list[Path] = []
    for root in (PROGRAM / "logs", PROGRAM / "维护记录"):
        if not root.is_dir():
            continue
        for current, _dirs, files in os.walk(root, followlinks=False):
            for name in files:
                item = Path(current) / name
                try:
                    if item.suffix.lower() == ".log" and item.stat().st_mtime < cutoff:
                        found.append(item)
                except OSError:
                    pass
    return found


def archive_candidates() -> list[Path]:
    root = PROGRAM / "tasks_round"
    if not root.is_dir():
        return []
    candidates: list[tuple[int, Path]] = []
    for item in root.iterdir():
        match = RESULT_RE.fullmatch(item.name)
        if match and item.is_file() and int(match.group(1)) <= 500:
            candidates.append((int(match.group(1)), item))
    return [item for _number, item in sorted(candidates)]


def print_plan(label: str, paths: list[Path]) -> None:
    files = size = 0
    for path in paths:
        count, bytes_ = file_count_and_bytes(path)
        files += count
        size += bytes_
    if paths:
        print(f"{label}: {len(paths)} 项，{files} 个文件，{format_mib(size)}")
        preview_limit = 20
        for path in paths[:preview_limit]:
            print(f"  - {path}")
        if len(paths) > preview_limit:
            print(f"  - … 其余 {len(paths) - preview_limit} 项未逐条显示")
    else:
        print(f"{label}: 无需清理")


def execute_group(
    label: str, paths: list[Path], dry_run: bool, refused: list[tuple[Path, str]], *, temporary_tree: bool = False
) -> tuple[int, int]:
    print_plan(label, paths)
    if dry_run:
        return 0, 0
    removed_files = removed_bytes = 0
    for path in paths:
        try:
            count, size = remove_path(path, temporary_tree=temporary_tree)
            removed_files += count
            removed_bytes += size
        except (OSError, PermissionError) as exc:
            refused.append((path, str(exc)))
            print(f"  ! 未删除 {path}: {exc}")
    return removed_files, removed_bytes


def archive_results(paths: list[Path], dry_run: bool, refused: list[tuple[Path, str]]) -> tuple[int, int]:
    print_plan("历史任务结果归档（R500 及之前）", paths)
    if not paths or dry_run:
        return 0, 0
    numbers = [int(RESULT_RE.fullmatch(path.name).group(1)) for path in paths]
    archive_dir = PROGRAM / "tasks_round" / "_archive"
    archive_dir.mkdir(parents=True, exist_ok=True)
    final_zip = archive_dir / f"R{min(numbers)}-R{max(numbers)}.zip"
    temp_zip = final_zip.with_suffix(".zip.tmp")
    try:
        with zipfile.ZipFile(temp_zip, "w", zipfile.ZIP_DEFLATED) as archive:
            for path in paths:
                archive.write(path, path.relative_to(PROGRAM / "tasks_round"))
        with zipfile.ZipFile(temp_zip) as archive:
            if archive.testzip() is not None or len(archive.namelist()) != len(paths):
                raise OSError("归档校验失败")
        temp_zip.replace(final_zip)
    except OSError as exc:
        temp_zip.unlink(missing_ok=True)
        refused.append((final_zip, f"归档未完成，未删除任何原文件: {exc}"))
        return 0, 0
    removed_files = removed_bytes = 0
    for path in paths:
        try:
            count, size = remove_path(path, archive_source=True)
            removed_files += count
            removed_bytes += size
        except (OSError, PermissionError) as exc:
            refused.append((path, str(exc)))
    return removed_files, removed_bytes


def main() -> int:
    parser = argparse.ArgumentParser(description="清理漫剧制作助手的可再生开发残留。")
    parser.add_argument("--dry-run", action="store_true", help="只显示计划，不删除或归档。")
    parser.add_argument("--deep", action="store_true", help="额外删除 logs 和维护记录中超过 30 天的 .log。")
    parser.add_argument("--archive", action="store_true", help="压缩归档 R500 及之前的任务结果；保留 R501 及之后。")
    args = parser.parse_args()

    before_files, before_bytes = file_count_and_bytes(DIST_ROOT)
    print(f"清理前目录大小: {format_mib(before_bytes)}（{before_files} 个文件）")
    if args.dry_run:
        print("演练模式：不会删除、移动或创建归档。")

    refused: list[tuple[Path, str]] = []
    pycache, pycache_refused = discover_pycache()
    refused.extend(pycache_refused)
    groups: list[tuple[str, list[Path]]] = [
        ("程序 __pycache__（受保护目录除外）", pycache),
        (".selftmp", [path for path in (PROGRAM / ".selftmp", DIST_ROOT / ".selftmp") if path.exists()]),
        ("data 测试残留（SH001/SH002/SH004）", [
            path for path in (PROGRAM / "data" / "SH001", PROGRAM / "data" / "SH002", PROGRAM / "data" / "SH004")
            if path.exists()
        ]),
    ]
    if args.deep:
        groups.append(("超过 30 天的 .log（logs/、维护记录/）", older_logs()))

    deleted_files = deleted_bytes = 0
    for label, paths in groups:
        count, size = execute_group(label, paths, args.dry_run, refused, temporary_tree=(label == ".selftmp"))
        deleted_files += count
        deleted_bytes += size
    if args.archive:
        count, size = archive_results(archive_candidates(), args.dry_run, refused)
        deleted_files += count
        deleted_bytes += size

    after_files, after_bytes = file_count_and_bytes(DIST_ROOT)
    print(f"本次删除统计: {deleted_files} 个文件，{format_mib(deleted_bytes)}")
    print(f"清理后目录大小: {format_mib(after_bytes)}（{after_files} 个文件）")
    print(f"目录净释放空间: {format_mib(max(0, before_bytes - after_bytes))}")
    if refused:
        print("被内置保护拒绝的项目:")
        for path, reason in refused:
            print(f"  - {path}: {reason}")
    else:
        print("被内置保护拒绝的项目: 无")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

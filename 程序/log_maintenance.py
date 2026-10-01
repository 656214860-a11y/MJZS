"""Bounded maintenance for program-owned diagnostic logs only.

The maintenance scope is deliberately narrow: ``程序/logs`` and
``程序/维护记录``.  It never walks, reads, or changes a user project.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import subprocess
import sys
import time


RETENTION_DAYS = 30
SINGLE_MAX_BYTES = 10 * 1024 * 1024
ROTATE_KEEP = 3
DIR_MAX_BYTES = 150 * 1024 * 1024

PROGRAM = Path(__file__).resolve().parent
LOG_DIRECTORY_NAMES = ("logs", "维护记录")
ROTATED_LOG_RE = re.compile(r".+\.log\.[1-3]$", re.IGNORECASE)


def _is_managed_log(path: Path) -> bool:
    """Only ordinary ``*.log`` files and this module's three rotations qualify."""
    return (path.is_file() and not path.is_symlink()
            and (path.suffix.lower() == ".log" or ROTATED_LOG_RE.fullmatch(path.name) is not None))


def log_files(directory: Path) -> list[Path]:
    """List a single managed directory without descending into any child directory."""
    try:
        return [path for path in directory.iterdir() if _is_managed_log(path)]
    except OSError:
        return []


def _remove(path: Path, result: dict, *, dry_run: bool) -> bool:
    try:
        size = path.stat().st_size
        if not dry_run:
            path.unlink()
        result["removed_files"] += 1
        result["removed_bytes"] += size
        return True
    except OSError:
        result["errors"] += 1
        return False


def _rotate(path: Path, result: dict, *, dry_run: bool) -> bool:
    """Move an oversized live log to ``.1`` and retain at most three copies."""
    try:
        if path.stat().st_size <= SINGLE_MAX_BYTES:
            return False
        if dry_run:
            result["rotated_files"] += 1
            return True
        for index in range(ROTATE_KEEP, 1, -1):
            source = path.with_name(path.name + "." + str(index - 1))
            target = path.with_name(path.name + "." + str(index))
            if source.exists():
                os.replace(source, target)
        os.replace(path, path.with_name(path.name + ".1"))
        path.touch()
        result["rotated_files"] += 1
        return True
    except OSError:
        result["errors"] += 1
        return False


def maintain_directory(directory: Path, *, now: float | None = None, dry_run: bool = False) -> dict:
    """Apply retention, rotation, then directory cap to one exact program log directory."""
    result = {"directory": Path(directory), "removed_files": 0, "removed_bytes": 0,
              "rotated_files": 0, "errors": 0}
    directory = Path(directory)
    if not directory.is_dir() or directory.is_symlink():
        return result
    cutoff = (time.time() if now is None else float(now)) - RETENTION_DAYS * 24 * 60 * 60
    for path in log_files(directory):
        try:
            if path.stat().st_mtime < cutoff:
                _remove(path, result, dry_run=dry_run)
        except OSError:
            result["errors"] += 1
    for path in log_files(directory):
        if path.suffix.lower() == ".log":
            _rotate(path, result, dry_run=dry_run)
    entries = []
    for path in log_files(directory):
        try:
            stat = path.stat()
            entries.append((stat.st_mtime, path, stat.st_size))
        except OSError:
            result["errors"] += 1
    total = sum(size for _mtime, _path, size in entries)
    for _mtime, path, size in sorted(entries, key=lambda row: (row[0], row[1].name)):
        if total <= DIR_MAX_BYTES:
            break
        if _remove(path, result, dry_run=dry_run):
            total -= size
    return result


def maintain_program_logs(program: Path | None = None, *, now: float | None = None,
                          dry_run: bool = False) -> tuple[dict, ...]:
    """Maintain only the two program-owned log directories, never project directories."""
    root = Path(program or PROGRAM)
    return tuple(maintain_directory(root / name, now=now, dry_run=dry_run)
                 for name in LOG_DIRECTORY_NAMES)


def launch_cleanup(program: Path | None = None) -> None:
    """Start best-effort post-exit maintenance without delaying UI shutdown."""
    root = Path(program or PROGRAM)
    subprocess.Popen([sys.executable, str(root / "log_maintenance.py"), "--cleanup"],
                     creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _format_mib(size: int) -> str:
    return f"{size / 1024 / 1024:.2f} MiB"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="维护程序 logs/ 与维护记录/ 下的 .log 文件。")
    parser.add_argument("--dry-run", action="store_true", help="仅显示维护计划，不改动文件。")
    parser.add_argument("--cleanup", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    results = maintain_program_logs(dry_run=args.dry_run)
    for result in results:
        print(f"{result['directory']}: 轮转 {result['rotated_files']} 个，"
              f"删除 {result['removed_files']} 个（{_format_mib(result['removed_bytes'])}），"
              f"错误 {result['errors']} 个")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

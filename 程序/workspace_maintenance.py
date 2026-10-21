"""仓库级有界卫生：只清理可再生的 gitignored 残留。

范围刻意收窄为三段：``__pycache__`` 字节码缓存、``.selftmp`` 超期临时目录、
以及"已并入 HEAD 且工作树干净并静置满一周"的 ``.wt/`` 工作树。用户可见删除
仍唯一走 ``storage_maintenance.recycle_paths()``；本模块删除的全部是临时文件
与缓存（AGENTS 约束 14"受控清理"），绝不触碰用户项目、``private``、``data``、
``运行环境/Python`` 与任何被 Git 跟踪的内容。

只在正常退出后的无窗口子进程执行；启动路径零扫描。git 用于缓存跟踪保护与工作树判定，
且三重保守回退：非主仓形态（无 ``.git``）、PATH 无 git、任何调用异常都跳过
工作树段；Git 仓库内无法核验跟踪状态时保留缓存。``git gc`` 永不进本模块——重打包
可能长时间占盘，只留在开发侧 ``scripts/repo_health.py``。

实际物理清理委托 ``storage_maintenance.remove_regenerable_tree()``；进程只经
``platform_tools``（不触审计 21 的直接 subprocess 名）。
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import subprocess
import sys
import time

from platform_tools import launch_background, run_process, tool_path
from storage_maintenance import remove_regenerable_tree


PROGRAM = Path(__file__).resolve().parent
DIST_ROOT = PROGRAM.parent

SELFTEMP_MAX_AGE_SECONDS = 7 * 24 * 60 * 60
WORKTREE_MIN_AGE_SECONDS = 7 * 24 * 60 * 60
LAUNCH_DELAY_SECONDS = 3
GIT_TIMEOUT_SECONDS = 30

PYCACHE_NAME = "__pycache__"
SELFTEMP_DIR_NAME = ".selftmp"
WORKTREE_DIR_NAME = ".wt"
TMP_PREFIX_RE = re.compile(r"tmp", re.IGNORECASE)
SWEEP_PROTECTED = (DIST_ROOT / "运行环境", DIST_ROOT / ".git", DIST_ROOT / "升级备份",
                   PROGRAM / "private", PROGRAM / "data")
SWEEP_LOG_NAME = "仓库清理.log"
PYCACHE_PROTECTED_NAMES = frozenset({"episode", "writing", "private", "data", "配置",
                                    "logs", "运行环境", ".git", "升级备份"})


def _inside(child: Path, parent: Path) -> bool:
    try:
        return Path(child).resolve(strict=False).is_relative_to(Path(parent).resolve(strict=False))
    except OSError:
        return False


def _protected(path: Path) -> bool:
    return any(_inside(path, guard) for guard in SWEEP_PROTECTED)


def _entry_stats(path: Path) -> tuple[int, int]:
    """统计一棵树的文件数与字节数；不跟随符号链接与目录联接。"""
    files = 0
    total = 0
    for dirpath, _dirnames, filenames in os.walk(path, followlinks=False):
        for name in filenames:
            try:
                total += Path(dirpath, name).lstat().st_size
                files += 1
            except OSError:
                continue
    return files, total


# ── 阶段 1：__pycache__ 字节码缓存 ─────────────────────────────────

def pycache_directories(root: Path) -> list[Path]:
    """列出 root 子树内的 __pycache__ 目录并就地剪枝；保护前缀整体跳过。"""
    root = Path(root)
    found: list[Path] = []
    if (any(part.casefold() in PYCACHE_PROTECTED_NAMES for part in root.parts)
            or not root.is_dir() or _protected(root)
            or any(p.is_symlink() or p.is_junction() for p in (root, *root.parents))):
        return found
    if root.name == PYCACHE_NAME:
        return [root]
    for dirpath, dirnames, _filenames in os.walk(root, followlinks=False):
        directory = Path(dirpath)
        keep = []
        for name in dirnames:
            child = directory / name
            if child.is_symlink() or child.is_junction():
                continue
            if name.casefold() in PYCACHE_PROTECTED_NAMES or _protected(child):
                continue
            if name == PYCACHE_NAME:
                found.append(child)
                continue
            keep.append(name)
        dirnames[:] = keep
    return found


def _cache_tree_safe(target: Path) -> bool:
    """整树预检：有非字节码、链接或受跟踪文件就保留整树，不做部分删除。"""
    def scan_error(error):
        raise error

    for directory, dirs, files in os.walk(target, followlinks=False, onerror=scan_error):
        for name in dirs + files:
            entry = Path(directory, name)
            if entry.is_symlink() or entry.is_junction():
                return False
            if name in files and (entry.suffix.lower() != '.pyc' or not entry.is_file()):
                return False
    for parent in target.parents:
        if (parent / '.git').exists():
            checked = run_git(['ls-files', '-z', '--', target.relative_to(parent).as_posix()], parent)
            if checked is None or checked.returncode:
                raise OSError('无法确认缓存的 Git 跟踪状态，保留目录')
            return not checked.stdout
    return True


def clean_pycache(roots: tuple[Path, ...], *, dry_run: bool = False) -> dict:
    result = {"category": "pycache", "removed_entries": 0, "removed_files": 0,
              "removed_bytes": 0, "errors": 0}
    for root in roots:
        root = Path(root)
        for target in pycache_directories(root):
            try:
                if _cache_tree_safe(target):
                    remove_regenerable_tree(target, result, dry_run=dry_run, stats=_entry_stats)
            except OSError:
                result['errors'] += 1
    return result


# ── 阶段 2：.selftmp 超期临时目录 ──────────────────────────────────

def clean_selftemp(selftmp: Path, *, now: float | None = None,
                   max_age_seconds: float = SELFTEMP_MAX_AGE_SECONDS,
                   dry_run: bool = False) -> dict:
    """只删 .selftmp 顶层 tmp 前缀且超期的条目；根目录与新条目永远保留。"""
    result = {"category": "selftmp", "root": Path(selftmp), "removed_entries": 0,
              "removed_files": 0, "removed_bytes": 0, "kept_recent": 0,
              "skipped": 0, "errors": 0}
    selftmp = Path(selftmp)
    if not selftmp.is_dir() or selftmp.is_symlink() or selftmp.is_junction():
        return result
    cutoff = (time.time() if now is None else float(now)) - max_age_seconds
    try:
        entries = sorted(selftmp.iterdir())
    except OSError:
        result["errors"] += 1
        return result
    for entry in entries:
        try:
            if entry.is_symlink() or entry.is_junction():
                result["skipped"] += 1
                continue
            if TMP_PREFIX_RE.match(entry.name) is None:
                continue
            if entry.lstat().st_mtime >= cutoff:
                result["kept_recent"] += 1
                continue
            remove_regenerable_tree(entry, result, dry_run=dry_run, stats=_entry_stats)
        except OSError:
            result["errors"] += 1
    return result


# ── 阶段 3：已并入且干净的工作树 ──────────────────────────────────

def run_git(args: list[str], repo_root: Path, *, run=None,
            timeout: float = GIT_TIMEOUT_SECONDS):
    """git 统一收口：隐藏控制台、固定 quotepath、异常一律返回 None（保守）。"""
    try:
        return run_process(["git", "-c", "core.quotepath=off", "-C", str(repo_root), *args],
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=timeout, run=run)
    except (OSError, subprocess.SubprocessError, ValueError):
        return None


def _decode_porcelain_path(raw: str) -> str:
    if len(raw) >= 2 and raw.startswith('"') and raw.endswith('"'):
        body = raw[1:-1]
        out: list[str] = []
        index = 0
        while index < len(body):
            if body[index] == "\\" and index + 1 < len(body) and body[index + 1] == "x":
                try:
                    out.append(chr(int(body[index + 2:index + 4], 16)))
                    index += 4
                    continue
                except ValueError:
                    pass
            out.append(body[index])
            index += 1
        return "".join(out)
    return raw


# 前缀 → (字段, 取值转换)。顺序即匹配顺序，前缀互斥。
_WORKTREE_FIELDS = (
    ("worktree ", "path", lambda value: Path(_decode_porcelain_path(value))),
    ("HEAD ", "head", str.strip),
    ("branch ", "branch", _decode_porcelain_path),
)
_WORKTREE_FLAGS = (("locked", "locked"), ("prunable", "prunable"))


def _apply_worktree_line(current: dict, line: str) -> None:
    """把一行 porcelain 输出写进当前条目；认不出的行忽略。"""
    for prefix, field, convert in _WORKTREE_FIELDS:
        if line.startswith(prefix):
            current[field] = convert(line[len(prefix):])
            return
    if line == "detached":
        current["branch"] = None
        return
    for prefix, field in _WORKTREE_FLAGS:
        if line.startswith(prefix):
            current[field] = True
            return


def _flush_worktree(entries: list, current: dict | None) -> None:
    if current and current.get("path"):
        entries.append(current)


def parse_worktree_list(text: str) -> tuple[dict, ...]:
    """解析 ``git worktree list --porcelain``；纯函数，供注入与单测。"""
    entries: list[dict] = []
    current: dict | None = None
    for line in (text or "").splitlines():
        if not line.strip():
            _flush_worktree(entries, current)
            current = None
            continue
        if current is None:
            current = {"path": None, "head": "", "branch": None,
                       "locked": False, "prunable": False}
        _apply_worktree_line(current, line)
    _flush_worktree(entries, current)
    return tuple(entries)


def local_worktrees(repo_root: Path, *, run=None) -> tuple[dict, ...]:
    """仅列出仓库根 ``.wt/`` 前缀下的工作树；仓库外工作树永不入候选。"""
    repo_root = Path(repo_root)
    if not (repo_root / ".git").is_dir() or tool_path("git") is None:
        return ()
    result = run_git(["worktree", "list", "--porcelain"], repo_root, run=run)
    if result is None or getattr(result, "returncode", 1) != 0:
        return ()
    scoped = repo_root / WORKTREE_DIR_NAME
    return tuple(entry for entry in parse_worktree_list(result.stdout or "")
                 if entry["path"] is not None and _inside(entry["path"], scoped))


def worktree_verdict(entry: dict, repo_root: Path, *, now: float | None = None,
                     min_age_seconds: float = WORKTREE_MIN_AGE_SECONDS, run=None) -> tuple[bool, str]:
    """顺序短路，全保守：locked/recent/unmerged/dirty 任一命中即保留。"""
    if entry.get("locked") or entry.get("prunable"):
        return False, "locked"
    path = Path(entry["path"])
    try:
        age = (time.time() if now is None else float(now)) - path.stat().st_mtime
        if age < min_age_seconds:
            return False, "recent"
    except OSError:
        return False, "missing"
    ancestor = run_git(["merge-base", "--is-ancestor", entry["head"], "HEAD"],
                       Path(repo_root), run=run)
    if ancestor is None or getattr(ancestor, "returncode", 1) != 0:
        return False, "unmerged"
    status = run_git(["status", "--porcelain"], path, run=run)
    if status is None or getattr(status, "returncode", 1) != 0:
        return False, "unverifiable"
    if (status.stdout or "").strip():
        return False, "dirty"
    return True, "merged-and-clean"


def clean_worktrees(repo_root: Path, *, now: float | None = None,
                    dry_run: bool = False, run=None) -> dict:
    """移除"已并入 HEAD、干净且静置满一周"的 .wt 工作树；绝不用 --force。"""
    result = {"category": "worktrees", "git": "present", "removed": [],
              "kept": [], "errors": 0}
    repo_root = Path(repo_root)
    # linked worktree 的 .git 是指向公共 gitdir 的普通文件；它和主仓目录同样可安全
    # 执行只读判定，不能因形态不同把工作树段误报为“非仓库”。
    if not (repo_root / ".git").exists():
        result["git"] = "not-a-repo"
        return result
    if tool_path("git") is None:
        result["git"] = "absent"
        return result
    entries = local_worktrees(repo_root, run=run)
    if not entries:
        return result
    removed_any = False
    for entry in entries:
        removable, reason = worktree_verdict(entry, repo_root, now=now, run=run)
        name = Path(entry["path"]).name
        if not removable:
            result["kept"].append((name, reason))
            continue
        files, size = _entry_stats(Path(entry["path"]))
        if dry_run:
            result["removed"].append({"name": name, "head": entry["head"],
                                      "bytes": size, "files": files, "planned": True})
            continue
        outcome = run_git(["worktree", "remove", str(entry["path"])], repo_root, run=run)
        if outcome is None or getattr(outcome, "returncode", 1) != 0:
            result["kept"].append((name, "remove-refused"))
            result["errors"] += 1
            continue
        result["removed"].append({"name": name, "head": entry["head"],
                                  "bytes": size, "files": files})
        removed_any = True
    if removed_any:
        run_git(["worktree", "prune"], repo_root, run=run)
    return result


# ── 汇总 / 日志 / 挂接 / CLI ──────────────────────────────────────

def maintain_repository(*, program: Path | None = None, dist_root: Path | None = None,
                        now: float | None = None, dry_run: bool = False,
                        run=None) -> dict:
    """三段依次执行，互不牵连：一段异常只记 errors，不影响其余段。"""
    root_program = Path(program or PROGRAM)
    root_dist = Path(dist_root or DIST_ROOT)
    pycache = clean_pycache((root_program, root_dist / WORKTREE_DIR_NAME), dry_run=dry_run)
    if (root_dist / PYCACHE_NAME).is_dir() and not _protected(root_dist / PYCACHE_NAME):
        merge = clean_pycache((root_dist / PYCACHE_NAME,), dry_run=dry_run)
        for key in ("removed_entries", "removed_files", "removed_bytes", "errors"):
            pycache[key] += merge[key]
    selftmp = {"category": "selftmp", "removed_entries": 0, "removed_files": 0,
               "removed_bytes": 0, "kept_recent": 0, "skipped": 0, "errors": 0}
    for home in (root_program / SELFTEMP_DIR_NAME, root_dist / SELFTEMP_DIR_NAME):
        part = clean_selftemp(home, now=now, dry_run=dry_run)
        for key in ("removed_entries", "removed_files", "removed_bytes",
                    "kept_recent", "skipped", "errors"):
            selftmp[key] += part[key]
    try:
        worktrees = clean_worktrees(root_dist, now=now, dry_run=dry_run, run=run)
    except OSError:
        worktrees = {"category": "worktrees", "git": "error", "removed": [],
                     "kept": [], "errors": 1}
    released = pycache["removed_bytes"] + selftmp["removed_bytes"] + sum(
        item["bytes"] for item in worktrees["removed"])
    return {"pycache": pycache, "selftmp": selftmp, "worktrees": worktrees,
            "released_bytes": released, "dry_run": bool(dry_run)}


def append_summary_log(program: Path, summary: dict) -> None:
    """向 程序/logs/仓库清理.log 追加一行；日志保留与轮转由 log_maintenance 统一负责。"""
    try:
        logs = Path(program) / "logs"
        logs.mkdir(parents=True, exist_ok=True)
        worktrees = summary["worktrees"]
        removed = "+".join(item["name"] for item in worktrees["removed"]) or "无"
        kept = "+".join(f"{name}:{reason}" for name, reason in worktrees["kept"]) or "无"
        line = (f"{time.strftime('%Y-%m-%d %H:%M:%S')} | 释放 {_format_mib(summary['released_bytes'])}"
                f" | pycache {summary['pycache']['removed_entries']} 目录"
                f" | selftmp {summary['selftmp']['removed_entries']} 项"
                f" | worktrees 移除[{removed}] 保留[{kept}]"
                f" | git={worktrees['git']}"
                f" | 错误 {summary['pycache']['errors'] + summary['selftmp']['errors'] + worktrees['errors']} 处\n")
        with open(logs / SWEEP_LOG_NAME, "a", encoding="utf-8", errors="replace") as handle:
            handle.write(line)
    except OSError:
        pass


def launch_cleanup(program: Path | None = None) -> None:
    """与 log_maintenance 同构：正常退出后另起无窗口进程做仓库卫生，不拖慢关窗。"""
    root = Path(program or PROGRAM)
    launch_background([sys.executable, str(root / "workspace_maintenance.py"), "--cleanup"],
                      stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _format_mib(size: int) -> str:
    return f"{size / 1024 / 1024:.2f} MiB"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="清理仓库级可再生残留：__pycache__、超期 .selftmp、已并净的 .wt 工作树。")
    parser.add_argument("--dry-run", action="store_true", help="仅显示清理计划，不改动任何文件。")
    parser.add_argument("--cleanup", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.cleanup and not args.dry_run:
        # 与 storage_maintenance 一致：等父进程真正退出再动盘。
        time.sleep(LAUNCH_DELAY_SECONDS)
    summary = maintain_repository(dry_run=args.dry_run)
    pycache = summary["pycache"]
    selftmp = summary["selftmp"]
    worktrees = summary["worktrees"]
    print(f"缓存：移除 {pycache['removed_entries']} 个 __pycache__（{_format_mib(pycache['removed_bytes'])}），错误 {pycache['errors']} 个")
    print(f"临时：移除 {selftmp['removed_entries']} 个超期 .selftmp 条目（{_format_mib(selftmp['removed_bytes'])}），"
          f"保留近期 {selftmp['kept_recent']} 个，跳过链接 {selftmp['skipped']} 个，错误 {selftmp['errors']} 个")
    print(f"工作树：git={worktrees['git']}，移除 {len(worktrees['removed'])} 个，"
          f"保留 {len(worktrees['kept'])} 个（{'，'.join(f'{name}:{reason}' for name, reason in worktrees['kept']) or '无'}）")
    print(f"合计释放：{_format_mib(summary['released_bytes'])}{'（计划，未改动）' if summary['dry_run'] else ''}")
    if not args.dry_run:
        append_summary_log(PROGRAM, summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""车道注册表：<git common-dir>/lanes.json —— 活跃工作树车道的 owner/role/last_seen 登记。

高并发治理（任务书 B3）：领号、scope、合并时刷新 last_seen；失联车道只警告不阻断。
读写都走原子替换；文件损坏时按空表降级（宁可少登记，不可拒绝领号）。
"""
from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path

LANES_NAME = "lanes.json"
STALE_HOURS = 24 * 7          # 7 天无心跳视为失联（警告级，不阻断）
ROLES = ("dev", "gui", "merge", "ci")


def lanes_path(common_dir: Path) -> Path:
    return Path(common_dir) / LANES_NAME


def _read(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) and isinstance(data.get("lanes"), dict) else {"lanes": {}}
    except (OSError, ValueError):
        return {"lanes": {}}


def _write(path: Path, doc: dict) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, path)


def _worktree_info(root: Path):
    """当前工作树 → (lane名, branch, worktree路径)。"""
    def git(*args):
        done = subprocess.run(["git", "-C", str(root), *args],
                              capture_output=True, text=True, timeout=15,
                              encoding="utf-8", errors="replace")
        return (done.stdout or "").strip()
    top = git("rev-parse", "--show-toplevel")
    branch = git("rev-parse", "--abbrev-ref", "HEAD")
    lane = Path(top).name if top else ""
    return lane, branch, top


def register(root: Path, common_dir: Path, *, owner: str = "", role: str | None = None,
             now: float | None = None) -> dict:
    """登记/刷新当前工作树车道；返回该车道条目。role 未指定时保留既有指定。"""
    if role is None:
        role = ""
    now = time.time() if now is None else now
    lane, branch, top = _worktree_info(root)
    if not lane:
        return {}
    path = lanes_path(common_dir)
    doc = _read(path)
    entry = doc["lanes"].get(lane, {})
    entry.update({"branch": branch, "worktree": top, "owner": owner or entry.get("owner", ""),
                  "role": role if role in ROLES else entry.get("role", "dev"),
                  "last_seen": now, "registered_at": entry.get("registered_at", now)})
    doc["lanes"][lane] = entry
    _write(path, doc)
    return entry


def heartbeat(root: Path, common_dir: Path, *, now: float | None = None) -> None:
    """只刷新 last_seen；车道未登记时顺带登记（owner/role 缺省）。"""
    register(root, common_dir, now=now)


def list_lanes(common_dir: Path, *, now: float | None = None, stale_hours: float = STALE_HOURS):
    """返回 [{lane, branch, owner, role, last_seen, idle_hours, stale}]，stale 仅标记不删除。"""
    now = time.time() if now is None else now
    rows = []
    for lane, entry in sorted(_read(lanes_path(common_dir))["lanes"].items()):
        seen = float(entry.get("last_seen") or 0)
        idle = round(max(0.0, now - seen) / 3600, 2) if seen else -1
        rows.append({"lane": lane, **{k: entry.get(k, "") for k in ("branch", "worktree", "owner", "role")},
                     "last_seen": seen, "idle_hours": idle, "stale": idle_hours_check(idle, stale_hours)})
    return rows


def idle_hours_check(idle: float, stale_hours: float) -> bool:
    return idle >= 0 and idle >= stale_hours


def stale_lanes(common_dir: Path, *, now: float | None = None):
    return [row for row in list_lanes(common_dir, now=now) if row["stale"]]

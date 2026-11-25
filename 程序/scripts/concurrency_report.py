"""Git 并发与锁机制只读基线报告（任务书 G0／G8 复用）。

采集《Git并发锁机制优化任务书》§1 验收线与 §0.2 共享锁台账的全部指标：
- 主干第一父链非轮次提交（24 小时窗与近 600 提交）及根目录受跟踪条目登记检查
- 全量历史（full-safe-history.jsonl）绿/红统计、7 天红灯段与停留、内容树绿凭据与自动全量状态
- 合并队列（merge-queue.json）各状态计数、失败率与陈旧失败项（分支已合入或已删）
- 工作树盘点（总数、脏树、游离 HEAD、ahead=0、合并中/变基中残留、lanes.json 登记与维护租约）
- 本地分支总数与未合入 master 分支数
- 无主领号（round-claims.json 中无提交且无主干结果文件的轮次）
- 锁文件状态（common-dir 顶层锁与 GUI 排队目录）及源码超时/等锁参数

只读不改仓库与 common-dir；时间窗锚定到 master HEAD 提交时间，不输出易变墙上时钟，
连续两次运行输出逐字一致。结果同时写入 ``程序/logs/concurrency_report.md``（已被 gitignore）。

用法（程序目录下）::

    python -B scripts/concurrency_report.py [--repo <路径>] [--no-write]
"""
from __future__ import annotations

import argparse
import ast
import ctypes
import json
import os
import re
import subprocess
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

PROGRAM = Path(__file__).resolve().parents[1]
DEFAULT_REPORT = PROGRAM / "logs" / "concurrency_report.md"

ROUND_RE = re.compile(r"^R(\d+)(?:-FAIL)?:")
RESULT_RE = re.compile(r"tasks_round_(\d+)_result\.md$")
HEAD_RE = re.compile(r"[0-9a-f]{40}")
FIRST_PARENT_LIMIT = 600
RECENT_HISTORY_LIMIT = 40
DAY_SECONDS = 86400
WEEK_SECONDS = 7 * DAY_SECONDS
WORKTREE_WORKERS = 8
KNOWN_LOCKS = (
    "round-claim.lock",
    "full-safe-selftest.lock",
    "full-safe-runner.lock",
    "gui-selftest.lock",
    "merge-lane.lock",
    "auto-full-safe.lock",
    "auto-full-waiter.lock",
)


def _git(repo: Path, *args: str, timeout: int = 30) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "--no-optional-locks", "-c", "core.quotepath=false", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )


def _git_out(repo: Path, *args: str, timeout: int = 30) -> str:
    done = _git(repo, *args, timeout=timeout)
    return done.stdout if done.returncode == 0 else ""


def _read_json_file(path: Path):
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return None


def _read_lock_object(path: Path):
    """兼容原地心跳写留下的尾部字节，不使用裸 json.loads。"""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None, "unreadable"
    stripped = text.strip()
    if not stripped:
        return None, "empty"
    try:
        value, _end = json.JSONDecoder().raw_decode(stripped)
    except ValueError:
        return None, "non-json"
    if isinstance(value, dict):
        return value, "json"
    return None, "non-object"


def _fmt_utc(ts: float | int | None) -> str:
    if ts is None:
        return "—"
    try:
        return datetime.fromtimestamp(float(ts), timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except (OSError, OverflowError, ValueError, TypeError):
        return "—"


def _parse_iso(text: object) -> int | None:
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(str(text))
    except ValueError:
        return None
    return int(parsed.timestamp())


def _sanitize_path(raw: str, main_root: Path) -> str:
    """脱敏工作树路径：主树标 (main)，仓内用相对路径，仓外只留末级目录名，不泄本机绝对路径或用户名。"""
    text = str(raw or "").strip()
    if not text:
        return "(unknown)"
    try:
        resolved = Path(text).resolve()
        root_resolved = main_root.resolve()
        if resolved == root_resolved:
            return "(main)"
        rel = resolved.relative_to(root_resolved).as_posix()
        return rel
    except (OSError, ValueError):
        name = Path(text.replace("\\", "/")).name or "(external)"
        return "<external>/" + name


def _pid_alive(pid: object) -> bool:
    try:
        num = int(pid)
    except (TypeError, ValueError):
        return False
    if num <= 0:
        return False
    if os.name == "nt":
        try:
            handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, num)
            if not handle:
                return False
            ctypes.windll.kernel32.CloseHandle(handle)
            return True
        except OSError:
            return False
    try:
        os.kill(num, 0)
    except OSError:
        return False
    return True


def _median(values: list[int | float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return float(ordered[mid])
    return (float(ordered[mid - 1]) + float(ordered[mid])) / 2.0


def _fmt_hours(seconds: float | None) -> str:
    if seconds is None:
        return "数据不足"
    return "%.1f 小时" % (seconds / 3600.0)


def _pct(num: int, den: int) -> str:
    if den <= 0:
        return "—"
    return "%.1f%%" % (100.0 * num / den)


def resolve_repo_and_common(repo: Path) -> tuple[Path, Path, Path]:
    top = _git_out(repo, "rev-parse", "--show-toplevel").strip()
    work_root = Path(top).resolve() if top else repo.resolve()
    common_raw = _git_out(work_root, "rev-parse", "--git-common-dir").strip()
    if not common_raw:
        raise RuntimeError("无法定位 git common-dir")
    common_path = Path(common_raw)
    common = common_path.resolve() if common_path.is_absolute() else (work_root / common_path).resolve()
    main_root = common.parent if common.name == ".git" else work_root
    return work_root, main_root, common


def collect_trunk_anchor(repo: Path) -> dict:
    ref = "master" if _git(repo, "rev-parse", "--verify", "refs/heads/master").returncode == 0 else "HEAD"
    raw = _git_out(repo, "show", "-s", "--format=%H%x1f%h%x1f%ct", ref).strip()
    parts = raw.split("\x1f")
    sha = parts[0] if len(parts) > 0 else ""
    short = parts[1] if len(parts) > 1 else ""
    ts = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0
    program_tree = _git_out(repo, "rev-parse", "--verify", f"{ref}:程序").strip()
    return {"ref": ref, "sha": sha, "short": short, "ts": ts, "program_tree": program_tree}


def collect_non_round_commits(repo: Path, ref: str, anchor_ts: int) -> dict:
    raw = _git_out(
        repo,
        "log",
        "--first-parent",
        f"-n{FIRST_PARENT_LIMIT}",
        "--format=%h%x1f%ct%x1f%s",
        ref,
    )
    non_round_600 = []
    non_round_24h = []
    total_checked = 0
    cutoff_24h = anchor_ts - DAY_SECONDS
    for line in raw.splitlines():
        if not line.strip():
            continue
        parts = line.split("\x1f", 2)
        if len(parts) < 3:
            continue
        total_checked += 1
        short, stamp_raw, subject = parts[0], parts[1], parts[2]
        stamp = int(stamp_raw) if stamp_raw.isdigit() else 0
        if not ROUND_RE.match(subject):
            item = {"sha": short, "ts": stamp, "at": _fmt_utc(stamp), "subject": subject}
            non_round_600.append(item)
            if stamp >= cutoff_24h:
                non_round_24h.append(item)
    return {
        "checked": total_checked,
        "count_24h": len(non_round_24h),
        "count_600": len(non_round_600),
        "items_600": non_round_600,
    }


def collect_root_layout(repo: Path, ref: str, program_dir: Path) -> dict:
    allowed = set()
    test_file = program_dir / "tests" / "test_root_layout.py"
    if test_file.is_file():
        try:
            tree = ast.parse(test_file.read_text(encoding="utf-8", errors="replace"))
            for node in tree.body:
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name) and target.id == "ALLOWED":
                            value = ast.literal_eval(node.value)
                            if isinstance(value, dict):
                                allowed = set(value.keys())
        except (OSError, SyntaxError, ValueError):
            allowed = set()
    ls_out = _git_out(repo, "ls-tree", "--name-only", ref)
    tracked_top = {line.strip() for line in ls_out.splitlines() if line.strip()}
    agents_files = [
        line for line in _git_out(repo, "ls-tree", "-r", "--name-only", ref, "--", ".agents").splitlines()
        if line.strip()
    ]
    unregistered = sorted(tracked_top - allowed) if allowed else []
    return {
        "tracked_top_count": len(tracked_top),
        "allowed_count": len(allowed),
        "unregistered_top": unregistered,
        "agents_tracked_count": len(agents_files),
    }


def _red_dwell_spans(rows: list[dict]) -> tuple[list[int], bool]:
    spans: list[int] = []
    red_at: int | None = None
    for row in rows:
        ok = row.get("ok")
        if ok is False and red_at is None:
            red_at = row["stamp"]
        elif ok is True and red_at is not None:
            spans.append(max(0, row["stamp"] - red_at))
            red_at = None
    return spans, red_at is not None


def collect_full_safe(common: Path, trunk: dict) -> dict:
    history_path = common / "full-safe-history.jsonl"
    valid_rows: list[dict] = []
    dropped = 0
    if history_path.is_file():
        decoder = json.JSONDecoder()
        try:
            lines = history_path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            lines = []
        for line in lines:
            if not line.strip():
                continue
            try:
                row = decoder.decode(line)
            except ValueError:
                row = None
            stamp = _parse_iso(row.get("at")) if isinstance(row, dict) else None
            head = str(row.get("head") or "") if isinstance(row, dict) else ""
            if stamp is None or not HEAD_RE.fullmatch(head):
                dropped += 1
            else:
                valid_rows.append(dict(row, stamp=stamp))
    total_valid = len(valid_rows)
    total_green = sum(1 for row in valid_rows if row.get("ok") is True)
    total_red = total_valid - total_green
    recent = valid_rows[-RECENT_HISTORY_LIMIT:]
    recent_green = sum(1 for row in recent if row.get("ok") is True)
    recent_red = len(recent) - recent_green

    cutoff_7d = trunk["ts"] - WEEK_SECONDS
    rows_7d = [row for row in valid_rows if row["stamp"] >= cutoff_7d]
    spans_7d, open_red_7d = _red_dwell_spans(rows_7d)
    spans_all, open_red_all = _red_dwell_spans(valid_rows)

    receipts_doc = _read_json_file(common / "full-safe-receipts.json")
    verified_trees = []
    last_full_round = 0
    if isinstance(receipts_doc, dict):
        raw_trees = receipts_doc.get("full_safe_verified_trees")
        if isinstance(raw_trees, list):
            verified_trees = [item for item in raw_trees if isinstance(item, dict)]
        try:
            last_full_round = int(receipts_doc.get("last_full_safe_all_round") or 0)
        except (TypeError, ValueError):
            last_full_round = 0
    tree_match = next(
        (item for item in verified_trees if item.get("tree") == trunk["program_tree"] and trunk["program_tree"]),
        None,
    )

    auto_doc = _read_json_file(common / "auto-full-safe-result.json")
    auto_summary = {}
    if isinstance(auto_doc, dict):
        auto_summary = {
            "head": str(auto_doc.get("head") or "")[:9],
            "returncode": auto_doc.get("returncode"),
            "finished_at": str(auto_doc.get("finished_at") or ""),
            "blocked": str(auto_doc.get("blocked") or ""),
            "red_count": len(auto_doc.get("red") or []) if isinstance(auto_doc.get("red"), list) else 0,
        }

    return {
        "history_exists": history_path.is_file(),
        "valid_total": total_valid,
        "dropped_invalid": dropped,
        "total_green": total_green,
        "total_red": total_red,
        "recent_window": len(recent),
        "recent_green": recent_green,
        "recent_red": recent_red,
        "rows_7d_count": len(rows_7d),
        "spans_7d_count": len(spans_7d),
        "spans_7d_median": _median(spans_7d),
        "spans_7d_max": max(spans_7d) if spans_7d else None,
        "open_red_7d": open_red_7d,
        "spans_all_count": len(spans_all),
        "spans_all_median": _median(spans_all),
        "spans_all_max": max(spans_all) if spans_all else None,
        "open_red_all": open_red_all,
        "verified_tree_count": len(verified_trees),
        "last_full_round": last_full_round,
        "trunk_tree_verified": tree_match is not None,
        "trunk_tree_round": tree_match.get("round") if isinstance(tree_match, dict) else None,
        "auto_result": auto_summary,
    }


def collect_merge_queue(repo: Path, common: Path, ref: str) -> dict:
    doc = _read_json_file(common / "merge-queue.json")
    items = doc.get("items") if isinstance(doc, dict) and isinstance(doc.get("items"), list) else []
    counts: Counter[str] = Counter()
    existing_branches = {
        line.strip()
        for line in _git_out(repo, "for-each-ref", "--format=%(refname:short)", "refs/heads").splitlines()
        if line.strip()
    }
    merged_branches = {
        line.strip()
        for line in _git_out(repo, "branch", "--merged", ref, "--format=%(refname:short)").splitlines()
        if line.strip()
    }
    stale_failed_merged = 0
    stale_failed_missing = 0
    for item in items:
        if not isinstance(item, dict):
            continue
        status = str(item.get("status") or "unknown")
        counts[status] += 1
        if status == "failed":
            branch = str(item.get("branch") or "")
            if branch in merged_branches:
                stale_failed_merged += 1
            elif branch and branch not in existing_branches:
                stale_failed_missing += 1
    recent = []
    for item in items[-5:]:
        if isinstance(item, dict):
            recent.append({
                "id": str(item.get("id") or ""),
                "status": str(item.get("status") or ""),
                "branch": str(item.get("branch") or ""),
                "note": str(item.get("note") or ""),
            })
    total = sum(counts.values())
    return {
        "total": total,
        "done": counts.get("done", 0),
        "failed": counts.get("failed", 0),
        "pending": counts.get("pending", 0),
        "serving": counts.get("serving", 0),
        "other": total - sum(counts.get(k, 0) for k in ("done", "failed", "pending", "serving")),
        "stale_failed_merged": stale_failed_merged,
        "stale_failed_missing": stale_failed_missing,
        "recent": recent,
    }


def _parse_worktree_list(repo: Path) -> list[dict]:
    done = _git(repo, "worktree", "list", "--porcelain", "-z")
    if done.returncode != 0:
        return []
    rows: list[dict] = []
    row: dict = {}
    for field in done.stdout.split("\0"):
        key, _, value = field.partition(" ")
        if key == "worktree":
            row = {"path": value}
            rows.append(row)
        elif key:
            row[key] = value or True
    return rows


def _branch_ahead_map(repo: Path, ref: str) -> dict[str, dict]:
    fmt = "%(refname:short)\t%(ahead-behind:" + ref + ")\t%(committerdate:unix)"
    out = _git_out(repo, "for-each-ref", "--format=" + fmt, "refs/heads")
    mapping: dict[str, dict] = {}
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        counts = parts[1].split()
        try:
            ahead, behind = int(counts[0]), int(counts[1])
        except (IndexError, ValueError):
            continue
        mapping[parts[0]] = {
            "ahead": ahead,
            "behind": behind,
            "committed": int(parts[2]) if parts[2].isdigit() else 0,
        }
    return mapping


def collect_worktrees_and_branches(repo: Path, main_root: Path, common: Path, ref: str, anchor_ts: int) -> dict:
    records = _parse_worktree_list(repo)
    branches_map = _branch_ahead_map(repo, ref)

    def probe(record: dict) -> dict:
        wt_path = Path(record["path"])
        branch = str(record.get("branch", "")).removeprefix("refs/heads/")
        detached = bool(record.get("detached"))
        label = _sanitize_path(record["path"], main_root)
        info = {
            "label": label,
            "branch": branch,
            "detached": detached,
            "prunable": bool(record.get("prunable")),
            "dirty": False,
            "merge_in_progress": False,
            "rebase_in_progress": False,
            "ahead": None,
            "error": False,
        }
        if not wt_path.is_dir():
            info["error"] = True
            return info
        st = _git(wt_path, "status", "--porcelain")
        if st.returncode == 0:
            info["dirty"] = bool(st.stdout.strip())
        else:
            info["error"] = True
        gitdir_out = _git_out(wt_path, "rev-parse", "--absolute-git-dir").strip()
        if gitdir_out:
            gitdir = Path(gitdir_out)
            info["merge_in_progress"] = (gitdir / "MERGE_HEAD").exists()
            info["rebase_in_progress"] = (gitdir / "rebase-merge").exists() or (gitdir / "rebase-apply").exists()
        if branch and branch in branches_map:
            info["ahead"] = branches_map[branch]["ahead"]
        elif record.get("HEAD"):
            cnt = _git_out(repo, "rev-list", "--count", f"{ref}..{record['HEAD']}").strip()
            if cnt.isdigit():
                info["ahead"] = int(cnt)
        return info

    with ThreadPoolExecutor(max_workers=WORKTREE_WORKERS) as pool:
        rows = list(pool.map(probe, records))
    rows.sort(key=lambda item: (item["label"], item["branch"]))

    # lanes.json 统计（锚定到 anchor_ts，确保确定性）
    lanes_doc = _read_json_file(common / "lanes.json")
    lanes = lanes_doc.get("lanes") if isinstance(lanes_doc, dict) and isinstance(lanes_doc.get("lanes"), dict) else {}
    lanes_total = sum(1 for v in lanes.values() if isinstance(v, dict))
    lanes_active_24h = 0
    for entry in lanes.values():
        if not isinstance(entry, dict):
            continue
        try:
            seen = float(entry.get("last_seen") or 0)
        except (TypeError, ValueError):
            seen = 0.0
        if seen and seen >= anchor_ts - DAY_SECONDS:
            lanes_active_24h += 1

    # maintenance-queue.json 活跃租约（与 worktree_ledger.active_leases 同口径，锚定到 anchor_ts）
    mq_doc = _read_json_file(common / "maintenance-queue.json")
    mq_items = mq_doc.get("items") if isinstance(mq_doc, dict) and isinstance(mq_doc.get("items"), list) else []
    active_leases = 0
    for item in mq_items:
        if not isinstance(item, dict) or item.get("status") != "claimed":
            continue
        until = _parse_iso(item.get("lease_until"))
        if until is not None and until > anchor_ts:
            active_leases += 1

    unmerged_branches = [
        line.strip()
        for line in _git_out(repo, "branch", "--no-merged", ref, "--format=%(refname:short)").splitlines()
        if line.strip()
    ]

    return {
        "total": len(rows),
        "dirty": sum(1 for r in rows if r["dirty"]),
        "detached": sum(1 for r in rows if r["detached"]),
        "ahead_zero": sum(1 for r in rows if r["ahead"] == 0),
        "merge_in_progress": [r for r in rows if r["merge_in_progress"]],
        "rebase_in_progress": [r for r in rows if r["rebase_in_progress"]],
        "error_count": sum(1 for r in rows if r["error"]),
        "lanes_registered": lanes_total,
        "lanes_active_24h": lanes_active_24h,
        "maintenance_leases": active_leases,
        "branches_total": len(branches_map),
        "branches_unmerged": len(unmerged_branches),
    }


def collect_orphan_claims(repo: Path, main_root: Path, common: Path, ref: str) -> dict:
    counter_doc = _read_json_file(common / "round-counter.json")
    last_claimed = 0
    if isinstance(counter_doc, dict):
        try:
            last_claimed = int(counter_doc.get("last_claimed") or 0)
        except (TypeError, ValueError):
            last_claimed = 0

    claims_doc = _read_json_file(common / "round-claims.json")
    claims = claims_doc.get("claims") if isinstance(claims_doc, dict) and isinstance(claims_doc.get("claims"), dict) else {}

    committed_rounds: set[int] = set()
    for line in _git_out(repo, "log", "--all", "--format=%s").splitlines():
        matched = ROUND_RE.match(line.strip())
        if matched:
            committed_rounds.add(int(matched.group(1)))

    result_rounds: set[int] = set()
    for name in _git_out(repo, "ls-tree", "-r", "--name-only", ref, "--", "程序/tasks_round").splitlines():
        matched = RESULT_RE.search(name)
        if matched:
            result_rounds.add(int(matched.group(1)))

    used_rounds = committed_rounds | result_rounds
    orphans_gone: list[dict] = []
    orphans_present: list[dict] = []
    for key, entry in claims.items():
        if not str(key).isdigit():
            continue
        num = int(key)
        if num in used_rounds:
            continue
        worktree_raw = entry.get("worktree", "") if isinstance(entry, dict) else str(entry or "")
        branch = entry.get("branch", "") if isinstance(entry, dict) else ""
        claimed_at = entry.get("at", "") if isinstance(entry, dict) else ""
        exists = bool(worktree_raw) and Path(worktree_raw).is_dir()
        item = {
            "round": num,
            "branch": str(branch),
            "worktree": _sanitize_path(worktree_raw, main_root),
            "at": str(claimed_at),
            "worktree_exists": exists,
        }
        if exists:
            orphans_present.append(item)
        else:
            orphans_gone.append(item)
    orphans_gone.sort(key=lambda item: item["round"])
    orphans_present.sort(key=lambda item: item["round"])
    return {
        "last_claimed": last_claimed,
        "total_claims": len(claims),
        "uncommitted_total": len(orphans_gone) + len(orphans_present),
        "orphans_gone": orphans_gone,
        "orphans_present": orphans_present,
    }


def collect_locks(common: Path, anchor_ts: int) -> dict:
    extra = sorted(
        p.name for p in common.glob("*.lock")
        if p.is_file() and p.name not in KNOWN_LOCKS
    )
    names = [*KNOWN_LOCKS, *extra]
    rows = []
    for name in names:
        path = common / name
        if not path.exists():
            rows.append({
                "name": name,
                "exists": False,
                "state": "不存在",
                "pid": "—",
                "round": "—",
                "has_heartbeat": "—",
                "started_at": "—",
            })
            continue
        obj, kind = _read_lock_object(path)
        if kind != "json" or obj is None:
            rows.append({
                "name": name,
                "exists": True,
                "state": "占位/非JSON" if kind == "non-json" else kind,
                "pid": "—",
                "round": "—",
                "has_heartbeat": "否",
                "started_at": "—",
            })
            continue
        pid = obj.get("pid")
        round_no = obj.get("round")
        has_hb = obj.get("heartbeat_at") is not None
        started_ts = obj.get("started_at") or obj.get("created_at")
        alive = _pid_alive(pid)
        if has_hb:
            try:
                hb_ts = float(obj["heartbeat_at"])
            except (TypeError, ValueError):
                hb_ts = 0.0
            # 不输出易变秒差：若 PID 已死或心跳早于 anchor_ts-180s 则判定静默
            if not alive or (hb_ts and anchor_ts - hb_ts >= 180.0):
                state = "静默(可回收)"
            else:
                state = "活跃(有心跳)"
        else:
            state = "旧锁(PID活)" if alive else "旧锁(PID死)"
        rows.append({
            "name": name,
            "exists": True,
            "state": state,
            "pid": str(pid) if pid is not None else "—",
            "round": ("R%s" % round_no) if round_no is not None else "—",
            "has_heartbeat": "有" if has_hb else "无",
            "started_at": _fmt_utc(started_ts),
        })
    gui_queue_dir = common / "gui-selftest.queue"
    tickets = sorted(p.name for p in gui_queue_dir.glob("*.ticket")) if gui_queue_dir.is_dir() else []
    return {"locks": rows, "gui_queue_tickets": len(tickets)}


def _extract_const(path: Path, name: str) -> str:
    if not path.is_file():
        return "未知"
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, SyntaxError):
        return "未知"
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    try:
                        return str(ast.literal_eval(node.value))
                    except ValueError:
                        return ast.unparse(node.value)
    return "未找到"


def collect_code_params(program_dir: Path, common: Path) -> dict:
    commit_src = (program_dir / "scripts" / "commit_round.py").read_text(encoding="utf-8", errors="replace")
    wait_match = re.search(r'"--wait-minutes"[^)]*default=([0-9.]+)', commit_src)
    commit_wait_min = wait_match.group(1) if wait_match else "未知"

    merge_src = (program_dir / "scripts" / "merge_round.py").read_text(encoding="utf-8", errors="replace")
    merge_wait_match = re.search(r"wait_for_lock\([^,]+,\s*([^)]+)\)", merge_src)
    merge_wait_expr = merge_wait_match.group(1).strip() if merge_wait_match else "未知"

    sched_src = (program_dir / "selftest_scheduling.py").read_text(encoding="utf-8", errors="replace")
    full_lock_match = re.search(r"def acquire_full_safe_lock[\s\S]{0,400}?acquire_pid_lock\(([^,]+)", sched_src)
    full_lock_const = full_lock_match.group(1).strip() if full_lock_match else "未知"

    scope_path = program_dir / "维护记录" / "基准脚本" / "branch_scope.py"
    scope_src = scope_path.read_text(encoding="utf-8", errors="replace") if scope_path.is_file() else ""
    has_trial_merge = "def _run_merge_tree(" in scope_src and "merge-tree" in scope_src
    active_hours = _extract_const(scope_path, "ACTIVE_HOURS")
    cache_doc = _read_json_file(common / "scope-gate-cache.json")
    cache_entries = len(cache_doc.get("entries")) if isinstance(cache_doc, dict) and isinstance(cache_doc.get("entries"), dict) else 0

    env_path = program_dir / "selftest_env.py"
    lease_path = program_dir / "维护记录" / "基准脚本" / "lock_lease.py"
    return {
        "commit_wait_minutes": commit_wait_min,
        "merge_wait_expr": merge_wait_expr,
        "full_lock_const": full_lock_const,
        "gui_wait_seconds": _extract_const(env_path, "GUI_WAIT_SECONDS"),
        "gui_full_suite_wait_seconds": _extract_const(env_path, "GUI_FULL_SUITE_WAIT_SECONDS"),
        "lease_heartbeat_seconds": _extract_const(lease_path, "LOCK_HEARTBEAT_SECONDS"),
        "lease_stale_seconds": _extract_const(lease_path, "LOCK_STALE_SECONDS"),
        "scope_trial_merge": has_trial_merge,
        "scope_active_hours": active_hours,
        "scope_cache_entries": cache_entries,
    }


def collect_all(repo: Path) -> dict:
    work_root, main_root, common = resolve_repo_and_common(repo)
    program_dir = work_root / "程序"
    trunk = collect_trunk_anchor(work_root)
    return {
        "trunk": trunk,
        "non_round": collect_non_round_commits(work_root, trunk["ref"], trunk["ts"]),
        "root_layout": collect_root_layout(work_root, trunk["ref"], program_dir),
        "full_safe": collect_full_safe(common, trunk),
        "merge_queue": collect_merge_queue(work_root, common, trunk["ref"]),
        "worktrees": collect_worktrees_and_branches(work_root, main_root, common, trunk["ref"], trunk["ts"]),
        "claims": collect_orphan_claims(work_root, main_root, common, trunk["ref"]),
        "locks": collect_locks(common, trunk["ts"]),
        "params": collect_code_params(program_dir, common),
    }


def render_markdown(data: dict) -> str:
    trunk = data["trunk"]
    nr = data["non_round"]
    rl = data["root_layout"]
    fs = data["full_safe"]
    mq = data["merge_queue"]
    wt = data["worktrees"]
    cl = data["claims"]
    lk = data["locks"]
    pm = data["params"]

    lines = [
        "# Git 并发与锁机制基线报告（只读）",
        "",
        "- 基准主干：`%s` `%s`（提交时间 `%s`）" % (trunk["ref"], trunk["short"], _fmt_utc(trunk["ts"])),
        "- 采集口径：只读（`git --no-optional-locks` 与 common-dir 台账），时间窗锚定到主干 HEAD 提交时间，不输出易变墙上时钟。",
        "",
        "## 1. §1 验收线指标总览",
        "",
        "| 验收线 | 当前基线值 | 2026-11-20 基线 | 目标 | 说明 |",
        "| --- | --- | --- | --- | --- |",
        "| 主干上的非轮次提交 | 24h 内 %d 个；近 %d 共 %d 个 | 24h 内 2 个（近 600 共 2 个） | 机制上写不进去 | 第一父链不以 `R<N>:`/`R<N>-FAIL:` 开头 |"
        % (nr["count_24h"], nr["checked"], nr["count_600"]),
        "| 主干根目录未登记条目（F2） | %d 个未登记（`.agents/` 受跟踪 %d 个） | 78 个 `.agents/`（主干必红） | 0 | 对照 `tests/test_root_layout.py` ALLOWED |"
        % (len(rl["unregistered_top"]), rl["agents_tracked_count"]),
        "| 7 天全量红灯段与停留 | %d 段，中位 %s／最长 %s%s | 18 段，中位 2.4 小时（最长 24.5 小时） | 合入不引红；环境红 ≤ 20 分钟 | `full-safe-history.jsonl` 锚点前 7 天（%d 条有效） |"
        % (
            fs["spans_7d_count"],
            _fmt_hours(fs["spans_7d_median"]),
            _fmt_hours(fs["spans_7d_max"]),
            "（末尾仍在红）" if fs["open_red_7d"] else "",
            fs["rows_7d_count"],
        ),
        "| 全量历史绿/红统计 | 近 %d 次绿 %d / 红 %d（%s）；全历史绿 %d / 红 %d（%s） | 最近 40 次绿 6 / 红 34（15.0%%） | 主干最新绿凭据比例 ≥ 90%% | 剔除 %d 条无效记录 |"
        % (
            fs["recent_window"],
            fs["recent_green"],
            fs["recent_red"],
            _pct(fs["recent_green"], fs["recent_window"]),
            fs["total_green"],
            fs["total_red"],
            _pct(fs["total_green"], fs["valid_total"]),
            fs["dropped_invalid"],
        ),
        "| 主干最新提交全量绿凭据 | %s（最近绿凭据 R%d，库内 %d 条） | — | ≥ 90%% | `full-safe-receipts.json` 对照 `master:程序` |"
        % (
            ("已覆盖（R%s）" % fs["trunk_tree_round"]) if fs["trunk_tree_verified"] else "未覆盖",
            fs["last_full_round"],
            fs["verified_tree_count"],
        ),
        "| 合并队列统计与失败率 | 共 %d：完成 %d、失败 %d（%s）、待 %d、执 %d | 31 条里失败 10 条（32.3%%） | 失败率 < 10%% | 失败项中 %d 已合入、%d 分支已删 |"
        % (
            mq["total"],
            mq["done"],
            mq["failed"],
            _pct(mq["failed"], mq["total"]),
            mq["pending"],
            mq["serving"],
            mq["stale_failed_merged"],
            mq["stale_failed_missing"],
        ),
        "| 重叠门禁状态 | %s（活跃窗 %s h，试合并缓存 %d 条） | 整文件拒绝（R3919/R3922 误拒） | 0 误拒（有回归用例） | `维护记录/基准脚本/branch_scope.py` |"
        % ("三方试合并已上线" if pm["scope_trial_merge"] else "整文件拒绝", pm["scope_active_hours"], pm["scope_cache_entries"]),
        "| 工作树数量与状态 | 总 %d 棵：脏 %d、游离 %d、`ahead=0` %d、租约 %d | 76 棵，脏 50，游离 7，`ahead=0` 49，租约 0 | 活跃车道 ≤ 20，无无主脏树 | `lanes.json` 登记 %d（24h 活跃 %d）；读取错误 %d |"
        % (
            wt["total"],
            wt["dirty"],
            wt["detached"],
            wt["ahead_zero"],
            wt["maintenance_leases"],
            wt["lanes_registered"],
            wt["lanes_active_24h"],
            wt["error_count"],
        ),
        "| 本地分支数量（F7） | 总 %d 个，未合入 `%s` %d 个 | 406 / 362 | 停用分支归档 | `git branch --no-merged %s` |"
        % (wt["branches_total"], trunk["ref"], wt["branches_unmerged"], trunk["ref"]),
        "| 合并中／变基中残留 | 合并中 %d 棵，变基中 %d 棵 | 5 棵合并中 | 0，或 `doctor` 有归属 | 扫描各工作树 `MERGE_HEAD` 与 `rebase-*` |"
        % (len(wt["merge_in_progress"]), len(wt["rebase_in_progress"])),
        "| 无主领号（无提交且无结果） | 共 %d 个（工作树已删 %d、仍在 %d） | 至少 1 个（R3917） | 0，或 `doctor` 有归属 | `round-claims.json` 共 %d 条，`last_claimed=R%d` |"
        % (
            cl["uncommitted_total"],
            len(cl["orphans_gone"]),
            len(cl["orphans_present"]),
            cl["total_claims"],
            cl["last_claimed"],
        ),
        "| 提交等锁上限 / GUI 等锁上限 | 提交 %s 分钟（合并 %s）；GUI %s 秒（遇全量 %s 秒） | 30 分钟 / 1800 秒 | 提交 5 分钟（P0-2） | 锁租约心跳 %s s、静默 %s s |"
        % (
            pm["commit_wait_minutes"],
            pm["merge_wait_expr"],
            pm["gui_wait_seconds"],
            pm["gui_full_suite_wait_seconds"],
            pm["lease_heartbeat_seconds"],
            pm["lease_stale_seconds"],
        ),
    ]

    lines += ["", "## 2. 主干非轮次提交明细（近 %d 第一父链）" % nr["checked"], ""]
    if nr["items_600"]:
        lines += ["| 提交 | 时间 (UTC) | 标题 |", "| --- | --- | --- |"]
        for item in nr["items_600"]:
            lines.append("| `%s` | %s | %s |" % (item["sha"], item["at"], item["subject"].replace("|", "\\|")))
    else:
        lines.append("- 无非轮次提交。")

    lines += ["", "## 3. 全量历史与后台自动全量状态", ""]
    auto = fs["auto_result"]
    if auto:
        lines.append(
            "- `auto-full-safe-result.json`：head=`%s`，returncode=`%s`，finished_at=`%s`，red=%d%s"
            % (
                auto["head"] or "—",
                auto["returncode"],
                auto["finished_at"] or "—",
                auto["red_count"],
                ("，blocked=`%s`" % auto["blocked"]) if auto["blocked"] else "",
            )
        )
    else:
        lines.append("- `auto-full-safe-result.json`：不存在或不可读。")
    lines.append(
        "- 全历史红灯停留：%d 段，中位 %s，最长 %s%s。"
        % (
            fs["spans_all_count"],
            _fmt_hours(fs["spans_all_median"]),
            _fmt_hours(fs["spans_all_max"]),
            "（末尾仍在红）" if fs["open_red_all"] else "",
        )
    )

    lines += ["", "## 4. 合并队列最近 5 条", ""]
    if mq["recent"]:
        lines += ["| 编号 | 状态 | 分支 | 备注 |", "| --- | --- | --- | --- |"]
        for item in mq["recent"]:
            lines.append(
                "| %s | %s | `%s` | %s |"
                % (item["id"], item["status"], item["branch"], (item["note"] or "—").replace("|", "\\|"))
            )
    else:
        lines.append("- 队列为空。")

    lines += ["", "## 5. 合并中／变基中残留工作树", ""]
    stuck = [
        ("MERGE_HEAD", r) for r in wt["merge_in_progress"]
    ] + [
        ("REBASE", r) for r in wt["rebase_in_progress"]
    ]
    if stuck:
        lines += ["| 现场 | 工作树（脱敏） | 分支 | 脏树 |", "| --- | --- | --- | --- |"]
        for kind, row in stuck:
            lines.append("| %s | `%s` | `%s` | %s |" % (kind, row["label"], row["branch"] or "(detached)", "是" if row["dirty"] else "否"))
    else:
        lines.append("- 无合并中或变基中残留。")

    lines += ["", "## 6. 无主领号明细（展示最近 20 条）", ""]
    combined = sorted(cl["orphans_gone"] + cl["orphans_present"], key=lambda item: item["round"])
    if combined:
        lines += ["| 轮次 | 分支 | 工作树（脱敏） | 工作树仍在 | 认领时间 |", "| --- | --- | --- | --- | --- |"]
        for item in combined[-20:]:
            lines.append(
                "| R%d | `%s` | `%s` | %s | %s |"
                % (
                    item["round"],
                    item["branch"] or "—",
                    item["worktree"],
                    "是" if item["worktree_exists"] else "否",
                    item["at"] or "—",
                )
            )
        if len(combined) > 20:
            lines.append("")
            lines.append("- 另有更早的 %d 条未展开。" % (len(combined) - 20))
    else:
        lines.append("- 无未提交且无结果文件的领号。")

    lines += ["", "## 7. 共享锁状态（common-dir）", ""]
    lines += ["| 锁文件 | 状态 | PID | 轮次 | 心跳字段 | 启动时间 (UTC) |", "| --- | --- | --- | --- | --- | --- |"]
    for row in lk["locks"]:
        lines.append(
            "| `%s` | %s | %s | %s | %s | %s |"
            % (row["name"], row["state"], row["pid"], row["round"], row["has_heartbeat"], row["started_at"])
        )
    lines.append("")
    lines.append("- `gui-selftest.queue` 排队票据数：%d" % lk["gui_queue_tickets"])

    lines += [
        "",
        "## 8. 锁与超时参数（源码静态读出）",
        "",
        "- `acquire_full_safe_lock` 持有锁常量：`%s`" % pm["full_lock_const"],
        "- `commit_round.py --wait-minutes` 默认：`%s` 分钟" % pm["commit_wait_minutes"],
        "- `merge_round.py` 等锁超时表达式：`%s` 秒" % pm["merge_wait_expr"],
        "- `selftest_env.py`：`GUI_WAIT_SECONDS=%s`，`GUI_FULL_SUITE_WAIT_SECONDS=%s`"
        % (pm["gui_wait_seconds"], pm["gui_full_suite_wait_seconds"]),
        "- `lock_lease.py`：`LOCK_HEARTBEAT_SECONDS=%s`，`LOCK_STALE_SECONDS=%s`"
        % (pm["lease_heartbeat_seconds"], pm["lease_stale_seconds"]),
    ]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo", default=str(PROGRAM.parent), help="Git 仓库或工作树路径")
    parser.add_argument("--output", default=str(DEFAULT_REPORT), help="报告输出路径（默认 程序/logs/concurrency_report.md）")
    parser.add_argument("--no-write", action="store_true", help="只输出到标准输出，不写文件")
    args = parser.parse_args(argv)
    data = collect_all(Path(args.repo))
    report = render_markdown(data)
    if not args.no_write:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(report, encoding="utf-8", newline="\n")
    sys.stdout.write(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

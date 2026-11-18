"""合并请求队列（任务书 B3）：<git common-dir>/merge-queue.json。

高并发下各车道不再各自阻塞等合并：``enqueue`` 只登记请求（亚秒级），
由合并道（专职或任一空闲会话）``serve`` 按 FIFO 逐条执行 merge_round。
队列项带租约；serve 中途死亡时过期 serving 项可被重新拾取，
绝不自动 abort 他人 MERGE_HEAD（merge_round 自身负责归属清理）。
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

PROGRAM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROGRAM))  # agent 包位于 程序/agent
QUEUE_NAME = "merge-queue.json"
SERVING_STALE_SECONDS = 45 * 60  # serving 超龄视为执行者失联，可重新拾取


def common_dir(root: Path = PROGRAM.parent) -> Path:
    out = subprocess.run(["git", "-C", str(root), "rev-parse", "--git-common-dir"],
                         capture_output=True, text=True, timeout=15,
                         encoding="utf-8", errors="replace")
    path = out.stdout.strip()
    if out.returncode or not path:
        raise RuntimeError("无法定位 git common-dir")
    p = Path(path)
    return p if p.is_absolute() else (root / p).resolve()


def queue_path(common: Path) -> Path:
    return Path(common) / QUEUE_NAME


def _read(path: Path) -> dict:
    try:
        from agent.core import read_json
        data = read_json(path)
    except Exception:
        data = None
    if isinstance(data, dict) and isinstance(data.get("items"), list):
        return data
    return {"items": []}


def _write(path: Path, doc: dict) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, path)


def _next_id(items: list) -> str:
    top = 0
    for item in items:
        try:
            top = max(top, int(str(item.get("id", "mq-0")).rsplit("-", 1)[-1]))
        except ValueError:
            continue
    return "mq-%d" % (top + 1)


def enqueue(common: Path, branch: str, summary: str, owner: str = "") -> dict:
    """登记合并请求；同分支已有 pending/serving 项时拒绝重复入队。"""
    branch = branch.strip()
    if not branch:
        raise ValueError("branch 不能为空")
    path = queue_path(common)
    doc = _read(path)
    for item in doc["items"]:
        if item.get("branch") == branch and item.get("status") in ("pending", "serving"):
            raise RuntimeError("分支 %s 已有未完成合并请求 %s（%s）" %
                               (branch, item.get("id"), item.get("status")))
    item = {"id": _next_id(doc["items"]), "branch": branch, "summary": summary,
            "owner": owner or _lane_name(), "status": "pending",
            "enqueued_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "lease_until": "", "round": None, "note": ""}
    doc["items"].append(item)
    _write(path, doc)
    return dict(item)


def _lane_name() -> str:
    try:
        top = subprocess.run(["git", "rev-parse", "--show-toplevel"],
                             capture_output=True, text=True, timeout=15,
                             cwd=str(PROGRAM), encoding="utf-8", errors="replace").stdout.strip()
        return Path(top).name if top else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def list_items(common: Path) -> list:
    return list(_read(queue_path(common))["items"])


def _pop_next(common: Path, now: float) -> dict | None:
    """取最早 pending；serving 超龄未完成的视为失联，重置回 pending 重试一次。"""
    path = queue_path(common)
    doc = _read(path)
    items = doc["items"]
    for item in items:
        if item.get("status") == "serving":
            try:
                seen = datetime.fromisoformat(str(item.get("serving_since", ""))).timestamp()
            except ValueError:
                seen = 0
            if now - seen > SERVING_STALE_SECONDS:
                item["status"] = "pending"
                item["note"] = (item.get("note", "") + "；" if item.get("note") else "") + \
                    "serving 超龄失联，重新入队"
                item["serving_since"] = ""
    pending = [i for i in items if i.get("status") == "pending"]
    if not pending:
        _write(path, doc)
        return None
    pending.sort(key=lambda i: str(i.get("enqueued_at", "")))
    item = pending[0]
    item["status"] = "serving"
    item["serving_since"] = datetime.now().astimezone().isoformat(timespec="seconds")
    _write(path, doc)
    return dict(item)


def _finish(common: Path, item_id: str, status: str, note: str = "", round_no: int | None = None) -> None:
    path = queue_path(common)
    doc = _read(path)
    for item in doc["items"]:
        if item.get("id") == item_id:
            item["status"] = status
            item["finished_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
            if note:
                item["note"] = (item.get("note", "") + "；" if item.get("note") else "") + note
            if round_no:
                item["round"] = round_no
    _write(path, doc)


def serve(common: Path, once: bool = False) -> int:
    """FIFO 执行 pending 项：调 merge_round.py；全部处理完（once 时处理一条）退出。"""
    failures = 0
    while True:
        item = _pop_next(common, time.time())
        if item is None:
            return 1 if failures else 0
        print("[merge-queue] 执行 %s 分支=%s 说明=%s" % (item["id"], item["branch"], item["summary"]), flush=True)
        cmd = [sys.executable, "-B", str(PROGRAM / "scripts" / "merge_round.py"),
               item["branch"], "-s", item["summary"]]
        proc = subprocess.run(cmd, cwd=str(PROGRAM))
        if proc.returncode == 0:
            _finish(common, item["id"], "done", round_no=_latest_round())
            print("[merge-queue] %s 完成" % item["id"], flush=True)
        else:
            failures += 1
            _finish(common, item["id"], "failed", note="merge_round 退出码 %d" % proc.returncode)
            print("[merge-queue] %s 失败 rc=%d" % (item["id"], proc.returncode), flush=True)
        if once:
            return proc.returncode


def _latest_round() -> int | None:
    try:
        out = subprocess.run([sys.executable, "-B", str(PROGRAM / "维护记录" / "基准脚本" / "round_claim.py"),
                              "show"], cwd=str(PROGRAM), capture_output=True, text=True, timeout=30,
                             encoding="utf-8", errors="replace")
        import re
        nums = [int(n) for n in re.findall(r"R(\d+)", out.stdout + out.stderr)]
        return max(nums) if nums else None
    except (OSError, subprocess.SubprocessError, ValueError):
        return None


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    en = sub.add_parser("enqueue", help="登记合并请求")
    en.add_argument("branch")
    en.add_argument("-s", "--summary", required=True)
    en.add_argument("--owner", default="")
    sub.add_parser("list", help="列出合并队列")
    sv = sub.add_parser("serve", help="FIFO 执行队列（合并道）")
    sv.add_argument("--once", action="store_true", help="只处理一条")
    args = parser.parse_args(argv)
    common = common_dir()
    if args.command == "enqueue":
        try:
            item = enqueue(common, args.branch, args.summary, args.owner)
        except (RuntimeError, ValueError) as exc:
            print(str(exc), file=sys.stderr)
            return 2
        print(json.dumps(item, ensure_ascii=False))
        return 0
    if args.command == "list":
        for item in list_items(common):
            print("%-8s %-8s %-40s %s" % (item.get("id"), item.get("status"),
                                          item.get("branch"), item.get("summary", "")))
        return 0
    return serve(common, once=args.once)


if __name__ == "__main__":
    raise SystemExit(main())

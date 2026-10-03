"""为共享 Git 仓库的并行工作树分配轮次，并原子认领任务队列。"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path


PROGRAM = Path(__file__).resolve().parents[2]
ROOT = PROGRAM.parent
RESULT_RE = re.compile(r"tasks_round_(\d+)_result\.md$")
LOCK_NAME = "round-claim.lock"
COUNTER_NAME = "round-counter.json"
DEFAULT_QUEUE = PROGRAM / "维护记录" / "任务队列.json"


def git_common_dir(root: Path = ROOT) -> Path:
    result = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "--git-common-dir"],
        text=True, capture_output=True, check=True,
    )
    path = Path(result.stdout.strip())
    return path if path.is_absolute() else (root / path).resolve()


def latest_result_round(tasks_round: Path = PROGRAM / "tasks_round") -> int:
    values = [int(match.group(1)) for item in tasks_round.glob("tasks_round_*_result.md")
              if (match := RESULT_RE.search(item.name))]
    return max(values, default=0)


def read_counter(counter: Path) -> int:
    try:
        value = json.loads(counter.read_text(encoding="utf-8"))
        return int(value.get("last_claimed", 0)) if isinstance(value, dict) else 0
    except (OSError, ValueError, TypeError):
        return 0


def _acquire_lock(common_dir: Path, timeout: float = 15.0) -> Path:
    lock = common_dir / LOCK_NAME
    deadline = time.monotonic() + timeout
    while True:
        try:
            descriptor = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            if time.monotonic() >= deadline:
                raise TimeoutError("共享认领锁被占用：%s" % lock)
            time.sleep(0.05)
            continue
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump({"pid": os.getpid(), "created_at": time.time()}, handle)
        return lock


@contextmanager
def shared_lock(common_dir: Path):
    common_dir.mkdir(parents=True, exist_ok=True)
    lock = _acquire_lock(common_dir)
    try:
        yield
    finally:
        try:
            lock.unlink()
        except FileNotFoundError:
            pass


def _atomic_json_write(path: Path, value: object) -> None:
    temporary = path.with_name(path.name + ".%s.tmp" % os.getpid())
    temporary.write_text(json.dumps(value, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def claim_next(*, common_dir: Path, tasks_round: Path) -> int:
    """在共享 git common-dir 下原子地领取下一个未使用轮次。"""
    with shared_lock(common_dir):
        counter = common_dir / COUNTER_NAME
        next_round = max(read_counter(counter), latest_result_round(tasks_round)) + 1
        _atomic_json_write(counter, {"last_claimed": next_round})
        return next_round


def _read_queue(queue_path: Path) -> dict:
    payload = json.loads(queue_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
        raise ValueError("任务队列格式无效：%s" % queue_path)
    return payload


def _queue_item(payload: dict, task_id: str) -> dict:
    for item in payload["items"]:
        if isinstance(item, dict) and item.get("id") == task_id:
            return item
    raise KeyError("任务队列不存在：%s" % task_id)


def _parse_time(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    parsed = datetime.fromisoformat(value)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _note(item: dict, text: str) -> None:
    previous = str(item.get("note", "")).strip()
    item["note"] = (previous + "；" if previous else "") + text


def claim_task(*, common_dir: Path, queue_path: Path, task_id: str, owner: str,
               lease_minutes: int = 60, now: datetime | None = None) -> dict:
    """认领待办；他人的未过期租约会被拒绝，过期租约可抢占并留痕。"""
    if not owner.strip() or lease_minutes <= 0:
        raise ValueError("owner 不可为空且 lease_minutes 必须为正数")
    now = now or datetime.now().astimezone()
    with shared_lock(common_dir):
        payload = _read_queue(queue_path)
        item = _queue_item(payload, task_id)
        if item.get("status") == "completed":
            raise RuntimeError("任务 %s 已完成，拒绝重新认领" % task_id)
        prior_owner = str(item.get("owner", ""))
        expires_at = _parse_time(item.get("lease_until"))
        active_other = item.get("status") == "claimed" and prior_owner != owner and expires_at and expires_at > now
        if active_other:
            raise RuntimeError("任务 %s 已由 %s 认领至 %s" % (task_id, prior_owner, expires_at.isoformat()))
        takeover = item.get("status") == "claimed" and prior_owner != owner and (not expires_at or expires_at <= now)
        item["status"] = "claimed"
        item["owner"] = owner
        item["lease_until"] = (now + timedelta(minutes=lease_minutes)).isoformat(timespec="seconds")
        if takeover:
            _note(item, "%s 过期后由 %s 抢占" % (prior_owner or "未署名认领", owner))
        _atomic_json_write(queue_path, payload)
        return dict(item)


def release_task(*, common_dir: Path, queue_path: Path, task_id: str, owner: str) -> dict:
    """释放自己持有的任务，保留释放痕迹以便后续接手。"""
    with shared_lock(common_dir):
        payload = _read_queue(queue_path)
        item = _queue_item(payload, task_id)
        if item.get("status") != "claimed" or item.get("owner") != owner:
            raise RuntimeError("任务 %s 不由 %s 持有，拒绝释放" % (task_id, owner))
        item["status"] = "pending"
        item["owner"] = ""
        item["lease_until"] = ""
        _note(item, "%s 已释放认领" % owner)
        _atomic_json_write(queue_path, payload)
        return dict(item)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=False)
    subparsers.add_parser("next", help="领取下一个轮次号")
    for command, help_text in (("claim", "认领队列任务"), ("release", "释放队列任务")):
        sub = subparsers.add_parser(command, help=help_text)
        sub.add_argument("task_id")
        sub.add_argument("--owner", required=True)
        sub.add_argument("--queue", type=Path, default=DEFAULT_QUEUE)
        if command == "claim":
            sub.add_argument("--lease-minutes", type=int, default=60)
    args = parser.parse_args(argv)
    common_dir = git_common_dir()
    if args.command in (None, "next"):
        print(claim_next(common_dir=common_dir, tasks_round=PROGRAM / "tasks_round"))
    elif args.command == "claim":
        item = claim_task(common_dir=common_dir, queue_path=args.queue, task_id=args.task_id,
                          owner=args.owner, lease_minutes=args.lease_minutes)
        print(json.dumps(item, ensure_ascii=False))
    else:
        item = release_task(common_dir=common_dir, queue_path=args.queue, task_id=args.task_id, owner=args.owner)
        print(json.dumps(item, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

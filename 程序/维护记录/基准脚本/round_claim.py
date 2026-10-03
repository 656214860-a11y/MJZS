"""为共享 Git 仓库的并行工作树分配唯一轮次号。"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path


PROGRAM = Path(__file__).resolve().parents[2]
ROOT = PROGRAM.parent
RESULT_RE = re.compile(r"tasks_round_(\d+)_result\.md$")
LOCK_NAME = "round-claim.lock"
COUNTER_NAME = "round-counter.json"


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
                raise TimeoutError("轮次号分配锁被占用：%s" % lock)
            time.sleep(0.05)
            continue
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump({"pid": os.getpid(), "created_at": time.time()}, handle)
        return lock


def claim_next(*, common_dir: Path, tasks_round: Path) -> int:
    """在共享 git common-dir 下原子地领取下一个未使用轮次。"""
    common_dir.mkdir(parents=True, exist_ok=True)
    lock = _acquire_lock(common_dir)
    try:
        counter = common_dir / COUNTER_NAME
        next_round = max(read_counter(counter), latest_result_round(tasks_round)) + 1
        temporary = counter.with_name(counter.name + ".%s.tmp" % os.getpid())
        temporary.write_text(json.dumps({"last_claimed": next_round}, ensure_ascii=False) + "\n",
                             encoding="utf-8")
        os.replace(temporary, counter)
        return next_round
    finally:
        try:
            lock.unlink()
        except FileNotFoundError:
            pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("next",), nargs="?", default="next")
    args = parser.parse_args(argv)
    if args.command == "next":
        print(claim_next(common_dir=git_common_dir(), tasks_round=PROGRAM / "tasks_round"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

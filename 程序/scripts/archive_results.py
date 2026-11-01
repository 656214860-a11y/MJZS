"""把旧的 tasks_round 结果文件按月移进 ``tasks_round/归档/<年-月>/``。

结果文件只增不改，一个月几十份，平铺在一个目录里 ``tasks_round_*_result.md`` 已有上千份。
归档只做 ``git mv``（历史、blame 不断），文件名不变；领号、轮次基线、自检台账都用递归匹配，
归档后看到的最大轮次号不变。月份取该文件首次入库的提交日期，不取文件时间。

用法（程序目录下，默认只预览）::

    python -B scripts/dev.py archive                 # 预览：保留本月和上月，其余归档
    python -B scripts/dev.py archive --keep-months 1 # 只保留本月
    python -B scripts/dev.py archive --apply         # 执行 git mv，随后用 dev.py commit 提交

最新一份结果不归档；没有入库记录的（未提交）文件不动。
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

PROGRAM = Path(__file__).resolve().parents[1]
TASKS_ROUND = PROGRAM / "tasks_round"
ARCHIVE_DIR = "归档"
RESULT_RE = re.compile(r"^tasks_round_(\d+)_result\.md$")
DEFAULT_KEEP_MONTHS = 2


def _git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-c", "core.quotepath=false", *args], cwd=PROGRAM,
                          capture_output=True, text=True, encoding="utf-8", errors="replace")


def first_added_months() -> dict[str, str]:
    """{平铺目录里的结果文件名: 首次入库的 YYYY-MM}，一次 git log 取完。"""
    done = _git("log", "--relative", "--diff-filter=A", "--name-only", "--format=@%as", "--", "tasks_round")
    if done.returncode:
        raise RuntimeError(done.stderr.strip() or "git log 失败")
    months: dict[str, str] = {}
    current = ""
    for line in done.stdout.splitlines():
        if line.startswith("@"):
            current = line[1:8]
        elif line and current:
            parts = Path(line).parts
            if len(parts) == 2 and parts[0] == "tasks_round":
                months[parts[1]] = current  # 日志从新到旧，后写入的是最早入库的那次
    return months


def months_to_keep(today: date, keep_months: int) -> set[str]:
    keep, year, month = set(), today.year, today.month
    for _ in range(max(1, keep_months)):
        keep.add("%04d-%02d" % (year, month))
        year, month = (year, month - 1) if month > 1 else (year - 1, 12)
    return keep


def plan(files: list[str], added: dict[str, str], today: date, keep_months: int) -> dict[str, list[str]]:
    """{月份: [要归档的文件名]}；只含轮次号编号的结果文件，最新一份与保留月份内的不动。"""
    numbered = {name: int(RESULT_RE.fullmatch(name).group(1)) for name in files if RESULT_RE.fullmatch(name)}
    if not numbered:
        return {}
    newest = max(numbered.values())
    keep = months_to_keep(today, keep_months)
    result: dict[str, list[str]] = defaultdict(list)
    for name in sorted(numbered, key=numbered.get):
        month = added.get(name)
        if month is None or month in keep or numbered[name] == newest:
            continue
        result[month].append(name)
    return dict(result)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--keep-months", type=int, default=DEFAULT_KEEP_MONTHS,
                        help="平铺目录保留最近几个月（含本月），默认 %d" % DEFAULT_KEEP_MONTHS)
    parser.add_argument("--apply", action="store_true", help="执行 git mv；不给只预览")
    args = parser.parse_args(argv)

    files = [item.name for item in TASKS_ROUND.iterdir() if item.is_file()]
    moves = plan(files, first_added_months(), date.today(), args.keep_months)
    total = sum(len(names) for names in moves.values())
    print("平铺目录结果文件 %d 份，将归档 %d 份：" % (sum(bool(RESULT_RE.fullmatch(n)) for n in files), total))
    for month in sorted(moves):
        print("  %s  %d 份（R%s–R%s）" % (month, len(moves[month]),
              RESULT_RE.fullmatch(moves[month][0]).group(1), RESULT_RE.fullmatch(moves[month][-1]).group(1)))
    if not args.apply or not total:
        if total:
            print("预览，未移动任何文件；确认后加 --apply。")
        return 0
    for month, names in sorted(moves.items()):
        folder = TASKS_ROUND / ARCHIVE_DIR / month
        folder.mkdir(parents=True, exist_ok=True)
        for start in range(0, len(names), 200):
            batch = names[start:start + 200]
            done = _git("mv", "--", *[str((TASKS_ROUND / name).relative_to(PROGRAM)) for name in batch],
                        str(folder.relative_to(PROGRAM)))
            if done.returncode:
                print("git mv 失败：" + done.stderr.strip(), file=sys.stderr)
                return done.returncode
    print("已移动 %d 份到 tasks_round/%s/<月>/；请用 dev.py commit 提交（暂存区已含移动）。" % (total, ARCHIVE_DIR))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

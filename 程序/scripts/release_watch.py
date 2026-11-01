r"""发布后观察的指标聚合与告警（U12）。只读 ``outputs/desktop-task-history.json``，不写任何文件。

口径取自发布检查单 §3：观察期 ``WINDOW_HOURS`` 小时，样本不足 ``MIN_SAMPLES`` 次不判回滚，
连续失败 ``STREAK`` 次提前告警。失败占比阈值用户尚未裁定：给了 ``--baseline``（上一版同口径失败占比）
就按「超过基线一倍」判，没给只报占比、不下回滚结论。

用法::

    python.exe -B scripts\release_watch.py [--since <起算epoch秒>] [--baseline 0.1]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.dont_write_bytecode = True
PROGRAM = Path(__file__).resolve().parents[1]
HISTORY = PROGRAM / 'outputs' / 'desktop-task-history.json'
WINDOW_HOURS = 24
MIN_SAMPLES = 5
STREAK = 3
FINISHED = ('succeeded', 'failed')


def assess(rows, now=None, since=None, baseline=None) -> dict:
    """纯函数：rows 为执行记录行（含 created／state），返回 {samples, failed, share, alerts, rollback}。"""
    now = time.time() if now is None else now
    start = max(now - WINDOW_HOURS * 3600, since or 0)
    done = sorted((row for row in rows if isinstance(row, dict) and row.get('state') in FINISHED
                   and isinstance(row.get('created'), (int, float)) and start <= row['created'] <= now),
                  key=lambda row: row['created'])
    failed = sum(1 for row in done if row['state'] == 'failed')
    share = failed / len(done) if done else 0.0
    tail = 0
    for row in reversed(done):
        if row['state'] != 'failed':
            break
        tail += 1
    alerts = []
    if tail >= STREAK:
        alerts.append('最近连续失败 %d 次' % tail)
    enough = len(done) >= MIN_SAMPLES
    rollback = bool(enough and baseline is not None and share > baseline * 2)
    if rollback:
        alerts.append('失败占比 %.0f%% 超过基线 %.0f%% 的一倍' % (share * 100, baseline * 100))
    if not enough:
        alerts.append('样本 %d 次，不足 %d 次，暂不判回滚' % (len(done), MIN_SAMPLES))
    return {'samples': len(done), 'failed': failed, 'share': round(share, 3), 'streak': tail,
            'alerts': alerts, 'rollback': rollback}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description='发布后观察指标聚合。')
    parser.add_argument('--since', type=float, default=None)
    parser.add_argument('--baseline', type=float, default=None)
    parser.add_argument('--history', default=str(HISTORY))
    args = parser.parse_args(argv)
    sys.path.insert(0, str(PROGRAM))
    from agent.core import read_json
    data = read_json(args.history, default={})
    rows = data.get('tasks', []) if isinstance(data, dict) else []
    report = assess(rows, since=args.since, baseline=args.baseline)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if report['rollback'] else 0


if __name__ == '__main__':
    raise SystemExit(main())

# -*- coding: utf-8 -*-
"""页级首帧指标汇总（R2979）：把真实使用里的 ``page.paint.*`` 慢操作读成一张表。

数据源两处，都在 ``程序/logs/``（运行数据，不入库）：
- ``app.log``＋``app.log.1``–``.3``：``perf`` logger 的「慢操作 page.paint.<页> <ms>ms」告警行，
  只记超阈值（PAGE_PAINT_WARN_MS=1000ms）的样本，适合看「哪些页在真实使用里卡过」；
- ``perf_metrics.json``：本会话 ``timed``/``record_elapsed`` 的累计（count/total/max/slow），
  进程退出时落盘，只反映最近一次会话。

用法：``python 基准脚本/paint_stats.py [--days N] [--json]``
只读不写；半月性能审计（Devin-Biweekly-Perf-Audit）每期跑一次，把输出贴进审查报告。
"""
import argparse
import json
import re
import sys
from pathlib import Path

PROG = Path(__file__).resolve().parents[2]
LOGS = PROG / 'logs'
SLOW_RE = re.compile(r'慢操作\s+(page\.paint\.[\w.\-]+)\s+([\d.]+)\s*ms')


def log_files():
    files = [LOGS / 'app.log']
    files += [LOGS / ('app.log.%d' % i) for i in (1, 2, 3)]
    return [p for p in files if p.is_file()]


def parse_slow_lines(days=None):
    """返回 {指标名: [毫秒,...]}；days 给定时按行首日期过滤。"""
    rows = {}
    for path in log_files():
        try:
            lines = path.read_text(encoding='utf-8', errors='replace').splitlines()
        except OSError:
            continue
        for line in lines:
            match = SLOW_RE.search(line)
            if not match:
                continue
            if days:
                stamp = line[:10]
                # 只粗判日期形态；解析失败的行不丢（宁可多收）。
                try:
                    from datetime import date, timedelta
                    cutoff = (date.today() - timedelta(days=days)).isoformat()
                    if stamp < cutoff:
                        continue
                except Exception:
                    pass
            rows.setdefault(match.group(1), []).append(float(match.group(2)))
    return rows


def metrics_file():
    path = LOGS / 'perf_metrics.json'
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def summarize():
    slow = parse_slow_lines()
    per_page = {}
    for name, values in slow.items():
        ordered = sorted(values)
        per_page[name] = {
            'slow_count': len(values),
            'avg_ms': round(sum(values) / len(values), 1),
            'max_ms': max(values),
            'p50_ms': ordered[len(ordered) // 2],
        }
    session = {}
    counters = {}
    data = metrics_file()
    for name, row in (data.get('metrics') or {}).items():
        if not isinstance(row, dict):
            continue
        session[name] = {k: row.get(k) for k in ('count', 'total_ms', 'max_ms', 'slow')}
    for name, value in (data.get('counters') or {}).items():
        if isinstance(value, (int, float)):
            counters[name] = value
    return {'slow_operations': per_page, 'session_metrics': session, 'counters': counters}


def main():
    parser = argparse.ArgumentParser(description='页级首帧慢操作汇总')
    parser.add_argument('--days', type=int, default=None, help='只统计最近 N 天的告警行')
    parser.add_argument('--json', action='store_true', help='输出 JSON')
    args = parser.parse_args()
    if args.days:
        # --days 走独立分支：parse_slow_lines 已支持过滤，这里重算一次即可。
        rows = parse_slow_lines(days=args.days)
        per_page = {name: {'slow_count': len(v), 'avg_ms': round(sum(v) / len(v), 1),
                           'max_ms': max(v), 'p50_ms': sorted(v)[len(v) // 2]}
                    for name, v in rows.items()}
        report = {'slow_operations': per_page, 'session_metrics': {}}
    else:
        report = summarize()
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=1))
        return 0
    pages = report['slow_operations']
    if not pages:
        print('没有 page.paint.* 超阈记录（logs/app.log* 与 perf_metrics.json 均无命中）。')
    else:
        print('%-28s %8s %10s %10s %10s' % ('指标', '超阈次数', '均值ms', 'P50ms', '最大ms'))
        for name in sorted(pages, key=lambda k: -pages[k]['slow_count']):
            row = pages[name]
            print('%-28s %8d %10.1f %10.1f %10.1f' % (
                name, row['slow_count'], row['avg_ms'], row['p50_ms'], row['max_ms']))
    session = report['session_metrics']
    paints = {k: v for k, v in session.items() if k.startswith('page.paint')}
    if paints:
        print('\n本会话累计（perf_metrics.json）：')
        for name in sorted(paints):
            row = paints[name]
            print('  %-28s 次数=%s 总耗时=%sms 最大=%sms 超阈=%s' % (
                name, row.get('count'),
                round(row.get('total_ms') or 0, 1), row.get('max_ms'), row.get('slow')))
    # R2990：首帧分解——fitwaits 是「等 _fit_pending 的 16ms 轮询数」，fitpasses 是窗内
    # 实际跑完的整页布局轮次；两者除以 paint 样本数得每次首帧均值，定性布局收敛成本。
    counters = report.get('counters') or {}
    if counters:
        pages = sorted({k.rsplit('.', 1)[0] for k in counters
                        if k.startswith('page.paint.') and k.rsplit('.', 1)[1] in ('fitwaits', 'fitpasses')})
        if pages:
            print('\n首帧分解（本会话均值/次；R2990 起记录）：')
            print('  %-28s %12s %14s' % ('页', '布局等待ms', '布局轮次'))
            for base in pages:
                count_row = session.get(base) or {}
                n = count_row.get('count') or 0
                if not n:
                    continue
                waits_ms = (counters.get(base + '.fitwaits') or 0) * 16 / n
                passes = (counters.get(base + '.fitpasses') or 0) / n
                print('  %-28s %12.0f %14.1f' % (base, waits_ms, passes))
    return 0


if __name__ == '__main__':
    sys.exit(main())

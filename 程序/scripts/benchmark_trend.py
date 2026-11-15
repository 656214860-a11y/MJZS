# -*- coding: utf-8 -*-
"""T8.3 基准趋势告警：对比全量绿凭据与启动耗时历史的最近样本与历史中位，回退超阈值只告警不阻断。

数据源：
- 全量耗时：Git common-dir 的 ``full-safe-receipts.json``（唯一权威凭据）。
- 启动耗时：Git common-dir 的 ``startup-perf-history.jsonl``（各工作树桌面启动性能用例
  追加的同机实测秒数；与凭据同处 common-dir，跨工作树共享，避免 .gitignore 的本机诊断文件
  在干净检出里没有历史可比）。

用法：python -B scripts/benchmark_trend.py  → 恒退 0（告警写 stdout）。
"""
import json
import re
import sys
from datetime import datetime
from pathlib import Path

PROGRAM = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROGRAM))

REGRESSION_RATIO = 1.25   # 最近一次比历史中位慢 25% 即告警
BASELINE_COUNT = 5        # 基线取最近 5 次绿全量的中位
STARTUP_HISTORY_NAME = 'startup-perf-history.jsonl'
STARTUP_HISTORY_KEEP = 60  # 追加式历史只留最近 60 条，防文件无限增长


def _median(values):
    ordered = sorted(values)
    mid = len(ordered) // 2
    return ordered[mid] if len(ordered) % 2 else (ordered[mid - 1] + ordered[mid]) / 2


def load_receipts(document):
    """从凭据文档取按时间排序的绿全量秒数序列。"""
    trees = document.get('full_safe_verified_trees') if isinstance(document, dict) else []
    rows = [r for r in trees if isinstance(r, dict) and isinstance(r.get('seconds'), (int, float))]
    rows.sort(key=lambda r: str(r.get('at', '')))
    return rows


def trend_report(rows):
    """返回 (告警清单, 摘要行)。rows 为 load_receipts 的输出。"""
    if len(rows) < 2:
        return [], "绿全量样本 %d 次，不足以比较（需 ≥2）。" % len(rows)
    baseline_rows = rows[-(BASELINE_COUNT + 1):-1]
    baseline = _median([r['seconds'] for r in baseline_rows])
    latest = rows[-1]
    ratio = latest['seconds'] / baseline if baseline else 0.0
    summary = "最近一次绿全量 %.0f 秒（R%s，%s）；近 %d 次中位 %.0f 秒；比值 %.2f。" % (
        latest['seconds'], latest.get('round', '?'), latest.get('at', '?'),
        len(baseline_rows), baseline, ratio)
    if ratio > REGRESSION_RATIO:
        return ["全量耗时回退：%.0f 秒 > 中位 %.0f 秒 × %.2f（阈值 %.2f）" % (
            latest['seconds'], baseline, ratio, REGRESSION_RATIO)], summary
    return [], summary


def _git_common_dir():
    try:
        import selftest_env as env
        return env.git_common_dir()
    except Exception:
        return ''


def startup_history_path(common_dir=None):
    """启动耗时历史的唯一归档：Git common-dir 下的 JSONL；拿不到 common-dir 返回 None。"""
    common = common_dir if common_dir is not None else _git_common_dir()
    if not common:
        return None
    return Path(common) / STARTUP_HISTORY_NAME


def _current_round():
    """台账当前轮次（与 benchmark_history.current_round 同口径），读不到记 None。"""
    try:
        matched = re.search(r'当前轮次：(\d+)',
                            (PROGRAM / 'project_status.md').read_text(encoding='utf-8'))
        return int(matched.group(1)) if matched else None
    except (OSError, ValueError):
        return None


def _cap_startup_history(path):
    """历史只留最近 KEEP 条：整文件重写比逐条插入简单，60 行以内成本可忽略。"""
    try:
        lines = path.read_text(encoding='utf-8').splitlines()
    except OSError:
        return
    if len(lines) <= STARTUP_HISTORY_KEEP:
        return
    import line_endings
    line_endings.write_text(path, '\n'.join(lines[-STARTUP_HISTORY_KEEP:]) + '\n')


def record_startup_perf(seconds, branch, *, common_dir=None):
    """追加一条启动实测：branch 区分首日／同日／空项目等启动分支，趋势只同分支互比。

    写失败只提示不阻断——性能记录是尽力归档，不是正确性门禁。返回历史文件路径，写不了返回 ''。
    """
    try:
        value = float(seconds)
    except (TypeError, ValueError):
        return ''
    if not branch or value != value or value in (float('inf'), float('-inf')):
        return ''
    path = startup_history_path(common_dir)
    if path is None:
        return ''
    record = {'at': datetime.now().isoformat(timespec='seconds'), 'round': _current_round(),
              'branch': str(branch), 'seconds': round(value, 3)}
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('a', encoding='utf-8', newline='') as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + '\n')
        _cap_startup_history(path)
    except (OSError, ValueError) as exc:
        print('启动耗时历史写不出来（不影响结果）：' + str(exc))
        return ''
    return str(path)


def load_startup_rows(common_dir=None):
    """读启动耗时历史：坏行跳过，按 at 排序；文件不存在视为无样本。"""
    path = startup_history_path(common_dir)
    if path is None or not path.is_file():
        return []
    rows = []
    try:
        lines = path.read_text(encoding='utf-8').splitlines()
    except OSError:
        return []
    for line in lines:
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict) and isinstance(row.get('seconds'), (int, float)) \
                and isinstance(row.get('branch'), str) and row['branch']:
            rows.append(row)
    rows.sort(key=lambda r: str(r.get('at', '')))
    return rows


def startup_trend_report(rows):
    """启动耗时趋势：只同 branch（首日／同日／空项目）互比，阈值与全量同为中位 ×1.25。

    返回 (告警清单, 摘要行)；样本不足的分支如实写进摘要，不静默。
    """
    by_branch = {}
    for row in rows:
        by_branch.setdefault(row.get('branch') or 'unknown', []).append(row)
    alerts, summaries = [], []
    for branch in sorted(by_branch):
        series = sorted(by_branch[branch], key=lambda r: str(r.get('at', '')))
        if len(series) < 2:
            summaries.append('%s 样本 %d 次不足' % (branch, len(series)))
            continue
        baseline_rows = series[-(BASELINE_COUNT + 1):-1]
        baseline = _median([r['seconds'] for r in baseline_rows])
        latest = series[-1]
        ratio = latest['seconds'] / baseline if baseline else 0.0
        summaries.append('%s 最近 %.2f 秒 vs 近 %d 次中位 %.2f 秒（比值 %.2f）'
                         % (branch, latest['seconds'], len(baseline_rows), baseline, ratio))
        if baseline and ratio > REGRESSION_RATIO:
            alerts.append('启动耗时回退（%s）：%.2f 秒 > 中位 %.2f 秒 × %.2f（阈值 %.2f）' % (
                branch, latest['seconds'], baseline, ratio, REGRESSION_RATIO))
    if not summaries:
        return [], '无启动耗时样本。'
    return alerts, '；'.join(summaries) + '。'


def main(argv=None):
    try:
        import file_cache
        common = _git_common_dir()
        receipts = Path(common) / 'full-safe-receipts.json' if common else None
        document = file_cache.read_json(receipts) if receipts and receipts.exists() else None
    except Exception:
        document = None
    if not document:
        print("[CI] 基准趋势：无全量绿凭据，跳过。")
    else:
        alerts, summary = trend_report(load_receipts(document))
        print("[CI] 基准趋势：%s" % summary)
        for line in alerts:
            print("【警告】%s（告警级，不阻断合并）" % line)
    startup_alerts, startup_summary = startup_trend_report(load_startup_rows())
    print("[CI] 启动基准趋势：%s" % startup_summary)
    for line in startup_alerts:
        print("【警告】%s（告警级，不阻断合并）" % line)
    return 0


if __name__ == "__main__":
    sys.exit(main())

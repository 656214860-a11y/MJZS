# -*- coding: utf-8 -*-
"""T8.3 基准趋势告警：对比全量绿凭据的最近耗时与历史中位，回退超阈值只告警不阻断。

数据源：Git common-dir 的 ``full-safe-receipts.json``（唯一权威凭据）。
用法：python -B scripts/benchmark_trend.py  → 恒退 0（告警写 stdout）。
"""
import json
import sys
from pathlib import Path

PROGRAM = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROGRAM))

REGRESSION_RATIO = 1.25   # 最近一次比历史中位慢 25% 即告警
BASELINE_COUNT = 5        # 基线取最近 5 次绿全量的中位


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


def main(argv=None):
    try:
        import selftest_env as env
        receipts = Path(env.git_common_dir()) / 'full-safe-receipts.json'
    except Exception:
        receipts = None
    if not receipts or not receipts.exists():
        print("[CI] 基准趋势：无全量绿凭据，跳过。")
        return 0
    document = json.loads(receipts.read_text(encoding='utf-8'))
    alerts, summary = trend_report(load_receipts(document))
    print("[CI] 基准趋势：%s" % summary)
    for line in alerts:
        print("【警告】%s（告警级，不阻断合并）" % line)
    return 0


if __name__ == "__main__":
    sys.exit(main())

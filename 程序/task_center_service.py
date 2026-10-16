"""运行状况汇总（无 Tk）：把分散在各处的运行事实整理成一份可读快照。

只读已有来源，不另建台账：``BackgroundTaskLifecycle`` 的最近任务状态、``app_logging`` 的计时／
计数／最近被忽略的异常、``diagnostic_capture`` 的已降级异常记录。读取失败的来源跳过。
"""
from __future__ import annotations

import app_logging

STATE_TEXT = {'running': '进行中', 'succeeded': '成功', 'failed': '失败', 'cancelled': '已取消'}


def snapshot(lifecycle=None, degradations=None, queue=None, retry=None) -> dict:
    """``lifecycle`` 为 BackgroundTaskLifecycle；``degradations`` 为降级记录列表（调用方注入）。"""
    last = getattr(lifecycle, '_last', None) if lifecycle is not None else None
    history = list(lifecycle.history()) if hasattr(lifecycle, 'history') else []
    if hasattr(retry, 'tickets'):
        for row in history:
            row['retryable'] = row.get('ticket') in retry.tickets()
    metrics = app_logging.metrics_snapshot()
    counters = metrics.pop('counters', {})
    return {
        'last_task': dict(last) if isinstance(last, dict) else None,
        'queued': list(queue.labels()) if hasattr(queue, 'labels') else [],
        'unresolved_queue': list(queue.unresolved()) if hasattr(queue, 'unresolved') else [],
        'task_history': history,
        'retry_ticket': retry.latest_failed_ticket(history) if hasattr(retry, 'latest_failed_ticket') else None,
        'timings': metrics,
        'counters': counters,
        'swallowed': app_logging.recent_swallowed(),
        'degradations': list(degradations or [])[-10:],
    }


def format_lines(data: dict) -> list:
    lines = ['【最近一次主动任务】']
    task = data.get('last_task')
    lines.append('  暂无' if not task else '  #%s %s' % (task.get('ticket'), STATE_TEXT.get(task.get('state'), task.get('state'))))
    lines.append('【排队中（前一项结束后依次执行）】')
    lines += ['  %d. %s' % (n, name or '（无名称）') for n, name in enumerate(data.get('queued', []), 1)] or ['  无']
    if data.get('unresolved_queue'):
        lines.append('【已领取、尚无完成记录（运行中或需核对，不自动重提）】')
        lines += ['  %s %s' % (row['id'], row['label']) for row in data['unresolved_queue']]
    lines.append('【最近完成的主动任务（最新在后，最多 20 条）】')
    for row in data.get('task_history', []):
        lines.append('  #%s %s %s%s' % (row.get('ticket'), STATE_TEXT.get(row.get('state'), row.get('state')),
                                       row.get('label') or '（无名称）',
                                       '' if row.get('elapsed_s') is None else '，%.1f 秒' % row['elapsed_s']))
        if row.get('error'):
            lines.append('      原因：' + row['error'] + ('（可重试）' if row.get('retryable') else ''))
    if not data.get('task_history'):
        lines.append('  暂无')
    lines.append('')
    lines.append('【模型调用结果（本次启动以来）】')
    counters = {k: v for k, v in data.get('counters', {}).items() if k.startswith('model.http.')}
    lines += ['  %s：%s 次' % (k.rsplit('.', 1)[-1], v) for k, v in sorted(counters.items())] or ['  暂无调用']
    lines.append('')
    lines.append('【耗时统计（次数／平均／最大／超阈值次数）】')
    rows = data.get('timings', {})
    for name in sorted(rows):
        row = rows[name]
        average = row['total_ms'] / row['count'] if row.get('count') else 0
        lines.append('  %s：%d 次，平均 %.0fms，最大 %.0fms，慢 %d 次' % (name, row['count'], average, row['max_ms'], row['slow']))
    if not rows:
        lines.append('  暂无记录')
    lines.append('')
    lines.append('【最近被忽略的异常】')
    lines += ['  ' + item for item in data.get('swallowed', [])] or ['  无']
    lines.append('')
    lines.append('【最近已降级的错误】')
    for row in data.get('degradations', []):
        lines.append('  %s %s %s：%s' % (row.get('at', ''), row.get('page', ''), row.get('exception', ''), row.get('message', '')))
    if not data.get('degradations'):
        lines.append('  无')
    return lines

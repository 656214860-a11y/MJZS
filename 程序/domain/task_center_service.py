"""运行状况汇总（无 Tk）：把分散在各处的运行事实整理成一份可读快照。

只读已有来源，不另建台账：``BackgroundTaskLifecycle`` 的最近任务状态、``app_logging`` 的计时／
计数／最近被忽略的异常、``diagnostic_capture`` 的已降级异常记录。读取失败的来源跳过。
"""
from __future__ import annotations

import app_logging

STATE_TEXT = {'running': '进行中', 'succeeded': '成功', 'failed': '失败', 'cancelled': '已取消'}


def project_snapshot(project, *, stage_records=None, gates=None, task_id=None) -> dict:
    """只读投影原始台账；历史记录缺失运行关联时保持未知，不按时间猜测。"""
    from pathlib import Path
    from agent.core import read, fingerprint
    root = Path(project).resolve()
    result = {'project_id': None, 'tasks': [], 'stages': [], 'errors': []}

    def source(path):
        path = Path(path).resolve()
        if not path.is_relative_to(root):
            result['errors'].append('台账引用越出项目范围，未读取')
            return {}
        if not path.is_file():
            return {}
        try:
            data = read(path)
            if not isinstance(data, dict):
                raise ValueError('顶层不是对象')
            return data
        except (OSError, ValueError) as exc:
            result['errors'].append(path.relative_to(root).as_posix() + '：读取失败（' + type(exc).__name__ + '）')
            return {}

    config = source(root/'config.json')
    project_id = str(config.get('project_id') or 'legacy-path:' + fingerprint(str(root))[:24])
    result['project_id'] = project_id

    from pet_llm import request_ledger_path
    cost_rows = source(request_ledger_path(root)).get('entries', [])
    if not isinstance(cost_rows, list) or any(not isinstance(row, dict) for row in cost_rows):
        result['errors'].append('费用台账格式错误')
        cost_rows = []
    costs = {row.get('id'): row for row in cost_rows}

    def add(stage, task, record, authority, receipt=None):
        if task_id is not None and str(task) != str(task_id):
            return
        receipt = receipt or {}
        state = str(record.get('state') or 'unknown')
        normalized = {'imported': 'recorded_ready', 'downloaded': 'recorded_ready', 'failed': 'failed',
                      'rejected': 'rejected'}.get(state, 'reconcile')
        trace = record.get('execution') if isinstance(record.get('execution'), dict) else {}
        remote = record.get('task_id') or receipt.get('prompt_id') or receipt.get('task_id')
        attempt = trace.get('attempt_id') or record.get('local_request') or (
            'legacy:' + fingerprint([authority, task, record.get('version'), record.get('record')])[:24])
        result['tasks'].append({'project_id': project_id, 'run_id': trace.get('run_id'),
            'task_id': str(task), 'attempt_id': str(attempt), 'stage': stage,
            'state': normalized, 'source_state': state, 'authority': authority,
            'remote_task_id': str(remote) if remote else None, 'version': record.get('version'),
            'artifact': record.get('file') or record.get('output_dir') or receipt.get('files'),
            'receipt': record.get('record'),
            'timings_s': attempt_timings(record),
            'reason_code': record.get('error_code') or state,
            'retry_reason': record.get('retry_reason') or '历史未登记',
            'cost': attempt_cost(costs.get(record.get('money_request_id'), {})),
            'reason': app_logging.redact(str(record.get('error') or record.get('note') or ''))[:300],
            'recovery': ('资产管理：接续取回；无编号时先核实提交' if stage == 'assets'
                         else '视频生成：查询任务／恢复任务编号；未知状态不重提')})

    ledger = root/'workflows/资产批量记录.json'
    for aid, job in source(ledger).items():
        if not isinstance(job, dict):
            result['errors'].append('资产记录格式错误：' + str(aid))
            continue
        receipt = source(root/str(job['record'])) if job.get('record') else {}
        add('assets', aid, job, ledger.relative_to(root).as_posix(), receipt)
    state_files = [root/'data/state.json', *sorted((root/'cloud_video').glob('*/data/state.json'))]
    for path in state_files:
        shots = source(path).get('shots', {})
        if not isinstance(shots, dict):
            result['errors'].append('视频镜头台账格式错误：' + path.relative_to(root).as_posix())
            continue
        for sid, versions in shots.items():
            if not isinstance(versions, list):
                result['errors'].append('视频版本列表格式错误：' + str(sid))
                continue
            for version in versions:
                if isinstance(version, dict):
                    add('video', sid, version, path.relative_to(root).as_posix())
                else:
                    result['errors'].append('视频版本记录格式错误：' + str(sid))
    from contract.pet_bus import STAGES
    for stage in STAGES:
        saved = (stage_records or {}).get(stage, {})
        saved = saved if isinstance(saved, dict) else {}
        gate = (gates or {}).get(stage, {})
        result['stages'].append({'stage': stage, 'recorded_state': saved.get('state', 'unknown'),
            'blocked': not gate.get('ok', False), 'waiting_for': gate.get('from', ''),
            'reason': app_logging.redact(str(gate.get('detail') or saved.get('reason') or '未取得当前门禁证据'))[:400],
            'authority': '阶段事件快照＋当前生产门禁；历史成功不代替当前成果核验'})
    return result


def attempt_timings(record):
    """仅相减已有时间戳；轮询看到的排队/运行耗时不是供应商精确耗时。"""
    import math
    pairs = {'submission': ('created', 'submitted_at'),
             'queue_observed': ('submitted_at', 'running_observed_at'),
             'run_observed': ('running_observed_at', 'succeeded_observed_at'),
             'download': ('download_started_at', 'download_completed_at'),
             'publication': ('download_completed_at', 'finished_at')}
    out = {}
    for name, (start, end) in pairs.items():
        a, b = record.get(start), record.get(end)
        valid = all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) for v in (a, b))
        out[name] = round(b-a, 3) if valid and b >= a else None
    return out


def attempt_cost(row):
    from decimal import Decimal, InvalidOperation
    from pet_llm import RequestLedger
    state = RequestLedger.effective_money_state(row)
    estimate = row.get('budget_cost') if state in ('estimated', 'reserved') else None
    actual = row.get('budget_cost') if state == 'reconciled' else None
    history = row.get('cost_reconciliations') or []
    if history and isinstance(history, list) and isinstance(history[0], dict):
        first = history[0]
        if first.get('previous_money_state') == 'estimated' and first.get('currency') == row.get('currency'):
            estimate = first.get('previous_amount')
    difference = None
    try:
        if actual is not None and estimate is not None:
            delta = Decimal(str(actual)) - Decimal(str(estimate))
            difference = str(delta) if delta.is_finite() else None
    except (InvalidOperation, ValueError):
        difference = None
    return {'request_id': row.get('id'), 'currency': row.get('currency'),
            'state': state or 'unknown', 'estimate': estimate, 'actual': actual, 'difference': difference}


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
        'unresolved_execution': lifecycle.unresolved_records() if hasattr(lifecycle, 'unresolved_records') else [],
        'task_history': history,
        'retry_ticket': retry.latest_failed_ticket(history) if hasattr(retry, 'latest_failed_ticket') else None,
        'timings': metrics,
        'counters': counters,
        'swallowed': app_logging.recent_swallowed(),
        'degradations': list(degradations or [])[-10:],
    }


def format_lines(data: dict) -> list:
    lines = ['【最近一次主动任务】']
    runtime = data.get('project_runtime')
    if runtime:
        lines += ['【当前项目恢复查询】', '  项目：' + runtime['project_id']]
        for row in runtime.get('stages', []):
            lines.append('  %s：历史 %s；%s' % (row['stage'], row['recorded_state'], row['reason']))
        for row in runtime['tasks']:
            lines.append('  %s %s / %s：%s（原状态 %s）；远端 %s；运行 %s' % (
                row['stage'], row['task_id'], row['attempt_id'], row['state'], row['source_state'],
                row['remote_task_id'] or '未登记', row['run_id'] or '历史未登记'))
            timings = row.get('timings_s') or {}
            labels = {'submission': '提交', 'queue_observed': '排队（观察）',
                      'run_observed': '运行（观察）', 'download': '下载', 'publication': '发布'}
            duration = '；'.join(label + '：' + ('未知' if timings.get(key) is None else str(timings[key]) + '秒')
                                 for key, label in labels.items())
            lines.append('    原因码：%s；新尝试原因：%s；%s' % (
                row.get('reason_code'), row.get('retry_reason'), duration))
            lines.append('    失败说明：%s' % (row.get('reason') or '未登记'))
            cost = row.get('cost') or {}
            values = [('未知' if cost.get(key) is None else str(cost[key])) for key in ('estimate', 'actual', 'difference')]
            lines.append('    费用：估算 %s；已核对 %s；差额 %s；币种 %s' % (
                *values, cost.get('currency') or '未知'))
            lines.append('    来源：%s；台账成果引用（未重新验收）：%s；%s' % (row['authority'], row['artifact'] or '未登记', row['recovery']))
        lines += ['  ' + error for error in runtime['errors']]
    task = data.get('last_task')
    lines.append('  暂无' if not task else '  #%s %s' % (task.get('ticket'), STATE_TEXT.get(task.get('state'), task.get('state'))))
    lines.append('【排队中（前一项结束后依次执行）】')
    lines += ['  %d. %s' % (n, name or '（无名称）') for n, name in enumerate(data.get('queued', []), 1)] or ['  无']
    if data.get('unresolved_queue'):
        lines.append('【已领取、尚无完成记录（运行中或需核对，不自动重提）】')
        lines += ['  %s %s' % (row['id'], row['label']) for row in data['unresolved_queue']]
    if data.get('unresolved_execution'):
        lines += ['', '执行记录（运行中或需对账，取消不代表远端停止）：']
        lines += ['  %s %s：%s；运行 %s；远端编号 %s' % (row['id'], row.get('label', ''),
                  row.get('state', 'unknown'), row.get('run_id') or '历史未登记', ', '.join(
                      remote.get('provider', '')+':'+remote['id'] for remote in row.get('remote_tasks', []))
                  or row.get('remote_task_id') or '未登记')
                  for row in data['unresolved_execution']]
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

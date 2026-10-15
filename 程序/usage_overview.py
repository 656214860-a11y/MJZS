# -*- coding: utf-8 -*-
"""项目用量总览：只读汇总已落盘的模型调用事件（`model_diagnostics/*.json`）与请求台账。

数据来源都是现成的：每次模型调用已写一条脱敏事件（模型、阶段、token 用量、成败）。
本模块不新增写入路径、不改调用流程；事件里没有用量字段的调用记为「用量未知」，
绝不当作 0。token／次数各列各的，不折算金额（金额只在配了价格表时由台账折算）。
"""
from __future__ import annotations

from pathlib import Path

import pet_llm
from file_cache import read_json

_KEYS = ('prompt_tokens', 'completion_tokens', 'cached_tokens', 'total_tokens')


def event_folders(project):
    root = Path(project)
    folders = [root / 'model_diagnostics']
    logs = root / 'logs'
    if logs.is_dir():
        folders.append(logs / 'model_diagnostics')
        folders.extend(sorted(path for path in logs.rglob('model_diagnostics') if path.is_dir()
                              and path != logs / 'model_diagnostics'))
    seen, out = set(), []
    for folder in folders:
        if folder.is_dir() and folder not in seen:
            seen.add(folder)
            out.append(folder)
    return out


def read_events(project):
    """逐条读取事件；损坏或不是对象的文件跳过并计数。返回 (事件列表, 跳过数)。"""
    events, skipped = [], 0
    for folder in event_folders(project):
        for path in sorted(folder.glob('*.json')):
            try:
                value = read_json(path)
            except (OSError, ValueError):
                skipped += 1
                continue
            if isinstance(value, dict):
                events.append(value)
            else:
                skipped += 1
    return events, skipped


def _blank():
    return {'calls': 0, 'ok': 0, 'failed': 0, 'unknown_usage': 0,
            'prompt_tokens': 0, 'completion_tokens': 0, 'cached_tokens': 0, 'total_tokens': 0}


def _number(value):
    import math
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0 else None


def cost_per_minute(project, duration_seconds, price_table, overheads=None):
    """按已录入用量及费率估算，费用缺项单列，绝不补零。非供应商对账账单。"""
    duration = _number(duration_seconds)
    if not duration:
        raise ValueError('每分钟成本需要有限且大于零的实际成片秒数')
    report = pet_llm.RequestLedger(project).load().report(price_table)
    money = report.get('money')
    overheads = overheads if isinstance(overheads, dict) else {}
    known = money['settled_amount'] if money else 0
    missing = []
    for key in ('gpu', 'storage', 'bandwidth', 'human'):
        amount = _number(overheads.get(key))
        if amount is None: missing.append(key)
        else: known += amount
    complete = bool(report['requests'] and money and money['complete'] and not missing)
    return {'known_amount': round(known, 4), 'known_per_minute': round(known * 60 / duration, 4),
            'total_per_minute': round(known * 60 / duration, 4) if complete else None,
            'complete': complete, 'missing_overheads': missing, 'requests': report,
            'duration_seconds': duration, 'currency': money['currency'] if money else None,
            'basis': 'recorded_usage_estimate_not_supplier_invoice'}


def _add(bucket, event):
    bucket['calls'] += 1
    bucket['ok' if event.get('ok') else 'failed'] += 1
    usage = event.get('usage') if isinstance(event.get('usage'), dict) else {}
    values = {key: _number(usage.get(key)) for key in _KEYS}
    if all(value is None for value in values.values()):
        bucket['unknown_usage'] += 1
        return
    for key in ('prompt_tokens', 'completion_tokens', 'cached_tokens'):
        bucket[key] += values[key] or 0
    total = values['total_tokens']
    if total is None:
        total = (values['prompt_tokens'] or 0) + (values['completion_tokens'] or 0)
    bucket['total_tokens'] += total


def summarize(project, budget=None):
    """汇总一个项目：总计、按模型、按阶段、按天；budget 为调用方传入的预算快照（可空）。"""
    events, skipped = read_events(project)
    total, by_model, by_stage, by_day = _blank(), {}, {}, {}
    for event in events:
        context = event.get('context') if isinstance(event.get('context'), dict) else {}
        keys = ((by_model, str(event.get('model') or '未知模型')),
                (by_stage, str(context.get('stage') or '未标阶段')),
                (by_day, str(event.get('at') or '')[:10] or '未知日期'))
        _add(total, event)
        for table, key in keys:
            _add(table.setdefault(key, _blank()), event)
    try:
        ledger_report = pet_llm.RequestLedger(project).load().report()
    except (OSError, ValueError, TypeError):
        ledger_report = None
    if ledger_report is not None and not ledger_report.get('requests'):
        ledger_report = None
    result = {'total': total, 'by_model': by_model, 'by_stage': by_stage, 'by_day': dict(sorted(by_day.items())),
              'skipped_files': skipped, 'budget': budget, 'requests': ledger_report}
    profile = Path(project) / 'cost_profile.json'
    if profile.is_file():
        try:
            config = read_json(profile)
            result['cost'] = cost_per_minute(project, config['duration_seconds'], config['price_table'], config.get('overheads'))
        except (OSError, ValueError, TypeError, KeyError) as error:
            result['cost_error'] = '成本配置无法核算：' + str(error)
    return result


def _line(name, bucket):
    text = '%s：%d 次（成功 %d／失败 %d），token %d（输入 %d／输出 %d／缓存命中 %d）' % (
        name, bucket['calls'], bucket['ok'], bucket['failed'], bucket['total_tokens'],
        bucket['prompt_tokens'], bucket['completion_tokens'], bucket['cached_tokens'])
    if bucket['unknown_usage']:
        text += '；另有 %d 次未上报用量（不计为 0）' % bucket['unknown_usage']
    return text


def report_text(summary):
    total = summary['total']
    if not total['calls'] and not any(summary.get(key) for key in ('requests', 'budget', 'cost', 'cost_error')):
        return '本项目还没有可汇总的模型调用记录。'
    lines = ['模型调用总览', _line('合计', total), '']
    for title, key in (('按模型', 'by_model'), ('按阶段', 'by_stage'), ('按天', 'by_day')):
        if summary[key]:
            lines.append(title)
            lines.extend('  ' + _line(name, bucket) for name, bucket in summary[key].items())
            lines.append('')
    budget = summary.get('budget')
    if isinstance(budget, dict) and budget:
        lines.append('预算（已用／额度）')
        for row in budget.values():
            lines.append('  %s：%s／%s' % (row.get('label'), row.get('used'), row.get('limit')))
        lines.append('')
    ledger_report = summary.get('requests')
    if ledger_report:
        lines.append('请求台账（视频秒数、生图、次数等，各列各的）')
        for kind, bucket in ledger_report['kinds'].items():
            if bucket.get('count'):
                lines.append('  %s：已结算 %g，预留 %g，未知 %d 笔，共 %d 笔' % (
                    kind, bucket['settled'], bucket['reserved'], bucket['unknown'], bucket['count']))
        lines.append('')
    if summary.get('skipped_files'):
        lines.append('有 %d 个事件文件损坏或格式不对，已跳过。' % summary['skipped_files'])
    if summary.get('cost_error'):lines.append(summary['cost_error'])
    if summary.get('cost'):
        cost = summary['cost']
        lines.append('已录入部分成本：%g %s／分钟；%s' % (cost['known_per_minute'], cost['currency'] or '币种未配置',
            '录入项齐全' if cost['complete'] else '总成本未知，仍有未知用量、预留或缺项'))
        lines.append('按录入用量和费率估算，尚非供应商对账结果；外部费用缺项：' + '、'.join(cost['missing_overheads']))
    lines.append('说明：只统计已落盘的调用事件；金额需配价格表后由请求台账折算，这里不估算。')
    return '\n'.join(lines).strip()

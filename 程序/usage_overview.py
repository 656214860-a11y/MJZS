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


def delivery_duration(project, selected):
    """从已确认且内容未变的交付记录取片长；每份采用分镜只计一个导出。"""
    from agent.core import file_hash, fingerprint
    from stage_path_service import read_dirs, write_dir
    from storyboard_adoption_contract import adopted
    root = Path(project).resolve()
    if not isinstance(selected, list) or not selected or any(not isinstance(p, str) or not p for p in selected):
        raise ValueError('delivery_outputs 需要非空交付文件路径列表')
    targets = [(root / p).resolve() for p in selected]
    folder = write_dir(root, 'delivery').resolve()
    folders = [p.resolve() for p in read_dirs(root, 'delivery')]
    if len(set(targets)) != len(targets) or any(not any(p.is_relative_to(f) for f in folders) for p in targets):
        raise ValueError('交付成本文件重复或不在本项目交付目录')
    found, sources = {}, set()
    for source in adopted(root):
        source = Path(source).resolve()
        relative = source.relative_to(root).as_posix()
        manifest = folder / '成果确认' / (fingerprint(relative)[:24] + '.json')
        if not manifest.is_file():
            continue
        data = read_json(manifest)
        if not isinstance(data, dict) or not isinstance(data.get('outputs'), list):
            raise ValueError('交付确认格式错误')
        for output in data['outputs']:
            if not isinstance(output, dict) or not isinstance(output.get('path'), str):
                raise ValueError('交付文件记录格式错误')
            path = (root / output['path']).resolve()
            if path not in targets:
                continue
            scope = data.get('scope') or {}
            validation = output.get('validation') or {}
            if not isinstance(scope, dict) or not isinstance(validation, dict):
                raise ValueError('交付确认范围或探测结果格式错误')
            duration = _number(validation.get('duration'))
            if (data.get('schema') != 1 or data.get('stage') != 'delivery'
                    or data.get('status') != 'complete' or data.get('reviewed') is not True
                    or scope.get('project') != str(root) or scope.get('source') != relative
                    or scope.get('source_sha256') != file_hash(source)
                    or validation.get('kind') != 'video' or validation.get('passed') is not True or not duration
                    or not path.is_file() or path.stat().st_size != output.get('size')
                    or file_hash(path) != output.get('sha256')):
                raise ValueError('交付文件或分镜已变化，或尚未确认，请重新校验交付成果')
            if source in sources or path in found:
                raise ValueError('同一集的多个导出不能重复计入成片时长')
            sources.add(source)
            found[path] = {'path': path.relative_to(root).as_posix(), 'sha256': output['sha256'],
                           'duration_seconds': duration, 'confirmation': manifest.relative_to(root).as_posix()}
    if len(found) != len(targets):
        raise ValueError('所选文件缺少当前已采用分镜的交付确认')
    return {'duration_seconds': sum(row['duration_seconds'] for row in found.values()),
            'outputs': [found[path] for path in targets]}


def cost_per_minute(project, duration_seconds, price_table, overheads=None, *, human_minutes=None):
    """按已录入用量及费率估算，费用缺项单列，绝不补零。非供应商对账账单。"""
    duration = _number(duration_seconds)
    if not duration:
        raise ValueError('每分钟成本需要有限且大于零的实际成片秒数')
    report = pet_llm.RequestLedger(project).load().report(price_table)
    money = report.get('money')
    overheads = overheads if isinstance(overheads, dict) else {}
    known = money['settled_amount'] if money else 0
    missing = []
    for key in ('gpu', 'storage', 'bandwidth'):
        amount = _number(overheads.get(key))
        if amount is None: missing.append(key)
        else: known += amount
    complete = bool(report['requests'] and money and money['complete'] and not missing)
    human = _number(overheads.get('human'))
    labor_time = _number(human_minutes)
    return {'known_amount': round(known, 4), 'known_per_minute': round(known * 60 / duration, 4),
            'human_amount': human, 'human_per_minute': round(human * 60 / duration, 4) if human is not None else None,
            'human_minutes': labor_time,
            'human_minutes_per_finished_minute': round(labor_time * 60 / duration, 4) if labor_time is not None else None,
            'including_human_per_minute': round((known + human) * 60 / duration, 4) if complete and human is not None else None,
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
    not_submitted = 0
    for event in events:
        context = event.get('context') if isinstance(event.get('context'), dict) else {}
        if context.get('not_submitted'):
            not_submitted += 1
            continue
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
              'skipped_files': skipped, 'not_submitted': not_submitted, 'budget': budget, 'requests': ledger_report}
    profile = Path(project) / 'cost_profile.json'
    if profile.is_file():
        try:
            config = read_json(profile)
            evidence = delivery_duration(project, config['delivery_outputs']) if 'delivery_outputs' in config else None
            duration = evidence['duration_seconds'] if evidence else config['duration_seconds']
            result['cost'] = cost_per_minute(project, duration, config['price_table'], config.get('overheads'),
                                           human_minutes=config.get('human_minutes'))
            result['cost']['delivery_evidence'] = evidence
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
    if not total['calls'] and not any(summary.get(key) for key in ('requests', 'budget', 'cost', 'cost_error', 'not_submitted')):
        return '本项目还没有可汇总的模型调用记录。'
    lines = ['模型调用总览', _line('合计', total), '']
    for title, key in (('按模型', 'by_model'), ('按阶段', 'by_stage'), ('按天', 'by_day')):
        if summary[key]:
            lines.append(title)
            lines.extend('  ' + _line(name, bucket) for name, bucket in summary[key].items())
            lines.append('')
    if summary.get('not_submitted'):
        lines.append('另有 %d 次发送前被阻止，未计入远端调用。' % summary['not_submitted'])
    budget = summary.get('budget')
    if isinstance(budget, dict) and budget:
        lines.append('预算（已用／额度）')
        for row in budget.values():
            lines.append('  %s：%s／%s' % (row.get('label'), row.get('used'), row.get('limit')))
        lines.append('')
    ledger_report = summary.get('requests')
    if ledger_report:
        for currency, money in ledger_report.get('model_costs', {}).items():
            lines.append('模型金额（冻结费率估算，未对账）：%s %s；预留 %s；未知 %d 笔' % (
                money['estimated_spent'], currency, money['held'], money['unknown']))
            lines.append('人工已核对账单：%s %s（凭据及修订记录保存在请求台账）' % (
                money.get('reconciled_spent', '0'), currency))
            if money.get('stale_receipts'):
                lines.append('有 %d 笔账单凭据缺失或已变化，原金额保留为待核实；请重新核对费用。' % money['stale_receipts'])
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
        lines.append('成本分母：%g 秒（%s）' % (cost['duration_seconds'],
            '已确认交付文件，摘要与分镜版本已核验' if cost.get('delivery_evidence') else '手工录入，尚未绑定交付证据'))
        lines.append('已录入制作成本（不含人工）：%g %s／分钟；%s' % (cost['known_per_minute'], cost['currency'] or '币种未配置',
            '录入项齐全' if cost['complete'] else '总成本未知，仍有未知用量、预留或缺项'))
        lines.append('按录入用量和费率估算，尚非供应商对账结果；外部费用缺项：' + '、'.join(cost['missing_overheads']))
        human = cost.get('human_per_minute')
        lines.append('人工编辑费用：' + ('未知（未计为零）' if human is None else
                     '%g %s／分钟（单列）' % (human, cost['currency'] or '币种未配置')))
        minutes = cost.get('human_minutes')
        lines.append('人工编辑耗时：' + ('未知（未计为零）' if minutes is None else
            '%g 分钟；每成片分钟需人工 %g 分钟' % (minutes, cost['human_minutes_per_finished_minute'])))
        full = cost.get('including_human_per_minute')
        lines.append('含人工全成本：' + ('未知（制作费用或人工金额未齐全）' if full is None else
            '%g %s／成片分钟（按已录入金额核算）' % (full, cost['currency'] or '币种未配置')))
    lines.append('说明：只统计已落盘的调用事件；金额需配价格表后由请求台账折算，这里不估算。')
    return '\n'.join(lines).strip()

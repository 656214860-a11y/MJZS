# -*- coding: utf-8 -*-
"""项目用量总览：只读汇总已落盘的模型调用事件（`model_diagnostics/*.json`）与请求台账。

数据来源都是现成的：每次模型调用已写一条脱敏事件（模型、阶段、token 用量、成败）。
本模块不新增写入路径、不改调用流程；事件里没有用量字段的调用记为「用量未知」，
绝不当作 0。token／次数各列各的，不折算金额（金额只在配了价格表时由台账折算）。
"""
from __future__ import annotations

from pathlib import Path
import hashlib
import json

import infra.pet_llm as pet_llm
from infra.file_cache import read_json

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
    from contract.stage_path_service import read_dirs, write_dir
    from domain.storyboard_adoption_contract import adopted
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


def untracked_comfy(project, ledger):
    """核对已有工作流与费用记录；未知节点不推断免费或套用单张图片价格。"""
    tracked = {row.get('id') for row in ledger.entries if row.get('state') != 'duplicate'}
    imported = {(source.get('source'), source.get('sha256'))
                for row in ledger.entries if row.get('cost_only') and row.get('state') != 'duplicate'
                for source in row.get('legacy_sources', []) if isinstance(source, dict)}
    missing = []
    for path in sorted((Path(project) / 'workflows').glob('comfy_*.json')):
        try:
            job = read_json(path)
        except (OSError, ValueError):
            job = None
        request_id = job.get('cost_request_id') if isinstance(job, dict) else None
        if isinstance(job, dict):
            digest = hashlib.sha256(json.dumps(job, sort_keys=True, ensure_ascii=False).encode('utf-8')).hexdigest()
            if ('comfy-task:' + path.name, digest) in imported:
                continue
        if not isinstance(request_id, str) or not request_id or request_id not in tracked:
            missing.append(path.name)
    return missing


def _finite_decimal(value):
    from decimal import Decimal, InvalidOperation
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    if isinstance(value, bool) or not number.is_finite() or number < 0:
        return None
    return number


def _decimal_text(value):
    if value is None:
        return None
    text = format(value, 'f')
    if '.' in text:
        text = text.rstrip('0').rstrip('.')
    return text or '0'


def _same_version(left, right):
    try:
        return int(left) == int(right)
    except (TypeError, ValueError):
        return str(left) == str(right)


def _relative(root, path):
    try:
        return Path(path).resolve().relative_to(Path(root).resolve()).as_posix()
    except (OSError, ValueError):
        return str(path)


def _attempt_money_accumulation(rows):
    """汇总台账金额事实；只展开一层循环，供嵌套深度门禁与状态判定共用。"""
    from decimal import Decimal
    total = Decimal(0)
    known = False
    states = []
    missing_rate = False
    stale_receipt = False
    for row in rows:
        state = pet_llm.RequestLedger.effective_money_state(row)
        states.append(state or 'unknown')
        amount = _finite_decimal(row.get('budget_cost'))
        missing_rate = missing_rate or amount is None
        if amount is not None:
            total += amount
            known = True
        stale_receipt = stale_receipt or (row.get('money_state') == 'reconciled' and state != 'reconciled')
    return {'total': total, 'known': known, 'states': states,
            'missing_rate': missing_rate, 'stale_receipt': stale_receipt}


def _attempt_bill_state(rows, facts, *, missing):
    """按优先级判定账单状态；每级只返回事实，不推断供应商未提供的数据。"""
    if not rows:
        label = ('版本登记的请求号在请求台账中缺失，费用未知；请到「设置→预算→费用核对」人工核对'
                 if missing else
                 '没有可关联的请求台账记录，费用未知；请到「设置→预算→费用核对」人工核对')
        return 'missing', label
    if facts['missing_rate']:
        return 'missing_rate', '缺费率或未计价，费用未知；请补费率并人工核对账单'
    if facts['stale_receipt']:
        return 'stale_receipt', '账单凭据缺失或已变化，原金额保留为待核实；请重新核对费用'
    states = facts['states']
    if any(state == 'unknown' for state in states):
        return 'unknown', '供应商用量或结果未知，费用未知；请查询终态后人工核对账单'
    if any(state == 'reserved' for state in states):
        return 'reserved', '费用仍是预留，供应商终态未知；请查询终态后人工核对账单'
    if states and all(state == 'reconciled' for state in states):
        return 'reconciled', '人工已核对账单'
    return 'estimated', '冻结费率估算，缺供应商账单核对'


def _attempt_cost_fact(rows, *, missing=False, not_submitted=False, duplicate_of=None):
    """一次视频尝试的账单事实；金额、估算和供应商对账状态分开，不把未知当零。"""
    rows = [row for row in rows if isinstance(row, dict)]
    currency = next((str(row.get('currency')) for row in rows if row.get('currency')), None)
    if not_submitted and not rows:
        return {'amount': '0', 'currency': currency, 'bill_state': 'not_submitted',
                'label': '发送前被拦截，未产生远端请求', 'manual_check_required': False, 'states': []}
    if any(row.get('state') == 'duplicate' for row in rows):
        label = ('同一远端任务已并入请求 %s；本行不重复计列' % duplicate_of if duplicate_of else
                 '同一远端任务被标重，但原请求缺失，费用未知；请人工核对')
        return {'amount': None, 'currency': currency, 'bill_state': 'duplicate', 'label': label,
                'manual_check_required': duplicate_of is None, 'states': ['duplicate']}
    facts = _attempt_money_accumulation(rows)
    bill_state, label = _attempt_bill_state(rows, facts, missing=missing)
    amount = _decimal_text(facts['total']) if facts['known'] else None
    if amount == '0' and bill_state == 'reconciled':
        label += '（确认零费用）'
    elif amount == '0' and bill_state == 'estimated':
        label += '；估算为 0 仍需账单核对'
    return {'amount': amount, 'currency': currency, 'bill_state': bill_state, 'label': label,
            'manual_check_required': bill_state not in ('reconciled',), 'states': facts['states']}


def adopted_video_versions(project, delivery_evidence=None):
    """读取采用版本证据：已确认交付旁的剪辑来源优先，缺失时退到视频阶段清单。"""
    root = Path(project).resolve()
    rows, issues = {}, []

    def remember(item, evidence, basis):
        if not isinstance(item, dict):
            return
        shot = item.get('shot', item.get('id'))
        version = item.get('version', item.get('adopted_version'))
        if shot is None or version is None:
            return
        rows[str(shot)] = {'version': version, 'sha256': item.get('sha256'),
                           'evidence': evidence, 'basis': basis}

    if isinstance(delivery_evidence, dict):
        for output in delivery_evidence.get('outputs') or []:
            if not isinstance(output, dict) or not output.get('path'):
                continue
            master = (root / output['path']).resolve()
            bundle_path = master.parent / 'edit_bundle.json'
            if not bundle_path.is_file():
                issues.append('交付成片旁缺少剪辑来源清单，采用版本未知：' + output['path'])
                continue
            try:
                bundle = read_json(bundle_path)
            except (OSError, ValueError):
                issues.append('剪辑来源清单无法读取，采用版本未知：' + _relative(root, bundle_path))
                continue
            if (not isinstance(bundle, dict) or bundle.get('master_sha256') != output.get('sha256')
                    or (bundle.get('master') and bundle.get('master') != master.name)
                    or not isinstance(bundle.get('manifest'), list)):
                issues.append('剪辑来源清单与已确认交付不一致，采用版本未知：' + _relative(root, bundle_path))
                continue
            evidence = _relative(root, bundle_path)
            for item in bundle['manifest']:
                remember(item, evidence, 'confirmed_edit_bundle')
        if rows:
            return {'rows': rows, 'basis': 'confirmed_edit_bundle', 'issues': issues}

    from contract.stage_path_service import read_dirs
    candidates = [folder / 'output' / name for folder in read_dirs(root, 'video')
                  for name in ('video_manifest.json', 'videos.json')]
    for path in candidates:
        if not path.is_file():
            continue
        try:
            data = read_json(path)
        except (OSError, ValueError):
            issues.append('视频阶段清单无法读取，采用版本未知：' + _relative(root, path))
            continue
        shots = data.get('shots') if isinstance(data, dict) else None
        if not isinstance(shots, list):
            issues.append('视频阶段清单格式无效，采用版本未知：' + _relative(root, path))
            continue
        evidence = _relative(root, path)
        for item in shots:
            remember(item, evidence, 'video_stage_manifest')
        if rows:
            return {'rows': rows, 'basis': 'video_stage_manifest', 'issues': issues}
    return {'rows': rows, 'basis': 'none', 'issues': issues}


def _video_attempt_totals(rows):
    from decimal import Decimal
    currencies = {}
    unknown = missing = not_submitted = duplicate = 0
    for row in rows:
        cost = row.get('cost') or {}
        amount = _finite_decimal(cost.get('amount'))
        state = cost.get('bill_state')
        currency = cost.get('currency')
        if state != 'duplicate' and (currency or amount is not None):
            currency = currency or '币种未配置'
            bucket = currencies.setdefault(currency, {'reconciled': Decimal(0), 'estimated': Decimal(0),
                                                      'held_or_unknown': Decimal(0)})
            if amount is not None:
                key = {'reconciled': 'reconciled', 'estimated': 'estimated'}.get(state, 'held_or_unknown')
                bucket[key] += amount
        if state in ('missing', 'missing_rate'):
            missing += 1
        elif state in ('unknown', 'reserved', 'stale_receipt'):
            unknown += 1
        elif state == 'not_submitted':
            not_submitted += 1
        elif state == 'duplicate':
            duplicate += 1
            unknown += 1 if cost.get('manual_check_required') else 0
    by_currency = {}
    for currency, bucket in sorted(currencies.items()):
        row = {key: _decimal_text(value) for key, value in bucket.items()}
        row['known_total'] = _decimal_text(bucket['reconciled'] + bucket['estimated'])
        by_currency[currency] = row
    return {'attempts': len(rows), 'unknown_count': unknown, 'missing_count': missing,
            'not_submitted': not_submitted, 'duplicate_count': duplicate, 'by_currency': by_currency}


def _legacy_cost_groups(entries, label):
    return [row for row in entries if isinstance(row, dict) and row.get('cost_only')
            and row.get('legacy_label') == label]


def _legacy_request_rows(entries, base):
    return [row for row in entries
            if isinstance(row, dict)
            and (str(row.get('id') or '') == base or str(row.get('id') or '').startswith(base + ':'))]


def _workspace_ledger_entries(root, workspace, errors):
    """只读云端工作集自己的旧台账；不用 RequestLedger.load，避免读视图产生备份写入。"""
    path = pet_llm.request_ledger_path(workspace)
    if not path.is_file():
        return []
    try:
        data = read_json(path)
    except (OSError, ValueError):
        errors.append('请求台账无法读取：' + _relative(root, path))
        return []
    entries = data.get('entries') if isinstance(data, dict) else None
    if not isinstance(entries, list) or any(not isinstance(row, dict) for row in entries):
        errors.append('请求台账格式无效：' + _relative(root, path))
        return []
    return entries


def _attempt_request_rows(entries, costs, version, sid, workspace_name, workspace_entries):
    """返回 (台账行, 登记请求号是否缺失, duplicate 主请求号)；不在跨工作集间猜旧键。"""
    base = 'video:%s:v%s' % (sid, version.get('version'))
    groups = _legacy_cost_groups(entries, workspace_name + ' / ' + base)
    request_id = version.get('money_request_id')
    if request_id:
        row = costs.get(str(request_id))
        if row is not None:
            return [row], False, _duplicate_owner(entries, row)
        if groups:
            return groups, False, None
        return [], True, None
    if groups:
        return groups, False, None
    return _legacy_request_rows(workspace_entries, base), False, None


def _duplicate_owner(entries, row):
    """找同一远端任务号的非重复账单主行；旧重复行无远端号时只认台账写下的主请求号。"""
    if row.get('state') != 'duplicate':
        return None
    remote = row.get('remote_task_id')
    if remote:
        for candidate in entries:
            if candidate is row or not isinstance(candidate, dict):
                continue
            if candidate.get('remote_task_id') == remote and candidate.get('state') != 'duplicate':
                return str(candidate.get('id') or '') or None
    note = str(row.get('note') or '')
    prefix = '同一远端任务已由请求 '
    if note.startswith(prefix) and ' 记账' in note:
        return note[len(prefix):].split(' 记账', 1)[0] or None
    return None


def video_attempt_costs(project, ledger=None, delivery_evidence=None):
    """逐尝试关联视频版本、请求台账与采用版本；只读，缺证据一律显示未知。"""
    root = Path(project).resolve()
    adoption = adopted_video_versions(root, delivery_evidence)
    errors = list(adoption['issues'])
    if ledger is not None:
        entries = list(getattr(ledger, 'entries', []) or [])
    else:
        entries = _workspace_ledger_entries(root, root, errors)
    costs = {str(row.get('id')): row for row in entries if isinstance(row, dict) and row.get('id')}
    rows = []
    workspace_ledgers = {}
    paths = []
    local_state = root / 'data' / 'state.json'
    if local_state.is_file():
        paths.append(local_state)
    cloud = root / 'cloud_video'
    if cloud.is_dir():
        paths.extend(sorted(cloud.glob('*/data/state.json')))
    for path in paths:
        try:
            data = read_json(path)
        except (OSError, ValueError):
            errors.append('视频任务台账无法读取：' + _relative(root, path))
            continue
        shots = data.get('shots') if isinstance(data, dict) else None
        if not isinstance(shots, dict):
            errors.append('视频任务台账格式无效：' + _relative(root, path))
            continue
        workspace = root if path == local_state else path.parent.parent
        for sid in sorted(shots, key=str):
            versions = shots[sid]
            if not isinstance(versions, list):
                errors.append('视频版本列表格式无效：' + str(sid))
                continue
            for version in versions:
                if not isinstance(version, dict):
                    errors.append('视频版本记录格式无效：' + str(sid))
                    continue
                workspace_name = _relative(root, workspace)
                if workspace_name not in workspace_ledgers:
                    workspace_ledgers[workspace_name] = (entries if workspace_name == '.' else
                                                         _workspace_ledger_entries(root, workspace, errors))
                request_rows, missing, duplicate_of = _attempt_request_rows(
                    entries, costs, version, sid, workspace_name, workspace_ledgers[workspace_name])
                cost = _attempt_cost_fact(request_rows, missing=missing,
                                          not_submitted=version.get('not_submitted') is True,
                                          duplicate_of=duplicate_of)
                marker = adoption['rows'].get(str(sid))
                adopted = None
                conflict = False
                if marker is not None:
                    adopted = _same_version(marker.get('version'), version.get('version'))
                    digest = marker.get('sha256')
                    if adopted and digest and version.get('sha256') and digest != version.get('sha256'):
                        adopted = False
                        conflict = True
                if conflict:
                    errors.append('视频采用清单与任务版本摘要不一致：%s v%s' % (sid, version.get('version')))
                rows.append({'shot': str(sid), 'version': version.get('version'),
                             'state': str(version.get('state') or 'unknown'),
                             'retry_reason': str(version.get('retry_reason') or '历史未登记'),
                             'charged': version.get('charged') is not False,
                             'not_submitted': version.get('not_submitted') is True,
                             'remote_task_id': version.get('task_id'),
                             'request_ids': [str(row.get('id')) for row in request_rows if row.get('id')],
                             'cost': cost, 'adopted': adopted,
                             'workspace': _relative(root, workspace),
                             'seconds': version.get('seconds')})
    workspaces = {}
    for row in rows:
        workspaces.setdefault(row['shot'], set()).add(row.get('workspace') or '.')
    ambiguous = sorted(shot for shot, places in workspaces.items() if len(places) > 1)
    for row in rows:
        if row['shot'] in ambiguous:
            row['adopted'] = None
    if ambiguous:
        errors.append('同一镜头号出现在多个视频工作集，采用版本无法自动对应：' + '、'.join(ambiguous))
    return {'rows': rows, 'totals': _video_attempt_totals(rows), 'errors': errors,
            'adoption_basis': adoption['basis']}


def cost_per_minute(project, duration_seconds, price_table, overheads=None, *, human_minutes=None):
    """按已录入用量及费率估算，费用缺项单列，绝不补零。非供应商对账账单。"""
    duration = _number(duration_seconds)
    if not duration:
        raise ValueError('每分钟成本需要有限且大于零的实际成片秒数')
    ledger = pet_llm.RequestLedger(project).load()
    report = ledger.report(price_table)
    untracked = untracked_comfy(project, ledger)
    money = report.get('money')
    overheads = overheads if isinstance(overheads, dict) else {}
    known = money['settled_amount'] if money else 0
    missing = []
    for key in ('gpu', 'storage', 'bandwidth'):
        amount = _number(overheads.get(key))
        if amount is None: missing.append(key)
        else: known += amount
    complete = bool((report['requests'] or report.get('model_costs')) and money
                    and money['complete'] and not missing and not untracked)
    human = _number(overheads.get('human'))
    labor_time = _number(human_minutes)
    return {'known_amount': round(known, 4), 'known_per_minute': round(known * 60 / duration, 4),
            'human_amount': human, 'human_per_minute': round(human * 60 / duration, 4) if human is not None else None,
            'human_minutes': labor_time,
            'human_minutes_per_finished_minute': round(labor_time * 60 / duration, 4) if labor_time is not None else None,
            'including_human_per_minute': round((known + human) * 60 / duration, 4) if complete and human is not None else None,
            'total_per_minute': round(known * 60 / duration, 4) if complete else None,
            'complete': complete, 'missing_overheads': missing, 'untracked_comfy': untracked, 'requests': report,
            'duration_seconds': duration, 'currency': money['currency'] if money else None,
            'basis': 'recorded_usage_estimate_not_supplier_invoice'}


def estimate_scenario(scenario, price_table):
    """不付费估算：按场景给定的阶段用量乘费率；费率、币种或版本不全的模型不给金额，也绝不补零。

    场景内容由调用方给事实（本函数不推算镜头数、候选数或尝试次数）：
    {"shots": 60, "candidates": 2, "attempts": 1, "stages": [
        {"name": "首帧", "model": "m", "kind": "images", "quantities": {"images": 120}}]}
    """
    table = price_table if isinstance(price_table, dict) else {}
    stages, unknown, amount = [], [], 0
    for stage in scenario.get("stages") or ():
        kind = str(stage.get("kind") or "")
        if kind not in pet_llm.REQUEST_KINDS:
            raise ValueError("未知请求单位：" + kind)
        model = str(stage.get("model") or "")
        quantities = {key: pet_llm.RequestLedger.decimal(value)
                      for key, value in (stage.get("quantities") or {}).items()}
        _rates, cost = pet_llm.RequestLedger._model_price(table, model, quantities)
        if cost is None:
            unknown.append({"stage": str(stage.get("name") or kind), "model": model, "kind": kind})
        else:
            amount += cost
        stages.append({"name": str(stage.get("name") or kind), "model": model, "kind": kind,
                       "quantities": {key: str(value) for key, value in quantities.items()},
                       "amount": None if cost is None else float(cost)})
    complete = bool(stages) and not unknown
    return {"shots": scenario.get("shots"), "candidates": scenario.get("candidates"),
            "attempts": scenario.get("attempts"), "stages": stages,
            "amount": float(amount) if complete else None, "complete": complete,
            "unknown_stages": unknown, "currency": table.get("currency"),
            "table_version": table.get("version"),
            "basis": "configured_rates_estimate_not_supplier_invoice"}


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
    ledger = None
    try:
        ledger = pet_llm.RequestLedger(project).load()
        ledger_report = ledger.report()
        untracked = untracked_comfy(project, ledger)
    except (OSError, ValueError, TypeError):
        ledger_report = None
        untracked = untracked_comfy(project, pet_llm.RequestLedger(project))
    if ledger_report is not None and not (ledger_report.get('requests') or ledger_report.get('model_costs')):
        ledger_report = None
    result = {'total': total, 'by_model': by_model, 'by_stage': by_stage, 'by_day': dict(sorted(by_day.items())),
              'skipped_files': skipped, 'not_submitted': not_submitted, 'budget': budget, 'requests': ledger_report,
              'untracked_comfy': untracked}
    profile = Path(project) / 'cost_profile.json'
    evidence = None
    if profile.is_file():
        try:
            config = read_json(profile)
            evidence = delivery_duration(project, config['delivery_outputs']) if 'delivery_outputs' in config else None
            if evidence:
                duration = evidence['duration_seconds']
            elif 'duration_seconds' not in config:
                raise ValueError('缺交付时长：请填写成片秒数，或绑定已确认的交付文件')
            else:
                duration = config['duration_seconds']
            result['cost'] = cost_per_minute(project, duration, config['price_table'], config.get('overheads'),
                                           human_minutes=config.get('human_minutes'))
            result['cost']['delivery_evidence'] = evidence
        except (OSError, ValueError, TypeError, KeyError) as error:
            result['cost_error'] = '成本配置无法核算：' + str(error)
    ledger_for_attempts = ledger
    if ledger_for_attempts is None:
        try:
            ledger_for_attempts = pet_llm.RequestLedger(project).load()
        except (OSError, ValueError, TypeError):
            ledger_for_attempts = None
    try:
        result['video_attempts'] = video_attempt_costs(project, ledger_for_attempts, evidence)
    except (OSError, ValueError, TypeError) as error:
        result['video_attempts'] = {'rows': [], 'totals': _video_attempt_totals([]), 'errors': [str(error)],
                                    'adoption_basis': 'none'}
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
    if (not total['calls'] and not any(summary.get(key) for key in ('requests', 'budget', 'cost', 'cost_error', 'not_submitted', 'untracked_comfy'))
            and not (summary.get('video_attempts') or {}).get('rows')):
        return '本项目还没有可汇总的模型调用记录。'
    lines = ['模型调用总览', _line('合计', total), '']
    if summary.get('untracked_comfy'):
        lines.append('Comfy 费用覆盖缺项：%d 份任务记录未关联有效台账，费用未知，不能按零元或单张图片计价。' % len(summary['untracked_comfy']))
        lines.extend('  workflows/' + name for name in summary['untracked_comfy'])
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
    video = summary.get('video_attempts') or {}
    attempts = video.get('rows') or []
    if attempts or video.get('errors'):
        lines.append('视频逐尝试费用（含失败与重试；采用版本优先取已确认交付旁的剪辑来源，缺失时取视频阶段清单）')
        basis = video.get('adoption_basis')
        if basis == 'none':
            lines.append('  采用版本：未知（没有已确认剪辑来源或视频阶段清单）')
        elif basis == 'video_stage_manifest':
            lines.append('  采用版本依据：视频阶段清单；交付确认证据缺失时仅作阶段事实，不替代交付门禁')
        for row in attempts:
            cost = row.get('cost') or {}
            if cost.get('bill_state') == 'not_submitted':
                money = '不产生远端费用（未发送）'
            elif cost.get('bill_state') == 'duplicate':
                money = '不重复计列'
            elif cost.get('amount') is None:
                money = '未知'
            else:
                money = '%s %s' % (cost['amount'], cost.get('currency') or '币种未配置')
            adopted = '采用' if row.get('adopted') is True else '未采用' if row.get('adopted') is False else '采用未知'
            requests = '、'.join(row.get('request_ids') or []) or '未登记'
            lines.append('  %s v%s：%s；%s；费用 %s（%s）；请求 %s；远端任务 %s；重试原因 %s；工作集 %s' % (
                row.get('shot'), row.get('version'), row.get('state'), adopted, money,
                cost.get('label') or '账单状态未知', requests,
                row.get('remote_task_id') or '未登记', row.get('retry_reason') or '历史未登记',
                row.get('workspace') or '.'))
        totals = video.get('totals') or {}
        for currency, bucket in (totals.get('by_currency') or {}).items():
            lines.append('  合计（%s）：可确定支出 %s（人工已核对 %s＋冻结费率估算 %s）；预留或未知金额 %s 未计入总支出' % (
                currency, bucket.get('known_total') or '0', bucket.get('reconciled') or '0',
                bucket.get('estimated') or '0', bucket.get('held_or_unknown') or '0'))
        missing = totals.get('missing_count') or 0
        unknown = totals.get('unknown_count') or 0
        if missing or unknown:
            lines.append('  需人工核对：台账或费率缺失 %d 次，供应商结果／凭据未知 %d 次；路径：设置→预算→费用核对。未知不记为 0，确认无费用须核对为 0。' % (
                missing, unknown))
        for warning in video.get('errors') or []:
            lines.append('  费用关联警告：' + warning)
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
    lines.append('说明：只统计已落盘的调用事件与请求台账；金额为冻结费率估算或人工核对值，未核对前不冒称供应商最终账单。')
    return '\n'.join(lines).strip()

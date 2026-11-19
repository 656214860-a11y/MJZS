# -*- coding: utf-8 -*-
"""L1 预算引擎（L1 任务书 I16／L1-Q13／L1-H10）。

机制层：预留、结算、超限判定、成本汇总，数据面为 ``infra.request_ledger``
的请求级台账（reserve/settle/cancel 原语复用，不另起账本）。策略——五类
配额口径、预警阈值、文案、计数载体——留在 L2/L3：pet_agent 五类硬上限判定
已迁 ``orchestrator/pet_budget.py``（L3）调用本模块 ``check_amount``，
L4 只负责显示（FL-13）。
"""
from __future__ import annotations

import datetime

from infra import request_ledger
from contract.infra_errors import ConfigError

__all__ = ['WARN_RATIO', 'check_amount', 'headroom', 'usage', 'reserve',
           'settle', 'cancel', 'summary']

WARN_RATIO = 0.9                                # 与 pet_agent.Budget 现值一致的默认预警阈值


def _int(value):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _since_epoch(since):
    """since 归一成 epoch 秒：None 不过滤；数值直用；'YYYY-MM-DD' 取当日 0 点。"""
    if since is None:
        return None
    if isinstance(since, (int, float)):
        return float(since)
    text = str(since).strip()
    try:
        day = datetime.date.fromisoformat(text[:10])
    except ValueError:
        raise ConfigError('since 需为 epoch 秒或 YYYY-MM-DD：' + str(since)) from None
    return datetime.datetime.combine(day, datetime.time.min).timestamp()


def _entry_stamp(entry):
    """条目时间戳：优先结算时刻，其次预留时刻；解析不出按 0 处理（不过滤掉）。"""
    for key in ('settled_at', 'at'):
        value = entry.get(key)
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            try:
                return datetime.datetime.fromisoformat(value.replace('Z', '+00:00')).timestamp()
            except ValueError:
                continue
    return 0.0


def check_amount(kind, used, limit, amount, *, warn_ratio=WARN_RATIO):
    """超限判定原语（pet 五类配额同口径，只算不扣）。

    返回 ``{ok, kind, used, limit, amount, remaining, warning, exceeded}``——
    字段与历史 ``pet_agent.Budget.check`` 逐字一致（L1-H10 行为等价）。
    """
    count = max(0, _int(amount) or 0)
    ok = used + count <= limit
    ratio = (used + count) / limit if limit else 1.0
    return {'ok': ok, 'kind': kind, 'used': used, 'limit': limit, 'amount': count,
            'remaining': max(0, limit - used - count),
            'warning': ok and ratio >= warn_ratio, 'exceeded': not ok}


def headroom(limit, used, reserved=0):
    """剩余量 = ``max(0, limit-used-reserved)``（skill_budget.remaining 同口径）。"""
    return max(0, int(limit) - int(used) - int(reserved))


def usage(ledger, kind=None):
    """台账用量 ``{kind: {settled, reserved, unknown, count}}``，与 ``report()['kinds']`` 同口径。

    ``ledger`` 为已加载的 ``infra.request_ledger.RequestLedger`` 实例（或有 ``report()`` 的等价物）；
    ``kind`` 给定时只回该类（无该类返回空 dict）。返回值是副本，调用方可改。
    """
    kinds = (ledger.report() or {}).get('kinds', {})
    if kind is None:
        return {name: dict(bucket) for name, bucket in kinds.items()}
    bucket = kinds.get(kind)
    return {kind: dict(bucket)} if bucket is not None else {}


def reserve(ledger, request_id, kind, amount, *, limits=None, meta=None,
            at=None):
    """预算预留：``limits={kind: 上限}`` 且该 kind 登记了上限时，先按台账
    ``settled+reserved`` 判定，越线抛 ``request_ledger.BudgetRejected`` 且不落账；
    通过则落预留，并把 ``stage``/``provider`` 回填到条目（成本汇总维度）。
    """
    meta = meta or {}
    cap = (limits or {}).get(kind)
    if cap is not None:
        bucket = usage(ledger, kind).get(kind, {})
        used = float(bucket.get('settled') or 0) + float(bucket.get('reserved') or 0)
        verdict = check_amount(kind, used, cap, amount)
        if verdict['exceeded']:
            raise request_ledger.BudgetRejected(
                '%s 配额已用完（%s/%s）：已拒绝本次预留' % (kind, used, cap))
    entry = ledger.reserve(request_id, kind, amount, at=at)
    for key in ('stage', 'provider'):
        if meta.get(key) is not None:
            entry[key] = str(meta[key])
    return entry


def settle(ledger, request_id, **kwargs):
    """结算：原样转 ``RequestLedger.settle``（实报量只写一次，不重复记账）。"""
    return ledger.settle(request_id, **kwargs)


def cancel(ledger, request_id, **kwargs):
    """取消：原样转 ``RequestLedger.cancel``（取消不退款，已实报量继续计）。"""
    return ledger.cancel(request_id, **kwargs)


def _kinds_of(entries):
    """与 ``RequestLedger.report()`` 同口径的 kinds 桶（作用于条目子集）。"""
    kinds = {kind: {'settled': 0.0, 'reserved': 0.0, 'unknown': 0, 'count': 0}
             for kind in request_ledger.REQUEST_KINDS}
    for entry in entries:
        if not isinstance(entry, dict) or entry.get('cost_only'):
            continue
        kind = entry.get('kind')
        bucket = kinds.setdefault(kind, {'settled': 0.0, 'reserved': 0.0,
                                         'unknown': 0, 'count': 0})
        state = entry.get('state')
        if state == 'duplicate':
            continue
        bucket['count'] += 1
        if state == 'cancelled':
            if entry.get('mode') == 'reported' and entry.get('amount') is not None:
                bucket['settled'] += float(entry['amount'])
            else:
                bucket['unknown'] += 1
            continue
        if state == 'unknown' or entry.get('mode') == 'unknown':
            bucket['unknown'] += 1
            continue
        if state == 'settled':
            bucket['settled'] += float(entry.get('amount') or 0)
        elif state == 'reserved':
            bucket['reserved'] += float(entry.get('amount') or 0)
    return kinds


def summary(project, since=None):
    """成本汇总（I16-3）：按 kind／stage／provider 聚合 request_ledger 条目。

    ``kinds`` 桶与 ``RequestLedger.report()['kinds']`` 同口径（since=None 时
    逐值相等）；``by_stage``/``by_provider`` 只累计 ``state=='settled'`` 且
    有实报量的条目（provider 取条目 ``provider`` 字段，缺省回落 ``model``，
    再缺省归 'unknown'）。``since`` 接受 epoch 秒或 'YYYY-MM-DD'，按条目
    ``settled_at``（无则 ``at``）过滤。
    """
    stamp = _since_epoch(since)
    ledger = request_ledger.RequestLedger(project)
    ledger.load()
    entries = [entry for entry in ledger.entries
               if stamp is None or _entry_stamp(entry) >= stamp]
    kinds = _kinds_of(entries)
    by_stage, by_provider = {}, {}
    for entry in entries:
        if not isinstance(entry, dict) or entry.get('cost_only'):
            continue
        if entry.get('state') != 'settled' or entry.get('amount') is None:
            continue
        kind = str(entry.get('kind') or 'unknown')
        amount = float(entry.get('amount') or 0)
        stage = str(entry.get('stage') or 'unknown')
        provider = str(entry.get('provider') or entry.get('model') or 'unknown')
        for table, key in ((by_stage, stage), (by_provider, provider)):
            bucket = table.setdefault(key, {})
            bucket[kind] = bucket.get(kind, 0.0) + amount
    return {'since': since, 'kinds': kinds, 'by_stage': by_stage,
            'by_provider': by_provider,
            'requests': sum(bucket['count'] for bucket in kinds.values())}


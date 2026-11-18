# -*- coding: utf-8 -*-
"""用量跨天归档：``<项目>/usage_history/YYYY-MM.json``，每个自然日一行合计。

只由 ``usage_snapshot`` 调用；读走 ``file_cache.read_json``，写走 ``agent.core.save``
原子发布。金额全程 Decimal 字符串，不做估算、不补零。
"""
import time
from decimal import Decimal, InvalidOperation
from pathlib import Path

from agent.core import save
from agent.publication import access
from infra.file_cache import read_json

HISTORY_DIR = 'usage_history'


def _path(project, year_month):
    return Path(project) / HISTORY_DIR / (str(year_month) + '.json')


def _dec(value):
    try:
        if value in (None, ''):
            return Decimal(0)
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return Decimal(0)
    return amount if amount >= 0 else Decimal(0)


def _month_key():
    """归档月份与「今天」同一口径：北京时间（UTC+8）零点分界；不依赖 pet_llm 防成环。"""
    return time.strftime('%Y-%m', time.gmtime(time.time() + 8 * 3600))


def record_today(project, day, tokens, cost, calls, currency=''):
    """把某一天的合计覆盖写进当月归档（同一天反复刷新，以最后一次为准）。

    返回是否写盘成功；任何异常向上抛由调用方吞掉——归档失败不影响记账。
    """
    day = str(day or '')
    if project is None or len(day) < 7:
        return False
    path = _path(project, day[:7])
    with access():
        try:
            data = read_json(path)
        except Exception:
            data = None
        if not isinstance(data, dict) or not isinstance(data.get('days'), dict):
            data = {'version': 1, 'currency': str(currency or 'CNY'), 'days': {}}
        days = data['days']
        try:
            tokens = max(0, int(tokens or 0))
            calls = max(0, int(calls or 0))
        except (TypeError, ValueError):
            return False
        days[day] = {'tokens': tokens, 'cost': format(_dec(cost), 'f'), 'calls': calls}
        data['days'] = dict(sorted(days.items()))
        if currency:
            data['currency'] = str(currency)
        # 月度用量归档同样是可重建运行记录：原子替换即可，不等落盘。
        save(path, data, durable=False)
    return True


def archive_yesterday(project, yesterday):
    """跨天归档入口：把昨日的 today 快照写进归档文件。"""
    if not isinstance(yesterday, dict):
        return False
    return record_today(project, yesterday.get('date'),
                        yesterday.get('token_used'), yesterday.get('money_spent'),
                        yesterday.get('calls'), currency=yesterday.get('currency') or '')


def this_month(project):
    """读当月归档；文件缺失或损坏返回 ``{'days': {}}``。"""
    try:
        data = read_json(_path(project, _month_key()))
    except Exception:
        data = None
    if not isinstance(data, dict) or not isinstance(data.get('days'), dict):
        return {'days': {}}
    return data

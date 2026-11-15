# -*- coding: utf-8 -*-
"""模型调用用量快照：今日明细（内存）＋项目累计（usage_summary.json）＋跨天归档。

``request_ledger`` 每结算成功一笔就调 :meth:`UsageSnapshot.record_call`；
桌面指示器经 :meth:`UsageSnapshot.current` 读快照，并订阅 ``pet_bus`` 的
``usage_updated`` 事件刷新。金额全程 ``Decimal`` 字符串：没有价格表时
``money_spent`` 保持 ``'0'`` 但界面凭「无费用来源」隐藏金额项，不补零。

持久化失败一律吞掉——记账绝不能弄断生产调用与请求结算。
"""
import threading
import time
from collections import deque
from decimal import Decimal, InvalidOperation
from pathlib import Path

import app_logging
from agent.core import save
from file_cache import read_json

import infra.usage_history as usage_history

SUMMARY_NAME = 'usage_summary.json'
DETAIL_LIMIT = 10000

_snapshots = {}
_null_snapshot = None
_bus = None
_errors = None


def bind_bus(bus, errors=None):
    """界面把当前项目事件总线交给快照层；换项目重建总线后由调用方重新 bind。"""
    global _bus, _errors
    _bus = bus
    _errors = errors if errors is not None else []


# 「今天」与 pet_llm.beijing 同一口径：北京时间（UTC+8，无夏令时）零点分界。
# 不反向依赖 pet_llm，避免 pet_llm→request_ledger→本模块→pet_llm 成环。
_BEIJING_OFFSET = 8 * 3600


def _day_key(at):
    return time.strftime('%Y-%m-%d', time.gmtime(at + _BEIJING_OFFSET))


def _clock_text(at):
    return time.strftime('%H:%M:%S', time.gmtime(at + _BEIJING_OFFSET))


def _stamp_text(at):
    return time.strftime('%Y-%m-%dT%H:%M:%S+08:00', time.gmtime(at + _BEIJING_OFFSET))


def _money(value):
    """合法非负金额 → Decimal；空／非法 → None（不编造、不估算）。"""
    try:
        if value in (None, ''):
            return None
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    return amount if amount >= 0 else None


def abbr_number(value):
    """千分位简写：<1000 原样；<100 万 K；≥100 万 M，各保留一位小数。"""
    n = int(value or 0)
    if n < 1000:
        return str(n)
    if n < 1000000:
        return '%.1fK' % (n / 1000)
    return '%.1fM' % (n / 1000000)


def money_amount(cost):
    """合法正金额 → Decimal；空／非法／为 0 → None（无价格表或零额一律隐藏）。"""
    try:
        if cost in (None, ''):
            return None
        amount = Decimal(str(cost))
    except (InvalidOperation, ValueError):
        return None
    return amount if amount > 0 else None


def money_text(amount, currency):
    """``¥0.82``／``$9`` 形式；未知币种退化为 ``<币种> <数>``，空币种只显数。"""
    number = format(amount.normalize(), 'f')
    code = str(currency or '').strip().upper()
    if code == 'CNY':
        return '¥' + number
    if code == 'USD':
        return '$' + number
    if code:
        return code + ' ' + number
    return number


class UsageSnapshot:
    """单个项目的用量快照；``project=None`` 时只记内存、不落盘不发事件。"""

    def __init__(self, project, clock=time.time):
        self.project = Path(project) if project else None
        self.clock = clock
        self._lock = threading.RLock()
        self._seq = 0
        self._today = self._fresh_today(_day_key(self.clock()))
        self._project_total = {'token_used': 0, 'money_spent': Decimal(0), 'total_calls': 0}
        self._balance = {}
        self._currency = ''
        self._history_at = 0.0
        if self.project is not None:
            self._load_project_total()

    @staticmethod
    def _fresh_today(day):
        return {'date': day, 'token_used': 0, 'money_spent': Decimal(0),
                'calls': 0, 'currency': '', 'details': deque(maxlen=DETAIL_LIMIT)}

    # -- 记账 -----------------------------------------------------
    def record_call(self, stage, model, tokens, cost='', currency='', request_id=''):
        """记一笔已结算的模型调用；返回是否计入（恒 True，失败也不抛）。"""
        try:
            tokens = max(0, int(tokens or 0))
        except (TypeError, ValueError):
            tokens = 0
        amount = _money(cost)
        stage, model = str(stage or ''), str(model or '')
        currency = str(currency or '') or self._currency
        rid = str(request_id or '')
        with self._lock:
            self._seq += 1
            seq = self._seq
            today_key = _day_key(self.clock())
            if today_key != self._today['date']:
                old = self._today
                self._today = self._fresh_today(today_key)
                self._history_at = 0.0
                if self.project is not None:
                    try:
                        usage_history.archive_yesterday(self.project, dict(old))
                    except Exception:
                        app_logging.swallowed()
            today = self._today
            today['token_used'] += tokens
            today['calls'] += 1
            if amount is not None:
                today['money_spent'] += amount
            if currency:
                today['currency'] = currency
                self._currency = currency
            today['details'].append({'at': _clock_text(self.clock()), 'stage': stage,
                                     'model': model, 'tokens': tokens})
            total = self._project_total
            total['token_used'] += tokens
            total['total_calls'] += 1
            if amount is not None:
                total['money_spent'] += amount
            if self.project is not None:
                try:
                    self._save_project_total()
                    # 当日行随调用节流刷新（≤60s 一次）；跨天由 archive_yesterday 兜底写全量。
                    now = self.clock()
                    if now - self._history_at >= 60:
                        self._history_at = now
                        usage_history.record_today(self.project, today['date'],
                                                   today['token_used'], today['money_spent'],
                                                   today['calls'], currency=self._currency)
                except Exception:
                    app_logging.swallowed()
        self._notify(seq, rid)
        return True

    def _notify(self, seq, request_id):
        """结算后通知界面刷新；总线缺失／事件不合契约都只记一笔，绝不影响结算。"""
        try:
            import contract.pet_bus as pet_bus
            if _bus is None or self.project is None:
                return
            pet_bus.emit_safe(_bus, _errors, 'usage_updated',
                              project=str(self.project), request_id=request_id, seq=seq)
        except Exception:
            app_logging.swallowed()

    # -- 持久化 -----------------------------------------------------
    def _load_project_total(self):
        try:
            data = read_json(self.project / SUMMARY_NAME)
        except Exception:
            data = None
        if not isinstance(data, dict):
            return
        try:
            tokens = int(data.get('total_tokens') or 0)
            calls = int(data.get('total_calls') or 0)
        except (TypeError, ValueError):
            return
        if tokens < 0 or calls < 0:
            return
        cost = _money(data.get('total_cost'))
        self._project_total = {'token_used': tokens, 'total_calls': calls,
                               'money_spent': cost if cost is not None else Decimal(0)}

    def _save_project_total(self):
        total = self._project_total
        # 用量汇总是可重建的运行记录：照常原子替换但不等落盘（agent.core.save_text 口径）。
        save(self.project / SUMMARY_NAME,
             {'version': 1, 'total_tokens': total['token_used'],
              'total_cost': format(total['money_spent'], 'f'),
              'total_calls': total['total_calls'],
              'updated_at': _stamp_text(self.clock())}, durable=False)

    # -- 读取 -------------------------------------------------------
    def current(self):
        """返回深拷贝快照：``{'today','project_total','balance','currency','date'}``。"""
        with self._lock:
            today = {key: value for key, value in self._today.items() if key != 'details'}
            today['money_spent'] = format(today['money_spent'], 'f')
            today['details'] = [dict(row) for row in self._today['details']]
            total = dict(self._project_total)
            total['money_spent'] = format(total['money_spent'], 'f')
            return {'today': today, 'project_total': total,
                    'balance': dict(self._balance), 'currency': self._currency,
                    'date': self._today['date']}


def get_snapshot(project):
    """按项目缓存快照单例；``project`` 为空返回共享只读空快照（不落盘不发事件）。"""
    global _null_snapshot
    if project is None or str(project) == '':
        if _null_snapshot is None:
            _null_snapshot = UsageSnapshot(None)
        return _null_snapshot
    try:
        key = str(Path(project).resolve())
    except (OSError, RuntimeError):
        key = str(project)
    snapshot = _snapshots.get(key)
    if snapshot is None:
        snapshot = _snapshots[key] = UsageSnapshot(Path(project))
    return snapshot

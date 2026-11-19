# -*- coding: utf-8 -*-
"""pet_agent 五类配额硬限制的策略层（L1 任务书 I16 自 pet_agent.py 迁入 L3 编排层，FL-13）。

机制——超限判定数学——在 ``infra.budget.check_amount``（L1）；本模块只留策略：
五类 kind 与别名、默认额度、九成预警阈值、会话内存计数载体。pet_agent（L4）
保留显示与事件出口，判定不再落在界面层（L1-H10 行为逐字等价）。
"""
import infra.budget as budget_engine


def _int(value):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


BUDGET_KINDS = ('image', 'firstframe', 'video', 'voice', 'tokens')
BUDGET_NAMES = {'image': '生图', 'firstframe': '首帧', 'video': '视频', 'voice': '配音', 'tokens': 'Token'}
BUDGET_ALIASES = {'token': 'tokens', 'tokens_per_day': 'tokens', 'keyframe': 'firstframe',
                  'shots': 'video', 'tts': 'voice', 'img': 'image'}
DEFAULT_BUDGET = {'image': 200, 'firstframe': 200, 'video': 100, 'voice': 200, 'tokens': 2000000}
WARN_RATIO = 0.9                                # 用到九成先报一声


def normalize_kind(kind):
    name = BUDGET_ALIASES.get(str(kind or '').strip().lower(), str(kind or '').strip().lower())
    if name not in BUDGET_KINDS:
        raise ValueError('未登记的配额类型：' + str(kind))
    return name


class Budget:
    """生图/首帧/视频/配音/Token 五类配额的硬限制：越线直接拒绝，不留「再试一次」的口子。"""

    def __init__(self, limits=None):
        self.limits = dict(DEFAULT_BUDGET)
        for kind, value in (limits or {}).items():
            try:
                name = normalize_kind(kind)
            except ValueError:
                continue
            number = _int(value)
            if number and number > 0:
                self.limits[name] = number
        self.used = {kind: 0 for kind in BUDGET_KINDS}

    def check(self, kind, amount=1):
        """只算不扣：够不够、还剩多少、要不要提前报警。"""
        name = normalize_kind(kind)
        return budget_engine.check_amount(name, self.used[name], self.limits[name], amount,
                                          warn_ratio=WARN_RATIO)

    def spend(self, kind, amount=1):
        """扣减：越线时原样返回拒绝结果且不扣，调用方据此暂停。"""
        result = self.check(kind, amount)
        if result['ok']:
            self.used[result['kind']] += result['amount']
        return result

    def sync_tokens(self, ledger, at=None):
        """把 pet_llm 台账里当天的 Token 用量同步进来（Token 也是一类配额）。"""
        if ledger is None:
            return self.used['tokens']
        try:
            self.used['tokens'] = int(ledger.today_tokens(at))
        except Exception:
            return self.used['tokens']
        return self.used['tokens']

    def snapshot(self):
        return {'limits': dict(self.limits), 'used': dict(self.used)}


__all__ = ['BUDGET_ALIASES', 'BUDGET_KINDS', 'BUDGET_NAMES', 'DEFAULT_BUDGET',
           'WARN_RATIO', 'Budget', 'normalize_kind']


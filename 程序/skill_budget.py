# -*- coding: utf-8 -*-
"""SKILL 预算硬限制：Token 日 200 万、生图 200 张/项目、视频 100 镜/项目。

三本账分开记，互不挪用：
- Token 走 pet_llm 那本台账（全程序只此一份，按北京时间的「当天」算）；
- 生图与视频是「项目内累计」，落在项目的 工作流任务/SKILL/预算.json。

界面与编排器都只问这里：check() 给结论（能不能再花），spend() 记账，snapshot() 给面板显示。
"""
import time
from pathlib import Path

from agent.core import save
from pet_bus import read_json

PROGRAM = Path(__file__).resolve().parent
BUDGET_PATH = ('工作流任务', 'SKILL', '预算.json')
# 第 44 期：「设置 → 预算」里改的就是三虎那本配额账（配置/宠物/配置.json 的 budget_limits），
# 这里不再另立一份存额度的文件——一份设置、两处（三虎账本与 SKILL 编排）都照它算。
PET_CONFIG = ('配置', '宠物', '配置.json')
PET_LIMIT_OF = {'tokens': 'tokens', 'images': 'image', 'videos': 'video'}
KINDS = ('tokens', 'images', 'videos')
DEFAULTS = {'tokens_per_day': 2000000, 'images_per_project': 200, 'videos_per_project': 100}
LIMIT_OF = {'tokens': 'tokens_per_day', 'images': 'images_per_project', 'videos': 'videos_per_project'}
LABELS = {'tokens': 'Token（每天）', 'images': '生图（每项目）', 'videos': '视频（每项目）'}


def budget_path(project):
    return Path(project).joinpath(*BUDGET_PATH)


def limits(config=None):
    """额度：默认三条硬限制，配置里写了就按配置（只认这三把键）。"""
    out = dict(DEFAULTS)
    data = config if isinstance(config, dict) else {}
    for key in DEFAULTS:
        try:
            value = int(data.get(key, out[key]))
        except (TypeError, ValueError):
            continue
        if value > 0:
            out[key] = value
    return out


def pet_config_path(program=None):
    return Path(program or PROGRAM).joinpath(*PET_CONFIG)


def pet_limits(program=None):
    """三虎配额账 → 这里的三把键；缺项不补（调用方 limits() 会补默认值）。"""
    data = read_json(pet_config_path(program))
    limits = data.get('budget_limits') if isinstance(data, dict) else None
    limits = limits if isinstance(limits, dict) else {}
    out = {}
    for kind, key in PET_LIMIT_OF.items():
        try:
            value = int(limits.get(key))
        except (TypeError, ValueError):
            continue
        if value > 0:
            out[LIMIT_OF[kind]] = value
    return out


def configured(program=None):
    """界面改完立刻按新额度算：默认三条 ＋ 配置文件里那几把键。"""
    return limits(pet_limits(program))


def for_project(project, program=None, ledger=None, clock=time.time):
    """按当前设置给一个项目建账本（编排器与阶段面板都走它，额度只此一处）。"""
    return Budget(project=project, config=pet_limits(program), ledger=ledger, clock=clock)


class Budget:
    """一个项目的预算账本；Token 那本可以挂在 pet_llm.Ledger 上（有就不自己记）。"""

    def __init__(self, project=None, config=None, ledger=None, clock=time.time):
        self.project = Path(project) if project else None
        self.config = config if isinstance(config, dict) else {}
        self.ledger = ledger
        self.clock = clock
        self.counters = {'tokens': 0, 'images': 0, 'videos': 0}
        self.load()

    # ── 额度与用量 ──────────────────────────────────────────────────────────
    def limit(self, kind):
        kind = self._kind(kind)
        return limits(self.config)[LIMIT_OF[kind]]

    def used(self, kind):
        kind = self._kind(kind)
        if kind == 'tokens' and self.ledger is not None:
            return int(self.ledger.today_tokens())
        return int(self.counters.get(kind, 0))

    def remaining(self, kind):
        return max(0, self.limit(kind) - self.used(kind))

    def check(self, kind, amount=1):
        """还能不能再花 amount：返回 (能不能, 一句话)。"""
        kind = self._kind(kind)
        amount = max(0, int(amount))
        left = self.remaining(kind)
        if amount > left:
            return False, '%s 额度不够：还剩 %d，本次要 %d' % (LABELS[kind], left, amount)
        return True, '%s 还剩 %d' % (LABELS[kind], left)

    def over(self, kind):
        return self.used(kind) >= self.limit(kind)

    def spend(self, kind, amount=1):
        """记账：Token 那本交给 pet_llm 的台账，其余加进本项目的计数器。"""
        kind = self._kind(kind)
        amount = max(0, int(amount))
        if kind == 'tokens' and self.ledger is not None:
            return self.used(kind)
        self.counters[kind] = self.counters.get(kind, 0) + amount
        self.save()
        return self.counters[kind]

    def snapshot(self):
        return {kind: {'used': self.used(kind), 'limit': self.limit(kind),
                       'remaining': self.remaining(kind), 'label': LABELS[kind]} for kind in KINDS}

    @staticmethod
    def _kind(kind):
        text = str(kind or '')
        if text not in KINDS:
            raise ValueError('没登记的预算类别：' + text)
        return text

    # ── 落盘 ────────────────────────────────────────────────────────────────
    def load(self):
        if self.project is None:
            return self
        data = read_json(budget_path(self.project))
        if isinstance(data, dict):
            for kind in KINDS:
                try:
                    self.counters[kind] = max(0, int(data.get(kind, 0)))
                except (TypeError, ValueError):
                    self.counters[kind] = 0
        return self

    def save(self):
        if self.project is None:
            return None
        path = budget_path(self.project)
        data = dict(self.counters)
        data['updated_at'] = float(self.clock())
        save(path, data)
        return path

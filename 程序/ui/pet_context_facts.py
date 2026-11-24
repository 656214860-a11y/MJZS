# -*- coding: utf-8 -*-
"""三虎对话快照里的项目事实：只汇总宿主已有的计数、缺口与门禁人话。

读盘仍走 ``voice.counts()``／``voice.gaps()`` 这两条既有出口（后者自带缓存），
这里不新增扫描，也不改路由与派发；返回固定形状，供 ``PetAgent.context()``
在 facts 回调给出非空字典时多带一个 ``facts`` 键。

同模块另收三虎的阶段停滞检测：阶段显示在跑、子进度满 ``STALL_SECONDS`` 没动时
``stall_note()`` 拼一句人话，同一波停滞只报一次——只提醒，不自动重试。
"""
import time

import contract.pet_bus as pet_bus

GAP_LIMIT = 4
STALL_SECONDS = 600.0          # 子进度多久没动算「卡住」


class StallWatch:
    """在跑阶段的停滞检测：``done`` 满 ``seconds`` 秒没动就命中一次。

    只读宿主递进来的阶段表（``machine.stages`` 的形状），不读盘、不订阅事件；
    同一波停滞只命中一次，直到 ``done`` 变化或阶段离开 running／retrying。
    """

    def __init__(self, clock=time.monotonic, seconds=STALL_SECONDS):
        self.clock = clock
        self.seconds = float(seconds)
        self.seen = {}                   # stage → [最近 done, 上次变化钟点, 已命中]

    def sample(self, stages, at=None):
        """喂一遍阶段表；有满时限的停滞返回 (stage, 分钟数, done, total)，否则 None。"""
        now = float(self.clock() if at is None else at)
        hit = None
        for stage, entry in (stages or {}).items():
            state = str((entry or {}).get('state') or '')
            detail = (entry or {}).get('detail')
            if state not in ('running', 'retrying') or not isinstance(detail, dict):
                self.seen.pop(stage, None)
                continue
            try:
                done, total = int(detail.get('done')), int(detail.get('total'))
            except (TypeError, ValueError):
                self.seen.pop(stage, None)
                continue
            record = self.seen.get(stage)
            if record is None or record[0] != done:
                self.seen[stage] = [done, now, False]
                continue
            if record[2] or now - record[1] < self.seconds:
                continue
            record[2] = True
            if hit is None:
                hit = (stage, int((now - record[1]) // 60), done, total)
        for stage in list(self.seen):
            if stage not in (stages or {}):
                self.seen.pop(stage, None)
        return hit


def format_stall_note(stage, minutes, done, total):
    """停滞提醒的人话：哪一步、卡了多久、完成到哪儿（只问一句，不动手）。"""
    return '【阶段停滞】「%s」已经在跑 %d 分钟没有新进度（完成 %d/%d），要我看看吗？' % (
        pet_bus.stage_label(stage), int(minutes), int(done), int(total))


def stall_note(voice, at=None):
    """心跳里的停滞提醒：安静期／免打扰里不动表，同一波只给一次；没有就空串。"""
    try:
        if voice.quiet(at=at) or voice.snoozing():
            return ''
        machine = voice.machine
        stages = getattr(machine, 'stages', None) if machine is not None else None
        watch = getattr(voice, '_stall_watch', None)
        if watch is None or getattr(voice, '_stall_machine', None) is not machine:
            watch = voice._stall_watch = StallWatch()
            voice._stall_machine = machine
        hit = watch.sample(stages, at=at)
        return format_stall_note(*hit) if hit else ''
    except Exception as exc:
        errors = getattr(voice, 'errors', None)
        if errors is not None:
            errors.append(('stall', str(exc)))
        return ''


def _current_stage(voice):
    try:
        state = voice.snapshot() or {}
    except Exception:
        return ''
    return str(state.get('stage') or '')


def facts_snapshot(voice):
    """返回固定形状的项目事实；没打开项目时返回空表，宿主据此不加 facts 键。"""
    agent = getattr(voice, 'agent', None)
    if getattr(agent, 'project', None) is None:
        return {}
    counts = dict(voice.counts() or {})
    gaps = [str(item) for item in list(voice.gaps() or [])[:GAP_LIMIT]]
    stage = _current_stage(voice)
    blocked = ''
    gate = getattr(voice, 'gate_reason', None)
    if stage and callable(gate):
        try:
            blocked = str(gate(stage) or '')
        except Exception:
            blocked = ''
    return {'counts': counts, 'gaps': gaps, 'blocked': blocked}

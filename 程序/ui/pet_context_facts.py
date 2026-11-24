# -*- coding: utf-8 -*-
"""三虎对话快照里的项目事实：只汇总宿主已有的计数、缺口与门禁人话。

读盘仍走 ``voice.counts()``／``voice.gaps()`` 这两条既有出口（后者自带缓存），
这里不新增扫描，也不改路由与派发；返回固定形状，供 ``PetAgent.context()``
在 facts 回调给出非空字典时多带一个 ``facts`` 键。
"""

GAP_LIMIT = 4


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

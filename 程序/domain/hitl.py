# -*- coding: utf-8 -*-
"""人在回路（HITL）请求/决策信封（L2）。

借鉴 Temporal 的「await signal + timer 超时竞速」、LangGraph 的「interrupt 返回一个值」、
Anthropic 的「审批者能改输入」：选择卡、审批门、红绿 Diff 共用同一套
``HITLRequest{kind, payload, risk, timeout}`` → ``Decision`` 协议，禁止散落弹窗。

本模块只做数据契约与纯函数（无 Tk、无网络、不读写盘）；``domain.confirm_gates`` 的
``ask`` 结果可用 ``from_confirm_result`` 转成选择卡请求。
"""
from __future__ import annotations

import re
import time
from enum import Enum


DEFAULT_TIMEOUT_SECONDS = 300
# 模型回话末尾的可点选项标记：```choices 每行一个选项。最多展示 4 个，超过截断。
CHOICE_FENCE_LANGUAGE = 'choices'
MAX_CHOICES = 4
# 只有不可逆副作用／对外发布／删除需要人工；其余低风险自动放行（避免橡皮图章）。
HIGH_RISK_ACTIONS = frozenset({'delete', 'publish', 'overwrite', 'adopt', 'release', 'replace'})

_CHOICE_OPEN = re.compile(r'^\s*`{3,}\s*choices\b.*$', re.IGNORECASE)
_CHOICE_CLOSE = re.compile(r'^\s*`{3,}\s*$')
_CHOICE_PARTIAL = re.compile(
    r'^\s*`{3,}\s*c(?:h(?:o(?:i(?:c(?:e(?:s)?)?)?)?)?)?\s*$', re.IGNORECASE)
_CHOICE_BULLET = re.compile(r'^\s*(?:[-*+]|\d+[.)、])\s*')
_CHOICE_QUOTES = (('“', '”'), ('「', '」'), ('『', '』'), ('"', '"'), ("'", "'"))


class RequestKind(str, Enum):
    CHOICE = 'choice'
    APPROVE = 'approve'
    DIFF = 'diff'


class Risk(str, Enum):
    LOW = 'low'
    HIGH = 'high'


class Decision(str, Enum):
    APPROVE = 'approve'
    REJECT = 'reject'
    REGENERATE = 'regenerate'
    EDIT = 'edit'
    TIMEOUT = 'timeout'


_DECISION_VALUES = frozenset(item.value for item in Decision)


def risk_of(kind, payload=None):
    """选择卡一律低风险；审批门按动作判定（删除/发布/覆盖/采用/发布/替换为高风险）。"""
    value = kind.value if isinstance(kind, RequestKind) else str(kind)
    if value == RequestKind.CHOICE.value:
        return Risk.LOW.value
    action = str((payload or {}).get('action') or '').strip().lower()
    return (Risk.HIGH if action in HIGH_RISK_ACTIONS else Risk.LOW).value


def make_request(kind, payload=None, *, risk=None, timeout=None, request_id=''):
    """构造一个 HITL 请求（dict，JSON 可序列化）。"""
    value = kind.value if isinstance(kind, RequestKind) else str(kind)
    body = dict(payload or {})
    if risk is None:
        grade = risk_of(value, body)
    else:
        grade = risk.value if isinstance(risk, Risk) else str(risk)
    return {
        'request_id': str(request_id or ''),
        'kind': value,
        'payload': body,
        'risk': grade,
        'timeout': int(DEFAULT_TIMEOUT_SECONDS if timeout is None else timeout),
        'created_at': int(time.time()),
    }


def decide(decision, payload=None):
    """构造一个决策；未知决策直接报错。"""
    value = decision.value if isinstance(decision, Decision) else str(decision)
    if value not in _DECISION_VALUES:
        raise ValueError('未知决策：%r' % value)
    return {'decision': value, 'payload': dict(payload or {})}


def auto_decision(request):
    """低风险自动放行；高风险返回 None（必须等人工）。"""
    if str((request or {}).get('risk') or '') == Risk.LOW.value:
        return decide(Decision.APPROVE)
    return None


def expired(request, *, now=None):
    """超时竞速：``now - created_at >= timeout`` 即过期；没有 created_at 视为未过期。"""
    created = int((request or {}).get('created_at') or 0)
    if not created:
        return False
    timeout = int((request or {}).get('timeout') or DEFAULT_TIMEOUT_SECONDS)
    moment = time.time() if now is None else float(now)
    return (moment - created) >= timeout


def timeout_decision():
    """超时默认策略：拒绝（让用户重来，而不是悄悄放行不可逆动作）。"""
    return decide(Decision.TIMEOUT)


def apply_decision(request, decision):
    """把决策落到请求副本上；EDIT/携带 payload 时合并进 ``payload``（选择卡回填选中项）。"""
    kind = str((decision or {}).get('decision') or '')
    if kind not in _DECISION_VALUES:
        raise ValueError('未知决策：%r' % kind)
    out = dict(request)
    out['decision'] = kind
    extra = dict((decision or {}).get('payload') or {})
    if kind == Decision.EDIT.value or extra:
        out['payload'] = dict(request.get('payload') or {}, **extra)
    return out


def from_confirm_result(result, *, timeout=None):
    """把 ``confirm_gates.run()`` 的 ``ask`` 结果转成选择卡请求；无待确认返回 None。"""
    if not isinstance(result, dict):
        return None
    items = tuple(result.get('ask') or ())
    if not items:
        return None
    candidates = []
    for item in items:
        candidates.append(dict(item) if isinstance(item, dict) else {'label': str(item)})
    return make_request(RequestKind.CHOICE,
                        {'gate_id': str(result.get('gate_id') or ''),
                         'title': str(result.get('title') or ''),
                         'candidates': candidates},
                        timeout=timeout)


def _choice_label(line):
    """一行选项 → 可显示的标签：去列表记号、去成对中英文引号。"""
    value = str(line or '').strip()
    previous = None
    while value and previous != value:
        previous = value
        value = _CHOICE_BULLET.sub('', value, count=1).strip()
    for left, right in _CHOICE_QUOTES:
        if len(value) >= 2 and value.startswith(left) and value.endswith(right):
            value = value[1:-1].strip()
            break
    return value


def parse_choice_reply(text):
    """拆出回复末尾的 ```choices 标记段。

    返回 ``{'text': 显示正文, 'candidates': [...], 'truncated': bool, 'open': bool}``。
    完整标记段从正文剥离；未闭合的标记段连同其后文字一起隐藏，``open`` 为 True。
    没有标记时原样返回正文，行为不变。
    """
    raw = str(text or '')
    lines = raw.splitlines(True)
    kept = []
    blocks = []
    opened = False
    index = 0
    while index < len(lines):
        line = lines[index]
        bare = line.rstrip('\r\n')
        if _CHOICE_OPEN.match(bare):
            body = []
            end = index + 1
            while end < len(lines) and not _CHOICE_CLOSE.match(lines[end].rstrip('\r\n')):
                body.append(lines[end])
                end += 1
            if end < len(lines):
                blocks.append(''.join(body))
                index = end + 1
                continue
            opened = True
            index = len(lines)
            continue
        if index == len(lines) - 1 and _CHOICE_PARTIAL.match(bare):
            opened = True
            index += 1
            continue
        kept.append(line)
        index += 1
    has_marker = bool(blocks) or opened
    display = ''.join(kept)
    if has_marker:
        display = display.rstrip()
    candidates = []
    for line in (blocks[-1].splitlines() if blocks else ()):
        label = _choice_label(line)
        if label:
            candidates.append(label)
    return {'text': display, 'candidates': candidates,
            'truncated': len(candidates) > MAX_CHOICES, 'open': opened}

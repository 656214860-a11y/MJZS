# -*- coding: utf-8 -*-
"""聊天消息的 typed parts 契约（L0）：一条消息 = 有序的类型化 part 列表。

借鉴 Vercel AI SDK 的 ``UIMessage.parts`` 数组与 Anthropic content blocks：
把 text / reasoning / tool_call / tool_result / source / file / artifact / data
统一成同一层抽象，供 01 创意对话气泡与 02–13 产物卡片共用。理由见
``程序/tasks_round/文件卡片与HITL交互任务书.md`` §2.2。

本模块只做数据契约与纯函数转换：不 import Tk、不发网络、不读写盘。持久化仍是
``domain.idea_transcript`` 的职责；落盘形态是「行 dict + ``parts`` 列表」，文件级
``schema_version`` 标识版本（从 v2 起一条消息必须带 ``parts``）。

折中口径（R3102）：旧行只有扁平 ``text``；读入时补 ``parts``（正文 → TEXT part，
旧 ``thinking``／``reasoning`` → REASONING part），写入时统一带 ``parts``。
``text`` 字段继续保留并作为正文的唯一投影，避免现有消费者与 556 个测试面同时改口径。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable

VERSION_KEY = 'schema_version'
SCHEMA_VERSION = 2


class PartType(str, Enum):
    TEXT = 'text'
    REASONING = 'reasoning'
    TOOL_CALL = 'tool_call'
    TOOL_RESULT = 'tool_result'
    SOURCE = 'source'
    FILE = 'file'
    ARTIFACT = 'artifact'
    DATA = 'data'


class PartState(str, Enum):
    PENDING = 'pending'
    STREAMING = 'streaming'
    DONE = 'done'
    ERROR = 'error'
    ABORTED = 'aborted'


class ArtifactKind(str, Enum):
    TEXT = 'text'
    CODE = 'code'
    IMAGE = 'image'
    SHEET = 'sheet'
    AUDIO = 'audio'
    VIDEO = 'video'
    JSON = 'json'


_TEXT_KINDS = (PartType.TEXT.value, PartType.REASONING.value)


@dataclass
class Artifact:
    """产物卡片的稳定标识：``kind`` + ``identifier`` 定位同一产物的多版本。"""
    kind: str
    identifier: str
    title: str = ''
    meta: dict = field(default_factory=dict)


@dataclass
class Document:
    """复合主键版本化：同一 ``id`` 的多次写入按 ``created_at`` 排序取版本。"""
    id: str
    created_at: str = ''
    content: str = ''
    meta: dict = field(default_factory=dict)


@dataclass
class Part:
    type: str
    payload: dict = field(default_factory=dict)
    state: str = PartState.DONE.value

    def text(self) -> str:
        return str(self.payload.get('text') or '')


@dataclass
class Message:
    id: str
    role: str
    created_at: str
    parts: list = field(default_factory=list)

    def text(self) -> str:
        return text_of(self.parts)


def part(kind, payload=None, state=None):
    """构造一个 part dict；``kind`` 可以是 ``PartType`` 或字符串。"""
    value = kind.value if isinstance(kind, PartType) else str(kind)
    return {'type': value,
            'payload': dict(payload or {}),
            'state': (state.value if isinstance(state, PartState) else str(state)) if state else PartState.DONE.value}


def text_part(text, state=None):
    return part(PartType.TEXT, {'text': str(text)}, state)


def reasoning_part(text, state=None):
    return part(PartType.REASONING, {'text': str(text)}, state)


def _valid_parts(value):
    return (isinstance(value, list)
            and all(isinstance(item, dict) and str(item.get('type') or '').strip() for item in value))


def _part_text(item):
    return str((item.get('payload') or {}).get('text') or '')


def parts_of(row):
    """返回一行的 parts 列表（缺失时按扁平字段派生，不落盘）。"""
    if not isinstance(row, dict):
        return []
    value = row.get('parts')
    return list(value) if _valid_parts(value) else derive_parts(row)


def has_parts(row):
    return isinstance(row, dict) and _valid_parts(row.get('parts'))


def derive_parts(row):
    """从扁平行派生 parts：REASONING（旧 thinking/reasoning）在前，TEXT 正文在后。"""
    if not isinstance(row, dict):
        return []
    parts = []
    thinking = row.get('thinking')
    if not isinstance(thinking, str) or not thinking.strip():
        thinking = row.get('reasoning')
    if isinstance(thinking, str) and thinking.strip():
        parts.append(reasoning_part(thinking))
    text = row.get('text')
    if isinstance(text, str) and text.strip():
        parts.append(text_part(text))
    return parts


def ensure_parts(row):
    """返回补好 ``parts`` 的行副本；已有合法 parts 时原样保留。"""
    if not isinstance(row, dict):
        return row
    out = dict(row)
    if not _valid_parts(out.get('parts')):
        out['parts'] = derive_parts(out)
    return out


def set_text(row, text):
    """改写平铺正文，并同步唯一 TEXT part（不触碰 reasoning/工具等其它 part）。"""
    out = ensure_parts(row)
    value = str(text)
    out['text'] = value
    rest = [item for item in out['parts'] if item.get('type') != PartType.TEXT.value]
    out['parts'] = rest + ([text_part(value)] if value.strip() else [])
    return out


def message_from_row(row):
    if not isinstance(row, dict):
        raise TypeError('消息行必须是 dict')
    return Message(id=str(row.get('at') or ''), role=str(row.get('role') or ''),
                   created_at=str(row.get('at') or ''), parts=parts_of(row))


def row_from_message(message, **extra):
    if not isinstance(message, Message):
        raise TypeError('message 必须是 Message')
    row = dict(extra)
    row.update({'role': str(message.role), 'text': message.text(),
                'at': str(message.created_at), 'parts': list(message.parts)})
    return row


def text_of(parts):
    return ''.join(_part_text(item) for item in (parts or [])
                   if isinstance(item, dict) and item.get('type') == PartType.TEXT.value)


def reasoning_of(parts):
    return ''.join(_part_text(item) for item in (parts or [])
                   if isinstance(item, dict) and item.get('type') == PartType.REASONING.value)


def _part_has_content(item):
    if not isinstance(item, dict):
        return False
    kind = str(item.get('type') or '')
    payload = item.get('payload') if isinstance(item.get('payload'), dict) else {}
    if kind in _TEXT_KINDS:
        return bool(str(payload.get('text') or '').strip())
    return bool(payload)


def has_content(row):
    """一行是否有可展示内容：正文或任一有内容的 part。"""
    if not isinstance(row, dict):
        return False
    if str(row.get('text') or '').strip():
        return True
    return any(_part_has_content(item) for item in (row.get('parts') or []))


def artifact_from_part(item):
    """从 ARTIFACT part 取出 ``Artifact``；不是产物 part 时返回 None。"""
    if not isinstance(item, dict) or item.get('type') != PartType.ARTIFACT.value:
        return None
    payload = item.get('payload') if isinstance(item.get('payload'), dict) else {}
    return Artifact(kind=str(payload.get('kind') or ArtifactKind.TEXT.value),
                    identifier=str(payload.get('identifier') or ''),
                    title=str(payload.get('title') or ''),
                    meta=dict(payload.get('meta') or {}))

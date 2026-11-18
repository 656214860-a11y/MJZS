# -*- coding: utf-8 -*-
"""结构化业务日志：``log_event(kind, **fields)``（L1 基础设施）。

现状 ``domain/`` 里 38 条日志全部只有中文单参数、0 个业务字段，出了事只能靠猜。
本模块是唯一入口：调用方给事件类别与白名单字段，落一条带业务上下文的结构化记录，
字段至少覆盖 stage／shot_id／asset_id／cost_ms／outcome。

硬边界：**不得写入用户项目内容、密钥或绝对路径**——字段值只允许标识符、枚举、
计数与耗时；错误原文、提示词、文件名等自由文本一律不进 ``fields``。
``FIELDS`` 是允许出现在 ``fields`` 里的键集合，新增字段须先在这里登记。

落盘口径（任务书轮 7 定稿）：

- 走 ``logging.getLogger("business")``，与 ``app_logging`` 的 perf／swallowed／
  crash／startup 同一根处理器，随 ``logs/app.log`` 滚动落盘；记录 message 是一行
  JSON：``{"kind": ..., <白名单字段按键名排序>, "dropped_fields": [...]?}``。
- **白名单外字段一律丢弃**，并把字段名记进 ``dropped_fields``（只记名字不记值，
  名字同样过安全字符集）；白名单字段的值未过校验同样丢弃并记名。选择「丢弃＋
  留名」而非抛 ``ValueError``：日志设施绝不能弄崩业务，登记遗漏在日志里可见即可。
- **字段值只允许 ``[A-Za-z0-9_.-]`` 形态的短标识符／枚举**（≤96 字符）：stage 键、
  镜头号、资产号、outcome 枚举都在此形态内；含空白、路径分隔符、盘符、URL、
  中文自由文本的一律判为不安全丢弃。``cost_ms`` 只收 int／float（bool 除外）且
  必须有限，统一输出为保留 1 位小数的毫秒数。调用方**不得**传自由文本——实现侧
  只做形态兜底，语义约束靠本 docstring 与评审。
- ``kind`` 是调用方给的事件类别枚举（如 ``recon.run``、``white_model.migrate``），
  同样只允许安全字符集（≤120 字符），不合法时降级为 ``"unknown"``。
- **绝不失败**：本函数自身任何异常都吞掉（``app_logging.swallowed`` 留痕），
  日志设施绝不能弄崩业务。
"""
from __future__ import annotations

import json
import logging
import math
import re

import infra.app_logging as app_logging

# fields 白名单：只允许这些键携带业务上下文，防止项目内容／密钥混进日志。
FIELDS = frozenset({"stage", "shot_id", "asset_id", "cost_ms", "outcome"})

_LOGGER_NAME = "business"
_MAX_TEXT = 96      # stage／shot_id／asset_id／outcome 等标识符值长度上限
_MAX_KIND = 120     # kind 事件类别长度上限
_MAX_DROPPED = 8    # 单条记录最多列出的丢弃字段名数量
_SAFE_VALUE = re.compile(r"[A-Za-z0-9_.\-]+")
_SAFE_NAME = re.compile(r"[^A-Za-z0-9_.\-]")

_logger = logging.getLogger(_LOGGER_NAME)
if _logger.level == logging.NOTSET:
    # 业务事件是 INFO 级运行事实；install() 之前（或根级别被调高时）也要能落盘。
    _logger.setLevel(logging.INFO)


def _clean_text(value) -> str | None:
    """标识符／枚举值：仅安全字符集短文本；None、bool、数字与一切可疑形态返回 None。"""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return None  # 数字只允许走 cost_ms；其它字段传数字视为调用方口径错误
    text = str(value).strip()
    if not text or len(text) > _MAX_TEXT or not _SAFE_VALUE.fullmatch(text):
        return None
    return text


def _clean_ms(value):
    """耗时字段：只收有限 int／float（bool 除外），统一成保留 1 位小数的毫秒。"""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    if not math.isfinite(number):
        return None
    return round(number, 1)


def _clean_kind(kind) -> str:
    text = str(kind or "").strip()
    if len(text) <= _MAX_KIND and _SAFE_VALUE.fullmatch(text):
        return text
    return "unknown"


def _clean_dropped_name(name) -> str:
    """丢弃字段名只作排障线索：非安全字符折叠为 ``_`` 并截断，绝不携带原值。"""
    return _SAFE_NAME.sub("_", str(name))[:40] or "?"


def _write_payload(kind, fields) -> None:
    payload = {"kind": _clean_kind(kind)}
    clean, dropped = {}, []
    for key, value in dict(fields).items():
        name = str(key)
        if name == "cost_ms":
            number = _clean_ms(value)
            if number is None:
                dropped.append(name)
            else:
                clean[name] = number
        elif name in FIELDS:
            text = _clean_text(value)
            if text is None:
                dropped.append(name)
            else:
                clean[name] = text
        else:
            dropped.append(name)
    for key in sorted(clean):
        payload[key] = clean[key]
    if dropped:
        payload["dropped_fields"] = sorted({_clean_dropped_name(name)
                                            for name in dropped})[:_MAX_DROPPED]
    _logger.info(json.dumps(payload, ensure_ascii=False))


def log_event(kind: str, **fields) -> None:
    """记录一条结构化业务事件；任何失败都吞掉并留痕，绝不向上抛。

    ``kind`` 为事件类别枚举；``fields`` 只允许 ``FIELDS`` 白名单键，值只允许
    标识符／枚举／计数／耗时（见模块 docstring）。白名单外字段丢弃并在记录的
    ``dropped_fields`` 里留名；值未过安全校验同样丢弃。
    """
    try:
        _write_payload(kind, fields)
    except Exception:
        app_logging.swallowed("business_log.log_event")

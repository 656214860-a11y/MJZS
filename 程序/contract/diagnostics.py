# -*- coding: utf-8 -*-
"""L0 启动诊断类型：``Severity``／``Diagnostic``／``StartupPhase``（任务书 D3，Q2/Q12/G3）。

分级协议：甲类（代码 bug，Q6 清单）fail-closed，乙类（用户环境，Q7 清单）
fail-open＋可见警告。本模块只放类型与常量，不 import 任何项目模块；
检查函数由 L1 提供、L5 组装后注入 ``contract.selfcheck.run()``。

``Diagnostic`` 的信息结构抄 ComfyUI 失败分级三段式（任务书 §3c-1）：
``code`` 是固定闭集的类别码（kind），``message`` 是「发生了什么」（what），
``remedy`` 是「怎么办」（fix），``escape_hint`` 是一条逃生通道（可空）。
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Severity(str, Enum):
    """诊断严重度闭集（K8 统一后五值：fatal/error/warn/degraded/info）。

    ``FATAL`` 拦住启动（甲类 fail-closed）；``ERROR``／``WARN``／``DEGRADED``／``INFO``
    由启动器按 Q2 策略放行或降级播报，具体出口在轮 3B 接线。
    ``contract.error_codes.ErrorCode.severity`` 与本枚举同词表（K8），
    旧 error_codes 的 ``recoverable`` 一律映射为 ``WARN``，可重试与否只读 ``retryable``。
    """

    FATAL = 'fatal'
    ERROR = 'error'
    WARN = 'warn'
    DEGRADED = 'degraded'
    INFO = 'info'


class StartupPhase(str, Enum):
    """启动阶段闭集（诊断报告 §6.1）：契约 → 配置 → 资源 → 界面外壳 → 就绪。"""

    CONTRACT = 'contract'
    CONFIG = 'config'
    RESOURCE = 'resource'
    UI_SHELL = 'ui_shell'
    READY = 'ready'


@dataclass(frozen=True)
class Diagnostic:
    """一条启动诊断。

    ``scope`` 标明产出该诊断的范围（自检内建项用 ``StartupPhase`` 值，
    注入检查自定，运行器自身异常用 ``'selfcheck'``）；``code`` 是固定闭集
    类别码，由产出方在模块内登记，不收自由文本；``escape_hint`` 可空。
    """

    severity: Severity
    scope: str
    code: str
    message: str
    remedy: str = ''
    escape_hint: str = ''

    def __post_init__(self):
        # severity 归一到枚举闭集：接受 'fatal' 等字符串，非法值当场拒绝。
        object.__setattr__(self, 'severity', Severity(self.severity))

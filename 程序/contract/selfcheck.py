# -*- coding: utf-8 -*-
"""L0 启动自检运行器：``run(checks)`` 逐项执行注入的检查并汇总 ``Diagnostic``。

分层（任务书 G3/Q12）：本模块只放运行器与 L0 自己能做的检查
（``default_checks()``：阶段契约、产物登记自洽）；L1 环境检查函数
由 L1 提供、L5 启动器组装后注入，L0 不为自检新增任何向上 import。

检查函数契约：返回 ``None``（通过）、单个 ``Diagnostic`` 或
``Diagnostic`` 序列；序列元素必须全是 ``Diagnostic``。检查自身抛异常
或返回值形状不符都记一条 DEGRADED（G5），**永不升级为 FATAL**，
其余检查照常执行——诊断器自己崩了不能掩盖原始启动失败（§3b-1 同旨）。

``run()`` 不扫描目录、不联网、不读用户项目；甲类「契约模块 import
失败」不靠本运行器发现，由轮 3B 的启动器保护负责。
"""
from __future__ import annotations

from collections import abc

from contract.diagnostics import Diagnostic, Severity, StartupPhase

# 本模块产出诊断的固定闭集类别码（§3c-1 的 kind 闭集）；注入检查各自
# 在自己的模块内登记码表，这里只管 L0 内建项与运行器自身异常。
CODE_STAGE_CONTRACT = 'stage-contract'
CODE_ARTIFACT_REGISTRY = 'artifact-registry'
CODE_CHECK_ERROR = 'check-error'

_SCOPE_SELF = 'selfcheck'


def _check_name(check) -> str:
    return getattr(check, '__name__', None) or type(check).__name__


def _check_error(check, exc: BaseException) -> Diagnostic:
    return Diagnostic(
        severity=Severity.DEGRADED,
        scope=_SCOPE_SELF,
        code=CODE_CHECK_ERROR,
        message='自检项 %s 自身异常：%s' % (_check_name(check), exc),
        remedy='该异常不阻断启动；请连同启动日志反馈给开发者',
    )


def _normalize(check, result) -> tuple[Diagnostic, ...]:
    """把检查返回值收成 Diagnostic 元组；形状不符抛 TypeError 由 run 记 DEGRADED。"""
    if result is None:
        return ()
    if isinstance(result, Diagnostic):
        return (result,)
    if isinstance(result, str) or not isinstance(result, abc.Iterable):
        raise TypeError('自检项返回值须为 None／Diagnostic／Diagnostic 序列，'
                        '实得 %s' % type(result).__name__)
    items = tuple(result)
    for item in items:
        if not isinstance(item, Diagnostic):
            raise TypeError('自检项返回序列含非 Diagnostic 项：%s'
                            % type(item).__name__)
    return items


def run(checks: abc.Iterable[abc.Callable[[], object]]) -> list[Diagnostic]:
    """逐项执行 ``checks`` 中的可调用对象，按序返回 ``Diagnostic`` 列表（空＝全绿）。

    ``checks`` 是调用方传入的可调用对象序列（G3：L1 提供、L5 组装注入），
    不是本模块自带集合——L0 内建检查经 ``default_checks()`` 一并注入。
    """
    found = []
    for check in checks:
        try:
            items = _normalize(check, check())
        except Exception as exc:  # 检查自身异常／返回值非法：G5 记 DEGRADED 不中断
            items = (_check_error(check, exc),)
        found.extend(items)
    return found


def _fatal(scope: str, code: str, message: str, remedy: str) -> Diagnostic:
    return Diagnostic(severity=Severity.FATAL, scope=scope, code=code,
                      message=message, remedy=remedy)


def _stage_contract_check() -> list[Diagnostic]:
    """甲类（Q6「阶段契约撕裂」）：``stage_layout`` 与 ``pet_bus.STAGES`` 不一致 → FATAL。"""
    from contract import stage_layout
    remedy = '阶段目录契约与运行时阶段表不一致，属代码缺陷；请升级程序或修复后重启'
    return [_fatal(StartupPhase.CONTRACT.value, CODE_STAGE_CONTRACT, error, remedy)
            for error in stage_layout.stage_contract_errors()]


def _artifact_registry_check() -> list[Diagnostic]:
    """甲类（Q6「产物版本登记不一致」）：``artifact_schema.REGISTRY`` 每项须有
    ``version``／``required``／``owner`` 且取值自洽 → FATAL。"""
    from contract import artifact_schema
    remedy = '产物版本登记不完整，属代码缺陷；请升级程序或修复 artifact_schema 后重启'
    problems = []
    for kind in sorted(artifact_schema.REGISTRY):
        spec = artifact_schema.REGISTRY[kind]
        if not isinstance(spec, dict):
            problems.append('%s 的登记项不是对象：%s' % (kind, type(spec).__name__))
            continue
        missing = [key for key in ('version', 'required', 'owner') if key not in spec]
        if missing:
            problems.append('%s 缺少登记字段：%s' % (kind, ', '.join(missing)))
        elif not isinstance(spec['version'], int) or spec['version'] < 1:
            problems.append('%s 的 version 必须是正整数，实得 %r'
                            % (kind, spec['version']))
        elif not isinstance(spec['required'], (tuple, list)) or not all(
                isinstance(key, str) and key for key in spec['required']):
            problems.append('%s 的 required 必须是非空字符串元组' % kind)
        elif not spec['owner']:
            problems.append('%s 的 owner 不能为空' % kind)
    return [_fatal(StartupPhase.CONTRACT.value, CODE_ARTIFACT_REGISTRY,
                   problem, remedy) for problem in problems]


def default_checks() -> tuple[abc.Callable[[], list[Diagnostic]], ...]:
    """L0 自带检查项（甲类两项）；L5 组装启动自检时与 L1 检查一并注入 ``run()``。"""
    return (_stage_contract_check, _artifact_registry_check)

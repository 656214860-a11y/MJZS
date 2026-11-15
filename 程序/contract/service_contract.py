"""L2 写服务的统一结果与失败分类契约。

调用方仅依据 ``ok`` 与结果类型决定展示、日志或取消收尾；服务不再以
裸布尔值、字符串或元组表达业务结果。``Cancelled`` 不是失败，即使它
的 ``ok`` 为假（因为操作没有产生可交付数据）。
"""
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ServiceResult:
    """一次服务操作的可观察结果。"""

    ok: bool
    reason: str = ''
    recoverable: bool = False
    data: Any = None


class UserError(ServiceResult):
    """用户可直接理解并修正的输入或前置条件错误。"""

    def __init__(self, reason: str, *, recoverable: bool = True, data: Any = None):
        super().__init__(False, reason, recoverable, data)


class SystemError(ServiceResult):
    """已记录细节、但 UI 只应展示通用提示的运行环境错误。"""

    def __init__(self, reason: str, *, recoverable: bool = True, data: Any = None):
        super().__init__(False, reason, recoverable, data)


class Cancelled(ServiceResult):
    """用户或编排取消；调用方不得把它计入失败或触发回滚。"""

    def __init__(self, reason: str = '操作已取消', *, data: Any = None):
        super().__init__(False, reason, True, data)


def success(data: Any = None, reason: str = '') -> ServiceResult:
    """构造成功结果，避免 L2 写服务返回裸业务数据。"""
    return ServiceResult(True, reason, False, data)


def is_failure(result: ServiceResult) -> bool:
    """取消不属于失败；供 L3 编排的重试／回滚判断复用。"""
    return not result.ok and not isinstance(result, Cancelled)

"""L0 结果契约：L2 写服务结果与 SKILL 工具执行结果。

写服务调用方仅依据 ``ok`` 与结果类型决定展示、日志或取消收尾；服务不再以
裸布尔值、字符串或元组表达业务结果。``Cancelled`` 不是失败，即使它
的 ``ok`` 为假（因为操作没有产生可交付数据）。SKILL 工具执行器统一返回
``ToolResult``，让 L3 编排不识别任何 UI 层异常类型。
"""
from dataclasses import dataclass
from typing import Any, Optional


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


# ── SKILL 工具执行协议（L0） ────────────────────────────────────────────────
# 编排层只消费这些闭集状态；「等付费确认」「预算不足」是编排结果，不属于
# 单次工具调用的结果，因此不放进这张表。
TOOL_DONE = 'done'
TOOL_PAGE = 'page'
TOOL_INPUT = 'input'
TOOL_FAILED = 'failed'
TOOL_MISSING = 'missing'
TOOL_STATUSES = (TOOL_DONE, TOOL_PAGE, TOOL_INPUT, TOOL_FAILED, TOOL_MISSING)


@dataclass(frozen=True)
class ToolResult:
    """一次 SKILL 工具调用的层间结果。

    ``data`` 只装业务输出；``page``／``page_title``／``hint`` 只在 ``page``
    状态下有意义。L4 负责把异常或页面动作适配成本对象，L3 不识别 UI 异常类。
    """

    status: str
    detail: str = ''
    data: Any = None
    page: Optional[int] = None
    page_title: str = ''
    hint: str = ''
    tool: str = ''

    def __post_init__(self) -> None:
        if self.status not in TOOL_STATUSES:
            raise ValueError('未知工具执行状态：%s' % self.status)


def tool_done(data: Any = None, *, detail: str = '', tool: str = '') -> ToolResult:
    return ToolResult(TOOL_DONE, detail=detail, data=data, tool=tool)


def _page_number(value: Any) -> Optional[int]:
    """把兼容输入收敛成非负页码；认不出的历史值返回 ``None``。"""
    if value in (None, ''):
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        page = value
    elif isinstance(value, float) and value.is_integer():
        page = int(value)
    elif isinstance(value, str):
        text = value.strip()
        if not text.isdigit():
            return None
        page = int(text)
    else:
        return None
    return page if page >= 0 else None


def tool_needs_page(page: int, *, title: str = '', hint: str = '', detail: str = '',
                    tool: str = '') -> ToolResult:
    page_number = _page_number(page)
    if page_number is None:
        raise ValueError('非法工具页面序号：%r' % (page,))
    return ToolResult(TOOL_PAGE, detail=detail, page=page_number, page_title=title,
                      hint=hint, tool=tool)


def tool_needs_input(detail: str, *, tool: str = '') -> ToolResult:
    return ToolResult(TOOL_INPUT, detail=str(detail), tool=tool)


def tool_failed(detail: str, *, tool: str = '', data: Any = None) -> ToolResult:
    return ToolResult(TOOL_FAILED, detail=str(detail), data=data, tool=tool)


def tool_missing(detail: str, *, tool: str = '') -> ToolResult:
    return ToolResult(TOOL_MISSING, detail=str(detail), tool=tool)


def coerce_tool_result(value: Any, *, tool: str = '') -> ToolResult:
    """把执行器返回值收敛为 ``ToolResult``；普通业务 dict 视为 done 的 ``data``。"""
    if isinstance(value, ToolResult):
        return value
    if isinstance(value, dict):
        status = str(value.get('status') or '')
        if status in TOOL_STATUSES:
            return ToolResult(status,
                              detail=str(value.get('detail') or ''),
                              data=value.get('data'),
                              page=_page_number(value.get('page')),
                              page_title=str(value.get('pageTitle') or value.get('page_title') or ''),
                              hint=str(value.get('hint') or ''),
                              tool=str(value.get('tool') or tool))
        return tool_done(value, tool=tool)
    return tool_done({'value': value}, tool=tool)

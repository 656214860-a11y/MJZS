"""L0 统一错误码注册表：日志、UI、交付报告与 HTTP 客户端共用同一套码。

每个码带严重度、可重试标记、用户可读说明与修复建议；``lookup`` 对未登记的码返回 ``E-UNKNOWN``，
调用方不必处理 ``KeyError``。``analyze()`` 是 Spring Boot ``FailureAnalyzer`` 式派发链：
按序遍历 analyzer、首个非 ``None`` 结果胜出，诊断器自身异常被吞掉继续下一条——
诊断器崩了不能掩盖原始失败（任务书 §3b-1）。
"""
from dataclasses import dataclass
from typing import Any, Callable

# 错误码严重度闭集（任务书 §3b-1）：fatal＝不可继续；degraded＝相关功能降级；
# recoverable＝按 remedy 修复后可重试；info＝仅提示无需处置。
SEVERITIES = frozenset({'fatal', 'degraded', 'recoverable', 'info'})


@dataclass(frozen=True)
class ErrorCode:
    code: str
    severity: str
    retryable: bool
    user_message: str
    remedy: str

    def __post_init__(self):
        if self.severity not in SEVERITIES:
            raise ValueError('未登记的错误码严重度：%r' % self.severity)


_ITEMS = (
    ErrorCode('E-UNKNOWN', 'recoverable', False, '发生了未分类的错误', '查看日志中的详细信息后重试'),
    ErrorCode('E-NET-TIMEOUT', 'recoverable', True, '网络请求超时', '检查网络或稍后重试'),
    ErrorCode('E-NET-UNREACHABLE', 'recoverable', True, '无法连接到服务', '检查网络、代理和服务地址'),
    ErrorCode('E-NET-RATE-LIMIT', 'recoverable', True, '请求过于频繁，服务限流', '稍等片刻后重试，或降低并发'),
    ErrorCode('E-NET-SERVER', 'recoverable', True, '远端服务暂时不可用', '稍后重试，持续失败请检查服务状态'),
    ErrorCode('E-NET-CLIENT', 'recoverable', False, '请求被服务拒绝', '检查请求参数、模型名与权限'),
    ErrorCode('E-AUTH-MISSING', 'recoverable', False, '缺少凭据', '在模型管理中配置对应密钥'),
    ErrorCode('E-AUTH-REJECTED', 'recoverable', False, '凭据被服务拒绝', '检查密钥是否有效、是否过期'),
    ErrorCode('E-ASSET-MISSING', 'recoverable', False, '缺少必需的资产文件', '在资产管理中补齐后重试'),
    ErrorCode('E-FILE-NOT-FOUND', 'recoverable', False, '文件不存在', '确认路径，文件是否被移动或删除'),
    ErrorCode('E-FILE-TOO-LARGE', 'recoverable', False, '文件超过允许的大小上限', '压缩或拆分文件后重试'),
    ErrorCode('E-PATH-UNSAFE', 'recoverable', False, '路径越界，已拒绝', '只使用项目目录内的文件'),
    ErrorCode('E-CONTRACT-VIOLATION', 'degraded', False, '产物不符合契约', '按报告中的字段修正后重新生成'),
    ErrorCode('E-STAGE-BLOCKED', 'recoverable', False, '前置阶段未完成，当前阶段被阻塞', '先完成并确认上一阶段'),
    ErrorCode('E-CANCELLED', 'info', False, '操作已取消', '无需处理，需要时重新发起'),
    ErrorCode('E-IO-WRITE', 'recoverable', True, '写入文件失败', '检查磁盘空间与目录权限'),
    ErrorCode('E-TOOL-MISSING', 'degraded', False, '缺少外部工具', '在配置中指定 ffmpeg 等工具路径'),
)

CODES: dict[str, ErrorCode] = {item.code: item for item in _ITEMS}


def lookup(code: str) -> ErrorCode:
    return CODES.get(str(code or ''), CODES['E-UNKNOWN'])


def describe(code: str) -> str:
    item = lookup(code)
    return f'[{item.code}] {item.user_message}（建议：{item.remedy}）'


def code_data(code: str, **extra: Any) -> dict[str, Any]:
    """放进 ``ServiceResult.data`` 的错误码载荷；保持四字段结果契约不变。"""
    return {'error_code': lookup(code).code, **extra}


def code_of(result: Any) -> str:
    """从 ``ServiceResult`` 取错误码；没有则返回空串。"""
    data = getattr(result, 'data', None)
    return str(data.get('error_code', '')) if isinstance(data, dict) else ''


_CLASS_TO_CODE = {'auth': 'E-AUTH-REJECTED', 'server': 'E-NET-SERVER', 'client': 'E-NET-CLIENT',
                  'network': 'E-NET-UNREACHABLE', 'protocol': 'E-NET-CLIENT'}


def from_http_result(result: dict[str, Any]) -> str:
    """把 ``api_endpoints._http_transport`` 的结果字典映射为错误码；成功返回空串。"""
    if result.get('ok'):
        return ''
    if result.get('status') == 429:
        return 'E-NET-RATE-LIMIT'
    text = str(result.get('error', '')).lower()
    if result.get('error_class') == 'network' and ('timed out' in text or 'timeout' in text):
        return 'E-NET-TIMEOUT'
    return _CLASS_TO_CODE.get(result.get('error_class', ''), 'E-UNKNOWN')


# FailureAnalyzer 派发链（§3b-1）：analyzer 返回 ErrorCode 或 None，首个非 None 胜出。
Analyzer = Callable[[Exception], 'ErrorCode | None']


def analyze(failure: Exception, analyzers: tuple[Analyzer, ...]) -> ErrorCode:
    """按序遍历 ``analyzers``，返回首个非 ``None`` 的 ``ErrorCode``；全落空返回 ``E-UNKNOWN``。

    某个 analyzer 自身抛异常时吞掉继续下一条——诊断器崩了不能掩盖
    ``failure`` 这个原始错误；``failure`` 本身不被本函数修改或吞没。
    """
    for fn in analyzers:
        try:
            hit = fn(failure)
        except Exception:
            continue
        if hit is not None:
            return hit
    return lookup('E-UNKNOWN')

"""L0 统一错误码注册表：日志、UI、交付报告与 HTTP 客户端共用同一套码。

每个码带可重试标记、用户可读说明与修复建议；``lookup`` 对未登记的码返回 ``E-UNKNOWN``，
调用方不必处理 ``KeyError``。
"""
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ErrorCode:
    code: str
    retryable: bool
    user_message: str
    remedy: str


_ITEMS = (
    ErrorCode('E-UNKNOWN', False, '发生了未分类的错误', '查看日志中的详细信息后重试'),
    ErrorCode('E-NET-TIMEOUT', True, '网络请求超时', '检查网络或稍后重试'),
    ErrorCode('E-NET-UNREACHABLE', True, '无法连接到服务', '检查网络、代理和服务地址'),
    ErrorCode('E-NET-RATE-LIMIT', True, '请求过于频繁，服务限流', '稍等片刻后重试，或降低并发'),
    ErrorCode('E-NET-SERVER', True, '远端服务暂时不可用', '稍后重试，持续失败请检查服务状态'),
    ErrorCode('E-NET-CLIENT', False, '请求被服务拒绝', '检查请求参数、模型名与权限'),
    ErrorCode('E-AUTH-MISSING', False, '缺少凭据', '在模型管理中配置对应密钥'),
    ErrorCode('E-AUTH-REJECTED', False, '凭据被服务拒绝', '检查密钥是否有效、是否过期'),
    ErrorCode('E-ASSET-MISSING', False, '缺少必需的资产文件', '在资产管理中补齐后重试'),
    ErrorCode('E-FILE-NOT-FOUND', False, '文件不存在', '确认路径，文件是否被移动或删除'),
    ErrorCode('E-FILE-TOO-LARGE', False, '文件超过允许的大小上限', '压缩或拆分文件后重试'),
    ErrorCode('E-PATH-UNSAFE', False, '路径越界，已拒绝', '只使用项目目录内的文件'),
    ErrorCode('E-CONTRACT-VIOLATION', False, '产物不符合契约', '按报告中的字段修正后重新生成'),
    ErrorCode('E-STAGE-BLOCKED', False, '前置阶段未完成，当前阶段被阻塞', '先完成并确认上一阶段'),
    ErrorCode('E-CANCELLED', False, '操作已取消', '无需处理，需要时重新发起'),
    ErrorCode('E-IO-WRITE', True, '写入文件失败', '检查磁盘空间与目录权限'),
    ErrorCode('E-TOOL-MISSING', False, '缺少外部工具', '在配置中指定 ffmpeg 等工具路径'),
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

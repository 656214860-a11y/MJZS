"""L0 统一错误码注册表：日志、UI、交付报告与 HTTP 客户端共用同一套码。

每个码带严重度、可重试标记、用户可读说明与修复建议；``lookup`` 对未登记的码返回 ``E-UNKNOWN``，
调用方不必处理 ``KeyError``。``analyze()`` 是 Spring Boot ``FailureAnalyzer`` 式派发链：
按序遍历 analyzer、首个非 ``None`` 结果胜出，诊断器自身异常被吞掉继续下一条——
诊断器崩了不能掩盖原始失败（任务书 §3b-1）。``classify(text)`` 是错误文本 → 错误码
分类器：关键词表 ``TEXT_RULES`` 自 ``ui/pet_agent_rules.PATTERNS`` 迁入（轮 5A D6），
「是否可重试」以码的 ``retryable`` 为唯一权威（G10），认不出返回 ``E-UNKNOWN``。
"""
import re
from dataclasses import dataclass
from typing import Any, Callable

from contract.diagnostics import Severity

# 错误码严重度闭集（K8 统一）：与 ``contract.diagnostics.Severity`` 同词表
# （fatal/error/warn/degraded/info 五值）。旧值 ``recoverable`` 已删除、一律
# 映射为 ``warn``——「是否可重试」以 ``retryable`` 字段为唯一权威（G10），
# 不再由 severity 表达。``degraded``＝相关功能降级；``info``＝仅提示无需处置。
SEVERITIES = frozenset(member.value for member in Severity)


@dataclass(frozen=True)
class ErrorCode:
    code: str
    severity: Severity
    retryable: bool
    user_message: str
    remedy: str

    def __post_init__(self) -> None:
        # severity 归一到 diagnostics.Severity 闭集：接受 'fatal'/'warn' 等
        # 字符串与枚举成员，'recoverable' 等非法值当场拒绝。
        object.__setattr__(self, 'severity', Severity(self.severity))


_ITEMS = (
    ErrorCode('E-UNKNOWN', Severity.WARN, False, '发生了未分类的错误', '查看日志中的详细信息后重试'),
    ErrorCode('E-NET-TIMEOUT', Severity.WARN, True, '网络请求超时', '检查网络或稍后重试'),
    ErrorCode('E-NET-UNREACHABLE', Severity.WARN, True, '无法连接到服务', '检查网络、代理和服务地址'),
    ErrorCode('E-NET-RATE-LIMIT', Severity.WARN, True, '请求过于频繁，服务限流', '稍等片刻后重试，或降低并发'),
    ErrorCode('E-NET-SERVER', Severity.WARN, True, '远端服务暂时不可用', '稍后重试，持续失败请检查服务状态'),
    ErrorCode('E-NET-CLIENT', Severity.WARN, False, '请求被服务拒绝', '检查请求参数、模型名与权限'),
    ErrorCode('E-QUOTA-EXCEEDED', Severity.WARN, False, '余额或配额不足', '充值或调整配额上限后重试'),
    ErrorCode('E-CONTENT-POLICY', Severity.WARN, False, '内容命中安全审核', '改写提示词后重新提交，勿原样重试'),
    ErrorCode('E-AUTH-MISSING', Severity.WARN, False, '缺少凭据', '在模型管理中配置对应密钥'),
    ErrorCode('E-AUTH-REJECTED', Severity.WARN, False, '凭据被服务拒绝', '检查密钥是否有效、是否过期'),
    ErrorCode('E-ASSET-MISSING', Severity.WARN, False, '缺少必需的资产文件', '在资产管理中补齐后重试'),
    ErrorCode('E-FILE-NOT-FOUND', Severity.WARN, False, '文件不存在', '确认路径，文件是否被移动或删除'),
    ErrorCode('E-FILE-TOO-LARGE', Severity.WARN, False, '文件超过允许的大小上限', '压缩或拆分文件后重试'),
    ErrorCode('E-PATH-UNSAFE', Severity.WARN, False, '路径越界，已拒绝', '只使用项目目录内的文件'),
    ErrorCode('E-CONTRACT-VIOLATION', Severity.DEGRADED, False, '产物不符合契约', '按报告中的字段修正后重新生成'),
    ErrorCode('E-STAGE-BLOCKED', Severity.WARN, False, '前置阶段未完成，当前阶段被阻塞', '先完成并确认上一阶段'),
    ErrorCode('E-CANCELLED', Severity.INFO, False, '操作已取消', '无需处理，需要时重新发起'),
    ErrorCode('E-IO-WRITE', Severity.WARN, True, '写入文件失败', '检查磁盘空间与目录权限'),
    ErrorCode('E-TOOL-MISSING', Severity.DEGRADED, False, '缺少外部工具', '在配置中指定 ffmpeg 等工具路径'),
    ErrorCode('E-IO-READ', Severity.WARN, True, '读取文件失败', '检查文件是否被占用、权限或路径'),
    ErrorCode('E-IO-CORRUPT', Severity.DEGRADED, False, '数据已损坏或不完整', '从备份恢复或重新生成'),
    ErrorCode('E-TOOL-FAILED', Severity.DEGRADED, True, '外部工具执行失败', '查看工具输出后重试'),
    ErrorCode('E-TOOL-TIMEOUT', Severity.DEGRADED, True, '外部工具执行超时', '检查工具状态或调大超时后重试'),
    ErrorCode('E-CONFIG-INVALID', Severity.WARN, False, '配置无效或缺失', '检查对应配置项后重试'),
    ErrorCode('E-START-FAILED', Severity.FATAL, False, '程序启动失败', '重新启动一次；仍然失败请把提示里的日志文件发给技术支持'),
    ErrorCode('E-START-SELFCHECK', Severity.FATAL, False, '启动自检没有通过', '按下面列出的处理建议逐条处理后重新启动'),
    ErrorCode('E-RECEIPT-UNKNOWN', Severity.ERROR, False, '请求是否受理无法确认', '稍后到任务中心核对，或重试'),
    ErrorCode('E-TASK-EXPIRED', Severity.ERROR, False, '任务已过期', '远端任务过期不会自动重发，请重新提交'),
    ErrorCode('E-CLIENT-TOO-OLD', Severity.ERROR, False, '客户端版本过低', '升级客户端后重试'),

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


# 错误文本分类表（轮 5A D6-a）：自 ``ui.pet_agent_rules.PATTERNS`` 逐字迁入的
# 「错误文本 → 错误码」关键词表，**顺序即优先级**（auth/quota 先于 params，content
# 先于 server），与原表一致不得调序。每行 ``(原 PATTERNS 类目, 错误码, 关键词表)``；
# 类目名仅作文档对照与 5B 接线索引——``classify`` 的产出是 ``ErrorCode``。
# ``quota``／``content`` 两个类目在码表里原本没有语义吻合的码，本轮按 registry
# 扩展机制各补一个（``E-QUOTA-EXCEEDED``／``E-CONTENT-POLICY``），避免挤进
# ``E-NET-CLIENT`` 让 remedy 张冠李戴。
TEXT_RULES = (
    ('auth', 'E-AUTH-REJECTED', ('401', '403', 'unauthorized', 'forbidden', '密钥', 'api key')),
    ('quota', 'E-QUOTA-EXCEEDED', ('402', '余额', '欠费', 'quota', 'insufficient', 'balance')),
    ('content', 'E-CONTENT-POLICY', ('content', '审核', '敏感', '违规', 'policy', 'blocked', 'safety')),
    ('params', 'E-NET-CLIENT', ('400', '参数', 'invalid', 'not valid', 'unsupported', '尺寸')),
    ('rate_limit', 'E-NET-RATE-LIMIT', ('429', 'rate limit', '限流', 'too many', '太频繁')),
    ('timeout', 'E-NET-TIMEOUT', ('timeout', 'timed out', '超时', '逾时')),
    ('server', 'E-NET-SERVER', ('500', '501', '502', '503', '504', 'server error', '服务不可用')),
)


def _mark_hit(haystack: str, mark: Any) -> bool:
    """单条关键词命中判定，与 ``pet_agent._mark_hit`` 同口径：纯数字标记只认
    「独立的一串数字」（退出码 4294967295 里的 429 不算限流），其余按子串。"""
    mark = str(mark).lower()
    if mark.isdigit():
        return re.search(r'(?<!\d)' + mark + r'(?!\d)', haystack) is not None
    return mark in haystack


def _status_text(status: Any) -> str:
    """HTTP 状态码归一成检索串片段：能转整数就用整数形（``429.0`` → ``'429'``），
    否则原样 ``str``——与 ``pet_agent.classify`` 的 ``_int`` 口径一致。"""
    try:
        return str(int(float(status)))
    except (TypeError, ValueError, OverflowError):
        return str(status)


def classify(text: Any, status: Any = None) -> ErrorCode:
    """错误文本 → ``ErrorCode``（轮 5A D6）：按 ``TEXT_RULES`` 顺序首个命中胜出，
    认不出返回 ``E-UNKNOWN``。

    ``status`` 是可选 HTTP 状态码，与 ``pet_agent.classify`` 同口径拼成
    ``'http <code>'`` 参与匹配；匹配全程小写化。只读纯函数，不联网不抛业务异常。
    """
    haystack = str(text or '').lower() + ' '
    if status not in (None, ''):
        haystack += 'http ' + _status_text(status)
    for _category, item_code, marks in TEXT_RULES:
        if any(_mark_hit(haystack, mark) for mark in marks):
            return lookup(item_code)
    return lookup('E-UNKNOWN')


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


_CJK_RE = re.compile('[一-鿿]')  # U+4E00–U+9FFF CJK 基本块
_BLANK_RE = re.compile(r'\s+')


def _one_line(text: str) -> str:
    return _BLANK_RE.sub(' ', text).strip()


def user_text(error: Any, *, fallback: str = 'E-UNKNOWN') -> str:
    """界面把失败变成用户可读文字的唯一出口（EC-1）：规则按序命中即返回。

    R1 ``error`` 带已登记 ``code`` 属性（``infra_errors`` 家族，不引入该模块、
    只看属性避免循环）→ ``describe(code)``；``str(error)`` 非空且含中文时再
    接 ``'：' + 说明``。
    R2 系统抛出的 ``OSError``（``errno`` 非 ``None``）→ ``FileNotFoundError``
    给 ``E-FILE-NOT-FOUND``，其余给 ``describe(fallback)``；系统原文含本机
    路径，不给用户看。
    R3 ``str(error)`` 含中文 → 原样返回（换行与连续空白并成一个空格）。
    R4 其余（空串、``None``、非异常对象）→ ``describe(fallback)``；
    ``fallback`` 未登记时 ``lookup`` 归到 ``E-UNKNOWN``。

    纯函数：不读写文件、不联网、不记日志、任何输入都不抛异常（内部出错
    返回 ``describe('E-UNKNOWN')``）。不调用 ``classify()``——``TEXT_RULES``
    关键词表为模型接口报错设计，套在任意程序报错上会归错（含 content
    一词即误判「内容审核」）。
    """
    try:
        code = getattr(error, 'code', None)
        if code in CODES:
            message = _one_line(str(error))
            if message and _CJK_RE.search(message):
                return describe(code) + '：' + message
            return describe(code)
        if isinstance(error, OSError) and getattr(error, 'errno', None) is not None:
            if isinstance(error, FileNotFoundError):
                return describe('E-FILE-NOT-FOUND')
            return describe(fallback)
        message = _one_line(str(error))
        if _CJK_RE.search(message):
            return message
        return describe(fallback)
    except Exception:
        return describe('E-UNKNOWN')

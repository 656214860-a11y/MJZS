# -*- coding: utf-8 -*-
"""模型路由层：ModelAdapter（GPT／Qwen／DeepSeek）＋ ModelRouter。

规格（用户附件）里的三条原则落在这里：
- SKILL 不绑定模型：SKILL 只声明 capabilities 与 preferredModels／fallbackModels；
- 模型由路由层按能力、成本、可用性动态选（密钥在 .env／环境变量里，读不到就算这个模型不可用）；
- 用户可全局／项目／单次三级覆盖，「自动」＝三级都不指定，交给路由层挑。

select() 的顺序就是规格里写的那四步：用户偏好 → preferredModels 里可用且在预算内的 →
按 capabilities 匹配 → skill.fallbackModels[0] 或 deepseek-v4-flash。
"""
import os
import threading
import time
from pathlib import Path

import infra.model_pool as model_pool
import infra.pet_llm as pet_llm
import infra.token_saver as token_saver
from infra.model_metering import submission_retryable
from infra.api_endpoints import configured_key, normalize_url

PROGRAM = Path(__file__).resolve().parents[1]
CAPABILITIES = ('long-context', 'structured-output', 'creative-writing', 'reasoning', 'vision')

# 面板上的五个选项：四个具体模型 ＋ 「自动」。键是模型 id，值是界面文案。
CHOICES = (('auto', '自动'), ('gpt-4o', 'GPT'), ('qwen-max', 'Qwen'),
           ('deepseek-v4-pro', 'DeepSeek Pro'), ('deepseek-v4-flash', 'DeepSeek Flash'))
CHOICE_IDS = tuple(choice[0] for choice in CHOICES)
LABEL_OF = dict(CHOICES)
DEFAULT_MODEL = 'deepseek-v4-flash'
AUTO = 'auto'
# 阶段配置可调推理等级（REQ-S01-82）：auto 不加任何参数；只对有 reasoning
# 能力标签的模型下发，免得给不支持的服务端送去不认得的字段被判 400。
REASONING_EFFORTS = ('low', 'medium', 'high')
REASONING_THINKING_BUDGET = {'low': 1024, 'medium': 8192, 'high': 32768}
CIRCUIT_FAILURE_THRESHOLD = 3
CIRCUIT_COOLDOWN_SECONDS = 60.0
# 记为熔断失败的状态：本地网络异常（0）与可重放的 HTTP 状态。与 model_metering.REPLAYABLE_RETRY_STATUS
# 同口径，但刻意不含 409——那是「提交已受理」的冲突码，不该把模型判进熔断。
CIRCUIT_RETRY_STATUS = (0, 408, 425, 429, 500, 502, 503, 504)
_CIRCUIT_LOCK = threading.Lock()
_CIRCUITS = {}


class _Circuit:
    def __init__(self):
        self.failures = 0
        self.opened_at = 0.0


def circuit_state(model_id):
    """返回模型熔断状态：closed／open／half_open。"""
    key = str(model_id or '').strip()
    with _CIRCUIT_LOCK:
        circuit = _CIRCUITS.get(key)
        if circuit is None or not circuit.opened_at:
            return {'state': 'closed', 'failures': circuit.failures if circuit else 0, 'opened_at': 0.0}
        elapsed = time.monotonic() - circuit.opened_at
        return {'state': 'half_open' if elapsed >= CIRCUIT_COOLDOWN_SECONDS else 'open',
                'failures': circuit.failures, 'opened_at': circuit.opened_at}


def circuit_allows(model_id):
    return circuit_state(model_id)['state'] != 'open'


def record_circuit_failure(model_id):
    key = str(model_id or '').strip()
    if not key:
        return circuit_state(key)
    with _CIRCUIT_LOCK:
        circuit = _CIRCUITS.setdefault(key, _Circuit())
        circuit.failures += 1
        if circuit.failures >= CIRCUIT_FAILURE_THRESHOLD:
            circuit.opened_at = time.monotonic()
        return {'state': 'open' if circuit.opened_at else 'closed',
                'failures': circuit.failures, 'opened_at': circuit.opened_at}


def record_circuit_success(model_id):
    key = str(model_id or '').strip()
    if not key:
        return circuit_state(key)
    with _CIRCUIT_LOCK:
        circuit = _CIRCUITS.setdefault(key, _Circuit())
        circuit.failures = 0
        circuit.opened_at = 0.0
        return {'state': 'closed', 'failures': 0, 'opened_at': 0.0}


def _responses_output_text(outputs):
    """Responses 协议 output 列表里的正文：只接受 output_text 项。"""
    parts = []
    for output in outputs if isinstance(outputs, list) else ():
        content = output.get('content') if isinstance(output, dict) else None
        for block in content if isinstance(content, list) else ():
            # 工具调用、推理项等不是给用户看的正文，绝不能转成字符串混进剧本。
            if isinstance(block, dict) and block.get('type') == 'output_text':
                value = block.get('text')
                if isinstance(value, str):
                    parts.append(value)
    return ''.join(parts)


def _parse_messages(data, meta):
    meta['finish_reason'] = str(data.get('stop_reason') or '')
    return token_saver.anthropic_text(data)


def _parse_responses(data, meta):
    meta['response_shape'] = sorted(str(key) for key in data.keys())
    meta['finish_reason'] = str(data.get('status') or '')
    text = _responses_output_text(data.get('output'))
    if not text and isinstance(data.get('output_text'), str):
        text = data['output_text']
    return text


def _parse_completions(data, meta):
    text = ''
    choices = data.get('choices')
    meta['response_shape'] = sorted(str(key) for key in data.keys())
    if isinstance(choices, list) and choices and isinstance(choices[0], dict):
        choice = choices[0]
        meta['finish_reason'] = str(choice.get('finish_reason') or '')
        message = choice.get('message') if isinstance(choice.get('message'), dict) else {}
        meta['message_fields'] = sorted(str(key) for key in message.keys())
        meta['reasoning_fields'] = [key for key in ('reasoning_content', 'reasoning', 'analysis')
                                    if message.get(key) not in (None, '', [], {})]
        meta['reasoning_lengths'] = {key: len(str(message.get(key) or '')) for key in meta['reasoning_fields']}
        content = message.get('content')
        if isinstance(content, str):
            text = content
        elif isinstance(content, list):
            text = ''.join(str(block.get('text') or '') for block in content if isinstance(block, dict))
    if not text:
        text = str(data.get('output_text') or data.get('content') or '')
    return text


_WIRE_PARSERS = {'messages': _parse_messages, 'responses': _parse_responses}


def _parse_response(wire_api, data, target):
    """按协议取出正文，并给出只含协议元数据的诊断（绝不记录提示词、正文或推理正文）。

    这样 DeepSeek 等推理模型返回空 content 时，界面/日志能区分「实际请求成功但没有正文」和
    「模型 ID、协议或网络失败」，而不会泄露用户创作内容。
    """
    meta = {'requested_model': target, 'wire_api': wire_api,
            'response_id': '', 'finish_reason': '', 'response_shape': [],
            'message_fields': [], 'reasoning_fields': [], 'reasoning_lengths': {},
            'content_length': 0}
    text = ''
    if isinstance(data, dict):
        meta['response_id'] = str(data.get('id') or data.get('request_id') or '')
        text = _WIRE_PARSERS.get(wire_api, _parse_completions)(data, meta)
    meta['content_length'] = len(text)
    return text, meta


def response_envelope_error(wire_api, data):
    """把 API 响应视为不可信输入：成功但缺少协议必备字段时判定为伪兼容/坏回执。"""
    if not isinstance(data, dict):
        return '响应不是 JSON 对象'
    if wire_api == 'chat' and not isinstance(data.get('choices'), list):
        return '响应缺少 choices 字段'
    if wire_api == 'responses' and not isinstance(data.get('output'), list):
        return '响应缺少 output 字段'
    if wire_api == 'messages' and not isinstance(data.get('content'), list):
        return '响应缺少 content 字段'
    return ''


# L0 轮 5A ``error_codes.classify`` 的码 → 本模块历史类别词表（R6-b）：
# 分类权威已收敛到 L0，这里只把码翻回既有消费者认的类别字符串。
_ERROR_CLASS_BY_CODE = {
    'E-NET-TIMEOUT': 'timeout',
    'E-AUTH-REJECTED': 'authentication', 'E-AUTH-MISSING': 'authentication',
    'E-NET-CLIENT': 'protocol',
    'E-QUOTA-EXCEEDED': 'configuration', 'E-CONTENT-POLICY': 'protocol',
    'E-CANCELLED': 'cancelled',
}


def error_class(error, status=None):
    """将可显示的失败归为稳定类别，供界面提示和无正文诊断使用。

    分类权威是 ``contract.error_codes.classify``（L0 轮 5A）：``status`` 为
    HTTP 状态码时先并入判定，缺失时纯按错误文本；认不出回 ``E-UNKNOWN``。
    """
    from contract import error_codes
    code = error_codes.classify(error, status=status).code
    return _ERROR_CLASS_BY_CODE.get(code, 'transport')


def failure_policy(result):
    """失败契约：HTTP 错误不等于未受理；远端编号优先阻止重复提交。"""
    result = result or {}
    status = result.get('status')
    meta = result.get('response_meta') or {}
    remote = result.get('provider_task_id') or result.get('task_id') or meta.get('response_id')
    accepted = result.get('accepted')
    if result.get('ok') or remote or accepted is True:
        acceptance = 'accepted'
    elif accepted is False or status in (400, 401, 403, 404, 422, 429):
        acceptance = 'not_accepted'
    else:
        acceptance = 'unknown'
    code = ('succeeded' if result.get('ok') else 'rate_limit' if status == 429 else 'authentication' if status in (401, 403)
            else 'unsupported_request' if status in (400, 404, 422)
            else 'server_error' if isinstance(status, int) and status >= 500
            else 'cancelled' if result.get('error_class') == 'cancelled' else 'receipt_unknown')
    retryable = submission_retryable(acceptance, code)
    return {'reason_code': code, 'acceptance': acceptance,
            'retryable': retryable, 'provider_task_id': remote}


def label_of(model):
    """模型 id → 界面文案（认不出的原样返回）。"""
    text = str(model or '').strip()
    return LABEL_OF.get(text, text)


def spend_kind(skill):
    """这个 SKILL 花的是哪本账：视频镜数／生图张数／Token（按 tools 前缀分，规则一条）。"""
    tools = [str(tool) for tool in (getattr(skill, 'tools', None) or [])]
    if any(tool.startswith('video.') for tool in tools):
        return 'videos'
    if any(tool.startswith(('firstframe.', 'asset.', 'edit.export')) for tool in tools):
        return 'images'
    return 'tokens'


class ModelAdapter:
    """一个模型服务商：认哪几个模型、密钥在哪、怎么发一条 chat。"""

    provider = ''
    key_env = ''
    base_url = ''
    path = '/chat/completions'
    wire_api = 'chat'                 # chat＝OpenAI 兼容 /chat/completions；responses＝/responses
    models = {}                       # 模型 id → {'capabilities': (...), 'cost': 1..3}

    def __init__(self, program=None, transport=None, config=None, key='', timeout=60):
        self.program = Path(program or PROGRAM)
        self.transport = transport or pet_llm.http_transport
        self.config = dict(config or {})
        self.key = key
        self.timeout = timeout

    # ── 可用性 ──────────────────────────────────────────────────────────────
    def credential(self):
        """密钥只从 .env／环境变量取：配置 JSON 里从不保存密钥（读不到就是空串）。"""
        if self.key:
            return self.key
        for folder in (self.program,):
            try:
                return configured_key({'key_env': self.key_env, 'project_dir': str(folder), 'secret_root': str(self.program)})
            except ValueError:
                pass
        return (os.environ.get(self.key_env, '') or '').strip()

    def available(self):
        return bool(self.credential())

    def supports(self, model):
        return str(model or '') in self.models

    def capabilities(self, model):
        entry = self.models.get(str(model or '')) or {}
        return tuple(entry.get('capabilities') or ())

    def cost(self, model):
        entry = self.models.get(str(model or '')) or {}
        return int(entry.get('cost') or 1)

    # ── 发一条 chat ─────────────────────────────────────────────────────────
    def endpoint(self):
        if self.wire_api == 'responses':
            return normalize_url(self.base_url) + '/responses'
        if self.wire_api == 'messages':
            return token_saver.anthropic_messages_endpoint(normalize_url(self.base_url))
        return normalize_url(self.base_url) + self.path

    def headers(self):
        key = self.credential()
        if not key:
            raise ValueError('%s 缺少 API Key（.env 里的 %s）' % (self.provider, self.key_env))
        if self.wire_api == 'messages':
            return token_saver.anthropic_headers(key)
        return {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + key}

    @staticmethod
    def prefixed(messages, system=''):
        """system 给了就摆在最前面：同一段前缀每次都在同一个位置，缓存才认得出来。"""
        items = list(messages or ())
        return ([{'role': 'system', 'content': str(system)}] + items) if system else items

    def payload(self, model, messages, options=None, system=''):
        """请求体：固定前缀（system）永远排在最前面，变化的内容在后面（附件通用原则 1）。

        wire_api='messages' 是 Anthropic 原生那一档：system 单列 ＋ 顶层 cache_control
        （附件 2A——不显式标记就等于放弃 90% 折扣）。
        """
        options = dict(options or {})
        limit = int(options.get('max_tokens') or 1024)
        body = {'model': str(model)}
        # Responses 协议不接受 Chat Completions 的 max_tokens；这两份字段不能
        # 同时发送，否则部分兼容服务会静默采用错误的上限或直接拒绝请求。
        body['max_output_tokens' if self.wire_api == 'responses' else 'max_tokens'] = limit
        # “OpenAI 兼容”并不表示每个模型都接受 temperature；未明确要求时让服务端使用
        # 自己的默认采样策略，避免部分推理／桌面网关模型直接拒绝请求。
        if 'temperature' in options:
            body['temperature'] = options['temperature']
        if self.wire_api == 'messages':
            payload=token_saver.anthropic_payload(str(model), system, list(messages or ()), body['max_tokens'],
                                                  options.get('cache_ttl') or '5m',
                                                  keep_tail=isinstance(options.get('tools'), list) or len(list(messages or ())) > 1)
            # 原生 Claude 工具只在 Messages 协议下有效；普通模型维持原请求格式。
            if isinstance(options.get('tools'),list):payload['tools']=options['tools']
            # 采样参数和 token 上限一样属于请求体：显式给了就不能因为换协议而悄悄丢掉。
            if 'temperature' in options:
                payload['temperature'] = options['temperature']
            budget = self._thinking_budget(model, options)
            if budget:
                payload['thinking'] = {'type': 'enabled', 'budget_tokens': budget}
            return payload
        effort = self._reasoning_effort(model, options)
        if effort and self.wire_api == 'responses':
            body['reasoning'] = {'effort': effort}
        elif effort:
            body['reasoning_effort'] = effort
        if self.wire_api == 'responses':
            body['input'] = self.prefixed(messages, system)
        else:
            body['messages'] = self.prefixed(messages, system)
        return body

    def _reasoning_effort(self, model, options):
        """options['reasoning'] → 线协议档位；模型没标推理能力时不下发。"""
        if 'reasoning' not in self.capabilities(model):
            return ''
        effort = str((options or {}).get('reasoning') or '').strip().lower()
        return effort if effort in REASONING_EFFORTS else ''

    def _thinking_budget(self, model, options):
        """Anthropic 思考预算：档位映射 token 数，必须小于 max_tokens（下限 1024）。"""
        effort = self._reasoning_effort(model, options)
        if not effort:
            return 0
        budget = REASONING_THINKING_BUDGET[effort]
        limit = int((options or {}).get('max_tokens') or 1024) - 1
        return min(budget, limit) if limit >= 1024 else 0

    def chat(self, messages, options=None, model='', system=''):
        """统一入口：返回 {'ok', 'text', 'model', 'status', 'usage', 'error'}，不抛异常。"""
        from contract.platform_tools import current_execution
        control = current_execution()
        timeout = control.remaining(self.timeout) if control is not None else self.timeout
        target = str(model or '') or next(iter(self.models), '')
        try:
            payload = self.payload(target, messages, options, system)
            result = self.transport(self.endpoint(), payload, self.headers(), timeout)
        except TimeoutError:
            return {'ok': False, 'status': 0, 'kind': 'network',
                    'error': '模型响应超时，请稍后重试或切换更快模型。',
                    'error_class': 'timeout', 'model': target, 'text': '',
                    'usage': pet_llm.usage_of(None), 'data': None}
        except Exception as exc:
            error = type(exc).__name__ + '：' + str(exc)
            return {'ok': False, 'status': 0, 'kind': 'bug', 'error': error, 'error_class': error_class(error),
                    'model': target, 'text': '', 'usage': pet_llm.usage_of(None), 'data': None}
        data = result.get('data') if isinstance(result, dict) else None
        # 各协议共用一套口径：Claude 的总输入含缓存读写，缓存写入数随结果保留。
        usage = pet_llm.usage_of(result)
        text, response_meta = _parse_response(self.wire_api, data, target)
        envelope_error = (response_envelope_error(self.wire_api, data)
                          if result.get('ok') and self.wire_api == 'chat' else '')
        if envelope_error:
            return {'ok': False, 'status': result.get('status'), 'error': envelope_error,
                    'kind': result.get('kind') or 'protocol', 'model': target, 'text': '',
                    'usage': usage, 'data': data, 'error_class': 'protocol', 'accepted': result.get('accepted'),
                    'provider_task_id': result.get('provider_task_id') or result.get('task_id'),
                    'response_meta': response_meta}
        return {'ok': bool(result.get('ok')), 'status': result.get('status'), 'error': result.get('error'),
                'kind': result.get('kind') or '', 'model': target, 'text': text, 'usage': usage, 'data': data,
                'error_class': '' if result.get('ok') else error_class(result.get('error'), status=result.get('status')),
                'response_meta': response_meta, 'accepted': result.get('accepted'),
                'provider_task_id': result.get('provider_task_id') or result.get('task_id')}

    def stream(self, messages, options=None, model='', system='', on_chunk=None, cancelled=None):
        """仅 chat 协议走 SSE；已发送后失败不得自动再次提交。"""
        if self.wire_api != 'chat' or not callable(on_chunk):
            return self.chat(messages, options=options, model=model, system=system)
        from contract.platform_tools import current_execution
        control = current_execution()
        timeout = control.remaining(self.timeout) if control is not None else self.timeout
        target = str(model or '') or next(iter(self.models), '')
        try:
            payload = self.payload(target, messages, options, system)
            result = model_pool.http_stream(self.endpoint(), payload, self.headers(), timeout,
                                            on_chunk, cancelled=cancelled)
        except Exception as exc:
            result = {'ok': False, 'status': 0, 'error': type(exc).__name__}
        if str(result.get('error') or '') == '请求已取消':
            return {'ok': False, 'status': 0, 'kind': 'client', 'error': '请求已取消', 'model': target, 'text': '',
                    'usage': pet_llm.usage_of(None), 'data': None, 'error_class': 'cancelled',
                    'response_meta': {'requested_model': target, 'wire_api': 'chat', 'content_length': 0}}
        if not result.get('ok') or not (result.get('data') or {}).get('choices'):
            return {'ok': False, 'status': result.get('status', 0), 'model': target,
                    'text': '', 'usage': pet_llm.usage_of(result),
                    'error': result.get('error') or '流式结果不完整，需核对供应商回执',
                    'failure': failure_policy(result)}
        text = str(result['data']['choices'][0]['message'].get('content') or '')
        return {'ok': True, 'status': result.get('status', 200), 'error': '', 'kind': '', 'model': target,
                'text': text, 'usage': pet_llm.usage_of(result), 'data': result.get('data'),
                'error_class': '', 'response_meta': {'requested_model': target, 'wire_api': 'chat',
                'response_id': '', 'finish_reason': result['data']['choices'][0].get('finish_reason') or '',
                'response_shape': ['choices'],
                'message_fields': ['content'], 'reasoning_fields': [], 'reasoning_lengths': {},
                'content_length': len(text)}}


class DeepSeekAdapter(ModelAdapter):
    """DeepSeek：默认 chat_completions，保留 wire_api 切换位（与宠物那套共用一份配置）。"""

    provider = 'DeepSeek'
    key_env = 'DEEPSEEK_API_KEY'
    models = {'deepseek-v4-pro': {'capabilities': ('long-context', 'structured-output', 'creative-writing',
                                                   'reasoning'), 'cost': 3},
              'deepseek-v4-flash': {'capabilities': ('long-context', 'structured-output', 'reasoning'),
                                    'cost': 1}}

    def __init__(self, program=None, transport=None, config=None, key='', timeout=None, **kwargs):
        cfg = pet_llm.load_config(config=config)
        super().__init__(program=program, transport=transport, config=cfg, key=key,
                         timeout=int(timeout or cfg.get('timeout') or 60))
        self.key_env = cfg.get('key_env') or self.key_env
        self.base_url = cfg.get('base_url') or 'https://api.deepseek.com'
        self.path = cfg.get('path') or '/chat/completions'
        self.wire_api = cfg.get('wire_api') or 'chat'
        self.config = cfg

    def endpoint(self):
        return pet_llm.endpoint(self.config)

    def headers(self):
        # 注入的 key 优先：credential()／available() 认它，出站请求头必须认同一把，
        # 否则「界面说这个模型能用」与「实际发出去用哪把钥匙」会分叉。
        if self.key:
            return {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + self.key}
        return pet_llm.headers(self.config, self.program)


class GPTAdapter(ModelAdapter):
    """GPT：OpenAI 兼容接口，密钥走 OPENAI_API_KEY。"""

    provider = 'GPT'
    key_env = 'OPENAI_API_KEY'
    base_url = 'https://api.openai.com/v1'
    models = {'gpt-4o': {'capabilities': ('vision', 'reasoning', 'creative-writing', 'structured-output',
                                          'long-context'), 'cost': 3},
              'gpt-4o-mini': {'capabilities': ('structured-output', 'reasoning'), 'cost': 1}}


class QwenAdapter(ModelAdapter):
    """Qwen：阿里云百炼的 OpenAI 兼容模式，密钥优先 DASHSCOPE_API_KEY。"""

    provider = 'Qwen'
    key_env = 'DASHSCOPE_API_KEY'
    base_url = 'https://dashscope.aliyuncs.com/compatible-mode/v1'
    models = {'qwen-max': {'capabilities': ('long-context', 'creative-writing', 'structured-output', 'vision'),
                           'cost': 2},
              'qwen-plus': {'capabilities': ('long-context', 'structured-output'), 'cost': 1}}

    def credential(self):
        key = super().credential()
        return key or (os.environ.get('QWEN_API_KEY', '') or '').strip()


class AnthropicAdapter(ModelAdapter):
    """Anthropic Claude：原生 /v1/messages ＋ 顶层 cache_control（附件 2A／2C）。

    模型管理里把 Provider 选成「anthropic」时，协议栏自动摆到 messages 那一档，走的就是这条路；
    这里再多给一条内置的，不经过池子也能直接点名这两个模型。
    """

    provider = 'Anthropic'
    key_env = 'ANTHROPIC_API_KEY'
    base_url = 'https://api.anthropic.com'
    wire_api = 'messages'
    models = {'claude-opus-5': {'capabilities': ('long-context', 'creative-writing', 'structured-output',
                                                 'reasoning'), 'cost': 3},
              'claude-sonnet-4.5': {'capabilities': ('long-context', 'creative-writing', 'structured-output'),
                                    'cost': 2}}


class PoolAdapter(ModelAdapter):
    """池里任意一条模型：地址／协议／模型名／密钥名全照「模型管理」的那一份记录来。

    模型管理是 API 配置的唯一入口——用户在那一栏把地址、协议或密钥名改了，阶段配置挑中这条时
    就得发到新地方去，所以这里不照着服务商写死一份。一条记录一个适配器：池里的密钥是「每条一个
    变量名」，合在一个适配器里就没法把 available() 说清楚是哪条缺密钥。
    """

    def __init__(self, record, model_id='', program=None, transport=None, key='', timeout=60):
        item = model_pool.record(record, model_id)
        model = item['model'] or str(model_id or '')
        super().__init__(program=program, transport=transport, key=key, timeout=timeout)
        self.provider = item['provider'] or model_pool.DEFAULT_PROVIDER
        self.key_env = item['key_env']
        self.base_url = item['base_url']
        self.path = item['path']
        self.wire_api = item['wire_api']
        self.record = item
        self.models = ({model: {'capabilities': tuple(item['capabilities']),
                                'cost': int(item['cost'] or 1)}} if model else {})

    def credential(self):
        """密钥只有一处判据：问 model_pool（.env → private/.env → 同名环境变量）。"""
        if self.key:
            return self.key
        try:
            return model_pool.key_of(self.record, self.program)
        except Exception:
            return ''


class Choice:
    """一次选型的结果：模型、适配器、为什么选它、是被哪一级覆盖的。"""

    def __init__(self, model='', adapter=None, reason='', level='', capabilities=(), cost=1, kind='tokens'):
        self.model = str(model or '')
        self.adapter = adapter
        self.reason = str(reason)
        self.level = str(level)
        self.capabilities = tuple(capabilities)
        self.cost = int(cost)
        self.kind = kind

    @property
    def ok(self):
        return bool(self.model and self.adapter is not None)

    def describe(self):
        if not self.ok:
            return self.reason or '没有可用模型'
        return '%s（%s）· %s' % (self.model, self.adapter.provider, self.reason)

    def __repr__(self):
        return 'Choice(%s)' % self.describe()


class ModelRouter:
    """按 SKILL 声明与用户选择挑模型；挑之前先过预算。"""

    def __init__(self, adapters=None, budget=None, ledger=None, program=None, config=None,
                 transport=None, clock=None, records=None):
        self.program = Path(program or PROGRAM)
        self.transport = transport
        self.config = config
        self.budget = budget
        self.ledger = ledger
        self.clock = clock
        # 显式给了适配器（用例、别的子系统）就以它为准：这时不去翻盘上的模型池，免得自检跟着
        # 真安装目录里的配置红绿。
        self.explicit = adapters is not None
        if self.explicit:
            with _CIRCUIT_LOCK:
                _CIRCUITS.clear()
        self.records = records if isinstance(records, dict) else None
        built = adapters if adapters is not None else self.default_adapters()
        self.adapters = list(built)
        self._table = None

    def pool(self):
        """模型管理里的那几条：给了 records 就用给的，否则按程序目录读一次全局配置。"""
        if self.explicit:
            return {}
        if self.records is None:
            self.records = model_pool.pool(self.config, self.program)
        return self.records

    def models_now(self):
        """手上有哪些模型、各自归谁发：池里的记录优先，池里没登记的才退回内置那三家。

        池里的记录压过照服务商写死的适配器，是因为「模型管理」是 API 配置的唯一入口：地址、
        协议、密钥名在那一栏改了就得以那一栏为准。只有池里没有的（gpt-4o-mini 这类内置档）
        才走内置适配器。
        """
        if self._table is None:
            table = {}
            for adapter in self.adapters:
                for model in (getattr(adapter, 'models', None) or {}):
                    table[model] = adapter
            for model_id, item in self.pool().items():
                table[model_id] = PoolAdapter(item, model_id, program=self.program,
                                              transport=self.transport)
            self._table = table
        return self._table

    def default_adapters(self):
        return [DeepSeekAdapter(program=self.program, transport=self.transport, config=self.config),
                GPTAdapter(program=self.program, transport=self.transport),
                QwenAdapter(program=self.program, transport=self.transport)]

    # ── 可用性 ──────────────────────────────────────────────────────────────
    def adapter_for(self, model):
        return self.models_now().get(str(model or '').strip())

    def usable(self, model):
        adapter = self.adapter_for(model)
        if adapter is None or not adapter.available():
            return None
        if not circuit_allows(model):
            return None
        if model_pool.health_is_blocked(model, program=self.program):
            return None
        return adapter

    def available_models(self):
        """现在真能用的模型（密钥配好了的），按成本从低到高。"""
        out = []
        for model, adapter in self.models_now().items():
            if adapter.available() and not model_pool.health_is_blocked(model, program=self.program):
                out.append((model, adapter.provider, adapter.cost(model)))
        return sorted(out, key=lambda item: (item[2], item[0]))

    def capability_models(self, capability):
        """带某项能力的可用模型（按成本从低到高）。"""
        return [(model, provider, cost) for model, provider, cost in self.available_models()
                if capability in (self.adapter_for(model).capabilities(model) if self.adapter_for(model) else ())]

    # ── 两级覆盖 ────────────────────────────────────────────────────────────
    def override(self, context=None):
        """单次 ＞ 项目；「自动」与空值都跳过。返回 (模型, 层级名)。"""
        ctx = dict(context or {})
        for key, level in (('model', '单次'), ('userPreferredModel', '单次'),
                           ('projectModel', '项目')):
            value = str(ctx.get(key) or '').strip()
            if value and value != AUTO:
                return value, level
        return '', ''

    # ── 选型 ────────────────────────────────────────────────────────────────
    def select(self, skill, context=None):
        choice = self._select(skill, context)
        choice.fallback_models = tuple(getattr(skill, 'fallbackModels', ()) or ()) if not choice.level else ()
        choice.required_capabilities = tuple(getattr(skill, 'capabilities', ()) or ())
        return choice

    def _select(self, skill, context=None):
        """规格里的四步；挑不出来时返回一个 ok=False 的 Choice，并说清楚为什么。"""
        ctx = dict(context or {})
        kind = spend_kind(skill)
        model, level = self.override(ctx)
        if model:
            adapter = self.usable(model)
            if adapter is None:
                return Choice(kind=kind, reason='指定的模型 %s 现在用不了（缺 API Key 或没登记）' % model)
            return Choice(model, adapter, '您指定（%s）' % level, level,
                          adapter.capabilities(model), adapter.cost(model), kind)
        affordable, why = self._affordable(kind)
        if not affordable:
            return Choice(kind=kind, reason=why)
        for name in getattr(skill, 'preferredModels', ()) or ():
            adapter = self.usable(name)
            if adapter is not None:
                return Choice(name, adapter, 'SKILL 的 preferredModels 里第一个可用的', '',
                              adapter.capabilities(name), adapter.cost(name), kind)
        for capability in getattr(skill, 'capabilities', ()) or ():
            matches = self.capability_models(capability)
            if matches:
                name, _provider, cost = matches[0]
                adapter = self.adapter_for(name)
                return Choice(name, adapter, '按能力 %s 匹配到最便宜的一个' % capability, '',
                              adapter.capabilities(name), cost, kind)
        for name in getattr(skill, 'fallbackModels', ()) or ():
            adapter = self.usable(name)
            if adapter is not None:
                return Choice(name, adapter, 'SKILL 的 fallbackModels 兜底', '',
                              adapter.capabilities(name), adapter.cost(name), kind)
        adapter = self.usable(DEFAULT_MODEL)
        if adapter is not None:
            return Choice(DEFAULT_MODEL, adapter, '实在没得挑，用默认的 Flash', '',
                          adapter.capabilities(DEFAULT_MODEL), adapter.cost(DEFAULT_MODEL), kind)
        return Choice(kind=kind, reason=missing_setup_hint())

    def _affordable(self, kind):
        if self.budget is None:
            return True, ''
        ok, why = self.budget.check(kind, 1)
        return ok, ('' if ok else why)

    # ── 发一条 chat ＋ 记账 ─────────────────────────────────────────────────
    def chat(self, choice, messages, options=None):
        """按选型发一条 chat；成功就把用量记进台账（Token 那本账跟着动）。"""
        if isinstance(choice, str):
            adapter = self.usable(choice)
            choice = Choice(choice, adapter, '直接指定', '', adapter.capabilities(choice) if adapter else (),
                            adapter.cost(choice) if adapter else 1, 'tokens')
        if not getattr(choice, 'ok', False):
            return {'ok': False, 'status': 0, 'error': choice.reason or '没有可用模型', 'model': '',
                    'text': '', 'usage': pet_llm.usage_of(None)}
        from contract.platform_tools import execution_checkpoint
        attempts = []
        candidates = [choice.model] + list(getattr(choice, 'fallback_models', ()))
        result = {}
        for model in dict.fromkeys(candidates):
            adapter = choice.adapter if model == choice.model else self.usable(model)
            if adapter is None:
                continue
            required = getattr(choice, 'required_capabilities', ())
            if model != choice.model and not set(required).issubset(adapter.capabilities(model)):
                continue
            execution_checkpoint()
            affordable, why = self._affordable(choice.kind)
            if not affordable:
                return dict(result, ok=False, error=why, route_stop='budget', attempts=attempts)
            result = adapter.chat(messages, options, model=model)
            policy = failure_policy(result)
            attempts.append({'model': model, 'status': result.get('status'), **policy})
            result = dict(result, attempts=list(attempts), failure=policy)
            if result.get('ok'):
                record_circuit_success(model)
                if self.ledger is not None:
                    tier = 'flash' if 'flash' in model else 'pro'
                    self.ledger.record(model, result.get('usage') or {}, tier=tier,
                                       at=self.clock() if callable(self.clock) else None)
                return result
            if result.get('status') in CIRCUIT_RETRY_STATUS:
                record_circuit_failure(model)
            if not policy['retryable']:
                return result
        return result


class ModelGateway:
    """LiteLLM Router 的零依赖等价：按候选模型组做健康/预算/重试与跨模型降级。"""

    def __init__(self, program=None, transport=None, config=None, budget=None, ledger=None, records=None):
        self.router = ModelRouter(program=program, transport=transport, config=config,
                                  budget=budget, ledger=ledger, records=records)
        self.default_models = []

    @classmethod
    def for_group(cls, group, current_model, *, records=None, program=None, transport=None,
                  budget=None, ledger=None):
        """按模型记录里的 group 字段生成候选组网关；当前模型优先。"""
        models = model_pool.group_candidates(group, current_model, records=records, program=program)
        gateway = cls(program=program, transport=transport, config=None, budget=budget,
                      ledger=ledger, records=records or model_pool.pool(None, program))
        gateway.default_models = models
        return gateway

    def _candidates(self, models):
        models = models if models is not None else self.default_models
        return list(dict.fromkeys(str(model) for model in (models or ()) if str(model)))

    def chat(self, models, messages, options=None, system=''):
        results = []
        for model in self._candidates(models):
            adapter = self.router.usable(model)
            if adapter is None:
                results.append({'model': model, 'ok': False, 'error': '模型不可用或未通过健康准入'})
                continue
            result = adapter.chat(messages, options=options, model=model, system=system)
            policy = failure_policy(result)
            results.append({'model': model, 'ok': bool(result.get('ok')),
                            'status': result.get('status'), **policy})
            result = dict(result, attempts=results)
            if result.get('ok'):
                record_circuit_success(model)
            elif result.get('status') in CIRCUIT_RETRY_STATUS:
                record_circuit_failure(model)
            if result.get('ok') or not policy['retryable']:
                return result
        if results:
            return {'ok': False, 'status': 0, 'error': '候选模型组全部失败或不可用',
                    'model': '', 'text': '', 'usage': pet_llm.usage_of(None),
                    'attempts': results, 'failure': failure_policy({})}
        return {'ok': False, 'status': 0, 'error': '没有给出候选模型', 'model': '', 'text': '',
                'usage': pet_llm.usage_of(None), 'failure': failure_policy({})}

    def stream(self, models, messages, options=None, system='', on_chunk=None, cancelled=None):
        for model in self._candidates(models):
            adapter = self.router.usable(model)
            if adapter is None:
                continue
            result = adapter.stream(messages, options=options, model=model, system=system,
                                    on_chunk=on_chunk, cancelled=cancelled)
            if result.get('ok'):
                record_circuit_success(model)
            elif result.get('status') in CIRCUIT_RETRY_STATUS:
                record_circuit_failure(model)
            if result.get('ok') or not failure_policy(result)['retryable']:
                return result
        return {'ok': False, 'status': 0, 'error': '候选模型组全部失败或不可用',
                'model': '', 'text': '', 'usage': pet_llm.usage_of(None),
                'failure': failure_policy({})}

    def chat_group(self, messages, options=None, system=''):
        return self.chat(None, messages, options=options, system=system)

    def stream_group(self, messages, options=None, system='', on_chunk=None, cancelled=None):
        return self.stream(None, messages, options=options, system=system, on_chunk=on_chunk, cancelled=cancelled)



# ── 三虎自己那颗脑袋用哪个模型（规格里的 ModelRouter.resolveAgentModel） ─────────
AGENT_TASKS = ('default', 'chat', 'escalate', 'fallback')
COMPLEXITIES = ('simple', 'medium', 'complex')


class AgentChoice:
    """一次选型的结果：模型 id、池里那条记录、为什么、是不是「自动」挑的、有没有降级兜底。"""

    def __init__(self, model='', record=None, reason='', task='default', auto=False, degraded=False,
                 ok=None):
        self.model = str(model or '')
        self.record = dict(record or {})
        self.reason = str(reason)
        self.task = str(task)
        self.auto = bool(auto)
        self.degraded = bool(degraded)
        self.ok = bool(self.model and self.record) if ok is None else bool(ok)

    @property
    def label(self):
        return model_pool.label_of(self.model, {self.model: self.record} if self.record else {})

    def describe(self):
        if not self.ok:
            return self.reason or '三虎现在没有可用模型'
        when = '自动' if self.auto else '指定'
        tail = '（降级兜底）' if self.degraded else ''
        return '%s · %s：%s%s' % (self.label, when, self.reason, tail)

    def __repr__(self):
        return 'AgentChoice(%s)' % self.describe()


def complexity_of(task='', context=None):
    """这一步有多难：上下文里写了就用它，没写就看任务表（复杂推理那几个算 complex）。"""
    ctx = dict(context or {})
    written = str(ctx.get('complexity') or '').strip().lower()
    if written in COMPLEXITIES:
        return written
    name = str(ctx.get('task') or task or '')
    tier = pet_llm.TASKS.get(name, pet_llm.TASKS[pet_llm.DEFAULT_TASK])[0]
    return 'complex' if tier == 'pro' else 'simple'


def auto_model(records, complexity='simple', program=None):
    """「自动」怎么挑：简单→池里最便宜的可用模型，中等→贵一档，复杂→最贵的那条。

    只挑「配好密钥」的：自动的意义就是不让用户操心，挑一个发不出去的等于没挑。
    桌面 Agent 仅供用户在阶段配置中明确选择，不能因常驻可用而抢走 API 自动路由。
    """
    usable = [(model_id, item) for model_id, item in records.items()
              if not model_pool.desktop_engine(model_id)
              and model_pool.available(item, program)]
    if not usable:
        return '', '池里没有配好密钥的模型'

    def cost(entry):
        return int(entry[1].get('cost') or 1)

    usable.sort(key=lambda entry: (cost(entry), entry[0]))
    if complexity == 'complex':
        model_id, item = usable[-1]          # 没配「升级模型」时的兜底：池里最贵的那条
    elif complexity == 'medium':
        middle = [entry for entry in usable if cost(entry) >= 2] or usable
        model_id, item = middle[0]
    else:
        model_id, item = usable[0]
    return model_id, '池里%s任务挑最便宜的可用模型（%s）' % (complexity, item['label'])


def resolve_agent_model(task_type='default', config=None, records=None, context=None, program=None):
    """规格里的 resolveAgentModel：三虎自己（路由、对话、升级、降级）用哪个模型。

    ① chat／escalate／fallback 直接取「三虎设置 → 模型」里那一项；
    ② default 设成「自动」时按复杂度挑，设成某一条就用那一条；
    ③ 挑中的那条不在池里／缺密钥 → 换降级模型；降级也不行 → ok=False 并说清原因。
    """
    task = str(task_type or 'default').strip()
    if task not in AGENT_TASKS:
        task = 'default'
    items = records if isinstance(records, dict) else model_pool.pool(config, program)
    tasks = model_pool.agent_models(config, program)
    auto = False
    if task == 'default':
        wanted = str(tasks.get('default') or model_pool.AUTO).strip()
        why = '三虎设置里选的默认模型'
        if wanted == model_pool.AUTO:
            auto = True
            complexity = complexity_of(context=context)
            # 规格里的「自动」：复杂任务走「升级模型」那一条，简单／中等才由池子的性价比决定。
            climb = str(tasks.get('escalate') or '').strip() if complexity == 'complex' else ''
            pick = items.get(climb) if climb else None
            if pick is not None and model_pool.available(pick, program):
                wanted = climb
                why = '自动：复杂任务用「升级模型」那一条（%s）' % pick['label']
            else:
                wanted, why = auto_model(items, complexity, program)
            if auto and not wanted:                       # 池里一条能用的都没有：就说这一句，别走降级
                return AgentChoice('', {}, why, task, ok=False)
    else:
        wanted = str(tasks.get(task) or '').strip()
        why = '三虎设置里的%s' % model_pool.TASK_LABELS.get(task, task)
    item = items.get(wanted) if wanted else None
    if item is not None and model_pool.available(item, program):
        return AgentChoice(wanted, item, why, task, auto=auto)
    bad = '%s现在用不了' % (('「%s」' % model_pool.label_of(wanted, items)) if wanted else '这一档还没选模型，')
    fallback_id = str(tasks.get('fallback') or '').strip()
    fallback_item = items.get(fallback_id) if fallback_id else None
    if fallback_item is not None and fallback_id != wanted and model_pool.available(fallback_item, program):
        return AgentChoice(fallback_id, fallback_item, bad + '，按降级模型兜底', task, degraded=True)
    if item is not None:
        reason = bad + '（%s）' % model_pool.status(item, program)[1]
    else:
        reason = bad + '（池里没有这一条，先去模型管理加上）'
    return AgentChoice('', {}, reason, task, ok=False)


def agent_patch(choice, records=None, config=None, program=None):
    """选型 → pet_llm 客户端的配置覆盖（「自动」时是空表：照旧按任务档位走）。"""
    if not getattr(choice, 'ok', False) or getattr(choice, 'auto', False):
        return {}
    return model_pool.patch_for(choice.model, records, config, program)


def missing_setup_hint(destination=''):
    """REL-03：缺模型或引擎时的统一提示——同一句话指出去处，去处可随界面替换。

    挂文件尾部（而不是常量区）：``docs/process/外部依赖清单.md`` 按行号登记本文件的
    四个供应商默认地址，前置插入会让登记失锚。
    """
    return ('需要配置模型或引擎：' + (destination or
            '在「模型管理」里「+ 新增模型…」并保存 API Key；'
            '或安装命令行引擎后在「调用设置」选择其 .exe'))


# A2（EC-5，盘点报告 §B2）：``failure_policy`` 的错误 ``reason_code`` → 登记表错误码。
# ``succeeded`` 与 ``acceptance`` 三值（accepted／not_accepted／unknown）不是错误，不进表。
# 挂文件尾部（同 ``missing_setup_hint`` 的考量）：``docs/process/外部依赖清单.md``
# 按行号登记本文件的四个供应商默认地址，前置插入会让登记失锚。
REASON_CODE_TO_CODE: dict[str, str] = {
    'rate_limit': 'E-NET-RATE-LIMIT',
    'authentication': 'E-AUTH-REJECTED',
    'unsupported_request': 'E-NET-CLIENT',
    'server_error': 'E-NET-SERVER',
    'cancelled': 'E-CANCELLED',
    'receipt_unknown': 'E-RECEIPT-UNKNOWN',
}

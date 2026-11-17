"""DeepSeek 客户端：Flash 默认、Pro 按需、缓存优先、输出限制、错峰、Token 台账。

附件第 10 节的七条策略逐条落在这里：
- Cache First：SYSTEM_PREFIX 是模块级常量，永不拼接时间戳/随机数；消息顺序固定为
  固定前缀 → 项目快照（键序稳定）→ 压缩后的指令，同一状态永远得到同一段前缀。
- 确定性优先：能算的都算在代码里，这里只负责「确实需要推理」的那一小步。
- Flash 默认：TASKS 表里只有复杂推理任务走 Pro，其余一律 Flash；Pro 遇限流/超时/5xx 降级 Flash。
- 输出限制：每个任务带 max_tokens，并被 MAX_OUTPUT_CEILING 兜住（配置写大了也不会失控）。
- 提示词压缩：compress() 只做可复现的机械压缩（去重复行/装饰线/统一空白），结果幂等。
- 批量与错峰：Queue 把非紧急请求推迟到北京时间 23:00-07:00；用户当面指令（urgent）立即发。
- 缓存监控：Ledger 记录 prompt/completion/缓存命中与当日消耗，命中率与 Flash 占比可查，并落盘。
传输函数可注入：测试与离线环境完全不联网。
"""
import json
import logging
import hashlib
import time
from pathlib import Path
import infra.model_pool as model_pool, contract.stage_layout as stage_layout
import infra.token_saver as token_saver
from infra.model_metering import REPLAYABLE_RETRY_STATUS, metered, replayable_retry
from contract.app_metadata import APP_NAME
from agent.core import save
from contract.pet_bus import read_json
from infra.api_endpoints import normalize_url

LOGGER = logging.getLogger('pet_llm')

PROGRAM = Path(__file__).resolve().parents[1]
CONFIG_PATH = ('配置', '宠物', '配置.json')
LEDGER_PATH = (stage_layout.WORKFLOW_DIR, '宠物', 'Token台账.json')

DEFAULTS = {
    'base_url': 'https://api.deepseek.com',
    'path': '/chat/completions',
    'responses_path': '/responses',
    'wire_api': 'chat',                  # chat＝OpenAI 兼容 /chat/completions；responses＝/responses
    'flash_model': 'deepseek-v4-flash',
    'pro_model': 'deepseek-v4-pro',
    'key_env': 'DEEPSEEK_API_KEY',
    'timeout': 60,
    'off_peak': (23, 7),                 # 北京时间，23:00-07:00 是折扣时段
    'max_tokens': {},
    'force_tier': '',                     # 空＝按任务默认；'flash'／'pro' 是宠物「切换模型」按下的显式档位
    # 第 43 期：降级模型那一条（base_url／key_env／path／wire_api／model），上一档限流、超时、
    # 5xx 时用它再发一次；空表＝不降级（老配置读出来就是这个样子，行为与以前一模一样）。
    'fallback': {},
    'budget': {'tokens_per_day': 2000000},
}
TIERS = ('flash', 'pro')
MAX_OUTPUT_CEILING = 2048
# 三虎意图模型只负责路由和短答，不能把整份剧本／资产清单塞进快照；正文创作仍走
# writing_api 的独立预算。限制按字符而非估算 token，保证本地离线也可预测。
REQUEST_CONTEXT_MAX_CHARS = 16000
REQUEST_DIRECTIVE_MAX_CHARS = 16000
RETRY_DELAYS = (30, 60, 120)
RETRYABLE_STATUS = REPLAYABLE_RETRY_STATUS  # 对话可重放口径；提交口径见 model_metering.submission_retryable
MAX_PAID_ATTEMPTS = 3  # 传输层重放与降级链共用的总发送上限：pro→flash→兜底 三步叠加不超过 3 次真实 POST

# 固定前缀：改动它等于让所有历史缓存失效，所以只放长期稳定的内容。
# 第 15 期把人设写进这里（名字＝pet_agent.PET_NAME，改一处要改两处，自检有用例盯着）：
# 名字与口吻长期不变、每次请求都该带上，缓存一次性失效可以接受。
SYSTEM_PREFIX = (
    f'你是{APP_NAME}的宠物 Agent，名字叫三虎：一只可爱的小猫，说话简洁，帮用户把漫剧做完。\n'
    '你负责把一句指令变成一次确定的动作。\n'
    '只输出一行 JSON，字段固定：{"intent": "", "stage": "", "params": {}, "reply": ""}\n'
    'stage 只能是：script storyboard assets final keyframe previs video audio edit delivery。\n'
    '不确定就 intent 填 unknown，reply 用一句中文说明缺什么。\n'
    'reply 是一句中文、尽量短（一行以内），可以带一点猫咪的口吻，但不要卖萌刷屏。\n'
    '不要编造镜头号、资产编号或文件名；不要输出解释性长文。'
)
# 第 64 期任务 10：创意对话不是「抽一句意图」，而是真的写东西，系统提示词得单给一份。
# 别的任务一个字没动：认不出来的任务名照旧用上面那份 SYSTEM_PREFIX。
CHAT_PREFIX = (
    f'你是{APP_NAME}的编剧搭子。用户写一段创意，你把它整理成能直接开拍的漫剧纲要。\n'
    '只写用户要的那份文字：一句话主线、人物、场景、风格、钩子与分集思路，能省的字都省。\n'
    '不要寒暄，不要复述用户的话，不要输出 JSON 或字段名，也不要编造镜头号与文件路径。\n'
    '用中文写，先给一句话主线，再分点。'
)
SYSTEM_BY_TASK = {'chat': CHAT_PREFIX}

TASKS = {
    'intent.route': ('flash', 256),
    'progress.summary': ('flash', 512),
    'shot.prompts': ('flash', 1024),
    'writing.breakdown': ('pro', 2048),
    'prompt.optimize': ('pro', 1536),
    'bug.diagnose': ('pro', 2048),
    'plan.multi_step': ('pro', 1536),
    'chat': ('pro', 2048),                 # 第 64 期任务 10：创意对话（要写长纲要，用 Pro）
}
PRO_TASKS = tuple(task for task, entry in TASKS.items() if entry[0] == 'pro')
DEFAULT_TASK = 'intent.route'


def config_path(program=None):
    return model_pool.config_file(program or PROGRAM)


def named_key(name, program=None):
    """供应商适配器读取统一密钥的兼容门面。"""
    return model_pool.named_key(name) if program is None else model_pool.named_key(name, program)


def save_named_key(name, value, program=None):
    """供应商适配器写入统一密钥的兼容门面。"""
    return (model_pool.save_named_key(name, value) if program is None
            else model_pool.save_named_key(name, value, program))


def ledger_path(project):
    return Path(project).joinpath(*LEDGER_PATH)


def load_config(program=None, config=None):
    """读全局配置：只认识 DEFAULTS 里的键，缺项补默认值；读配置不改磁盘。"""
    # 读不出来（没有／坏 JSON／读不动）一律当空表：损坏的全局配置不能让宠物整块起不来。
    data = config if config is not None else read_json(config_path(program))
    merged = dict(DEFAULTS)
    if isinstance(data, dict):
        merged.update({key: value for key, value in data.items() if key in DEFAULTS})
    return merged


def beijing(now=None):
    """北京时间（UTC+8）：错峰窗口与「当天」都以它为准，不受本机时区影响。"""
    return (time.time() if now is None else float(now)) + 8 * 3600


def clock_hour(now=None):
    return int(beijing(now) % 86400 // 3600)


def in_off_peak(now=None, window=None):
    start, end = window or DEFAULTS['off_peak']
    hour = clock_hour(now)
    return hour >= start or hour < end


def next_off_peak(now=None, window=None):
    """下一次进入折扣时段的时间戳；已经在窗口里就返回当前时间。"""
    start, end = window or DEFAULTS['off_peak']
    now = time.time() if now is None else float(now)
    if in_off_peak(now, (start, end)):
        return now
    local = beijing(now)
    target = local - (local % 86400) + start * 3600
    if target < local:
        target += 86400
    return target - 8 * 3600


def compress(text, limit=None, seen=None):
    """确定性压缩：统一空白、丢掉纯装饰分隔线、重复行只留一次。

    只做可复现的机械压缩——压缩后的每一行都原本就出现过，结果幂等（再压一次不变）。
    """
    kept = []
    marks = set(seen or ())
    for raw in str(text).splitlines():
        line = ' '.join(raw.split())
        if not line or not line.strip('-=*_#~·—'):
            continue
        if line in marks:
            continue
        marks.add(line)
        kept.append(line)
    result = '\n'.join(kept)
    if limit is not None and len(result) > int(limit):
        result = result[:int(limit)]
    return result


def choose(task, config=None):
    """任务 → (档位, max_tokens)。只有复杂推理任务用 Pro，其余一律 Flash。

    配置里写了 force_tier 时以它为准（宠物「换模型」按下的显式档位）：用户按的那一下
    比任务默认更权威；认不出来的值一律忽略，不至于因为写错一个字就换错模型。
    """
    tier, default_max = TASKS.get(task, TASKS[DEFAULT_TASK])
    cfg = load_config(config=config)
    forced = str(cfg.get('force_tier') or '').strip().lower()
    if forced in TIERS:
        tier = forced
    overrides = cfg.get('max_tokens') if isinstance(cfg.get('max_tokens'), dict) else {}
    limit = int(overrides.get(task, default_max))
    return tier, max(1, min(limit, MAX_OUTPUT_CEILING))


def model_for(tier, config=None):
    cfg = load_config(config=config)
    return cfg['pro_model'] if tier == 'pro' else cfg['flash_model']


def credential(config=None, program=None):
    """密钥只从 .env／环境变量／本机加密那份取：配置 JSON 里从不保存密钥。

    第 43 期：与 model_router 的适配器对齐——先看程序目录的 .env，再看 private/.env，
    都找不到才用同名环境变量。原来只认第一处，密钥放在环境变量（或 private/.env）里时，
    三虎整条链路都发不出去，而「模型管理 → 测试连接」说这个模型是好的。

    最后一道是「直接输入」的那把（model_secrets：DPAPI 加密存在 private/密钥 下）——判据只能
    有这一处：界面说这个模型能用，这里就得找得到同一把钥匙。
    """
    cfg = load_config(config=config)
    return model_pool.credential(cfg.get('key_env') or DEFAULTS['key_env'], program)


def key_ok(config=None, program=None):
    """这份配置现在拿得到密钥吗（降级之前先看一眼，免得白跑一次注定失败的请求）。"""
    try:
        return bool(credential(config, program))
    except Exception:
        return False


def fallback_patch(config=None):
    """降级模型那一条 → 一份客户端配置覆盖（没配降级就返回空表，调用方据此跳过）。"""
    cfg = load_config(config=config)
    entry = cfg.get('fallback')
    if not isinstance(entry, dict):
        return {}
    patch = {}
    for key in ('base_url', 'key_env', 'path', 'wire_api', 'responses_path'):
        if entry.get(key):
            patch[key] = entry[key]
    if entry.get('model'):
        patch['flash_model'] = entry['model']
        patch['pro_model'] = entry['model']
    return patch


def headers(config=None, program=None):
    cfg = load_config(config=config)
    return {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + credential(cfg, program)}


def endpoint(config=None):
    cfg = load_config(config=config)
    base = normalize_url(cfg['base_url'])
    return base + (cfg['responses_path'] if cfg.get('wire_api') == 'responses' else cfg['path'])


def snapshot_message(context):
    """项目快照：键序固定（sort_keys），同一状态永远得到同一段文本，前缀缓存才不会被打破。"""
    if not context:
        return ''
    encoded = json.dumps(context, ensure_ascii=False, sort_keys=True, default=str)
    if len(encoded) > REQUEST_CONTEXT_MAX_CHARS:
        # 不截断 JSON（会给模型一段半截结构），改发可审计的稳定摘要。保留顶层键可以让
        # 路由仍知道项目状态的类别，摘要哈希让诊断可关联同一份超限上下文而不泄露内容。
        keys = sorted(str(key) for key in context) if isinstance(context, dict) else []
        encoded = json.dumps({
            'truncated': True,
            'original_chars': len(encoded),
            'sha256_16': hashlib.sha256(encoded.encode('utf-8')).hexdigest()[:16],
            'top_level_keys': keys[:64],
        }, ensure_ascii=False, sort_keys=True)
    return '项目快照：' + encoded


def build_payload(task, text, context=None, config=None, model=None):
    """请求体：固定前缀在前、快照居中、压缩后的指令在后。"""
    cfg = load_config(config=config)
    tier, limit = choose(task, cfg)
    # 第 66 期：消息顺序走 token_saver.layout_messages（固定前缀 → 快照 → 指令）；
    # model_router 那一路用的是同一个函数，「统一前缀布局」全程序只留一份实现。
    fixed = [SYSTEM_BY_TASK.get(task, SYSTEM_PREFIX)]
    snapshot = snapshot_message(context)
    if snapshot:
        fixed.append(snapshot)
    messages = token_saver.layout_messages(
        fixed=fixed, current=compress(text, limit=REQUEST_DIRECTIVE_MAX_CHARS))
    # 不给兼容接口强塞 temperature：部分推理模型会把该字段视为无效请求参数。
    payload = {'model': model or model_for(tier, cfg), 'max_tokens': limit}
    if cfg.get('wire_api') == 'responses':
        payload['input'] = messages
    else:
        payload['messages'] = messages
    return payload


def http_transport(url, payload, headers, timeout, attempt_budget=None):
    """兼容入口：实际传输已下沉至 model_pool 的单向基础设施链。attempt_budget 为可变计数列表时，全链共享发送次数上限。"""
    return model_pool.http_transport(url, payload, headers, timeout, attempt_budget=attempt_budget)


is_retryable = replayable_retry


# 用量口径的唯一实现在 token_saver；这里保留名字给台账与旧调用方。
reported_usage = token_saver.reported_usage


def usage_of(result):
    """取用量：三格总有值；缓存写入只在服务端报了非零时才带 cache_creation_tokens。"""
    data = (result or {}).get('data')
    reported = reported_usage(data.get('usage') if isinstance(data, dict) else None)
    usage = {key: int(reported.get(key) or 0) for key in ('prompt_tokens', 'completion_tokens', 'cached_tokens')}
    if reported.get('cache_creation_tokens'):
        usage['cache_creation_tokens'] = reported['cache_creation_tokens']
    return usage


class Ledger:
    """Token 与成本台账：当日消耗、缓存命中率、Flash 占比、预算硬限制。"""

    def __init__(self, project=None, clock=time.time):
        self.project = Path(project) if project else None
        self.clock = clock
        self.entries = []

    def record(self, model, usage, tier='flash', at=None):
        entry = {'at': float(self.clock() if at is None else at), 'model': str(model), 'tier': str(tier),
                 'prompt_tokens': int(usage.get('prompt_tokens') or 0),
                 'completion_tokens': int(usage.get('completion_tokens') or 0),
                 'cached_tokens': int(usage.get('cached_tokens') or 0)}
        if usage.get('cache_creation_tokens'):
            entry['cache_creation_tokens'] = int(usage['cache_creation_tokens'])
        self.entries.append(entry)
        return entry

    def hit_rate(self):
        prompt = sum(entry['prompt_tokens'] for entry in self.entries)
        cached = sum(entry['cached_tokens'] for entry in self.entries)
        return round(cached / prompt, 3) if prompt else 0.0

    def flash_share(self):
        if not self.entries:
            return 0.0
        return round(sum(1 for entry in self.entries if entry['tier'] == 'flash') / len(self.entries), 3)

    def day_key(self, at=None):
        return time.strftime('%Y-%m-%d', time.gmtime(beijing(at)))

    def today_tokens(self, at=None):
        key = self.day_key(at)
        return sum(entry['prompt_tokens'] + entry['completion_tokens'] for entry in self.entries
                   if self.day_key(entry['at']) == key)

    def over_budget(self, limit, at=None):
        if limit in (None, 0):
            return False
        return self.today_tokens(at) >= int(limit)

    def save(self):
        if self.project is None:
            return None
        path = ledger_path(self.project)
        save(path, {'updated_at': self.clock(), 'entries': self.entries})
        return path

    def load(self):
        if self.project is None:
            return self
        data = read_json(ledger_path(self.project))
        if isinstance(data, dict) and isinstance(data.get('entries'), list):
            self.entries = [entry for entry in data['entries'] if isinstance(entry, dict)]
        return self


class Queue:
    """非实时请求的错峰队列：折扣时段优先发送；用户当面指令（urgent）立即发。"""

    def __init__(self, config=None, clock=time.time):
        self.config = load_config(config=config)
        self.clock = clock
        self.items = []

    def enqueue(self, task, text, urgent=False, at=None):
        now = float(self.clock() if at is None else at)
        window = tuple(self.config.get('off_peak') or DEFAULTS['off_peak'])
        immediate = bool(urgent) or in_off_peak(now, window)
        item = {'task': task, 'text': text, 'urgent': bool(urgent), 'queued_at': now,
                'send_after': now if immediate else next_off_peak(now, window)}
        self.items.append(item)
        return item

    def ready(self, at=None):
        now = float(self.clock() if at is None else at)
        due = [item for item in self.items if item['send_after'] <= now]
        self.items = [item for item in self.items if item['send_after'] > now]
        return due


class Client:
    """一次调用＝构造（缓存优先）→ 发送（可注入传输）→ 降级 → 记账。ask() 不抛异常。"""

    def __init__(self, project=None, config=None, transport=None, clock=time.time, program=None):
        self.project = Path(project) if project else None
        self.config = load_config(config=config)
        self.transport = transport or http_transport
        self.clock = clock
        self.program = program
        self.ledger = Ledger(self.project, clock=clock)
        self.calls = []

    def payload(self, task, text, context=None, model=None, config=None):
        return build_payload(task, text, context, config or self.config, model)

    def flush(self):
        return self.ledger.save()

    def _record_diagnostic(self, result, task, tier, cfg, context=None, path=None):
        """每次发送前保存未知事件，响应后原位更新；正文和凭据不落盘。"""
        if self.project is None:
            return None
        from infra.model_diagnostics import record, event
        envelope = dict(result or {})
        envelope['response_meta'] = {
            'requested_model': str(envelope.get('model') or ''),
            'wire_api': str(cfg.get('wire_api') or ''),
        }
        metadata = {'subsystem': 'pet', 'task': task, 'tier': tier, **(context or {})}
        if path is not None:
            save(path, event(envelope, context=metadata))
            return path
        return record(self.project, envelope, context=metadata)

    def _attempt(self, send, url, payload, head, timeout, task, tier, cfg, context, at):
        model = payload.get('model')
        pending = {'ok': False, 'status': None, 'model': model, 'usage': {},
                   'error_class': 'pending'}
        path = self._record_diagnostic(pending, task, tier, cfg, context)
        ledger = RequestLedger(self.project) if self.project else None

        def usage_of(result):
            data = result.get('data')
            return reported_usage(data.get('usage') if isinstance(data, dict) else None)

        def diagnose(result, usage):
            self._record_diagnostic({**result, 'model': model, 'usage': usage},
                                    task, tier, cfg, context, path)
        if ledger:
            estimate = len(json.dumps(payload, ensure_ascii=False).encode('utf-8')) + 256
            result, usage, rejected = metered(
                ledger, (context['request_id'], model, context['stage'], estimate, int(payload['max_tokens'])),
                lambda: send(url, payload, head, timeout), usage_of, on_result=diagnose)
            if rejected is not None:
                result = {'ok': False, 'status': 0, 'kind': 'budget', 'error': str(rejected), 'usage': {}}
                self._record_diagnostic({**result, 'model': model, 'error_class': 'budget'}, task, tier, cfg, {**context, 'not_submitted': True}, path)
                return result
        else:
            result = send(url, payload, head, timeout)
            usage = usage_of(result)
            diagnose(result, usage)
        if usage:
            self.ledger.record(model, usage, tier=tier, at=at)
        return result

    def ask(self, task, text, context=None, urgent=False, transport=None, at=None, model_patch=None):
        """发起一次请求；model_patch 仅覆盖本次调用的模型连接配置。"""
        cfg = dict(self.config)
        if isinstance(model_patch, dict):
            cfg.update(model_patch)
        try:
            budget = (cfg.get('budget') or {}).get('tokens_per_day')
            if self.ledger.over_budget(budget, at):
                return {'ok': False, 'status': 0, 'kind': 'budget', 'error': 'Token 预算已用完，已暂停自动调用', 'model': None,
                        'degraded': False, 'budget': True, 'usage': usage_of(None), 'request': None}
            tier, _limit = choose(task, cfg)
            send = transport or self.transport
            attempt_budget = None
            if transport is None and self.transport is http_transport:
                attempt_budget = [MAX_PAID_ATTEMPTS]
                inner_send = send

                def send(url, payload, head, timeout, _inner=inner_send, _budget=attempt_budget):
                    return _inner(url, payload, head, timeout, attempt_budget=_budget)
            url = endpoint(cfg)
            head = headers(cfg, self.program)
            timeout = cfg.get('timeout', DEFAULTS['timeout'])
            model = model_for(tier, cfg)
            payload = self.payload(task, text, context, model=model, config=cfg)
            from uuid import uuid4
            invocation = uuid4().hex
            stage = str((context or {}).get('stage') or 'assistant')
            attempt = 0

            def send_attempt(attempt_tier):
                nonlocal attempt
                attempt += 1
                metadata = {'stage': stage, 'invocation_id': invocation,
                            'request_id': invocation + '-' + str(attempt), 'attempt': attempt}
                return self._attempt(send, url, payload, head, timeout, task,
                                     attempt_tier, cfg, metadata, at)

            result = send_attempt(tier)
            degraded = False
            if not result.get('ok') and result.get('kind') != 'budget' and tier == 'pro' and is_retryable(result.get('status')):
                degraded = True
                model = model_for('flash', cfg)
                payload = self.payload(task, text, context, model=model, config=cfg)
                result = send_attempt('flash')
            # 第 43 期：还不行就把「三虎设置 → 模型」里那条降级模型接上，再发最后一次。
            # 刚才试过的那条（含档位上这两条）不重复试；密钥拿不到就不白跑。
            patch = fallback_patch(cfg)
            spent = {model, model_for('flash', cfg), model_for('pro', cfg)}
            if (not result.get('ok') and result.get('kind') != 'budget' and patch and is_retryable(result.get('status'))
                    and patch.get('pro_model') not in spent):
                switched = {**cfg, **patch}
                if key_ok(switched, self.program):
                    cfg, degraded = switched, True
                    url = endpoint(cfg)
                    head = headers(cfg, self.program)
                    model = model_for(tier, cfg)
                    payload = self.payload(task, text, context, model=model, config=cfg)
                    result = send_attempt(tier)
            usage = usage_of(result)
            self.calls.append({'task': task, 'model': model, 'status': result.get('status'),
                               'degraded': degraded, 'urgent': bool(urgent)})
            reply = {'ok': bool(result.get('ok')), 'status': result.get('status'), 'error': result.get('error'),
                     'data': result.get('data'), 'model': model, 'degraded': degraded, 'budget': result.get('kind') == 'budget',
                     'usage': usage, 'request': payload, 'url': url, 'kind': result.get('kind')}
            return reply
        except Exception as exc:                     # 界面线程调用：出错也要给出结构化结果，不抛异常
            LOGGER.exception('模型调用异常')
            return {'ok': False, 'status': 0, 'kind': 'bug', 'error': type(exc).__name__ + '：' + str(exc),
                    'model': None,
                    'degraded': False, 'budget': False, 'usage': usage_of(None), 'request': None}


from infra.request_ledger import REQUEST_KINDS, BudgetRejected, RequestLedger, record_request, request_ledger_path

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
import os
import time
import threading
from contextlib import contextmanager
from pathlib import Path
import model_pool
import token_saver
from app_metadata import APP_NAME
from agent.core import save
from pet_bus import read_json
from api_endpoints import configured_key, normalize_url

LOGGER = logging.getLogger(__name__)
_REQUEST_LOCK = threading.RLock()

PROGRAM = Path(__file__).resolve().parent
CONFIG_PATH = ('配置', '宠物', '配置.json')
LEDGER_PATH = ('工作流任务', '宠物', 'Token台账.json')

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
RETRYABLE_STATUS = (0, 408, 409, 425, 429, 500, 502, 503, 504)

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


def http_transport(url, payload, headers, timeout):
    """兼容入口：实际传输已下沉至 model_pool 的单向基础设施链。"""
    return model_pool.http_transport(url, payload, headers, timeout)


def is_retryable(status):
    return status in RETRYABLE_STATUS


def usage_of(result):
    """取用量：DeepSeek 用 prompt_cache_hit_tokens 报告命中缓存的部分。"""
    data = (result or {}).get('data')
    usage = data.get('usage') if isinstance(data, dict) else None
    usage = usage if isinstance(usage, dict) else {}
    # 第 66 期：命中那一格两家的写法不同——DeepSeek 报 prompt_cache_hit_tokens，
    # Claude 报 cache_read_input_tokens；口径统一成 cached_tokens，台账只认这一格。
    cached = usage.get('prompt_cache_hit_tokens') or usage.get('cache_read_input_tokens') or 0
    return {'prompt_tokens': int(usage.get('prompt_tokens') or usage.get('input_tokens') or 0),
            'completion_tokens': int(usage.get('completion_tokens') or usage.get('output_tokens') or 0),
            'cached_tokens': int(cached)}


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
        from model_diagnostics import record, event
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
        if ledger:
            estimate = len(json.dumps(payload, ensure_ascii=False).encode('utf-8')) + 256
            try:
                ledger.authorize_model(context['request_id'], model, context['stage'], estimate, int(payload['max_tokens']))
            except (ValueError, OSError) as error:
                result = {'ok': False, 'status': 0, 'kind': 'budget', 'error': str(error), 'usage': {}}
                self._record_diagnostic({**result, 'model': model, 'error_class': 'budget'}, task, tier, cfg, {**context, 'not_submitted': True}, path)
                return result
        try:
            result = send(url, payload, head, timeout)
        except Exception:
            if ledger:
                ledger.settle_model(context['request_id'], {})
            raise
        data = result.get('data')
        raw = data.get('usage') if isinstance(data, dict) else None
        usage = {}
        if isinstance(raw, dict):
            aliases = {'prompt_tokens': ('prompt_tokens', 'input_tokens'),
                       'completion_tokens': ('completion_tokens', 'output_tokens'),
                       'cached_tokens': ('cached_tokens', 'prompt_cache_hit_tokens', 'cache_read_input_tokens'),
                       'total_tokens': ('total_tokens',)}
            for key, names in aliases.items():
                for name in names:
                    value = raw.get(name)
                    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
                        usage[key] = value
                        break
        self._record_diagnostic({**result, 'model': model, 'usage': usage},
                                task, tier, cfg, context, path)
        if ledger:
            ledger.settle_model(context['request_id'], usage)
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

# ── O29 请求级可对账台账 ─────────────────────────────────────────────────────
# 与 Token 台账分工：Token 台账算「当天花了多少」，这里回答「这一笔请求怎么回事」——
# 请求号、调用种类、估计还是实报、预留还是结算、关联哪个远端任务。token／秒／次数
# 各列各的，不把它们相加成金额；价格表可选，带上版本与日期；缺 usage 记「未知」而不是 0。
REQUEST_LEDGER_PATH = ('工作流任务', '宠物', '请求台账.json')
REQUEST_KINDS = ('tokens', 'seconds', 'images', 'videos', 'requests')
REQUEST_STATES = ('reserved', 'settled', 'unknown', 'cancelled', 'duplicate')
REQUEST_MODES = ('estimated', 'reported', 'unknown')


def request_ledger_path(project):
    return Path(project).joinpath(*REQUEST_LEDGER_PATH)


class BudgetRejected(ValueError):
    """请求未发送：金额预留未通过。"""


class RequestLedger:
    """一条请求一行：预留 → 结算／未知／取消，同一请求号只认一笔（重试不重复结算）。"""

    def __init__(self, project=None, clock=time.time):
        self.project = Path(project) if project else None
        self.clock = clock
        self.entries = []

    def _find(self, request_id, kind=None):
        rid = str(request_id)
        for entry in self.entries:
            if entry.get('id') == rid and (kind is None or entry.get('kind') == kind):
                return entry
        return None

    def _stamp(self, at):
        return float(self.clock() if at is None else at)

    def _remote_owner(self, remote_task_id):
        if not remote_task_id:
            return None
        for entry in self.entries:
            if entry.get('remote_task_id') == remote_task_id and entry.get('state') != 'duplicate':
                return entry
        return None

    def reserve(self, request_id, kind, amount, *, remote_task_id=None, note='', at=None):
        """先占一笔：同一请求号＋种类只占一次；已有就原样返回（重试不重复预留）。"""
        existing = self._find(request_id, kind)
        if existing is not None:
            return existing
        amount = self._quantity(amount)
        entry = {'id': str(request_id), 'kind': str(kind), 'amount': amount,
                 'mode': 'estimated', 'state': 'reserved', 'remote_task_id': None,
                 'note': str(note or ''), 'at': self._stamp(at), 'settled_at': None}
        self.entries.append(entry)
        if remote_task_id:
            self.link(request_id, remote_task_id)
        return entry

    def link(self, request_id, remote_task_id):
        """把请求号绑到远端任务号；同一远端任务只认第一笔账单，后来者标 duplicate。"""
        entry = self._find(request_id)
        if entry is None or not remote_task_id:
            return entry
        task = str(remote_task_id)
        owner = self._remote_owner(task)
        if owner is not None and owner.get('id') != entry.get('id'):
            entry['state'] = 'duplicate'
            entry['note'] = '同一远端任务已由请求 ' + str(owner.get('id')) + ' 记账，本笔不重复结算'
            return entry
        entry['remote_task_id'] = task
        return entry

    def settle(self, request_id, *, kind=None, amount=None, usage=None, mode='reported',
               remote_task_id=None, note='', at=None):
        """结算实报量：同一请求号只写一次，重复调用只是覆盖，不会翻倍。"""
        entry = self._find(request_id, kind)
        if entry is None:
            entry = self.reserve(request_id, kind or ('tokens' if usage is not None else 'requests'), 0)
        if entry.get('state') == 'duplicate':
            return entry
        if amount is None and isinstance(usage, dict):
            total = usage.get('total_tokens')
            if total is None:
                total = (usage.get('prompt_tokens') or 0) + (usage.get('completion_tokens') or 0)
            amount = total
        if amount is None:
            return self.mark_unknown(request_id, reason=note or '结算时没有可用量', at=at)
        entry['amount'] = self._quantity(amount)
        entry['mode'] = str(mode)
        entry['state'] = 'settled'
        entry['settled_at'] = self._stamp(at)
        if remote_task_id:
            entry['remote_task_id'] = str(remote_task_id)
        if note:
            entry['note'] = str(note)
        return entry

    def mark_unknown(self, request_id, *, reason='', at=None):
        """用量的确不知道时记「未知」：既不记 0（会显示成免费），也不丢这笔账。"""
        entry = self._find(request_id)
        if entry is None:
            entry = self.reserve(request_id, 'requests', 0)
        if entry.get('state') == 'duplicate':
            return entry
        entry['state'] = 'unknown'
        entry['mode'] = 'unknown'
        entry['amount'] = None
        entry['settled_at'] = self._stamp(at)
        if reason:
            entry['note'] = str(reason)
        return entry

    def cancel(self, request_id, *, reason='', at=None):
        """取消只改本机记录：不伪造远端退款，也不抹掉已经实报的用量。"""
        entry = self._find(request_id)
        if entry is None:
            return None
        entry['state'] = 'cancelled'
        entry['cancelled_at'] = self._stamp(at)
        if entry.get('mode') != 'reported':
            entry['mode'] = 'unknown'
            entry['amount'] = None
        if reason:
            entry['note'] = str(reason)
        return entry

    def report(self, price_table=None, currency='CNY'):
        """汇总：token／秒／次数各列各的，另给未知、重复、取消的编号；配了价格表才折算金额。"""
        kinds = {kind: {'settled': 0.0, 'reserved': 0.0, 'unknown': 0, 'count': 0}
                 for kind in REQUEST_KINDS}
        unknown, duplicates, cancelled = [], [], []
        for entry in self.entries:
            if entry.get('cost_only'):
                continue
            kind = entry.get('kind')
            bucket = kinds.setdefault(kind, {'settled': 0.0, 'reserved': 0.0, 'unknown': 0, 'count': 0})
            state = entry.get('state')
            if state == 'duplicate':
                duplicates.append(entry.get('id'))
                continue
            bucket['count'] += 1
            if state == 'cancelled':
                # 取消不退款：已经实报的量继续计，没上报的算未知，都不记 0。
                cancelled.append(entry.get('id'))
                if entry.get('mode') == 'reported' and entry.get('amount') is not None:
                    bucket['settled'] += float(entry['amount'])
                else:
                    bucket['unknown'] += 1
                    unknown.append(entry.get('id'))
                continue
            if state == 'unknown' or entry.get('mode') == 'unknown':
                bucket['unknown'] += 1
                unknown.append(entry.get('id'))
                continue
            if state == 'settled':
                bucket['settled'] += float(entry.get('amount') or 0)
            elif state == 'reserved':
                bucket['reserved'] += float(entry.get('amount') or 0)
        out = {'kinds': kinds, 'unknown_ids': unknown, 'duplicate_ids': duplicates,
               'cancelled_ids': cancelled,
               'requests': sum(bucket['count'] for bucket in kinds.values())}
        if price_table:
            out['money'] = self.price(kinds, price_table, currency)
            out['money']['estimated_requests'] = sum(
                1 for entry in self.entries if entry.get('state') == 'settled' and entry.get('mode') == 'estimated')
            if out['money']['estimated_requests']:out['money']['complete'] = False
        if price_table and any('money_state' in row for row in self.entries):
            out['money'] = self.priced_models(price_table, currency)
        out['model_costs'] = self.model_costs()
        return out

    def priced_models(self, price_table, currency):
        legacy = RequestLedger()
        legacy.entries = [row for row in self.entries if 'money_state' not in row and not row.get('cost_group')]
        money = legacy.report(price_table, currency)['money']
        spent, held = self.decimal(money['settled_amount']), self.decimal(money['reserved_amount'])
        versions = set()
        for row in self.entries:
            if 'money_state' not in row or row.get('state') == 'duplicate':
                continue
            versions.add(str(row.get('price_version') or 'unknown'))
            cost = row.get('budget_cost')
            if cost is None or row.get('currency') != money['currency']:
                money['missing_rates'].append(str(row.get('model') or 'unknown'))
                money['complete'] = False
                continue
            if row['money_state'] in ('estimated', 'reconciled'):
                spent += self.decimal(cost)
            else:
                held += self.decimal(cost)
                money['complete'] = False
                if row['money_state'] == 'unknown':
                    money['unknown_requests'] += 1
        money.update(settled_amount=float(round(spent, 4)), reserved_amount=float(round(held, 4)),
                     amount=float(round(spent + held, 4)), frozen_model_price_versions=sorted(versions))
        return money

    def model_costs(self):
        groups = {}
        for row in self.entries:
            if 'money_state' not in row or row.get('state') == 'duplicate':
                continue
            currency = str(row.get('currency') or '币种未配置')
            group = groups.setdefault(currency, {'estimated_spent': '0', 'reconciled_spent': '0', 'held': '0', 'unknown': 0})
            if row.get('budget_cost') is None or row['money_state'] == 'unknown':
                group['unknown'] += 1
            if row.get('budget_cost') is not None:
                key = {'estimated': 'estimated_spent', 'reconciled': 'reconciled_spent'}.get(row['money_state'], 'held')
                group[key] = str(self.decimal(group[key]) + self.decimal(row['budget_cost']))
        return groups

    @staticmethod
    def _quantity(value):
        import math
        if isinstance(value, bool):raise ValueError('用量或费率必须是有限非负数')
        try: number = float(value)
        except (ValueError, TypeError):raise ValueError('用量或费率必须是有限非负数') from None
        if not math.isfinite(number) or number < 0:raise ValueError('用量或费率必须是有限非负数')
        return number

    @staticmethod
    def price(kinds, price_table, currency='CNY'):
        """只有配了价格表才折算金额；带上价格表的版本／日期，缺费率不猜。"""
        table = price_table if isinstance(price_table, dict) else {}
        rates = table.get('rates') if isinstance(table.get('rates'), dict) else {}
        from decimal import Decimal
        settled, reserved, missing, unknown = Decimal(0), Decimal(0), [], 0
        for kind, bucket in kinds.items():
            unknown += bucket.get('unknown', 0)
            rate = rates.get(kind)
            if rate is None:
                if bucket.get('settled') or bucket.get('reserved'):
                    missing.append(kind)
                continue
            rate = Decimal(str(RequestLedger._quantity(rate)))
            settled += Decimal(str(RequestLedger._quantity(bucket.get('settled', 0)))) * rate
            reserved += Decimal(str(RequestLedger._quantity(bucket.get('reserved', 0)))) * rate
        return {'amount': float(round(settled + reserved, 4)),
                'settled_amount': float(round(settled, 4)), 'reserved_amount': float(round(reserved, 4)),
                'unknown_requests': unknown, 'complete': not missing and not unknown and not any(
                    bucket.get('reserved') for bucket in kinds.values()),
                'currency': str(table.get('currency') or currency),
                'table_version': table.get('version'), 'table_at': table.get('at'),
                'missing_rates': sorted(missing)}

    def save(self):
        if self.project is None:
            return None
        path = request_ledger_path(self.project)
        save(path, {'updated_at': self.clock(), 'entries': self.entries})
        return path

    def load(self):
        if self.project is None:
            return self
        from agent.core import read
        path = request_ledger_path(self.project)
        data = read(path) if path.exists() else {'entries': []}
        if (not isinstance(data, dict) or not isinstance(data.get('entries'), list)
                or any(not isinstance(row, dict) for row in data['entries'])):
            raise ValueError('请求台账损坏，请恢复后继续')
        self.entries = data['entries']
        return self

    @contextmanager
    def transaction(self):
        """重新读盘、检查、保存共用同一把跨进程锁，防止并发覆盖与超支。"""
        with _REQUEST_LOCK:
            if self.project is None:
                yield
                return
            path = request_ledger_path(self.project).with_suffix('.lock')
            path.parent.mkdir(parents=True, exist_ok=True)
            import msvcrt
            with path.open('a+b') as stream:
                if not path.stat().st_size:
                    stream.write(b'0')
                    stream.flush()
                stream.seek(0)
                try:
                    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                except OSError:
                    raise ValueError('请求台账正在更新，请稍后重试') from None
                try:
                    self.load()
                    yield
                    self.save()
                finally:
                    stream.seek(0)
                    msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)

    @staticmethod
    def decimal(value):
        from decimal import Decimal, InvalidOperation
        try:
            result = Decimal(str(value))
        except (InvalidOperation, ValueError):
            raise ValueError('金额和费率必须是有限非负数') from None
        if isinstance(value, bool) or not result.is_finite() or result < 0:
            raise ValueError('金额和费率必须是有限非负数')
        return result

    def authorize_model(self, request_id, model, stage, input_estimate, output_limit):
        """冻结配置费率及估计用量；启用金额上限后，未知费用不能按零继续。"""
        if type(input_estimate) is not int or input_estimate < 0 or type(output_limit) is not int or output_limit < 0:
            raise ValueError('请求用量预估必须是非负整数')
        return self.authorize_units(request_id, model, stage, 'tokens',
                                    {'prompt_tokens': input_estimate, 'completion_tokens': output_limit})

    @classmethod
    def _model_price(cls, table, model, quantities):
        rate_map = table.get('model_rates') or {}
        if not isinstance(rate_map, dict):
            raise ValueError('模型费率格式不正确')
        rates = rate_map.get(model)
        known = isinstance(rates, dict) and all(key in rates for key in quantities)
        known = known and bool(table.get('version')) and bool(table.get('currency'))
        rates = {key: str(cls.decimal(rates[key])) for key in quantities} if known else None
        cost = sum((value * cls.decimal(rates[key]) for key, value in quantities.items()), cls.decimal(0)) if rates else None
        return rates, cost

    def preview_units(self, model, kind, quantities):
        """只读批次报价快照；不建账、不预留，执行时仍逐请求原子检查。"""
        from agent.core import read
        if not quantities or kind not in REQUEST_KINDS:
            raise ValueError('请求用量单位不能为空或未知')
        quantities = {key: self.decimal(value) for key, value in quantities.items()}
        self.load()
        path = self.project / 'cost_profile.json' if self.project else None
        profile = read(path) if path is not None and path.exists() else {}
        if not isinstance(profile, dict) or not isinstance(profile.get('price_table', {}), dict):
            raise ValueError('成本配置格式不正确')
        table = profile.get('price_table', {})
        _rates, cost = self._model_price(table, model, quantities)
        cap = self.decimal(profile['budget_amount']) if profile.get('budget_amount') is not None else None
        reasons = []
        if cost is None:
            reasons.append('金额预算需要模型费率、币种和价格表版本，请先配置')
        if kind == 'tokens' and quantities.get('completion_tokens', 0) <= 0:
            reasons.append('金额预算需要明确的输出Token上限')
        used = self.decimal(0)
        try:
            self.check_legacy_video_costs('')
        except ValueError as exc:
            reasons.append(str(exc)); used = None
        for row in self.entries:
            if row.get('state') == 'duplicate' or row.get('cost_group'):
                continue
            if row.get('budget_cost') is None or row.get('currency') != table.get('currency'):
                reasons.append('存在未计价费用或币种不一致，请核对后继续'); used = None
            elif used is not None:
                used += self.decimal(row['budget_cost'])
        if cap is not None and used is not None and cost is not None and used + cost > cap:
            reasons.append('超过项目金额预算，请核对费用或明确提高预算后重试')
        return {'model': model, 'currency': table.get('currency'), 'price_version': table.get('version'),
                'cost': str(cost) if cost is not None else None,
                'used': str(used) if used is not None else None,
                'cap': str(cap) if cap is not None else None,
                'remaining': str(cap - used) if cap is not None and used is not None else None,
                'notes': list(dict.fromkeys(reasons)), 'allowed': cap is None or not reasons}

    def preview_text(self, model, kind, quantities):
        quote = self.preview_units(model, kind, quantities)
        if not quote['allowed']:
            raise ValueError('本批次金额预检未通过：' + '；'.join(quote['notes']))
        currency = quote['currency'] or '币种未配置'
        return ('模型：%s；价格版本：%s。\n本批预计：%s %s；项目已占用（含预留）：%s %s。\n'
                '项目金额上限：%s；剩余金额：%s。\n%s\n预估不锁定额度；每次发送前重新核验，实际账单需核对。') % (
                    model, quote['price_version'] or '未配置', quote['cost'] or '未知', currency,
                    quote['used'] if quote['used'] is not None else '未知', currency,
                    quote['cap'] if quote['cap'] is not None else '未启用',
                    quote['remaining'] if quote['remaining'] is not None else '未知', '；'.join(quote['notes']))

    def legacy_video_costs(self, request_id=''):
        """只读归组旧视频来源；只保存摘要，不复制提示词、配置或私有任务内容。"""
        groups = {}
        if self.project is None:
            return groups
        from agent.core import read
        def fingerprint(value):
            return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode('utf-8')).hexdigest()
        def add(workspace, key, source, value, *, pending=False, root_row=None):
            relative = workspace.relative_to(self.project).as_posix()
            gid = 'legacy-cost:' + fingerprint([relative, key])
            group = groups.setdefault(gid, {'label': relative + ' / ' + key, 'sources': [], 'pending': False, 'root_rows': []})
            group['sources'].append({'source': source, 'sha256': fingerprint(value)})
            group['pending'] |= pending
            if root_row is not None:
                group['root_rows'].append(root_row)
        workspaces = [self.project]
        cloud = self.project / 'cloud_video'
        if cloud.exists():
            workspaces.extend(sorted(path for path in cloud.iterdir() if path.is_dir()))
        for workspace in workspaces:
            legacy = self if workspace == self.project else RequestLedger(workspace).load()
            for row in legacy.entries:
                rid = str(row.get('id') or '')
                if row.get('state') == 'duplicate' or row.get('cost_only'):
                    continue
                if workspace == self.project and ('money_state' in row or not rid.startswith('video:')):
                    continue
                accounted = self._find(rid, row.get('kind'))
                if workspace != self.project and accounted and 'money_state' in accounted and not accounted.get('cost_only'):
                    continue
                key = rid.rsplit(':', 1)[0] if rid.startswith('video:') and rid.endswith((':count', ':seconds')) else rid
                add(workspace, key, 'ledger:' + rid + ':' + str(row.get('kind')),
                    {k: v for k, v in row.items() if k != 'cost_group'},
                    pending=row.get('state') == 'reserved', root_row=row if workspace == self.project else None)
            path = workspace / 'data' / 'state.json'
            if not path.exists():
                continue
            state = read(path)
            shots = state.get('shots') if isinstance(state, dict) else None
            if not isinstance(shots, dict) or any(not isinstance(vs, list) for vs in shots.values()):
                raise ValueError('旧视频任务状态损坏，无法核对历史费用：' + workspace.name)
            for sid, versions in shots.items():
                for index, version in enumerate(versions, 1):
                    if not isinstance(version, dict):
                        raise ValueError('旧视频任务记录损坏，无法核对历史费用')
                    if version.get('not_submitted') is True:
                        continue
                    rid = version.get('money_request_id') or 'video:' + str(version.get('local_request', ''))
                    accounted = self._find(rid)
                    if rid == request_id or (accounted and 'money_state' in accounted and not accounted.get('cost_only')):
                        continue
                    key = f"video:{sid}:v{version.get('version', index)}"
                    add(workspace, key, 'task:' + key, version,
                        pending=version.get('state') in ('submitting', 'queued', 'running'))
        for group in groups.values():
            group['sources'].sort(key=lambda source: (source['source'], source['sha256']))
            group['digest'] = fingerprint(group['sources'])
        return groups

    def check_legacy_video_costs(self, request_id):
        for gid, group in self.legacy_video_costs(request_id).items():
            entry = self._find(gid)
            if entry is None or entry.get('legacy_digest') != group['digest']:
                label = '旧视频任务费用' if any(s['source'].startswith('task:') for s in group['sources']) else '旧视频会话费用'
                raise ValueError(label + '尚未纳入项目总账或来源已变化，请导入后核对：' + group['label'])

    def import_legacy_video_costs(self):
        """显式导入未知费用；源会话不修改，来源变化使原金额失效并保留审计。"""
        changed = 0
        with self.transaction():
            groups = self.legacy_video_costs()
            for gid, group in groups.items():
                entry = self._find(gid)
                if entry is not None and entry.get('legacy_digest') == group['digest']:
                    continue
                if entry is None:
                    entry = self.reserve(gid, 'videos', 0)
                    entry.update(cost_only=True, stage='legacy-video')
                else:
                    entry.setdefault('legacy_changes', []).append({
                        'at': self.clock(), 'digest': entry.get('legacy_digest'),
                        'budget_cost': entry.get('budget_cost'), 'money_state': entry.get('money_state')})
                entry.update(legacy_digest=group['digest'], legacy_sources=group['sources'],
                             legacy_label=group['label'], money_state='unknown', budget_cost=None,
                             state='reserved' if group['pending'] else 'unknown', mode='unknown')
                for row in group['root_rows']:
                    row['cost_group'] = gid
                changed += 1
        return changed

    def authorize_units(self, request_id, model, stage, kind, quantities, *, amount=None):
        """所有模型共用金额上限；按明确计费单位冻结预留。"""
        from agent.core import read
        if not quantities or kind not in REQUEST_KINDS:
            raise ValueError('请求用量单位不能为空或未知')
        quantities = {key: self.decimal(value) for key, value in quantities.items()}
        with self.transaction():
            if self._find(request_id) is not None:
                raise ValueError('该请求已有记录，请核对原任务，不能重复发送')
            path = self.project / 'cost_profile.json' if self.project else None
            profile = read(path) if path is not None and path.exists() else {}
            if not isinstance(profile, dict):
                raise ValueError('成本配置格式不正确')
            table = profile.get('price_table') or {}
            if not isinstance(table, dict):
                raise ValueError('价格表格式不正确')
            cap = profile.get('budget_amount')
            if cap is not None:
                cap = self.decimal(cap)
                self.check_legacy_video_costs(request_id)
                if kind == 'tokens' and quantities.get('completion_tokens', 0) <= 0:
                    raise ValueError('金额预算需要明确的输出Token上限')
            rates, cost = self._model_price(table, model, quantities)
            if cap is not None:
                if not rates or not table.get('version') or not table.get('currency'):
                    raise ValueError('金额预算需要模型费率、币种和价格表版本，请先配置')
                used = self.decimal(0)
                for row in self.entries:
                    if row.get('state') == 'duplicate' or row.get('cost_group'):
                        continue
                    money = row.get('budget_cost')
                    if money is None or row.get('currency') != table['currency']:
                        raise ValueError('存在未计价费用或币种不一致，请核对后继续')
                    used += self.decimal(money)
                if used + cost > cap:
                    raise ValueError('超过项目金额预算，请核对费用或明确提高预算后重试')
            entry = self.reserve(request_id, kind, sum(quantities.values()) if amount is None else amount)
            entry.update(model=model, stage=stage, input_estimate=float(quantities.get('prompt_tokens', 0)),
                         output_limit=float(quantities.get('completion_tokens', 0)),
                         quantities={key: str(value) for key, value in quantities.items()},
                         rates=rates, price_version=table.get('version'), currency=table.get('currency'),
                         budget_cost=str(cost) if cost is not None else None, money_state='reserved')
            return dict(entry)

    @contextmanager
    def metered_units(self, request_id, model, stage, kind, amount, *, quantities=None):
        """成功产物按单价估算；任何发送后异常都不自动释放额度。"""
        try:
            self.authorize_units(request_id, model, stage, kind, quantities if quantities is not None else {kind: amount}, amount=amount)
        except (ValueError, OSError) as exc:
            raise BudgetRejected(str(exc)) from exc
        try:
            yield
        except Exception:
            self.settle_units(request_id)
            raise
        else:
            self.settle_units(request_id, amount=amount)

    def settle_units(self, request_id, *, amount=None, remote_task_id=None):
        """异步生成与同步请求共享结算；未知不释放费用，重复回执不重复计费。"""
        with self.transaction():
            entry = self._find(request_id)
            if entry is None:
                raise ValueError('请求预留记录缺失')
            if entry.get('money_state') == 'reconciled':
                return
            if remote_task_id:
                self.link(request_id, remote_task_id)
            if entry.get('state') == 'duplicate' or entry.get('money_state') in ('estimated', 'reconciled'):
                return
            if amount is None:
                self.mark_unknown(request_id)
                entry['money_state'] = 'unknown'
            else:
                self.settle(request_id, amount=amount, mode='estimated')
                entry['money_state'] = 'estimated'

    def settle_model(self, request_id, usage):
        """费用按冻结费率估算；未报齐输入/输出用量时保留全部预留，不假装退款。"""
        with self.transaction():
            entry = self._find(request_id)
            if entry is None:
                raise ValueError('请求预留记录缺失')
            if entry.get('money_state') == 'reconciled' or (entry.get('state') == 'settled' and entry.get('money_state') == 'estimated'):
                return
            keys = ('prompt_tokens', 'completion_tokens')
            known = all(type(usage.get(key)) is int and usage[key] >= 0 for key in keys)
            if not known:
                self.mark_unknown(request_id)
                entry['money_state'] = 'unknown'
                return
            self.settle(request_id, usage=usage)
            rates = entry.get('rates')
            cost = sum((self.decimal(usage[key]) * self.decimal(rates[key]) for key in keys), self.decimal(0)) if rates else None
            entry.update(budget_cost=str(cost) if cost is not None else None, money_state='estimated')

    def reconcile_cost(self, request_id, kind, amount, currency, evidence, reviewer):
        """人工核对请求的最终账单金额，保留每次修订，不改变远端任务状态。"""
        amount = self.decimal(amount)
        currency, reviewer = str(currency).strip().upper(), str(reviewer).strip()
        if len(currency) != 3 or not currency.isascii() or not currency.isalpha() or not reviewer:
            raise ValueError('请填写三字母币种和核对人')
        path = Path(evidence)
        if not path.is_file() or path.stat().st_size == 0:
            raise ValueError('请选择非空的本地账单凭据文件')
        digest = hashlib.sha256()
        with path.open('rb') as stream:
            for chunk in iter(lambda: stream.read(65536), b''):
                digest.update(chunk)
        with self.transaction():
            entry = self._find(request_id, kind)
            if entry is None or entry.get('state') not in ('unknown', 'settled', 'cancelled'):
                raise ValueError('只能核对已结算、未知或已取消请求，进行中请求请先查询最终结果')
            if entry.get('cost_group'):
                raise ValueError('该用量已合并，请核对对应的旧视频费用组')
            if entry.get('cost_only'):
                current = self.legacy_video_costs().get(request_id)
                if current is None or current['digest'] != entry.get('legacy_digest'):
                    raise ValueError('旧视频来源已变化，请重新导入后核对')
            if entry.get('currency') and str(entry['currency']).upper() != currency:
                raise ValueError('币种与原请求不一致，不能直接覆盖或自动换汇')
            currency = entry.get('currency') or currency
            audit = {'amount': str(amount), 'currency': currency, 'reviewer': reviewer,
                     'evidence_path': str(path.resolve()), 'evidence_sha256': digest.hexdigest(),
                     'previous_amount': entry.get('budget_cost'), 'previous_money_state': entry.get('money_state')}
            if entry.get('legacy_digest'):
                audit['legacy_digest'] = entry['legacy_digest']
            history = entry.setdefault('cost_reconciliations', [])
            if not isinstance(history, list) or any(not isinstance(item, dict) for item in history):
                raise ValueError('费用核对记录损坏，请先恢复台账')
            if entry.get('money_state') == 'reconciled' and history and all(history[-1].get(key) == audit[key] for key in
                               ('amount', 'currency', 'reviewer', 'evidence_path', 'evidence_sha256')):
                return dict(entry)
            audit['at'] = self.clock()
            history.append(audit)
            entry.update(budget_cost=str(amount), currency=currency, money_state='reconciled')
            return dict(entry)


def record_request(project, request_id, kind, amount, *, note='', mode='reported'):
    """把一笔已完成的付费请求写进项目请求台账；同一 request_id＋kind 只算一笔，重复调用只覆盖。

    生产路径上的记账不能影响制作：任何落盘或数据问题都只返回 None，不抛异常。
    不传远端任务号，避免按任务号去重把同一请求的两类用量（次数与秒数）误判为重复。"""
    try:
        ledger = RequestLedger(project)
        with ledger.transaction():
            ledger.reserve(request_id, kind, amount, note=note)
            ledger.settle(request_id, kind=kind, amount=amount, mode=mode, note=note)
        return ledger
    except (OSError, ValueError, TypeError):
        return None

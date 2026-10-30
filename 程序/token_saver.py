# -*- coding: utf-8 -*-
"""第 66 期：多模型子 Agent Token 节省（附件《多模型子 Agent Token 节省完整命令清单》）。

附件自己分成五段，这里就按五段落：

- 阶段零 扫描：scan() 看一眼当前配置与基线（只读，不写盘）；
- 阶段一 通用优化六条：统一前缀布局、AGENTS.md 只回结论、推理强度降档、子 Agent 廉价模型、
  自动压缩阈值、项目级 .codexignore——每一条都有常量、算法与落盘函数；
- 阶段二 各提供商缓存：Claude 显式 cache_control、Qwen／DeepSeek 前缀字节级稳定、
  Seedance 固定前缀、GPT 前缀 ≥1024；
- 阶段三 ClawMux：压缩必须在路由之前（按最小路由层级窗口的 90% 打硬上限）＋可写盘的 clawmux.json；
- 阶段四 CC Switch：四家 Provider 的地址清单与本地路由环境变量；
- 阶段五 验证：命中率怎么读、Claude 的 usage 字段怎么算。

真发请求仍走 pet_llm／model_router，这里只做「算得准、写得出、验得到」这三件事，不另开传输。
"""
import hashlib
import json
import os
import re
from pathlib import Path

PROGRAM = Path(__file__).resolve().parent


# ── 阶段一 ·【通用原则 1】统一前缀布局 —— 固定内容永远放最前面 ───────────────
LAYOUT = ('固定：System Prompt／工具定义／长期上下文', '半固定：对话历史', '变化：当前任务')


def layout_messages(fixed=(), history=(), current=None):
    """按「固定在前、变化在后」把消息排好：同一份 fixed 永远得到同一段前缀。

    固定内容放最前是 Token 优化的第一原则；反过来（用户输入在前、固定内容在后）会让
    所有缓存全部失效。
    """
    out = [{'role': 'system', 'content': str(text)} for text in fixed if text]
    for item in history or ():
        out.append(dict(item))
    if current is not None:
        out.append({'role': 'user', 'content': str(current)})
    return out


def prefix_fingerprint(text):
    """一段前缀的指纹（前 16 位）：两次算出同一个值，才谈得上命中缓存。"""
    return hashlib.sha256(str(text).encode('utf-8')).hexdigest()[:16]


DYNAMIC = (
    re.compile(r'\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}'),               # 年月日时分
    re.compile(r'\b\d{10,13}\b'),                                   # 秒／毫秒时间戳
    re.compile(r'[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-'),                  # UUID
    re.compile(r'\b(?:uuid4|time\.time|datetime\.now|random\.\w+)\b'),
)


def has_dynamic(text):
    """前缀里混进了时间戳／随机 ID 吗（DeepSeek 那条：不许往 System Prompt 里注入动态内容）。"""
    return any(pattern.search(str(text)) for pattern in DYNAMIC)


def is_stable(text):
    """这段前缀能不能拿去当缓存前缀：非空，且不含动态内容。"""
    return bool(str(text)) and not has_dynamic(text)


# ── 阶段一 ·【通用原则 2】子 Agent 上下文压缩 —— 只返回浓缩结论 ─────────────
AGENTS_FILE = 'AGENTS.md'
AGENTS_HEADING = '## Token 节省规则（所有子 Agent 必须遵守）'
AGENTS_RULES = (
    '1. 输出未知大小的命令必须设上限：COMMAND 2>&1 | head -c 6000。',
    '2. 完整日志、完整测试输出、完整 git diff 不直接回主 Agent；只回：结论 ＋ 关键错误行 ＋ 文件:行号。',
    '3. 子 Agent 返回固定三段：结论（1-3 行）→ 关键依据 → 潜在风险；不贴原始日志、不贴超过 20 行的代码块。',
    '4. 读文件优先用精确路径，不做全目录扫描。',
    '5. 漫剧素材分析类子 Agent 只回结构化摘要（角色名、出现场景、情绪标签），不回原文段落。',
)


def agents_section():
    """要写进项目 AGENTS.md 的那一段（正文与附件一字不差）。"""
    return AGENTS_HEADING + '\n\n' + '\n'.join(AGENTS_RULES) + '\n'


def merge_agents(text):
    """已经写过这一段就原样返回（幂等）；没写过就接在后面，用户自己写的内容一个字不动。"""
    body = '' if text is None else str(text)
    if AGENTS_HEADING in body:
        return body
    if not body.strip():
        return agents_section()
    tail = '' if body.endswith('\n') else '\n'
    return body + tail + '\n' + agents_section()


# ── 阶段一 ·【通用原则 3】推理强度降档 —— 省 30-70% 输出 ─────────────────────
REASONING_EFFORTS = ('none', 'minimal', 'low', 'medium', 'high', 'xhigh')
REASONING_SAVING = {'none': '关掉推理，最省',
                    'minimal': '简单 bug 修复省 60-70%',
                    'low': '单文件改动省 40-50%，默认就这一档',
                    'medium': '基线：日常混合任务',
                    'high': '多花 30%，架构重构才临时提档',
                    'xhigh': '多花 60% 以上，只给复杂算法'}
SUMMARIES = ('none', 'auto')
VERBOSITIES = ('low', 'medium', 'high')


# ── 阶段一 ·【通用原则 5】自动压缩阈值 —— 只能调低不能调高 ───────────────────
COMPACT_RATIO = 0.7
COMPACT_CEILING = 0.9          # 上限就是窗口的 90%；再往上写会被静默忽略


def compact_limit(window=128000, ratio=COMPACT_RATIO):
    """按窗口算推荐阈值：窗口的 70%。再大也压回 90% 这条上限。"""
    size = int(window)
    if size <= 0:
        return 0
    return max(1, min(int(size * float(ratio)), int(size * COMPACT_CEILING)))


# ── 阶段一 ·【通用原则 4】子 Agent 切换廉价模型 ──────────────────────────────
SUBAGENT_MODEL = 'fast'
MAX_THINKING_TOKENS = 10000
SUBAGENT_LIMIT = 2             # 注意事项 5：并行子 Agent 控制在 2 个以内
SUBAGENT_ENV_KEYS = ('CODEX_CODE_SUBAGENT_MODEL', 'MAX_THINKING_TOKENS')


def subagent_env(values=None):
    """给子 Agent 进程加的两个环境变量（附件通用原则 4）。"""
    table = dict(values or {})
    return {'CODEX_CODE_SUBAGENT_MODEL': str(table.get('subagent_model') or SUBAGENT_MODEL),
            'MAX_THINKING_TOKENS': str(_positive(table.get('max_thinking_tokens'), MAX_THINKING_TOKENS))}


def parallel_advice(count):
    """注意事项 5：并行子 Agent 超过 2 个，Token 涨得快而质量涨得少。"""
    number = int(count)
    if number > SUBAGENT_LIMIT:
        return '并行子 Agent %d 个：建议压到 %d 个以内。' % (number, SUBAGENT_LIMIT)
    return '并行子 Agent %d 个：在 %d 个以内，合适。' % (number, SUBAGENT_LIMIT)


# ── 阶段一 ·【通用原则 6】项目级 .codexignore ───────────────────────────────
CODEXIGNORE = '.codexignore'
IGNORE_PATTERNS = ('node_modules/', 'dist/', 'build/', '.next/', 'coverage/', 'docs/', '*.log', '*.min.js',
                   '*.map', 'test/fixtures/', '__snapshots__/', 'assets/raw/', 'renders/')


def codexignore_text():
    return '\n'.join(IGNORE_PATTERNS) + '\n'


def merge_codexignore(text):
    """缺哪几条补哪几条；已经有的一行不动，也不重复。"""
    original = '' if text is None else str(text)
    have = {line.strip() for line in original.split('\n') if line.strip()}
    missing = [pattern for pattern in IGNORE_PATTERNS if pattern not in have]
    if not missing:
        return original
    head = '\n'.join(missing)
    if not original.strip():
        return head + '\n'
    return original.rstrip('\n') + '\n' + head + '\n'


# ── 这一页的八个值：五个进 config.toml，三个给子 Agent ───────────────────────
SETTING_KEYS = ('model_reasoning_effort', 'model_reasoning_summary', 'model_verbosity',
                'model_context_window', 'model_auto_compact_token_limit')
SUBAGENT_KEYS = ('subagent_model', 'max_thinking_tokens', 'subagent_limit')
DEFAULT_VALUES = {'model_reasoning_effort': 'low', 'model_reasoning_summary': 'none', 'model_verbosity': 'low',
                  'model_context_window': 128000, 'model_auto_compact_token_limit': 90000,
                  'subagent_model': SUBAGENT_MODEL, 'max_thinking_tokens': MAX_THINKING_TOKENS,
                  'subagent_limit': SUBAGENT_LIMIT}


def _positive(value, fallback):
    try:
        number = int(str(value).strip())
    except (TypeError, ValueError):
        return int(fallback)
    return number if number > 0 else int(fallback)


def normalize(values=None):
    """八个值过一遍默认与钳制：认不出的退回默认，压缩阈值不许高过窗口的 90%。"""
    raw = dict(values or {})
    out = {}
    effort = str(raw.get('model_reasoning_effort') or DEFAULT_VALUES['model_reasoning_effort']).strip().lower()
    out['model_reasoning_effort'] = effort if effort in REASONING_EFFORTS else DEFAULT_VALUES['model_reasoning_effort']
    for key, allowed in (('model_reasoning_summary', SUMMARIES), ('model_verbosity', VERBOSITIES)):
        value = str(raw.get(key) or DEFAULT_VALUES[key]).strip().lower()
        out[key] = value if value in allowed else DEFAULT_VALUES[key]
    window = _positive(raw.get('model_context_window'), DEFAULT_VALUES['model_context_window'])
    out['model_context_window'] = window
    ceiling = int(window * COMPACT_CEILING)
    limit = _positive(raw.get('model_auto_compact_token_limit'), DEFAULT_VALUES['model_auto_compact_token_limit'])
    out['model_auto_compact_token_limit'] = min(limit, ceiling)
    out['subagent_model'] = str(raw.get('subagent_model') or DEFAULT_VALUES['subagent_model']).strip() or SUBAGENT_MODEL
    out['max_thinking_tokens'] = _positive(raw.get('max_thinking_tokens'), MAX_THINKING_TOKENS)
    out['subagent_limit'] = max(1, min(_positive(raw.get('subagent_limit'), SUBAGENT_LIMIT), SUBAGENT_LIMIT))
    return out


def toml_value(value):
    if isinstance(value, bool):
        return 'true' if value else 'false'
    if isinstance(value, (int, float)):
        return str(value)
    return '"%s"' % str(value)


def config_lines(values=None):
    """写进 config.toml 的那五行（顺序固定，方便比对）。"""
    table = normalize(values)
    return tuple('%s = %s' % (key, toml_value(table[key])) for key in SETTING_KEYS)


def config_values(text):
    """从一份 config.toml 里读回这五个键；只认顶层那一段，进了 [section] 就不看了。"""
    found = {}
    for line in str(text or '').split('\n'):
        stripped = line.strip()
        if stripped.startswith('['):
            break
        if not stripped or stripped.startswith('#') or '=' not in stripped:
            continue
        key, value = stripped.split('=', 1)
        key = key.strip()
        if key in SETTING_KEYS:
            found[key] = value.strip().strip('"')
    return found


def merge_config(text, values=None):
    """把这几行合进一份 config.toml：顶层认得的键就地改，其余一个字不动；缺的补在最上面。

    幂等：合过一次之后再合，五把键都在顶层了，原文原样返回。
    """
    original = '' if text is None else str(text)
    wanted = dict(zip(SETTING_KEYS, config_lines(values)))
    out = []
    seen = set()
    top = True
    for line in original.split('\n'):
        stripped = line.strip()
        if stripped.startswith('['):
            top = False
        key = ''
        if '=' in stripped and not stripped.startswith('#'):
            key = stripped.split('=', 1)[0].strip()
        if top and key in wanted:
            out.append(wanted[key])
            seen.add(key)
        else:
            out.append(line)
    missing = [wanted[key] for key in SETTING_KEYS if key not in seen]
    if not missing:
        return original
    body = '\n'.join(out).lstrip('\n')
    if not body.strip():
        return '\n'.join(missing) + '\n'
    return '\n'.join(missing) + '\n\n' + body.rstrip('\n') + '\n'


# ── 阶段二 · 按提供商适配的缓存配置 ─────────────────────────────────────────
CACHE_MODES = (('Claude', '显式 cache_control（不标记等于放弃 90% 折扣）', '缓存读取 90% off'),
               ('Qwen', 'API Key 认证下自动缓存（OAuth 不算）', '命中约 90%'),
               ('DeepSeek', '隐式前缀缓存（命中后成本降至 1/120）', '前缀必须字节级稳定'),
               ('Seedance', '隐式 ＋ 显式缓存', '固定前缀＝画风／角色参考图／镜头语言'),
               ('GPT', '自动前缀缓存（前缀 ≥1024 token 才触发）', '保持前缀字节级一致'))
CACHE_TTLS = ('5m', '1h')
ANTHROPIC_PATH = '/v1/messages'
ANTHROPIC_VERSION = '2023-06-01'
ANTHROPIC_MODELS = {'claude-opus-5', 'claude-sonnet-4.5'}


def anthropic_messages_endpoint(base_url):
    """将 Anthropic API 根地址规范为唯一的 Messages 请求地址。"""
    base = str(base_url or '').strip().rstrip('/')
    lowered = base.lower()
    if lowered.endswith(ANTHROPIC_PATH):
        return base
    if lowered.endswith('/v1'):
        return base + '/messages'
    return base + ANTHROPIC_PATH


def cache_control(ttl='5m'):
    """Claude 的缓存断点：顶层一个 ephemeral 就够；长时间任务可开 1 小时。"""
    marker = {'type': 'ephemeral'}
    if str(ttl) == '1h':
        marker['ttl'] = '1h'
    return marker


class SplitSystem(str):
    """拼好的 system 文本，另记下前面那段固定前缀；当普通字符串用时就是整段文本。"""
    fixed = ''


def split_system(fixed, variable):
    """固定规则在前、每次变化的项目上下文在后；Claude 只在固定块上打断点。"""
    text = SplitSystem(str(fixed or '') + str(variable or ''))
    text.fixed = str(fixed or '')
    return text


def anthropic_payload(model, system, messages, max_tokens=1024, ttl='5m', keep_tail=False):
    """Anthropic 原生请求体：system 单列 ＋ 缓存断点（附件 2A）。

    普通字符串 system 用顶层 cache_control。split_system 拆过的 system 发成块列表，
    固定块上显式打断点；单轮请求不再保留顶层断点，免得每次都变的用户消息按 1.25 倍
    写进缓存。带工具或多轮时（keep_tail）对话尾部会被下一次复用，顶层断点照留。
    """
    body = {'model': str(model), 'max_tokens': int(max_tokens), 'system': str(system),
            'messages': [dict(item) for item in messages]}
    fixed = getattr(system, 'fixed', '')
    if not fixed:
        body['cache_control'] = cache_control(ttl)
        return body
    blocks = [{'type': 'text', 'text': fixed, 'cache_control': cache_control(ttl)}]
    rest = str(system)[len(fixed):]
    if rest:
        blocks.append({'type': 'text', 'text': rest})
    body['system'] = blocks
    if keep_tail:
        body['cache_control'] = cache_control(ttl)
    return body


def anthropic_headers(key):
    """Anthropic 认 x-api-key，不认 Bearer。"""
    return {'Content-Type': 'application/json', 'x-api-key': str(key), 'anthropic-version': ANTHROPIC_VERSION}


def _first(*values):
    """第一个合法的非负整数计数；布尔、负数、字符串都当没报。"""
    return next((value for value in values
                 if isinstance(value, int) and not isinstance(value, bool) and value >= 0), None)


def reported_usage(raw):
    """服务端实际报了哪几格就给哪几格（没报的不填 0）：各家用量写法统一成一套口径。

    - 命中：DeepSeek 报 prompt_cache_hit_tokens，Claude 报 cache_read_input_tokens，
      OpenAI 兼容报 prompt_tokens_details.cached_tokens，Responses 报 input_tokens_details.cached_tokens。
    - Claude 的 input_tokens 不含缓存读写；总输入要把 cache_read 与 cache_creation 加回去，
      命中率才不会超过 100%。
    """
    raw = raw if isinstance(raw, dict) else {}
    read = _first(raw.get('cache_read_input_tokens'))
    claude_written = _first(raw.get('cache_creation_input_tokens'))
    written = _first(claude_written, raw.get('cache_creation_tokens'))
    prompt = _first(raw.get('prompt_tokens'))
    if prompt is None:
        prompt = _first(raw.get('input_tokens'))
        if prompt is not None and (read is not None or claude_written is not None):
            prompt += (read or 0) + (claude_written or 0)
    nested = [raw[name].get('cached_tokens') for name in ('prompt_tokens_details', 'input_tokens_details')
              if isinstance(raw.get(name), dict)]
    usage = {'prompt_tokens': prompt,
             'completion_tokens': _first(raw.get('completion_tokens'), raw.get('output_tokens')),
             'cached_tokens': _first(raw.get('cached_tokens'), raw.get('prompt_cache_hit_tokens'), read, *nested),
             'cache_creation_tokens': written,
             'total_tokens': _first(raw.get('total_tokens'))}
    return {key: value for key, value in usage.items() if value is not None}


def anthropic_usage(data):
    """Claude 的用量：总输入＝input＋cache_read＋cache_creation（附件 2C），四格齐全。"""
    usage = reported_usage(data.get('usage') if isinstance(data, dict) else None)
    return {key: int(usage.get(key) or 0)
            for key in ('prompt_tokens', 'completion_tokens', 'cached_tokens', 'cache_creation_tokens')}


def anthropic_text(data):
    """只提取 Claude 可展示的正文，绝不把 thinking／签名当聊天文本。"""
    if not isinstance(data, dict):
        return ''
    visible = []
    content = data.get('content')
    if isinstance(content, (list, tuple)):
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get('type') in ('text', 'output_text') and block.get('text'):
                visible.append(str(block['text']))
    if visible:
        return ''.join(visible).strip()
    # 少数中转网关在 /v1/messages 上仍返回 OpenAI Chat Completions 外壳。
    # 先走原生 content，只有没有正文时才兼容读取 choices，避免误展示 thinking。
    choices = data.get('choices')
    if isinstance(choices, (list, tuple)) and choices and isinstance(choices[0], dict):
        message = choices[0].get('message')
        content = message.get('content') if isinstance(message, dict) else ''
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, (list, tuple)):
            return ''.join(str(block.get('text') or '') for block in content
                           if isinstance(block, dict) and block.get('type') in ('text', 'output_text')).strip()
    output = data.get('output_text')
    return str(output).strip() if isinstance(output, str) else ''


SEEDANCE_PREFIX_FIELDS = ('画风定义', '角色参考图描述', '镜头语言偏好')


def seedance_prefix(style='', characters=(), camera=''):
    """Seedance／火山方舟的固定前缀：画风 → 角色参考图 → 镜头语言，顺序与文字都固定。"""
    lines = []
    if style:
        lines.append('%s：%s' % (SEEDANCE_PREFIX_FIELDS[0], style))
    if characters:
        lines.append('%s：%s' % (SEEDANCE_PREFIX_FIELDS[1],
                                 '、'.join(str(item) for item in characters)))
    if camera:
        lines.append('%s：%s' % (SEEDANCE_PREFIX_FIELDS[2], camera))
    return '\n'.join(lines)


def cache_hit_sentence(usage):
    """一次用量里的命中：DeepSeek 的 prompt_cache_hit_tokens 与 Claude 的 cache_read 同一口径。"""
    table = usage if isinstance(usage, dict) else {}
    prompt = int(table.get('prompt_tokens') or 0)
    cached = int(table.get('cached_tokens') or 0)
    if not prompt:
        return '这次没报用量。'
    return '本次输入 %d，其中 %d 走缓存（%d%%）。' % (prompt, cached, round(cached / prompt * 100))


def hit_rate_line(rate):
    """命中率一行：附件认的目标是 70% 以上。"""
    value = float(rate or 0)
    return '缓存命中率 %d%%（目标 70%% 以上）%s' % (round(value * 100), '，达标' if value >= 0.7 else '')


# ── 阶段三 · ClawMux：路由 + 上下文压缩代理 ─────────────────────────────────
CLAWMUX_FILE = '~/.openclaw/clawmux.json'
CLAWMUX_PORT = 3456
CLAWMUX_HOST = '127.0.0.1'
CLAWMUX_TIERS = ('LIGHT', 'MEDIUM', 'HEAVY')
CLAWMUX_DEFAULT_MODELS = {'LIGHT': 'zai/glm-5-turbo', 'MEDIUM': 'anthropic/claude-sonnet-4.5',
                          'HEAVY': 'openai/gpt-5.4'}
CLAWMUX_THRESHOLD = 0.75
CLAWMUX_TARGET = 0.6
CLAWMUX_BAD_PROVIDER = 'clawmux'          # 用它当 provider 会无限循环
COMPRESS_HARD_RATIO = 0.9                 # 硬上限＝最小路由层级上下文窗口的 90%


def clawmux_config(port=None, models=None, threshold=None, target=None):
    """一份能直接写到 ~/.openclaw/clawmux.json 的配置。"""
    table = dict(CLAWMUX_DEFAULT_MODELS)
    for tier, value in dict(models or {}).items():
        if str(tier).upper() in CLAWMUX_TIERS and str(value).strip():
            table[str(tier).upper()] = str(value).strip()
    return {'compression': {'threshold': float(CLAWMUX_THRESHOLD if threshold is None else threshold),
                            'model': table['LIGHT'],
                            'targetRatio': float(CLAWMUX_TARGET if target is None else target)},
            'routing': {'models': table},
            'server': {'port': int(port or CLAWMUX_PORT), 'host': CLAWMUX_HOST}}


def clawmux_json(**kwargs):
    """写盘的正文：键序固定，同一份配置永远得到同一段文字。"""
    return json.dumps(clawmux_config(**kwargs), ensure_ascii=False, indent=2, sort_keys=True) + '\n'


def routing_problems(config=None):
    """路由表要过得了检查：三层齐全、写成 provider/model、别拿 clawmux 当 provider。"""
    table = dict((config or clawmux_config()).get('routing', {}).get('models', {}))
    out = []
    for tier in CLAWMUX_TIERS:
        value = str(table.get(tier) or '')
        if not value:
            out.append('%s 这一层还没配模型' % tier)
        elif '/' not in value:
            out.append('%s 的模型要写成 provider/model' % tier)
        elif value.split('/', 1)[0] == CLAWMUX_BAD_PROVIDER:
            out.append('%s 不能用 clawmux 当 provider，会无限循环' % tier)
    return tuple(out)


def compression_limit(windows):
    """压缩必须在路由之前：按所有路由模型里最小的上下文窗口打 90% 的硬上限。"""
    values = [int(item) for item in windows if int(item) > 0]
    return int(min(values) * COMPRESS_HARD_RATIO) if values else 0


def health_url(port=None, host=None):
    return 'http://%s:%d/health' % (str(host or CLAWMUX_HOST), int(port or CLAWMUX_PORT))


def clawmux_steps(port=None):
    """怎么起 ClawMux 的四步（照附件抄，不添油加醋）。"""
    return ('npm install -g clawmux', 'clawmux init', '照着写 %s' % CLAWMUX_FILE,
            '验证：%s' % health_url(port))


# ── 阶段四 · CC Switch 多 Provider 管理 ─────────────────────────────────────
PROVIDERS = (
    {'name': '火山引擎 Agent Plan（DeepSeek）', 'base_url': 'https://ark.cn-beijing.volces.com/api/plan/v3',
     'note': '别写 /api/coding/v3 或 /api/v3，否则不消耗套餐额度'},
    {'name': 'Anthropic（Claude）', 'base_url': 'https://api.anthropic.com', 'note': '缓存要显式标记'},
    {'name': '阿里云百炼（Qwen）', 'base_url': 'https://dashscope.aliyuncs.com/compatible-mode/v1',
     'note': '走兼容端点，API Key 认证'},
    {'name': 'OpenAI（GPT）', 'base_url': 'https://api.openai.com', 'note': '自动前缀缓存'},
)
FORBIDDEN_URLS = ('/api/coding/v3', '/api/v3')
LOCAL_ROUTE_PORT = 15721
LOCAL_ROUTE_ENV = {'ANTHROPIC_AUTH_TOKEN': 'PROXY_MANAGED',
                   'ANTHROPIC_BASE_URL': 'http://127.0.0.1:%d' % LOCAL_ROUTE_PORT}


def provider_rows():
    return tuple((item['name'], item['base_url'], item['note']) for item in PROVIDERS)


def url_ok(url):
    """注意事项 1：火山引擎那条地址写错就等于白花钱。"""
    text = str(url or '')
    return bool(text) and not any(bad in text for bad in FORBIDDEN_URLS)


# ── 阶段五 · 验证与监控 ─────────────────────────────────────────────────────
VERIFY_STEPS = (('/cost：看当前消耗', '输出 token 降了就是降档生效'),
                ('cache_info 事件：看命中率', 'DeepSeek／GPT 的隐式缓存都从这里看'),
                ('/stats：Qwen 的缓存节省', '应看到 90% 上下的命中'),
                ('usage.cache_read_input_tokens', 'Claude 读到数就说明 cache_control 生效了'),
                ('ClawMux 日志：压缩前后对比', '两次 token 数之差就是省下的'),
                ('CC Switch：逐家用量', '按 Provider 看 Token、命中与费用'))


# ── 速查表与注意事项（附件最后两段，一字不改） ───────────────────────────────
SPEED_TABLE = (
    (1, '统一前缀布局', '缓存命中率 70%+', '所有 LLM'),
    (2, '推理强度降档', '30-70% 输出', '所有 LLM'),
    (3, '子 Agent 切换 fast 模型', '~80% 子任务', 'Codex 子 Agent'),
    (4, '修复自动压缩阈值', '40-60%', 'Codex'),
    (5, 'AGENTS.md 工具输出截断', '~50%', '所有 LLM'),
    (6, 'Claude 显式 cache_control 标记', '90% 缓存读取', 'Claude'),
    (7, 'Qwen /stats 验证缓存', '90% 缓存命中', 'Qwen'),
    (8, '多模型路由前统一压缩（ClawMux）', '视场景而定', '所有 LLM'),
    (9, '.codexignore', '视项目而定', 'Codex'),
    (10, 'CC Switch 多 Provider 管理', '30% 整体成本降低', '所有'),
)

NOTES = (
    '1. 火山引擎 Agent Plan 的地址是 https://ark.cn-beijing.volces.com/api/plan/v3，别用 /api/coding/v3 或 /api/v3。',
    '2. Claude 的缓存必须显式标记 cache_control，不标记等于放弃 90% 折扣。',
    '3. Qwen 的缓存只在 API Key 认证下生效，OAuth 不算。',
    '4. 多模型路由时压缩必须在路由之前完成。',
    '5. 并行子 Agent 控制在 2 个以内，再多 Token 涨得快、质量涨得少。',
    '6. model_auto_compact_token_limit 只能调低不能调高，写大了会被静默忽略。',
    '7. 同一任务中不中途切换模型，切换会让整个前缀缓存失效。',
    '8. AGENTS.md 过长末尾会被静默截断，可用 RUST_LOG=codex_core=warn 看警告。',
)


def speed_table_text():
    """速查表按列对齐的纯文本行（界面里直接贴）。"""
    rows = [('优先级', '优化项', '预期节省', '适用模型')] + [tuple(str(cell) for cell in row) for row in SPEED_TABLE]
    widths = [max(len(row[index]) for row in rows) for index in range(len(rows[0]))]
    return tuple(' | '.join(cell.ljust(width) for cell, width in zip(row, widths)).rstrip() for row in rows)


# ── 写盘：项目级三份 ＋ 全局一份 ─────────────────────────────────────────────
GLOBAL_CONFIG = 'config.toml'


def codex_home(home=None):
    """Codex 的全局配置目录：传进来的 ＞ CODEX_HOME ＞ ~/.codex。"""
    if home:
        return Path(home)
    env = (os.environ.get('CODEX_HOME') or '').strip()
    return Path(env) if env else Path.home() / '.codex'


def read_text(path):
    """读一份文本；读不出来（没有／不是文本）一律当空串，写盘那一步会把它当成新文件。"""
    try:
        return Path(path).read_text(encoding='utf-8')
    except (OSError, UnicodeDecodeError):
        return ''


def write_text(path, text):
    """保存用户可编辑的 Codex 配置，复用全局原子写入语义。"""
    from agent.core import save_text
    path = Path(path)
    save_text(path, text, encoding='utf-8')
    return path


def deliver_project(project, values=None):
    """项目级三份：AGENTS.md 的 Token 规则、.codexignore、.codex/config.toml。返回写过的路径。"""
    root = Path(project)
    written = [write_text(root / AGENTS_FILE, merge_agents(read_text(root / AGENTS_FILE))),
               write_text(root / CODEXIGNORE, merge_codexignore(read_text(root / CODEXIGNORE)))]
    config = root / '.codex' / GLOBAL_CONFIG
    written.append(write_text(config, merge_config(read_text(config), values)))
    return tuple(written)


def deliver_global(values=None, home=None):
    """全局那一份：~/.codex/config.toml 合进这五条键。"""
    path = codex_home(home) / GLOBAL_CONFIG
    return write_text(path, merge_config(read_text(path), values))


def preview_text(values=None):
    """这几份文件写下去会长什么样（设置页里直接贴出来给用户看）。"""
    table = normalize(values)
    return '\n'.join(['# ' + AGENTS_FILE, agents_section().rstrip(),
                       '', '# ' + CODEXIGNORE, codexignore_text().rstrip(),
                       '', '# .codex/' + GLOBAL_CONFIG, '\n'.join(config_lines(table)),
                       '', '# ' + CLAWMUX_FILE, clawmux_json().rstrip()]) + '\n'


# ── 阶段零 · 扫描现有配置与基线 ─────────────────────────────────────────────
def scan(project=None, home=None, environ=None):
    """看一眼当前配置与基线（只读）：全局配置里写了哪几把键、项目里三份文件齐不齐。"""
    env = dict(os.environ if environ is None else environ)
    target = codex_home(home)
    global_values = config_values(read_text(target / GLOBAL_CONFIG))
    project_config = read_text(Path(project) / '.codex' / GLOBAL_CONFIG) if project else ''
    agents = read_text(Path(project) / AGENTS_FILE) if project else ''
    ignore = read_text(Path(project) / CODEXIGNORE) if project else ''
    have = {line.strip() for line in ignore.split('\n') if line.strip()}
    return {'home': target, 'config_file': target / GLOBAL_CONFIG,
            'config_keys': tuple(sorted(global_values)), 'project_keys': tuple(sorted(config_values(project_config))),
            'agents': bool(agents.strip()), 'agents_rules': AGENTS_HEADING in agents,
            'codexignore': bool(ignore.strip()),
            'ignore_missing': tuple(pattern for pattern in IGNORE_PATTERNS if pattern not in have),
            'subagent_env': {key: env.get(key, '') for key in SUBAGENT_ENV_KEYS},
            'reasoning': global_values.get('model_reasoning_effort', '')}


def scan_lines(report):
    """把上面那份扫描结果写成人话（一行一件事）。"""
    table = dict(report or {})
    lines = ['全局配置：%s' % ('已写 %s' % '、'.join(table.get('config_keys') or ())
                            if table.get('config_keys') else '还没写过，推理强度用默认的 low'),
             '推理强度：%s' % (table.get('reasoning') or '低（默认）')]
    env = dict(table.get('subagent_env') or {})
    lines.append('子 Agent：%s＝%s，%s＝%s' % (SUBAGENT_ENV_KEYS[0], env.get(SUBAGENT_ENV_KEYS[0]) or '没设',
                                             SUBAGENT_ENV_KEYS[1], env.get(SUBAGENT_ENV_KEYS[1]) or '没设'))
    if table:
        lines.append('项目 AGENTS.md：%s' % ('已带 Token 规则' if table.get('agents_rules')
                                        else ('有，但还没加规则' if table.get('agents') else '还没有')))
        rest = len(table.get('ignore_missing') or ())
        lines.append('.codexignore：%s' % ('已齐' if not rest else '还缺 %d 条' % rest))
    return tuple(lines)

# -*- coding: utf-8 -*-
"""单模型多 API 路线、服务商预设、持久化探活状态与远端模型拉取（L1 基础设施）。

从 ``model_pool`` 拆出，保持模块体积与复杂度在门禁范围内：
- 内置 9 项主流厂商一键预设（地址＋默认协议，用户均可覆盖）；
- 规范化 ``routes`` 列表，并在顶层保留首选启用路线的镜像字段以 100% 兼容存量消费者；
- 按 ``model_id + route_id`` 隔离 DPAPI 本机密钥，避免同模型多条路线互相覆盖密钥；
- 持久化轻量探测状态元数据（不含正文与密钥），产出左侧卡片与路线卡的四态徽标；
- 经 ``model_pool.http_transport`` 统一出站通道异步拉取 ``GET /models`` 候选模型列表。
"""
from __future__ import annotations

import time
from pathlib import Path

import infra.model_secrets as model_secrets
import infra.token_saver as token_saver
from infra.api_endpoints import normalize_url

PROBE_STATUS_KEY = 'model_probe_status'
DEFAULT_ROUTE_ID = 'r1'
DEFAULT_PATH = '/chat/completions'
DEFAULT_WIRE = 'chat'
VALID_WIRES = ('chat', 'responses', 'messages')

# 主流服务商一键预设：(id, 显示名, 默认根地址, 默认协议, 建议环境变量名)
PROVIDER_PRESETS = (
    ('deepseek', 'DeepSeek 官方', 'https://api.deepseek.com', 'chat', 'DEEPSEEK_API_KEY'),
    ('openai', 'OpenAI 官方', 'https://api.openai.com/v1', 'chat', 'OPENAI_API_KEY'),
    ('anthropic', 'Anthropic (Claude)', 'https://api.anthropic.com', 'messages', 'ANTHROPIC_API_KEY'),
    ('qwen', '阿里百炼 (Qwen)', 'https://dashscope.aliyuncs.com/compatible-mode/v1', 'chat', 'DASHSCOPE_API_KEY'),
    ('moonshot', '月之暗面 (Kimi)', 'https://api.moonshot.cn/v1', 'chat', 'MOONSHOT_API_KEY'),
    ('zhipu', '智谱 (GLM)', 'https://open.bigmodel.cn/api/paas/v4', 'chat', 'ZHIPU_API_KEY'),
    ('siliconflow', '硅基流动 (SiliconFlow)', 'https://api.siliconflow.cn/v1', 'chat', 'SILICONFLOW_API_KEY'),
    ('openrouter', 'OpenRouter', 'https://openrouter.ai/api/v1', 'chat', 'OPENROUTER_API_KEY'),
    ('custom', '自定义中转', '', 'chat', ''),
)

PRESET_BY_ID = {row[0]: {'id': row[0], 'label': row[1], 'base_url': row[2],
                         'wire_api': row[3], 'key_env': row[4]} for row in PROVIDER_PRESETS}
PRESET_BY_LABEL = {row[1]: PRESET_BY_ID[row[0]] for row in PROVIDER_PRESETS}


def preset_labels():
    """返回服务商预设下拉选项顺序列表。"""
    return [row[1] for row in PROVIDER_PRESETS]


def preset_by_label(text):
    """按显示名或预设 id 匹配内置服务商预设；未命中返回 None。"""
    key = str(text or '').strip()
    if not key:
        return None
    if key in PRESET_BY_LABEL:
        return dict(PRESET_BY_LABEL[key])
    lowered = key.casefold()
    for preset in PRESET_BY_ID.values():
        if preset['id'] == lowered or preset['label'].casefold() == lowered:
            return dict(preset)
    return None


def match_preset(provider='', base_url=''):
    """按已有 provider 或 base_url 猜测最贴合的预设显示名。"""
    hit = preset_by_label(provider)
    if hit:
        return hit['label']
    url = str(base_url or '').strip().lower()
    if url:
        for row_id, label, preset_url, _wire, _env in PROVIDER_PRESETS:
            if not preset_url:
                continue
            host = preset_url.split('://', 1)[-1].split('/', 1)[0].lower()
            if host and host in url:
                return label
    raw_provider = str(provider or '').strip()
    if raw_provider and raw_provider.casefold() not in ('openai-compatible', 'custom', '自定义', 'desktop'):
        return raw_provider
    return PRESET_BY_ID['custom']['label']


def _clean_route_id(raw_id, index, used):
    text = str(raw_id or '').strip()
    if not text or text in used:
        seq = index + 1
        while f'r{seq}' in used:
            seq += 1
        text = f'r{seq}'
    used.add(text)
    return text


def normalize_route(raw, fallback=None, index=0, used=None):
    """规范化单条 API 路线记录，补齐默认值并丢弃未知键。"""
    source = raw if isinstance(raw, dict) else {}
    base = fallback if isinstance(fallback, dict) else {}
    seen = used if isinstance(used, set) else set()
    route_id = _clean_route_id(source.get('id'), index, seen)
    wire = str(source.get('wire_api') or base.get('wire_api') or DEFAULT_WIRE).strip()
    if wire not in VALID_WIRES:
        wire = DEFAULT_WIRE
    path = str(source.get('path') or base.get('path') or DEFAULT_PATH).strip() or DEFAULT_PATH
    enabled_raw = source.get('enabled')
    enabled = True if enabled_raw is None else bool(enabled_raw)
    provider = str(source.get('provider') or (base.get('provider') if index == 0 else '') or '').strip()
    if provider == 'desktop':
        provider = ''
    base_url = str(source.get('base_url') if 'base_url' in source else (base.get('base_url') if index == 0 else '') or '').strip()
    remote_model = str(source.get('model') if 'model' in source else (base.get('model') if index == 0 else '') or '').strip()
    key_env = str(source.get('key_env') if 'key_env' in source else (base.get('key_env') if index == 0 else '') or '').strip()
    name = str(source.get('name') or '').strip()
    return {
        'id': route_id,
        'name': name,
        'provider': provider,
        'base_url': base_url,
        'path': path,
        'wire_api': wire,
        'model': remote_model,
        'key_env': key_env,
        'enabled': enabled,
    }


def normalize_routes(source, base_item):
    """把记录里的 ``routes`` 列表规范化；空列表返回空列表（调用方回落旧单路线语义）。"""
    raw_routes = source.get('routes') if isinstance(source, dict) else None
    if not isinstance(raw_routes, list) or not raw_routes:
        return []
    used = set()
    out = []
    for index, entry in enumerate(raw_routes):
        if isinstance(entry, dict):
            out.append(normalize_route(entry, fallback=base_item, index=index, used=used))
    return out


def primary_route(routes):
    """返回第一条启用路线；全部停用时退回第一条。"""
    for route in routes or ():
        if route.get('enabled', True):
            return route
    return routes[0] if routes else None


def apply_primary_mirror(item):
    """把首选启用路线镜像写回顶层字段，确保所有存量消费方与测试无需感知 routes。"""
    routes = item.get('routes') if isinstance(item, dict) else None
    if not isinstance(routes, list) or not routes:
        return item
    chosen = primary_route(routes)
    if not chosen:
        return item
    item['base_url'] = chosen['base_url']
    item['path'] = chosen['path'] or DEFAULT_PATH
    item['wire_api'] = chosen['wire_api'] if chosen['wire_api'] in VALID_WIRES else DEFAULT_WIRE
    item['key_env'] = chosen['key_env']
    if chosen['provider'] and item.get('provider') != 'desktop':
        item['provider'] = chosen['provider']
    if not item.get('model') and chosen['model']:
        item['model'] = chosen['model']
    return item


def routes_of(item, model_id=''):
    """永远返回非空规范化路线列表；老单路线记录无损合成为 1 条默认路线。"""
    base = item if isinstance(item, dict) else {}
    existing = base.get('routes')
    if isinstance(existing, list) and existing:
        used = set()
        return [normalize_route(entry, fallback=base, index=i, used=used)
                for i, entry in enumerate(existing) if isinstance(entry, dict)]
    used = set()
    single = {
        'id': DEFAULT_ROUTE_ID,
        'name': '',
        'provider': '' if base.get('provider') == 'desktop' else str(base.get('provider') or ''),
        'base_url': str(base.get('base_url') or ''),
        'path': str(base.get('path') or DEFAULT_PATH),
        'wire_api': str(base.get('wire_api') or DEFAULT_WIRE),
        'model': str(base.get('model') or model_id or ''),
        'key_env': str(base.get('key_env') or ''),
        'enabled': True,
    }
    return [normalize_route(single, fallback=base, index=0, used=used)]


def route_secret_name(model_id, route, index=0):
    """路线级独立本机密钥名：显式 key_env 优先；首路线兼容旧名，备用路线按 route_id 隔离。"""
    explicit = str((route or {}).get('key_env') or '').strip()
    if explicit:
        return explicit
    base_model = str(model_id or (route or {}).get('model') or '').strip()
    if not base_model:
        return ''
    route_id = str((route or {}).get('id') or f'r{index + 1}').strip()
    if index == 0 and route_id == DEFAULT_ROUTE_ID:
        return model_secrets.name_for(base_model, '')
    return model_secrets.name_for(f'{base_model}__{route_id}', '')


def route_as_record(parent_item, route, model_id='', index=0):
    """把某条路线展开为标准模型池记录字典，供探测、认证和适配器复用。"""
    parent = dict(parent_item or {})
    r = normalize_route(route, fallback=parent, index=index)
    out = dict(parent)
    out.pop('routes', None)
    out['base_url'] = r['base_url']
    out['path'] = r['path'] or DEFAULT_PATH
    out['wire_api'] = r['wire_api']
    out['model'] = r['model'] or str(parent.get('model') or model_id or '').strip()
    out['key_env'] = r['key_env']
    if r['provider'] and out.get('provider') != 'desktop':
        out['provider'] = r['provider']
    if not out.get('label'):
        out['label'] = str(parent.get('label') or out['model'] or model_id or '')
    return out


def route_key_of(parent_item, route, program=None, model_id='', index=0, override_key=''):
    """解析某条路线的有效 API Key（未落盘临时测试可传 override_key）。"""
    typed = str(override_key or '').strip()
    if typed:
        return typed
    import infra.model_pool as model_pool
    env_name = str((route or {}).get('key_env') or '').strip()
    if env_name:
        try:
            return model_pool.credential(env_name, program)
        except Exception:
            return ''
    auto_name = route_secret_name(model_id or (parent_item or {}).get('model', ''), route, index)
    if auto_name:
        local = model_secrets.load(auto_name, program)
        if local:
            return local
    return ''


def local_route_key_of(parent_item, route, program=None, model_id='', index=0):
    """读取该路线保存在本机 DPAPI 的密钥（没有返回空串）。"""
    name = route_secret_name(model_id or (parent_item or {}).get('model', ''), route, index)
    return model_secrets.load(name, program) if name else ''


def save_route_key(parent_item, route, key, program=None, model_id='', index=0):
    """把路线输入的密钥加密存到本机 DPAPI，返回写入的 secret_name。"""
    import infra.model_pool as model_pool
    base_model = str(model_id or (parent_item or {}).get('model') or (route or {}).get('model') or '').strip()
    name = route_secret_name(base_model, route, index)
    model_pool.save_key_env({'key_env': name, 'model': base_model}, key, program, base_model)
    return name


def clear_route_key(parent_item, route, program=None, model_id='', index=0):
    """清除该路线保存在本机 DPAPI 的密钥。"""
    name = route_secret_name(model_id or (parent_item or {}).get('model', ''), route, index)
    return model_secrets.clear(name, program) if name else False


def route_status(parent_item, route, program=None, model_id='', index=0, override_key=''):
    """单条路线静态配置完整性判定（返回人话原因，供四态徽标与准入复用）。"""
    r = normalize_route(route, fallback=parent_item, index=index)
    if not r['enabled']:
        return False, '已停用'
    remote_model = r['model'] or str((parent_item or {}).get('model') or model_id or '').strip()
    if not remote_model:
        return False, '缺模型 ID'
    if not r['base_url']:
        return False, '缺 API 地址'
    if not route_key_of(parent_item, r, program=program, model_id=model_id,
                        index=index, override_key=override_key):
        return False, '待填 Key'
    return True, '可用'


def any_route_available(item, program=None, model_id=''):
    """多路线记录整体静态可用性：至少一条启用路线配置完整即算可用。"""
    routes = routes_of(item, model_id=model_id)
    first_why = '无可用路线'
    for index, route in enumerate(routes):
        ok, why = route_status(item, route, program=program, model_id=model_id, index=index)
        if ok:
            return True, '可用'
        if index == 0 or first_why == '无可用路线':
            first_why = why
    return False, first_why


def route_config_version(parent_item, route, model_id='', index=0):
    """路线级配置指纹：连接项变动自动失效旧绿灯。"""
    flat = route_as_record(parent_item, route, model_id=model_id, index=index)
    return '%s · %s · %s · %s' % (
        flat['wire_api'], flat['base_url'] or '（无地址）',
        flat['model'] or '（无模型 ID）', flat['key_env'] or '（无密钥名）',
    )


def probe_key(model_id, route_id=DEFAULT_ROUTE_ID):
    """持久化探活表键名。"""
    return '%s::%s' % (str(model_id or '').strip(), str(route_id or DEFAULT_ROUTE_ID).strip())


def short_probe_error(result):
    """把底层 HTTP/网络报错翻成零基础一眼看懂的短句。"""
    data = result if isinstance(result, dict) else {}
    status = data.get('status')
    raw = str(data.get('error') or '').strip()
    low = raw.lower()
    if status == 401:
        return '401 密钥无效'
    if status == 403:
        return '403 无权访问'
    if status == 404:
        return '404 地址或模型不存在'
    if status == 402:
        return '402 余额不足'
    if status == 429:
        return '429 请求限流'
    if isinstance(status, int) and status >= 500:
        return f'{status} 服务端异常'
    if 'timeout' in low or 'timed out' in low or '超时' in raw:
        return '连接超时'
    if 'getaddrinfo' in low or 'dns' in low or 'name or service' in low:
        return '域名解析失败'
    if 'ssl' in low or 'certificate' in low or '证书' in raw:
        return 'SSL 证书异常'
    if 'refused' in low or '连接被拒' in raw or 'urlerror' in low:
        return '无法连接服务器'
    if status:
        return f'HTTP {status} 失败'
    if len(raw) > 22:
        return raw[:21] + '…'
    return raw or '连接失败'


def all_probe_status(config=None, program=None):
    """读取全部持久化路线探活状态元数据。"""
    import infra.model_pool as model_pool
    data = model_pool.raw(program, config)
    stored = data.get(PROBE_STATUS_KEY)
    if not isinstance(stored, dict):
        return {}
    return {str(k): dict(v) for k, v in stored.items() if isinstance(v, dict)}


def probe_status_of(model_id, route, parent_item, *, config=None, program=None,
                    probe_map=None, index=0):
    """取该路线与当前配置版本匹配的最近探测元数据；配置已变更则返回空字典。"""
    mid = str(model_id or '').strip()
    if not mid:
        return {}
    table = probe_map if isinstance(probe_map, dict) else all_probe_status(config=config, program=program)
    rid = str((route or {}).get('id') or f'r{index + 1}').strip()
    entry = table.get(probe_key(mid, rid))
    if not isinstance(entry, dict):
        return {}
    expected = route_config_version(parent_item, route, model_id=mid, index=index)
    if entry.get('config_version') and entry['config_version'] != expected:
        return {}
    return dict(entry)


def record_probe_status(model_id, route, parent_item, result, *, program=None, index=0):
    """只把轻量探活元数据持久化到配置，绝不存正文或密钥。"""
    import infra.model_pool as model_pool
    mid = str(model_id or '').strip()
    if not mid:
        return {}
    rid = str((route or {}).get('id') or f'r{index + 1}').strip()
    data = result if isinstance(result, dict) else {}
    entry = {
        'at': time.strftime('%Y-%m-%d %H:%M:%S'),
        'ok': bool(data.get('ok')),
        'ms': int(data.get('ms') or 0),
        'status': int(data.get('status') or 0),
        'error_short': '' if data.get('ok') else short_probe_error(data),
        'error': '' if data.get('ok') else str(data.get('error') or '')[:200],
        'config_version': route_config_version(parent_item, route, model_id=mid, index=index),
        'checks': [dict(c) for c in (data.get('checks') or []) if isinstance(c, dict)],
    }

    def mutate(cfg):
        table = cfg.get(PROBE_STATUS_KEY)
        next_table = ({str(k): dict(v) for k, v in table.items() if isinstance(v, dict)}
                      if isinstance(table, dict) else {})
        next_table[probe_key(mid, rid)] = entry
        cfg[PROBE_STATUS_KEY] = next_table
        return cfg

    try:
        model_pool._update(mutate, program)
    except RuntimeError:
        pass
    return entry


def _probe_with_override_key(flat, override_key, transport, program, timeout):
    """未落盘的新输入 Key 临时测通：复用 model_pool 探测逻辑，不写盘、不改密钥存储。"""
    import infra.model_pool as model_pool
    url = normalize_url(flat['base_url'])
    messages = [{'role': 'user', 'content': 'ping'}]
    wire = flat['wire_api']
    if wire == 'responses':
        url = url + '/responses'
        body = {'model': flat['model'], 'max_output_tokens': model_pool.PROBE_TOKENS, 'input': messages}
    elif wire == 'messages':
        url = token_saver.anthropic_messages_endpoint(url)
        body = {'model': flat['model'], 'max_tokens': model_pool.PROBE_TOKENS, 'messages': messages}
    else:
        url = url + (flat['path'] or DEFAULT_PATH)
        body = {'model': flat['model'], 'max_tokens': model_pool.PROBE_TOKENS, 'messages': messages}
    headers = (token_saver.anthropic_headers(override_key) if wire == 'messages'
               else {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + override_key})
    send = transport or model_pool.http_transport
    started = time.time()
    try:
        raw = dict(send(url, body, headers, timeout) or {})
    except Exception as exc:
        raw = {'ok': False, 'status': 0, 'error': type(exc).__name__ + '：' + str(exc)}
    ms = int(round((time.time() - started) * 1000))
    answer = {
        'ok': bool(raw.get('ok')),
        'status': raw.get('status') or 0,
        'error': raw.get('error') or '',
        'data': raw.get('data'),
        'url': url,
        'ms': ms,
        'model': flat['model'],
        'usage_note': model_pool.PROBE_USAGE_NOTE,
        'config_version': model_pool.config_version(flat),
    }
    answer['signals'] = model_pool.body_signals(answer)
    answer['checks'] = model_pool.classify(flat, answer, full=False)
    answer['summary'] = model_pool.probe_summary(answer['checks'])
    answer['full_task'] = model_pool.PROBE_FULL_TASK_STATE
    return answer


def probe_route(parent_item, route, *, model_id='', index=0, transport=None,
                program=None, options=None):
    """探测单条 API 路线：options 可含 timeout/override_key/persist；支持未落盘密钥。"""
    import infra.model_pool as model_pool
    opts = dict(options or {})
    timeout = opts.get('timeout', 8)
    override_key = opts.get('override_key', '')
    persist = opts.get('persist', True)
    r = normalize_route(route, fallback=parent_item, index=index)
    flat = route_as_record(parent_item, r, model_id=model_id, index=index)
    if not flat.get('key_env') and not override_key:
        auto = route_secret_name(model_id or flat['model'], r, index)
        if auto:
            flat['key_env'] = auto
    ok, why = route_status(parent_item, r, program=program, model_id=model_id,
                           index=index, override_key=override_key)
    if not ok:
        result = {
            'ok': False, 'status': 0, 'error': why, 'ms': 0, 'model': flat['model'],
            'usage_note': model_pool.PROBE_USAGE_NOTE,
            'config_version': route_config_version(parent_item, r, model_id=model_id, index=index),
        }
        result['checks'] = model_pool.classify(flat, result, full=False)
        result['summary'] = model_pool.probe_summary(result['checks'])
        result['error_short'] = why
        return result
    typed = str(override_key or '').strip()
    if typed:
        result = _probe_with_override_key(flat, typed, transport, program, timeout)
    else:
        result = model_pool.probe(flat, transport=transport, program=program, timeout=timeout)
    result['error_short'] = '' if result.get('ok') else short_probe_error(result)
    if persist and model_id and not typed:
        record_probe_status(model_id, r, parent_item, result, program=program, index=index)
    return result


def verify_route(parent_item, route, *, model_id='', index=0, transport=None,
                 program=None, options=None):
    """对单条路线运行小样本完整验证（发一次短对话），并同步更新健康台账。"""
    import infra.model_pool as model_pool
    opts = dict(options or {})
    timeout = opts.get('timeout', 15)
    override_key = opts.get('override_key', '')
    r = normalize_route(route, fallback=parent_item, index=index)
    flat = route_as_record(parent_item, r, model_id=model_id, index=index)
    if not flat.get('key_env') and not override_key:
        auto = route_secret_name(model_id or flat['model'], r, index)
        if auto:
            flat['key_env'] = auto
    if str(override_key or '').strip():
        return {'ok': False, 'error': '请先点击「保存」后再运行小样本完整验证。',
                'content_length': 0, 'checks': [], 'config_version': route_config_version(parent_item, r, model_id, index)}
    outcome = model_pool.verify_sample(flat, transport=transport, program=program, timeout=timeout)
    if model_id:
        model_pool.record_health(flat, outcome, program=program)
    return outcome


def route_badge(parent_item, route, *, model_id='', index=0, program=None,
                probe_map=None, override_key=''):
    """计算单条 API 路线的四态徽标（ok / idle / error / missing / disabled）。"""
    r = normalize_route(route, fallback=parent_item, index=index)
    if not r['enabled']:
        return {'state': 'disabled', 'label': '已停用', 'short': '已停用', 'detail': '此路线已临时停用', 'probe': {}}
    ok, why = route_status(parent_item, r, program=program, model_id=model_id,
                           index=index, override_key=override_key)
    if not ok:
        return {'state': 'missing', 'label': why, 'short': why, 'detail': why, 'probe': {}}
    cached = probe_status_of(model_id, r, parent_item, program=program, probe_map=probe_map, index=index)
    if cached:
        if cached.get('ok'):
            ms = int(cached.get('ms') or 0)
            text = f'已测通 · {ms}ms' if ms else '已测通'
            return {'state': 'ok', 'label': text, 'short': f'{ms}ms' if ms else '可用',
                    'detail': text, 'probe': cached}
        short = cached.get('error_short') or short_probe_error(cached)
        return {'state': 'error', 'label': short, 'short': short,
                'detail': cached.get('error') or short, 'probe': cached}
    return {'state': 'idle', 'label': '已配置 · 未测', 'short': '未测试',
            'detail': '配置齐全，点击右侧「测试」验证连通性', 'probe': {}}


def _local_model_badge(model_id, item):
    """Desktop / CLI 本地模型卡片状态（只检单文件存在，绝不递归扫描）。"""
    import infra.model_pool as model_pool
    program_path = str((item or {}).get('program') or '').strip()
    vendor = model_pool.provider_name(model_id, item)
    mode = model_pool.call_mode(item, model_id)
    if program_path:
        if Path(program_path).is_file():
            return {'state': 'ok', 'short': '程序就绪', 'meta': f'{vendor} · {mode} 本机程序'}
        return {'state': 'error', 'short': '路径无效', 'meta': f'{vendor} · 请重新定位程序'}
    return {'state': 'missing', 'short': '待定位程序', 'meta': f'{vendor} · 点击检查或自动搜寻'}


def _aggregate_api_badge(model_id, item, badges, primary_vendor):
    total = len(badges)
    active = [(i, b) for i, b in enumerate(badges) if b['state'] != 'disabled']
    ok_list = [(i, b) for i, b in active if b['state'] == 'ok']
    idle_list = [(i, b) for i, b in active if b['state'] == 'idle']
    err_list = [(i, b) for i, b in active if b['state'] == 'error']
    if total > 1:
        meta_tail = f'{total}条线路（{len(ok_list)}已测通）' if ok_list else f'{total}条线路'
    else:
        meta_tail = '1条线路'
    if not active:
        return {'state': 'missing', 'short': '全部停用', 'meta': f'{primary_vendor} · {total}条线路（已全停用）'}
    first_idx, first_badge = active[0]
    if first_badge['state'] == 'ok':
        return {'state': 'ok', 'short': first_badge['short'], 'meta': f'{primary_vendor} · {meta_tail}'}
    if ok_list:
        backup_badge = ok_list[0][1]
        short = f"已切备用 · {backup_badge['short']}" if backup_badge['short'].endswith('ms') else '已切备用'
        return {'state': 'warn', 'short': short, 'meta': f'{primary_vendor} · {meta_tail}'}
    if idle_list and (first_badge['state'] == 'idle' or not err_list):
        return {'state': 'idle', 'short': '未测试', 'meta': f'{primary_vendor} · {meta_tail}'}
    if err_list:
        first_err = err_list[0][1]
        return {'state': 'error', 'short': first_err['short'], 'meta': f"{primary_vendor} · {meta_tail}"}
    return {'state': 'missing', 'short': first_badge['short'], 'meta': f'{primary_vendor} · {meta_tail}'}


def model_badge(model_id, item, *, program=None, probe_map=None):
    """左侧双行模型卡片的聚合状态徽标与副标题文案。"""
    import infra.model_pool as model_pool
    if model_pool.call_mode(item, model_id) in ('Desktop', 'CLI'):
        return _local_model_badge(model_id, item)
    routes = routes_of(item, model_id=model_id)
    badges = [route_badge(item, r, model_id=model_id, index=i, program=program, probe_map=probe_map)
              for i, r in enumerate(routes)]
    vendor = model_pool.provider_name(model_id, item)
    return _aggregate_api_badge(model_id, item, badges, vendor)


def _extract_model_ids(payload):
    """解析 OpenAI / Anthropic / 常见中转站 ``/models`` 响应体里的模型 ID 列表。"""
    if not isinstance(payload, dict):
        return []
    raw_list = payload.get('data') if isinstance(payload.get('data'), list) else payload.get('models')
    if not isinstance(raw_list, list):
        return []
    found = []
    seen = set()
    for entry in raw_list:
        if isinstance(entry, str):
            mid = entry.strip()
        elif isinstance(entry, dict):
            mid = str(entry.get('id') or entry.get('name') or entry.get('model') or '').strip()
        else:
            mid = ''
        if mid and mid not in seen:
            seen.add(mid)
            found.append(mid)
    return sorted(found, key=str.casefold)


def attach_routes(source, item):
    """若原始记录带有 routes 列表，则规范化并同步镜像首选启用路线到顶层字段。"""
    if isinstance(source, dict) and isinstance(source.get('routes'), list) and source['routes']:
        item['routes'] = normalize_routes(source, item)
        apply_primary_mirror(item)
    return item


def adapter_has_available_route(adapter):
    """多路线 PoolAdapter 可用性判定：任一启用路线具备有效地址与密钥即返回 True。"""
    return any(route_status(adapter.record, r, program=adapter.program,
                            model_id=adapter.model_id, index=i, override_key=adapter.key)[0]
               for i, r in enumerate(adapter.routes))


def _active_route_entries(adapter, circuit_allows):
    ready, open_fallback = [], []
    base_id = adapter.model_id or adapter.record.get('model', '')
    for idx, route in enumerate(adapter.routes):
        ok, _why = route_status(adapter.record, route, program=adapter.program,
                                model_id=adapter.model_id, index=idx, override_key=adapter.key)
        if not ok:
            continue
        cid = probe_key(base_id, route['id'])
        (ready if circuit_allows(cid) else open_fallback).append((idx, route, cid))
    return ready or open_fallback


def _build_route_sub_adapter(adapter, idx, route, adapter_cls):
    flat = route_as_record(adapter.record, route, model_id=adapter.model_id, index=idx)
    key = adapter.key or route_key_of(
        adapter.record, route, program=adapter.program, model_id=adapter.model_id, index=idx)
    sub = adapter_cls(program=adapter.program, transport=adapter.transport, key=key, timeout=adapter.timeout)
    sub.provider = flat['provider'] or adapter.provider
    sub.key_env = flat['key_env']
    sub.base_url = flat['base_url']
    sub.path = flat['path']
    sub.wire_api = flat['wire_api']
    sub.models = {flat['model']: {'capabilities': tuple(adapter.record.get('capabilities') or ()),
                                  'cost': int(adapter.record.get('cost') or 1)}}
    return sub, flat['model']


def _should_failover(result, failure_policy):
    status = result.get('status')
    if status in (0, 401, 403, 408, 425, 429) or (isinstance(status, int) and status >= 500):
        return True
    return bool(failure_policy(result).get('retryable'))


def execute_route_chat(adapter, messages, options, model, system, router_mod):
    """单模型多条有序 API 路线自动故障转移（非流式）。"""
    candidates = _active_route_entries(adapter, router_mod.circuit_allows)
    if not candidates:
        return {'ok': False, 'status': 0, 'kind': 'configuration',
                'error': '该模型下没有已启用且配置完整的 API 路线',
                'error_class': 'authentication', 'model': str(model or adapter.model_id),
                'text': '', 'usage': router_mod.pet_llm.usage_of(None), 'data': None}
    attempts, last = [], None
    for idx, route, cid in candidates:
        sub, remote_model = _build_route_sub_adapter(adapter, idx, route, router_mod.ModelAdapter)
        result = sub.chat(messages, options=options, model=remote_model or model, system=system)
        attempts.append({'route_id': route['id'], 'route_name': route.get('name') or route['id'],
                         'ok': bool(result.get('ok')), 'status': result.get('status'),
                         'error': '' if result.get('ok') else str(result.get('error') or '')})
        result = dict(result, route_id=route['id'], route_attempts=attempts)
        last = result
        if result.get('ok'):
            router_mod.record_circuit_success(cid)
            return result
        if result.get('status') in router_mod.CIRCUIT_RETRY_STATUS or result.get('status') in (401, 403):
            router_mod.record_circuit_failure(cid)
        if not _should_failover(result, router_mod.failure_policy):
            return result
    return last


def execute_route_stream(adapter, messages, req, router_mod):
    """单模型多条有序 API 路线自动故障转移（流式：仅在尚未吐出首块正文前切换，绝不拼接半截回复）。"""
    options = req.get('options')
    model = req.get('model', '')
    system = req.get('system', '')
    on_chunk = req.get('on_chunk')
    cancelled = req.get('cancelled')
    candidates = _active_route_entries(adapter, router_mod.circuit_allows)
    if not candidates:
        return {'ok': False, 'status': 0, 'kind': 'configuration',
                'error': '该模型下没有已启用且配置完整的 API 路线',
                'error_class': 'authentication', 'model': str(model or adapter.model_id),
                'text': '', 'usage': router_mod.pet_llm.usage_of(None), 'data': None}
    attempts, last = [], None
    for idx, route, cid in candidates:
        sub, remote_model = _build_route_sub_adapter(adapter, idx, route, router_mod.ModelAdapter)
        emitted = [0]
        def wrapped_chunk(piece, _count=emitted):
            _count[0] += 1
            if callable(on_chunk):
                on_chunk(piece)
        result = sub.stream(messages, options=options, model=remote_model or model, system=system,
                            on_chunk=wrapped_chunk if callable(on_chunk) else None, cancelled=cancelled)
        attempts.append({'route_id': route['id'], 'route_name': route.get('name') or route['id'],
                         'ok': bool(result.get('ok')), 'status': result.get('status')})
        result = dict(result, route_id=route['id'], route_attempts=attempts)
        last = result
        if result.get('ok'):
            router_mod.record_circuit_success(cid)
            return result
        if result.get('status') in router_mod.CIRCUIT_RETRY_STATUS or result.get('status') in (401, 403):
            router_mod.record_circuit_failure(cid)
        if emitted[0] > 0 or result.get('error_class') == 'cancelled' or not _should_failover(result, router_mod.failure_policy):
            return result
    return last


def fetch_remote_models(base_url, *, api_key='', wire_api='chat', transport=None, timeout=10):
    """经统一出站通道请求 ``GET <base_url>/models``，返回可选远端模型 ID 列表。"""
    import infra.model_pool as model_pool
    raw_url = str(base_url or '').strip()
    if not raw_url:
        return {'ok': False, 'models': [], 'error': '请先填写 API 地址'}
    try:
        clean = normalize_url(raw_url)
    except ValueError as exc:
        return {'ok': False, 'models': [], 'error': str(exc)}
    if wire_api == 'messages' and not clean.endswith('/v1'):
        url = clean + '/v1/models'
    else:
        url = clean + '/models'
    key = str(api_key or '').strip()
    if wire_api == 'messages':
        headers = token_saver.anthropic_headers(key) if key else {'anthropic-version': '2023-06-01'}
    else:
        headers = {'Authorization': 'Bearer ' + key} if key else {}
    send = transport or model_pool.http_transport
    try:
        result = dict(send(url, None, headers, timeout) or {})
    except Exception as exc:
        return {'ok': False, 'models': [], 'error': f'拉取失败：{type(exc).__name__}（可手动输入模型 ID）'}
    if not result.get('ok'):
        reason = short_probe_error(result)
        return {'ok': False, 'models': [], 'error': f'无法自动拉取模型列表（{reason}），请直接手动输入模型 ID'}
    models = _extract_model_ids(result.get('data'))
    if not models:
        return {'ok': False, 'models': [], 'error': '该地址未返回模型列表，请直接手动输入模型 ID'}
    return {'ok': True, 'models': models, 'error': ''}

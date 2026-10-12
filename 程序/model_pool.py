# -*- coding: utf-8 -*-
"""三虎模型池：模型管理（模型池＋API 配置）与「三虎设置 → 模型」共用的那一份设置。

规格（用户附件《三虎模型设置》）在这里落成三条：
- 模型管理是唯一入口：一个模型＝一条记录（显示名／Provider／模型 ID／API 根地址／协议／
  能力标签／上下文长度／备注／密钥名），密钥只在 .env／环境变量或本机加密那份里
  （model_secrets），配置 JSON 从不写 Key；
- agent.models 四个字段（default／chat／escalate／fallback）引用池里的模型 id，default 还认「自动」；
- 界面上的选项全部从池里长出来，不硬编码。

存储沿用宠物那份全局配置（配置/宠物/配置.json）——pet_llm 认的就是它，多存两把键互不打扰。
"""
import json
import os
import re
import time
from pathlib import Path

import model_secrets
import token_saver
from agent.core import save, replace, temporary_path
from api_endpoints import configured_key, normalize_url
from pet_bus import read_json

PROGRAM = Path(__file__).resolve().parent
CONFIG_PATH = ('配置', '宠物', '配置.json')
AUTO = 'auto'                                    # 「自动」是特殊值，由 model_router 解析
AUTO_LABEL = '自动'
FIELDS = ('label', 'model', 'base_url', 'path', 'wire_api', 'key_env', 'provider', 'note', 'program')
WIRE_APIS = (('chat', 'chat/completions（OpenAI 兼容）'), ('responses', 'responses 新协议'),
             ('messages', 'messages（Anthropic 原生）'))
WIRE_LABELS = dict(WIRE_APIS)
DEFAULT_PATH = '/chat/completions'
DEFAULT_WIRE = 'chat'
# 第 65 期任务 8：「测试连接」发的是最小一次请求，原来是 1 个 token，有些服务商拒收
# 这么小的值（回了 400 就说这条模型不可用）。统一改成 16。
PROBE_TOKENS = 16
# O29：探测会真的发一次最小请求，用量不读回来——标清楚可能产生用量，别让人以为免费。
PROBE_USAGE_NOTE = '测试连接会真实发一次最小请求，可能产生用量'
# Provider 只登记「这条是谁家的」：真发请求仍看 wire_api（默认 OpenAI 兼容），所以它只是标签。
PROVIDERS = (('openai-compatible', 'openai-compatible'), ('anthropic', 'anthropic'),
             ('custom', '自定义'))
PROVIDER_IDS = tuple(value for value, _label in PROVIDERS)
PROVIDER_LABELS = dict(PROVIDERS)
DEFAULT_PROVIDER = 'openai-compatible'
# 第 65 期任务 8：协议（wire_api）跟着 Provider 走，用户不用自己配对。
# 第 66 期：anthropic 改成原生 messages 那一档——Claude 的缓存必须显式 cache_control，
# 只有走原生协议才带得上；「自定义」按 OpenAI 兼容起步，要 /responses 在协议栏手动改一档。
PROVIDER_WIRES = {'openai-compatible': 'chat', 'anthropic': 'messages', 'custom': 'chat'}
# 能力标签：路由的第三步按它挑模型（model_router.select），所以取值范围只有这七个。
CAPABILITY_TAGS = ('long-context', 'structured-output', 'creative-writing', 'reasoning',
                   'vision', 'fast', 'cheap')
CAPABILITY_LABELS = {'long-context': '长上下文', 'structured-output': '结构化输出',
                     'creative-writing': '创意写作', 'reasoning': '推理', 'vision': '视觉',
                     'fast': '快', 'cheap': '便宜'}
# 四个任务维度：标签与用途就按规格里的那张表（界面上照抄，不另编一套说法）。
TASK_FIELDS = (('default', '默认模型', '意图路由、参数抽取、通知生成、简单决策'),
               ('chat', '对话模型', '闲聊、解释、建议、追问'),
               ('escalate', '升级模型', '复杂推理、Bug 诊断、多步规划'),
               ('fallback', '降级模型', '上一栏限流／超时／503 时的容错'))
TASK_KEYS = tuple(field for field, _label, _note in TASK_FIELDS)
TASK_LABELS = {field: label for field, label, _note in TASK_FIELDS}
TASK_NOTES = {field: note for field, _label, note in TASK_FIELDS}
# 桌面 Agent 不是 API：在阶段配置中选中后，工作流会切换到对应的本机 Agent 引擎。
DESKTOP_ENGINES = {'chatgpt-desktop': 'codex', 'claude-desktop': 'claude', 'claude-desktop-app': 'claude-desktop-app'}

# 出厂模型与桌面 Agent：模型池是唯一的模型选择来源。
BUILTIN = (
    ('deepseek-v4-flash', {'label': 'DeepSeek V4 Flash', 'model': 'deepseek-v4-flash',
                           'base_url': 'https://api.deepseek.com', 'path': '/chat/completions',
                           'wire_api': 'chat', 'key_env': 'DEEPSEEK_API_KEY', 'cost': 1,
                           'provider': 'openai-compatible', 'context_length': 64000,
                           'capabilities': ['long-context', 'structured-output', 'reasoning',
                                            'fast', 'cheap']}),
    ('deepseek-v4-pro', {'label': 'DeepSeek V4 Pro', 'model': 'deepseek-v4-pro',
                         'base_url': 'https://api.deepseek.com', 'path': '/chat/completions',
                         'wire_api': 'chat', 'key_env': 'DEEPSEEK_API_KEY', 'cost': 3,
                         'provider': 'openai-compatible', 'context_length': 64000,
                         'capabilities': ['long-context', 'structured-output', 'creative-writing',
                                          'reasoning']}),
    ('gpt-4o', {'label': 'GPT-4o', 'model': 'gpt-4o', 'base_url': 'https://api.openai.com/v1',
                'path': '/chat/completions', 'wire_api': 'chat', 'key_env': 'OPENAI_API_KEY', 'cost': 3,
                'provider': 'openai-compatible', 'context_length': 128000,
                'capabilities': ['vision', 'reasoning', 'creative-writing', 'structured-output',
                                 'long-context']}),
    ('qwen-max', {'label': 'Qwen-Max', 'model': 'qwen-max',
                  'base_url': 'https://dashscope.aliyuncs.com/compatible-mode/v1',
                  'path': '/chat/completions', 'wire_api': 'chat', 'key_env': 'DASHSCOPE_API_KEY', 'cost': 2,
                  'provider': 'openai-compatible', 'context_length': 32000,
                  'capabilities': ['long-context', 'creative-writing', 'structured-output', 'vision']}),
    ('chatgpt-desktop', {'label': 'ChatGPT Desktop · Codex', 'model': 'codex',
                         'provider': 'desktop', 'note': '本机 ChatGPT / Codex Agent',
                         'capabilities': ['long-context', 'creative-writing', 'reasoning']}),
    ('claude-desktop', {'label': 'Claude Code', 'model': 'claude',
                        'provider': 'desktop', 'note': '本机 Claude Agent',
                        'capabilities': ['long-context', 'creative-writing', 'reasoning']}),
    ('claude-desktop-app', {'label': 'Claude Desktop', 'model': 'claude-desktop-app',
                            'provider': 'desktop', 'note': 'Claude 桌面应用（非 Claude Code）；打开后由用户发送',
                            'capabilities': ['long-context', 'creative-writing', 'reasoning']}),
)
TASKS_DEFAULT = {'default': AUTO, 'chat': 'deepseek-v4-pro', 'escalate': 'deepseek-v4-pro',
                 'fallback': 'deepseek-v4-flash'}


def default_pool():
    """出厂模型池的副本：每次都是新对象，界面改它不会污染模块里的常量。"""
    return {model_id: record(value, model_id) for model_id, value in BUILTIN}


def desktop_engine(model_id):
    """模型池中的桌面 Agent id → 工作流引擎；普通 API 模型返回空串。"""
    name = str(model_id or '').strip()
    if name in DESKTOP_ENGINES:
        return DESKTOP_ENGINES[name]
    # 模型管理允许手填 ID；Claude Code 的常用写法仍是同一个 CLI，
    # 不按 claude 前缀猜测，避免把 Claude API 或桌面应用误识别为 CLI。
    alias = re.sub(r'[\s_-]+', '-', name.casefold())
    return 'claude' if alias in ('claude-code', 'claude-code-cli') else ''


def provider_name(model_id, value):
    """阶段配置的一级目录名；Provider 协议字段不承担厂商展示职责。"""
    model = str((value or {}).get('model') or model_id or '').strip().casefold()
    # 「GPT」是厂商展示名，不是 API 协议：桌面 ChatGPT/Codex 与 API 的 gpt-* 模型
    # 都归在同一目录，但仍各自保留原来的 desktop／openai-compatible 调用方式。
    if model_id == 'chatgpt-desktop' or model.startswith('gpt-'):
        return 'GPT'
    if desktop_engine(model_id):
        return 'Anthropic'
    configured = str((value or {}).get('provider') or '').strip()
    # 用户在 API 统一配置中手填的厂商名是该条模型的展示归属，不能在阶段配置里
    # 退化成笼统的「自定义模型」。内建协议名仍按 URL 显示成用户更熟悉的厂商名。
    if configured and configured not in PROVIDER_IDS and configured != 'desktop':
        return configured
    url = str((value or {}).get('base_url') or '').lower()
    if 'deepseek' in url:
        return 'DeepSeek'
    if 'openai' in url:
        return 'OpenAI'
    if 'dashscope' in url or 'qwen' in url:
        return 'Qwen'
    if configured == 'anthropic':
        return 'Anthropic'
    return PROVIDER_LABELS.get(configured, configured or '自定义')


def capabilities_of(value):
    """能力标签：认得的留着（按登记表排序、去重），认不出来的一律丢。

    界面上的多选传 list，配置文件里手写的可能是一句话（"fast, cheap"），两种都收。
    """
    if isinstance(value, str):
        pieces = [piece for piece in re.split(r'[,，;；、\s]+', value) if piece]
    elif isinstance(value, (list, tuple, set)):
        pieces = [str(piece).strip() for piece in value]
    else:
        pieces = []
    known = set(pieces)
    return [tag for tag in CAPABILITY_TAGS if tag in known]


def capability_text(value):
    """能力标签 → 列表里那一格的中文文案（认不出的照原样念，不吞掉用户写的东西）。"""
    return '、'.join(CAPABILITY_LABELS.get(tag, tag) for tag in capabilities_of(value))


def context_length_of(value):
    """上下文长度：正整数才认，其余（空、0、乱写）一律当没填——存 0 会让界面显示一个假的数。"""
    try:
        number = int(str(value).strip())
    except (TypeError, ValueError):
        return ''
    return number if number > 0 else ''


def record(value, model_id=''):
    """一条模型记录：字段补全、空白剪掉；认不出来的键一律丢，不写进配置。"""
    source = value if isinstance(value, dict) else {}
    item = {key: str(source.get(key) or '').strip() for key in FIELDS}
    item['model'] = item['model'] or str(model_id or '').strip()
    item['label'] = item['label'] or item['model']
    if model_id == 'claude-desktop' and item['label'] == 'Claude Desktop · Claude Code':
        item['label'] = 'Claude Code'
    item['path'] = item['path'] or DEFAULT_PATH
    item['wire_api'] = item['wire_api'] if item['wire_api'] in WIRE_LABELS else DEFAULT_WIRE
    # 第 65 期任务 5：用户报「provider → 自定义不可用」。Provider 只是一行标签（真发请求看
    # wire_api），所以这里不再把写进来的名字换成默认值——选「自定义」的人自己敲一个服务商名
    # 也要存得住，只有空着才退回默认。
    item['provider'] = item['provider'] or DEFAULT_PROVIDER
    item['capabilities'] = capabilities_of(source.get('capabilities'))
    item['context_length'] = context_length_of(source.get('context_length'))
    if isinstance(source.get('history_locations'), list):
        item['history_locations'] = [dict(label=str(entry['label']), provider=str(entry['provider']))
                                     for entry in source['history_locations'] if isinstance(entry, dict)
                                     and entry.get('label') and entry.get('provider')]
    try:
        item['cost'] = max(1, min(3, int(source.get('cost') or 1)))
    except (TypeError, ValueError):
        item['cost'] = 1
    return item


def model_id_of(value, model_id=''):
    """记录／id → 池里的键：显式给的 id 优先，其次记录里的模型 ID（显示名不算数）。"""
    if isinstance(value, dict):
        return str(model_id or value.get('model') or '').strip()
    return str(value or '').strip()


def config_file(program=None):
    return Path(program or PROGRAM).joinpath(*CONFIG_PATH)


def raw(program=None, config=None):
    """共享配置文件原样读出（读不出来当空表：坏配置不能让三虎整块起不来）。"""
    if isinstance(config, dict):
        return dict(config)
    try:
        data = read_json(config_file(program))
    except Exception:                             # 连程序目录都算不出来：当没有配置
        data = {}
    return dict(data) if isinstance(data, dict) else {}


def pool(config=None, program=None):
    """模型池：配置里写了就用配置里的（模型管理是唯一入口），没写才是出厂那四条。

    第 59 期第 5 条：顺序也要「简洁易懂」——出厂那几条按固定次序打头，其余按显示名排在后面；
    阶段配置的下拉与设置里的模型池都读这一份，两边顺序自然一致。
    """
    data = raw(program, config)
    stored = data.get('models')
    if not isinstance(stored, dict):
        return default_pool()
    out = {}
    for model_id, value in stored.items():
        item = record(value, model_id)
        if item['model']:
            out[str(model_id)] = item
    # 旧配置补齐桌面入口，但尊重用户在模型管理中明确删除的记录。
    deleted = data.get('deleted_desktop_models') or []
    for model_id, value in BUILTIN:
        if model_id in DESKTOP_ENGINES and model_id not in out and model_id not in deleted:
            out[model_id] = record(value, model_id)
    return ordered(out)


def ordered(items):
    """模型池的展示顺序：出厂那几条按出厂次序，其余按显示名（第 59 期第 5 条）。"""
    builtin = [model_id for model_id, _value in BUILTIN]
    rank = {model_id: index for index, model_id in enumerate(builtin)}
    rest = sorted((model_id for model_id in items if model_id not in rank),
                  key=lambda model_id: (str(items[model_id].get('label') or '').lower(), model_id))
    return {model_id: items[model_id]
            for model_id in [item for item in builtin if item in items] + rest}


def agent_models(config=None, program=None):
    """三虎四个任务各用哪个模型：缺项补出厂默认，「自动」原样留着交给路由器。"""
    data = raw(program, config)
    section = data.get('agent')
    stored = section.get('models') if isinstance(section, dict) else None
    out = dict(TASKS_DEFAULT)
    if isinstance(stored, dict):
        for key in TASK_KEYS:
            value = str(stored.get(key) or '').strip()
            if value:
                out[key] = value
    return out


def label_of(model, records=None, config=None, program=None, labeler=None):
    """模型 id → 界面文案（池里没有就原样返回，认不出也不至于念不出名字）。"""
    text = str(model or '').strip()
    if text == AUTO:
        return AUTO_LABEL
    items = records if isinstance(records, dict) else pool(config, program)
    item = items.get(text)
    return labeler(text, item['label']) if item and callable(labeler) else (item['label'] if item else text)


def options(records=None, config=None, program=None, with_auto=True, labeler=None):
    """下拉／子菜单的选项：(id, 文案)；「自动」只给默认模型那一栏用。"""
    items = records if isinstance(records, dict) else pool(config, program)
    out = [(AUTO, AUTO_LABEL)] if with_auto else []
    out.extend((model_id, labeler(model_id, item['label']) if callable(labeler) else item['label'])
               for model_id, item in items.items())
    return tuple(out)


def id_of_label(text, choices):
    """界面文案 → id（认不出来原样退回，菜单／下拉都不用额外记一份）。"""
    wanted = str(text or '').strip()
    for model_id, label in choices:
        if wanted in (model_id, label):
            return model_id
    return wanted


def wire_for_provider(provider):
    """第 65 期任务 8：Provider → 该配哪一档协议（认不出来的一律回默认那档）。

    界面按这个把「协议」栏自动摆好：换了 Provider，协议跟着动，用户不必自己配对。
    """
    wanted = str(provider or '').strip()
    return PROVIDER_WIRES.get(wanted) or DEFAULT_WIRE


def key_of(value, program=None):
    """这条记录能用的密钥：由模型池统一解析 .env／环境变量／本机加密存储。

    「可用」的判据只能有一处：界面说这个模型能用，三虎真发的时候就必须找得到同一把 Key，
    所以这里不另写一遍读取逻辑，读不到一律当空串。
    """
    item = record(value)
    name = item['key_env']
    if not name:
        return ''
    try:
        return credential(name, program)
    except Exception:
        return ''


def credential(name, program=None):
    """按变量名解析密钥；这是模型客户端与供应商适配器共用的唯一读取链。"""
    key_name = str(name or '').strip()
    root = Path(program or PROGRAM)
    # 新保存（及旧 .env 迁入）的密钥以本程序的 DPAPI 存储为准。否则进程环境里
    # 同名的遗留值会盖过刚保存的新值，迁移完成后的读取与保存结果相互矛盾。
    local = model_secrets.load(key_name, root)
    if local:
        return local
    for folder in (root, root / 'private'):
        try:
            return configured_key({'key_env': key_name, 'project_dir': str(folder)})
        except ValueError:
            continue
    key = (os.environ.get(key_name, '') or '').strip()
    if key and key not in ('replace_me', '<YOUR_API_KEY>') and key.isascii() \
            and not any(char.isspace() for char in key):
        return key
    raise ValueError('当前接口缺少有效 API Key，请在模型管理里填写并保存')


def redacted(key):
    """给人看的那一眼：前 4 位 ＋ ****（规格：密钥永远不整把露面）。"""
    return model_secrets.redacted(key)


def secret_name(value, model_id=''):
    """这条记录的本机密钥叫什么名字：填了密钥名就用它，没填按模型 ID 起一个。"""
    item = record(value, model_id)
    return model_secrets.name_for(item['model'], item['key_env'])


def local_key_of(value, program=None, model_id=''):
    """「直接输入」那把密钥（DPAPI 加密存在 private/密钥 下）；没有就是空串。"""
    return model_secrets.load(secret_name(value, model_id), program)


def save_local_key(value, key, program=None, model_id=''):
    """把直接输入的密钥加密存本机，并把它的名字写回记录（三虎那条链也据此找得到）。

    返回补好名字的记录：调用方拿它去写池子，两处（.env 名／本机密钥名）就指的是同一把钥匙。
    """
    item = record(value, model_id)
    name = model_secrets.name_for(item['model'], item['key_env'])
    model_secrets.save(name, key, program)
    item['key_env'] = name
    return item


def clear_local_key(value, program=None, model_id=''):
    """删掉本机加密那份；本来就没存返回 False。"""
    return model_secrets.clear(secret_name(value, model_id), program)


# R505 P0：旧明文密钥文件的兼容定位；新密钥绝不再写入此路径。
ENV_FILE = ('private', '.env')


def env_file(program=None):
    return Path(program or PROGRAM).joinpath(*ENV_FILE)


def migrate_key_env(program=None):
    """显式迁移本程序旧 ``private/.env``；成功后不保留明文副本。"""
    root = Path(program or PROGRAM)
    return model_secrets.migrate_legacy_env(env_file(root), root)


def save_key_env(value, key, program=None, model_id=''):
    """兼容旧调用名：新密钥只保存到本机 DPAPI。

    ``private/.env`` 仅保留给显式迁移入口定位，不能再作为写入目标。
    """
    text = str(key or '').strip()
    if not text:
        raise ValueError('API Key 不能为空')
    if any(char.isspace() for char in text):
        raise ValueError('API Key 不能带空格')
    name = secret_name(value, model_id)
    if not name:
        raise ValueError('请先填模型 ID（或密钥名），才知道这份密钥该记在谁名下')
    root = Path(program or PROGRAM)
    migrate_key_env(root)
    return model_secrets.save(name, text, root)


def save_named_key(name, value, program=None):
    """按变量名保存密钥到本机 DPAPI 存储。"""
    text = str(name or '').strip()
    if not text:
        raise ValueError('请先填写密钥名（.env 里的变量名）')
    return save_key_env({'key_env': text, 'model': text}, value, program)


def named_key(name, program=None):
    """第 65 期任务 1：按 .env 变量名取密钥（判据仍只有 pet_llm 那一份，读不到就是空串）。"""
    return key_of({'key_env': name}, program)


def status(value, program=None):
    """这条记录现在能不能发得出去：(可用?, 一句话说明)。"""
    item = record(value)
    if item['provider'] == 'desktop':
        return True, '桌面 Agent'
    if not item['model']:
        return False, '缺模型 ID'
    if not item['base_url']:
        return False, '缺 API 根地址'
    if not key_of(item, program):
        if item['key_env']:
            return False, '缺 %s（.env）' % item['key_env']
        return False, '缺 API Key（.env 里的变量名，或本机加密存的那把）'
    return True, '可用'


def available(value, program=None):
    return status(value, program)[0]


def upsert(data, value, model_id=""):
    """把一条记录写进配置（同 id 覆盖）；返回新的配置对象。

    第一次落盘会把出厂那四条一起写进去——模型池一旦写进配置就以配置为准，
    少了这一步，用户加一条自己的模型就会把 DeepSeek／GPT／Qwen 全弄丢。
    """
    key = model_id_of(value, model_id)
    if not key:
        raise ValueError('模型 ID 不能为空')
    items = pool(data)
    previous = items.get(key, {})
    updated = record(value, key)
    locations = list(previous.get('history_locations') or [])
    if previous and (previous.get('label'), provider_name(key, previous)) != (updated['label'], provider_name(key, updated)):
        old_location = {'label': previous['label'], 'provider': provider_name(key, previous)}
        if old_location not in locations:
            locations.append(old_location)
    if locations:
        updated['history_locations'] = locations
    items[key] = updated
    result = dict(data)
    result['models'] = items
    if key in DESKTOP_ENGINES and 'deleted_desktop_models' in result:
        result['deleted_desktop_models'] = [item for item in result['deleted_desktop_models'] if item != key]
    return result


def remove(data, model_id):
    """从配置里删掉一条；返回新的配置对象。"""
    items = pool(data)
    key = str(model_id or '').strip()
    items.pop(key, None)
    result = dict(data)
    result['models'] = items
    if key in DESKTOP_ENGINES:
        result['deleted_desktop_models'] = sorted(set(data.get('deleted_desktop_models') or []) | {key})
    return result


def with_tasks(data, tasks):
    """把四个任务维度写进配置：认不出来的 id 也留着（模型管理里可能只是还没加回来）。"""
    result = dict(data)
    section = dict(result.get('agent')) if isinstance(result.get('agent'), dict) else {}
    section['name'] = section.get('name') or '三虎'
    section['models'] = {key: str((tasks or {}).get(key) or TASKS_DEFAULT[key]).strip()
                         for key in TASK_KEYS}
    result['agent'] = section
    return result


def store(data, program=None):
    """落盘到 配置/宠物/配置.json（原子替换）；返回写到的路径。"""
    path = config_file(program)
    save(path, data)
    return path


def patch_for(model_id, records=None, config=None, program=None):
    """池里那一条 → pet_llm 客户端的配置覆盖：换服务商只换这几个键，其余设置照旧。"""
    text = str(model_id or '').strip()
    if not text or text == AUTO:
        return {}
    items = records if isinstance(records, dict) else pool(config, program)
    item = items.get(text)
    if not item or desktop_engine(text):
        return {}
    patch = {'base_url': item['base_url'], 'path': item['path'], 'wire_api': item['wire_api'],
             'key_env': item['key_env']}
    if item['model']:
        patch['flash_model'] = item['model']
        patch['pro_model'] = item['model']
    return patch


def probe(value, transport=None, program=None, timeout=8, ledger=None):
    """测试连接：拿这一条发最小一次请求（16 个 token），不写盘、不记账。

    顺带把这一趟的耗时量出来（规格里那成功一句要报延迟）；结果里带 'ms'。"""
    item = record(value)
    ok, why = status(item, program)
    if not ok:
        return {'ok': False, 'status': 0, 'error': why, 'model': item['model'], 'url': ''}
    try:
        url = normalize_url(item['base_url'])
    except ValueError as exc:
        return {'ok': False, 'status': 0, 'error': str(exc), 'model': item['model'], 'url': ''}
    if item['wire_api'] == 'responses':
        url = url + '/responses'
        body = {'model': item['model'], 'max_output_tokens': PROBE_TOKENS,
                'input': [{'role': 'user', 'content': 'ping'}]}
    elif item['wire_api'] == 'messages':
        # 第 66 期：Anthropic 原生那一档——地址、鉴权头、版本头都与 OpenAI 兼容那档不同。
        url = token_saver.anthropic_messages_endpoint(url)
        body = {'model': item['model'], 'max_tokens': PROBE_TOKENS,
                'messages': [{'role': 'user', 'content': 'ping'}]}
    else:
        url = url + item['path']
        body = {'model': item['model'], 'max_tokens': PROBE_TOKENS,
                'messages': [{'role': 'user', 'content': 'ping'}]}
    send = transport or http_transport
    head = (token_saver.anthropic_headers(key_of(item, program)) if item['wire_api'] == 'messages'
            else {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + key_of(item, program)})
    started = time.time()
    request_id = 'probe:%s:%d' % (item['model'], int(started * 1000))
    try:
        result = dict(send(url, body, head, timeout) or {})
    except Exception as exc:                      # 网络层抛异常也要变成一句话，不丢给界面线程
        if ledger is not None:
            ledger.mark_unknown(request_id, reason=PROBE_USAGE_NOTE)
        return {'ok': False, 'status': 0, 'error': type(exc).__name__ + '：' + str(exc),
                'model': item['model'], 'url': url, 'ms': elapsed_ms(started),
                'usage_note': PROBE_USAGE_NOTE}
    if ledger is not None:
        ledger.mark_unknown(request_id, reason=PROBE_USAGE_NOTE)
    return {'ok': bool(result.get('ok')), 'status': result.get('status'),
            'error': result.get('error'), 'model': item['model'], 'url': url,
            'ms': elapsed_ms(started), 'usage_note': PROBE_USAGE_NOTE}


def http_transport(url, payload, headers, timeout):
    """模型供应商通用 HTTP 传输；仅在实际请求时加载网络栈。"""
    import ssl
    import urllib.error
    import urllib.request

    body = json.dumps(payload, ensure_ascii=False).encode('utf-8')
    request = urllib.request.Request(url, data=body, headers=dict(headers), method='POST')
    for attempt in range(3):
        try:
            with _http_opener().open(request, timeout=timeout) as response:
                raw = response.read()
                return {'ok': True, 'status': getattr(response, 'status', 200),
                        'data': json.loads(raw or b'{}')}
        except urllib.error.HTTPError as exc:
            detail = exc.read()[:400].decode('utf-8', 'replace')
            return {'ok': False, 'status': exc.code, 'error': 'HTTP ' + str(exc.code) + '：' + detail}
        except urllib.error.URLError as exc:
            if attempt < 2 and isinstance(getattr(exc, 'reason', None), ssl.SSLEOFError):
                time.sleep(0.25 * (attempt + 1))
                continue
            return {'ok': False, 'status': 0, 'error': type(exc).__name__ + '：' + str(exc)}
        except Exception as exc:
            return {'ok': False, 'status': 0, 'error': type(exc).__name__ + '：' + str(exc)}


def http_stream(url, payload, headers, timeout, on_chunk, cancelled=None):
    """OpenAI 兼容 SSE 流；协议不支持或流异常由调用方回退普通请求。"""
    import urllib.error
    import urllib.request
    if cancelled and cancelled():
        return {'ok': False, 'status': 0, 'error': '请求已取消'}
    body = dict(payload or {})
    body['stream'] = True
    request = urllib.request.Request(url, data=json.dumps(body, ensure_ascii=False).encode('utf-8'),
                                     headers=dict(headers), method='POST')
    parts = []
    finish_reason = ''
    try:
        with _http_opener().open(request, timeout=timeout) as response:
            for raw in response:
                if cancelled and cancelled():
                    return {'ok': False, 'status': 0, 'error': '请求已取消'}
                line = raw.decode('utf-8', 'replace').strip()
                if not line.startswith('data:'):
                    continue
                data = line[5:].strip()
                if data == '[DONE]':
                    break
                try:
                    item = json.loads(data)
                    choice = item.get('choices', [{}])[0]
                    finish_reason = choice.get('finish_reason') or finish_reason
                    delta = choice.get('delta', {}).get('content') or ''
                except (ValueError, IndexError, AttributeError):
                    continue
                if delta:
                    parts.append(str(delta)); on_chunk(str(delta))
            return {'ok': True, 'status': getattr(response, 'status', 200),
                    'data': {'choices': [{'finish_reason': finish_reason,
                                          'message': {'content': ''.join(parts)}}]}}
    except (urllib.error.URLError, OSError, ValueError) as exc:
        return {'ok': False, 'status': 0, 'error': type(exc).__name__ + '：' + str(exc)}


def elapsed_ms(started):
    """这一趟花了多少毫秒（四舍五入到整数；clock 读不出来就当 0，别让报数把测试连接带崩）。"""
    try:
        return int(round((time.time() - float(started)) * 1000))
    except (TypeError, ValueError):
        return 0


def _http_opener():
    """Never forward model credentials or request bodies through redirects."""
    import urllib.request

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None

    return urllib.request.build_opener(NoRedirect())

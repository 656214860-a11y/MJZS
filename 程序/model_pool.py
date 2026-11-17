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
import app_logging
import json
import os
import re
import time
from pathlib import Path

import infra.config_snapshot as config_snapshot, model_secrets, token_saver
import infra.client_profiles as client_profiles
from infra.model_metering import REPLAYABLE_RETRY_STATUS
from agent.core import save
from api_endpoints import configured_key, normalize_url, _http_error_kind, _request_headers, _retry_after_seconds, _decode_response_body, wait_for_rpm, elapsed_ms, _RateBucket, _http_opener, HTTP_USER_AGENT
from contract.pet_bus import read_json

PROGRAM = Path(__file__).resolve().parent
CONFIG_PATH = ('配置', '宠物', '配置.json')
AUTO = 'auto'                                    # 「自动」是特殊值，由 model_router 解析
AUTO_LABEL = '自动'
FIELDS = ('label', 'model', 'base_url', 'path', 'wire_api', 'key_env', 'provider', 'note', 'program', 'call_mode', 'provider_label', 'modality', 'rpm', 'group', 'weight')
# 模型功能（模态）：列表按此分组。文本是三虎决策模型池主体；图片/语音/视频模型当前在各自窗口配置，分类先建好暂空。
MODALITIES = (('text', '文本'), ('image', '图片'), ('audio', '语音'), ('video', '视频'))
MODALITY_LABELS = dict(MODALITIES)
DEFAULT_MODALITY = 'text'
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
# O37：「连接成功」不等于「完整工作流可用」。最小请求只证明地址、鉴权与协议握手；
# 长文本、流式、中断、工具与阶段文档都得另跑一次真实任务才算数。结果按这五个维度分开报。
PROBE_DIMENSIONS = (('connectivity', '连通性'), ('protocol', '协议兼容'),
                    ('model_id', '模型标识'), ('capabilities', '能力声明'),
                    ('full_task', '完整任务'))
PROBE_DIMENSION_LABELS = dict(PROBE_DIMENSIONS)
PROBE_FULL_TASK_STATE = '未验证'
PROBE_FULL_TASK_NOTE = ('测试连接只发一次最小请求，只证明连通与鉴权；'
                        '长文本、流式、中断、工具与阶段文档要另跑完整任务')
# 每种协议「一次能用的响应」应该长什么样：HTTP 200 但形状对不上，就是「伪兼容协议」。
PROBE_WIRE_FIELDS = {'chat': ('choices', 'output_text'),
                     'responses': ('output', 'output_text'),
                     'messages': ('content', 'stop_reason', 'type')}
# 小样本验证：用户点名才发一次真实短请求，看正文有没有真的回来、有没有被长度截断。
VERIFY_TOKENS = 64
SAMPLE_PROMPT = '只回答两个字：收到'
# 长度上限截断的 finish_reason：正文只回来一半，完整任务算没通过。
TASK_TRUNCATED = ('length', 'max_tokens', 'max_output_tokens')
# 每条模型最近一次完整任务的结果（只存元数据与配置版本，不存正文）。
HEALTH_KEY = 'model_health'
# Provider 只登记「这条是谁家的」：真发请求仍看 wire_api（默认 OpenAI 兼容），所以它只是标签。
PROVIDERS = (('openai-compatible', 'OpenAI 兼容接口'), ('anthropic', 'anthropic'),
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
    if alias in ('claude-code', 'claude-code-cli'):
        return 'claude'
    # 新客户端由档案决定路由，但 R1706 之前就有路由的名字优先，档案只给它们兜底。
    return '' if alias in client_profiles.BUILTIN_MODEL_NAMES else client_profiles.engine_for_model(name)


def provider_name(model_id, value):
    """阶段配置的一级目录名；Provider 协议字段不承担厂商展示职责。"""
    model = str((value or {}).get('model') or model_id or '').strip().casefold()
    if str((value or {}).get('provider_label') or '').strip():
        return str(value['provider_label']).strip()
    if model_id == 'chatgpt-desktop' or model.startswith('gpt-'):
        return 'GPT'
    engine = desktop_engine(model_id)
    if engine:
        if engine in ('claude', 'claude-desktop-app'):
            return 'Anthropic'
        found = client_profiles.profile_for_model(model_id, value)
        if found:
            return found['display']
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


# 显示名推断里需要整体大写的厂商缩写。
LABEL_ACRONYMS = {'gpt': 'GPT', 'glm': 'GLM', 'api': 'API', 'cli': 'CLI', 'vl': 'VL', 'ai': 'AI'}


def suggest_label(model, records=None):
    """按模型 ID 推断显示名：先认池里／出厂已有的同名模型，认不出就把 ID 分词首字母大写。"""
    name = str(model or '').strip()
    if not name:
        return ''
    known = dict(BUILTIN)
    known.update(records or {})
    for item in known.values():
        if str((item or {}).get('model') or '').strip().casefold() == name.casefold() and item.get('label'):
            return str(item['label'])
    words = [part for part in re.split(r'[-_\s]+', name) if part]
    return ' '.join(LABEL_ACRONYMS.get(word.casefold(), word[:1].upper() + word[1:]) for word in words)


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
    item['modality'] = item['modality'] if item['modality'] in MODALITY_LABELS else DEFAULT_MODALITY
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


def group_candidates(group, current_model, records=None, program=None):
    """同一模型组内按当前模型优先返回候选 id；无组或组为空就只返回当前模型。"""
    group = str(group or '').strip()
    current = str(current_model or '').strip()
    if not group:
        return [current] if current else []
    table = records if isinstance(records, dict) else pool(program=program)
    members = [model_id for model_id, item in table.items()
               if str(item.get('group') or '').strip() == group]
    def rank(model_id):
        try:
            weight = int(table[model_id].get('weight') or 1)
        except (TypeError, ValueError):
            weight = 1
        return (-weight, model_id != current, model_id)
    return sorted(members, key=rank)


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
            return configured_key({'key_env': key_name, 'project_dir': str(folder), 'secret_root': str(root)})
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
    if 'deleted_desktop_models' in result:
        result['deleted_desktop_models'] = [item for item in result['deleted_desktop_models'] if item != key]
    return result


def remove(data, model_id):
    """从配置里删掉一条，ID 记进删除记录（键名沿用只记桌面入口时的 deleted_desktop_models）；返回新的配置对象。"""
    items = pool(data)
    key = str(model_id or '').strip()
    items.pop(key, None)
    result = dict(data)
    result['models'] = items
    if key:
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
    """落盘到 配置/宠物/配置.json（原子替换）；返回写到的路径。覆盖前留快照，失败不拦保存。"""
    path = config_file(program)
    config_snapshot.keep(path, Path(program or PROGRAM) / 'data' / 'config_snapshots', 'pool')
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


def config_version(value, program=None):
    """配置版本：这一条模型当前生效的协议／地址／模型 ID／密钥名（不含密钥值）。

    换了协议、地址、模型 ID 或密钥名，版本就变——「最近完整任务结果」据此判断是不是
    同一条配置跑出来的，避免拿旧绿灯替新配置背书。
    """
    item = record(value)
    return '%s · %s · %s · %s' % (item['wire_api'], item['base_url'] or '（无地址）',
                                  item['model'] or '（无模型 ID）', item['key_env'] or '（无密钥名）')


def request_spec(item, program=None, tokens=PROBE_TOKENS, prompt='ping'):
    """一次请求的地址／请求体／请求头：测试连接与小样本验证共用同一份拼法。"""
    url = normalize_url(item['base_url'])
    messages = [{'role': 'user', 'content': prompt}]
    if item['wire_api'] == 'responses':
        url = url + '/responses'
        body = {'model': item['model'], 'max_output_tokens': tokens, 'input': messages}
    elif item['wire_api'] == 'messages':
        # 第 66 期：Anthropic 原生那一档——地址、鉴权头、版本头都与 OpenAI 兼容那档不同。
        url = token_saver.anthropic_messages_endpoint(url)
        body = {'model': item['model'], 'max_tokens': tokens, 'messages': messages}
    else:
        url = url + item['path']
        body = {'model': item['model'], 'max_tokens': tokens, 'messages': messages}
    head = (token_saver.anthropic_headers(key_of(item, program)) if item['wire_api'] == 'messages'
            else {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + key_of(item, program)})
    return url, body, head


def body_signals(result):
    """从传输结果里只取元数据：响应形状、服务端模型标识、有没有正文、有没有推理字段。

    与本项目「诊断不存正文」的口径一致：这里只算长度与字段名，绝不把正文带出去。
    """
    data = result.get('data') if isinstance(result, dict) else None
    signals = {'shape': [], 'response_model': '', 'has_text': False,
               'reasoning_fields': [], 'finish_reason': '', 'content_length': 0}
    if not isinstance(data, dict):
        return signals
    signals['shape'] = sorted(str(key) for key in data.keys())
    signals['response_model'] = str(data.get('model') or data.get('model_id') or '')
    signals['finish_reason'] = str(data.get('stop_reason') or data.get('status') or '')
    text = ''
    choices = data.get('choices')
    if isinstance(choices, list) and choices and isinstance(choices[0], dict):
        choice = choices[0]
        signals['finish_reason'] = str(choice.get('finish_reason') or signals['finish_reason'])
        message = choice.get('message') if isinstance(choice.get('message'), dict) else {}
        signals['reasoning_fields'] = [key for key in ('reasoning_content', 'reasoning', 'analysis')
                                       if message.get(key) not in (None, '', [], {})]
        content = message.get('content')
        if isinstance(content, str):
            text = content
        elif isinstance(content, list):
            text = ''.join(str(block.get('text') or '') for block in content if isinstance(block, dict))
    if not text:
        text = str(data.get('output_text') or data.get('content') or '')
    blocks = data.get('content')                       # Anthropic messages 原生形状
    if isinstance(blocks, list):
        pieces = [block for block in blocks if isinstance(block, dict)]
        thinking = [block.get('type') for block in pieces
                    if block.get('type') in ('thinking', 'redacted_thinking')]
        if thinking:
            signals['reasoning_fields'] = thinking
        text = text or ''.join(str(block.get('text') or '') for block in pieces
                               if block.get('type') == 'text')
    signals['has_text'] = bool(str(text).strip())
    signals['content_length'] = len(str(text))
    return signals


def _full_task_check(result, signals, ok, full):
    """「完整任务」这一维：最小探测永远未验证；跑了完整任务才按正文与截断判。"""
    if not full:
        return {'ok': None, 'detail': PROBE_FULL_TASK_STATE + ' · ' + PROBE_FULL_TASK_NOTE}
    if not ok:
        error = str(result.get('error') or '')
        if '取消' in error or '中断' in error:
            return {'ok': False, 'detail': '流式／请求被中断，完整任务没跑完：' + (error or '未知原因')}
        return {'ok': False, 'detail': '完整任务没跑通：' + (error or '没有响应')}
    if not signals['has_text']:
        return {'ok': False, 'detail': '请求成功但正文是空的（可能只有推理），完整任务拿不到内容'}
    if str(signals['finish_reason']).lower() in TASK_TRUNCATED:
        return {'ok': False, 'detail': '正文被长度上限截断（finish_reason=%s）' % signals['finish_reason']}
    return {'ok': True, 'detail': '正文 %d 字，finish_reason=%s'
            % (signals['content_length'], signals['finish_reason'] or '未报')}


def classify(item, result, full=False):
    """把一次请求结果拆成五个维度；「连通」与「完整工作流可用」分开，不互相冒充。

    full=False（测试连接的最小请求）：完整任务一维恒为「未验证」。
    full=True（小样本验证跑过真实任务）：按正文、截断、模型标识与服务端实况判定。
    """
    signals = body_signals(result)
    ok = bool(result.get('ok'))
    status = result.get('status')
    wire = item.get('wire_api') or DEFAULT_WIRE
    if ok:
        connectivity = {'ok': True, 'detail': ('HTTP %s' % status) if status else '已连上'}
    else:
        reason = str(result.get('error') or '没有响应')
        connectivity = {'ok': False, 'detail': (('HTTP %s · ' % status) if status else '') + reason}
    fields = PROBE_WIRE_FIELDS.get(wire, ())
    matched = [field for field in fields if field in signals['shape']]
    if not ok:
        protocol = {'ok': None, 'detail': '未取到响应，协议无法判断'}
    elif matched:
        protocol = {'ok': True, 'detail': '%s · %s 对得上' % (wire, '／'.join(matched))}
    else:
        protocol = {'ok': False, 'detail': '回了 %s 但没有 %s 字段，疑似「伪兼容协议」'
                                           % (status, '／'.join(fields))}
    requested = str(item.get('model') or '')
    returned = signals['response_model']
    if not ok:
        model_id = {'ok': None, 'detail': '未取到响应，模型标识无法核对'}
    elif not returned:
        model_id = {'ok': None, 'detail': '响应没带 model 字段，模型标识无法核对'}
    elif returned == requested:
        model_id = {'ok': True, 'detail': returned}
    else:
        model_id = {'ok': False, 'detail': '请求的是 %s，服务端回的是 %s' % (requested, returned)}
    declared = capability_text(item)
    if not ok:
        capabilities = {'ok': None, 'detail': declared or '未声明能力标签'}
    elif signals['reasoning_fields'] and not signals['has_text']:
        capabilities = {'ok': False, 'detail': (declared + ' · ' if declared else '')
                        + '仅返回推理（%s），没有正文' % '／'.join(signals['reasoning_fields'])}
    else:
        capabilities = {'ok': True, 'detail': declared or '未声明能力标签'}
    checks = {'connectivity': connectivity, 'protocol': protocol, 'model_id': model_id,
              'capabilities': capabilities,
              'full_task': _full_task_check(result, signals, ok, full)}
    return [{'key': key, 'label': PROBE_DIMENSION_LABELS[key], 'ok': checks[key]['ok'],
             'detail': checks[key]['detail']} for key, _label in PROBE_DIMENSIONS]


def probe_summary(checks):
    """五个维度 → 一句话（连通性：通过；协议兼容：异常；完整任务：未验证）。"""
    marks = {True: '通过', False: '异常'}
    return '；'.join('%s：%s' % (entry['label'], marks.get(entry['ok'], '未验证')) for entry in checks)


def health(config=None, program=None):
    """每条模型最近一次「完整任务」（小样本验证）的结果，按模型 id 存；只存元数据，不存正文。"""
    data = raw(program, config)
    stored = data.get(HEALTH_KEY)
    if not isinstance(stored, dict):
        return {}
    return {str(key): dict(value) for key, value in stored.items() if isinstance(value, dict)}


def health_of(value, config=None, program=None):
    return health(config, program).get(model_id_of(value), {})


def record_health(value, outcome, program=None):
    """把一次完整任务结果记到这一条模型名下（读改写合并；只留元数据与配置版本）。"""
    model_id = model_id_of(value)
    if not model_id:
        return {}
    source = outcome or {}
    entry = {'at': str(source.get('at') or ''), 'ok': bool(source.get('ok')),
             'config_version': str(source.get('config_version') or ''),
             'content_length': int(source.get('content_length') or 0),
             'finish_reason': str(source.get('finish_reason') or ''),
             'error': str(source.get('error') or '')}
    checks = source.get('checks')
    if isinstance(checks, list):
        entry['checks'] = [dict(check) for check in checks if isinstance(check, dict)]
    data = raw(program)
    table = health(program=program)
    table[model_id] = entry
    data[HEALTH_KEY] = table
    store(data, program)
    return entry


def health_is_blocked(value, program=None):
    """最近一次完整任务失败且配置版本一致时，阻止路由继续把这条模型当可用候选。"""
    item = record(value)
    entry = health_of(value, program=program)
    if not entry:
        return False
    if entry.get('ok') is True:
        return False
    if entry.get('config_version') and entry.get('config_version') != config_version(item):
        return False
    return True


def require_certified(program=None):
    """无人值守前是否强制五合一认证；默认关闭，模型配置页可改。"""
    data = raw(program)
    settings = data.get('model_settings') if isinstance(data, dict) else {}
    return bool((settings or {}).get('require_certified'))


def set_require_certified(value, program=None):
    data = raw(program)
    settings = data.get('model_settings') if isinstance(data, dict) else None
    if not isinstance(settings, dict):
        settings = {}
    settings['require_certified'] = bool(value)
    data['model_settings'] = settings
    store(data, program)
    return settings


def certify(value, transport=None, program=None, timeout=15, prompt=None):
    """五合一认证：连接、协议、模型标识、能力声明、完整任务；成功才记绿灯。"""
    outcome = verify_sample(value, transport=transport, program=program, timeout=timeout, prompt=prompt)
    record_health(value, outcome, program=program)
    return outcome


def probe(value, transport=None, program=None, timeout=8, ledger=None):
    """测试连接：拿这一条发最小一次请求（16 个 token），不写盘、不记账。

    第 O37：结果分五层报——连通性／协议兼容／模型标识／能力声明／完整任务。
    「连接成功」只代表这次最小请求通了；完整工作流（长文本、流式、中断、工具、
    阶段文档）永远标「未验证」，不会被这条绿灯冒充。规格里那句延迟仍在，带 'ms'。
    """
    item = record(value)

    def finish(result):
        answer = dict(result or {})
        answer.setdefault('model', item['model'])
        answer.setdefault('url', '')
        answer.setdefault('ms', 0)
        answer.setdefault('usage_note', PROBE_USAGE_NOTE)
        answer['config_version'] = config_version(item)
        answer['signals'] = body_signals(answer)
        answer['checks'] = classify(item, answer, full=False)
        answer['summary'] = probe_summary(answer['checks'])
        answer['full_task'] = PROBE_FULL_TASK_STATE
        return answer

    ok, why = status(item, program)
    if not ok:
        return finish({'ok': False, 'status': 0, 'error': why})
    try:
        url, body, head = request_spec(item, program, PROBE_TOKENS, 'ping')
    except ValueError as exc:
        return finish({'ok': False, 'status': 0, 'error': str(exc)})
    send = transport or http_transport
    started = time.time()
    request_id = 'probe:%s:%d' % (item['model'], int(started * 1000))
    try:
        result = dict(send(url, body, head, timeout) or {})
    except Exception as exc:                      # 网络层抛异常也要变成一句话，不丢给界面线程
        if ledger is not None:
            ledger.mark_unknown(request_id, reason=PROBE_USAGE_NOTE)
        return finish({'ok': False, 'status': 0, 'error': type(exc).__name__ + '：' + str(exc),
                       'url': url, 'ms': elapsed_ms(started)})
    if ledger is not None:
        ledger.mark_unknown(request_id, reason=PROBE_USAGE_NOTE)
    return finish({'ok': bool(result.get('ok')), 'status': result.get('status'),
                   'error': result.get('error'), 'url': url, 'ms': elapsed_ms(started),
                   'data': result.get('data')})


def verify_sample(value, transport=None, program=None, timeout=15, prompt=None, max_tokens=VERIFY_TOKENS):
    """小样本验证：用户点名时才发一次真实短请求，把「完整任务」这一层跑出来。

    与「测试连接」分工：测试连接只证明连通与鉴权；这里看正文有没有真的回来（不是
    只有推理）、有没有被长度上限截断、服务端报的模型与请求是否一致。默认不自动跑，
    也不批量跑——只在用户对某一条点「小样本验证」时发这一次，避免产生大量费用。
    """
    item = record(value)
    outcome = {'at': time.strftime('%Y-%m-%dT%H:%M:%S'), 'ok': False, 'model': item['model'],
               'config_version': config_version(item), 'content_length': 0,
               'finish_reason': '', 'error': '', 'checks': []}
    ok, why = status(item, program)
    if not ok:
        result = {'ok': False, 'error': why}
    else:
        try:
            url, body, head = request_spec(item, program, max_tokens, prompt or SAMPLE_PROMPT)
        except ValueError as exc:
            result = {'ok': False, 'error': str(exc)}
        else:
            send = transport or http_transport
            try:
                result = dict(send(url, body, head, timeout) or {})
            except Exception as exc:
                result = {'ok': False, 'status': 0, 'error': type(exc).__name__ + '：' + str(exc)}
    signals = body_signals(result)
    result['signals'] = signals
    outcome['checks'] = classify(item, result, full=True)
    outcome['content_length'] = signals['content_length']
    outcome['finish_reason'] = signals['finish_reason']
    outcome['ok'] = bool(result.get('ok')) and signals['has_text']
    outcome['error'] = '' if outcome['ok'] else str(result.get('error') or '请求成功但没有正文')
    return outcome


def model_admission_error(item, *, require_context_length=False, require_certified=False, stage=''):
    """发送前模型准入：空地址／空模型 ID／未知协议仍拒绝；需要上下文预算时拒绝未填窗口；
    require_certified 为真时要求最近一次五合一认证是绿灯。"""
    item = dict(item or {})
    if not str(item.get('model') or '').strip():
        return '模型记录缺少模型 ID，无法发送'
    if not str(item.get('base_url') or '').strip():
        return '模型记录缺少 API 根地址，无法发送'
    wire = item.get('wire_api') or DEFAULT_WIRE
    if wire not in dict(WIRE_APIS):
        return '模型协议不受支持：%s' % wire
    if require_context_length:
        limit = context_length_of(item.get('context_length'))
        if not limit:
            return ('%s的模型记录没有填写上下文窗口（context_length），不能投入无人值守或长文本任务；'
                    '请先在模型管理补全该字段。' % (str(item.get('label') or item.get('model') or '这条模型')))
    if require_certified:
        entry = health_of(item)
        if not entry or entry.get('ok') is not True or entry.get('config_version') != config_version(item):
            return ('%s还没有通过五合一认证，不能投入无人值守；请先在模型管理做小样本验证。'
                    % (str(item.get('label') or item.get('model') or '这条模型')))
    return ''


@app_logging.timed('model.http', 30000)
def http_transport(url, payload, headers, timeout):
    """兼容入口：保留 model_pool 的补丁点，实际传输在 api_endpoints。"""
    result = _http_transport(url, payload, headers, timeout)
    app_logging.count('model.http.' + ('ok' if result.get('ok') else str(result.get('kind') or result.get('status'))))
    return result


def _http_transport(url, payload, headers, timeout):
    import api_endpoints as endpoints
    return endpoints._http_transport(url, payload, headers, timeout, opener=_http_opener)


def http_stream(url, payload, headers, timeout, on_chunk, cancelled=None):
    import api_endpoints as endpoints
    return endpoints.http_stream(url, payload, headers, timeout, on_chunk,
                                 cancelled=cancelled, opener=_http_opener)


# ── DeepSeek Search／Fetch 工具接口 ───────────────────────────────────────────
# 这两个接口是只读的原始 JSON API，和模型调用共用同一把钥匙（DEEPSEEK_API_KEY）与同一套
# 传输栈。放在这里而不是新开模块，是因为「出站 HTTP 只有一个实现」「密钥只有一条读取链」
# 本来就是本模块的职责；调用方（L2 采风服务）只管业务，不碰网络栈、不碰密钥。
TOOLS_BASE_URL = 'https://api.deepseek.com'
TOOLS_SEARCH_PATH = '/v1/tools/search'
TOOLS_FETCH_PATH = '/v1/tools/fetch'
TOOLS_KEY_ENV = 'DEEPSEEK_API_KEY'
TOOLS_QUERY_LIMIT = 128          # 文档：query 1～128 个 Unicode 字符，不能全为空白
TOOLS_COUNT_RANGE = (1, 50)      # 文档：count 1～50，默认 10
TOOLS_URL_LIMIT = 8192
TOOLS_TIMEOUT = 20
# 文档的错误分工：408／429／5xx 等一等再试；402 先充值；其余 4xx 不改请求就别重试。
# 0 是本地网络异常，和 408 一样按可重试处理（与 model_metering.REPLAYABLE_RETRY_STATUS 同口径）。
TOOLS_RETRY_STATUS = (0, 408, 425, 429, 500, 502, 503, 504)
TOOLS_BALANCE_STATUS = 402
TOOLS_RATE_STATUS = 429
TOOLS_URL_PATTERN = re.compile(r'^https?://[^\s/?#]+', re.IGNORECASE)


def tools_base(program=None):
    """Search／Fetch 的根地址：模型池里 DeepSeek 那条的地址优先，其次出厂地址。

    用户把 DeepSeek 换成自建代理时，这三个接口应当跟着模型走，而不是绕回出厂域名。
    """
    try:
        for item in (pool(program=program) or {}).values():
            url = str((item or {}).get('base_url') or '').strip()
            if 'deepseek' in url.lower():
                return normalize_url(url)
    except Exception:
        # 配置读不出来不该让采风变成「崩溃」，退回出厂地址由请求自己报鉴权错。
        return TOOLS_BASE_URL
    return TOOLS_BASE_URL


def tools_headers(program=None):
    """这两个接口的鉴权头：与模型调用同一把钥匙，缺钥匙时抛 ValueError（调用方转成用户提示）。"""
    return {'Content-Type': 'application/json',
            'Authorization': 'Bearer ' + credential(TOOLS_KEY_ENV, program)}


def tools_error_kind(status):
    """HTTP 状态 → 重试策略：balance（先充值）／rate（退避）／auth／blocked／empty／server…"""
    if status == TOOLS_BALANCE_STATUS:
        return 'balance'
    if status == TOOLS_RATE_STATUS:
        return 'rate'
    if status == 403:
        return 'blocked'
    if status == 404:
        return 'empty'
    return _http_error_kind(status)


def tools_retryable(status):
    """这一状态值得等一等再试吗（402 充值、401 换钥匙、其余 4xx 都不该重试）。"""
    try:
        return int(status) in TOOLS_RETRY_STATUS
    except (TypeError, ValueError):
        return False


def _tools_url_problem(url):
    """文档要求的 url 形状：含 host 的 http(s)，且不带用户名密码。"""
    if not url:
        return 'url 不能为空'
    if len(url) > TOOLS_URL_LIMIT:
        return 'url 超过 %d 个字符' % TOOLS_URL_LIMIT
    match = TOOLS_URL_PATTERN.match(url)
    if not match:
        return 'url 必须是含 host 的 HTTP／HTTPS 地址'
    authority = re.sub(r'^https?://', '', match.group(0), flags=re.IGNORECASE)
    if '@' in authority:
        return 'url 不能携带用户名或密码'
    return ''


def _tools_request(path, payload, timeout, transport, program, headers=None):
    """一次只读工具请求：形状与 http_transport 一致，ok 时带上已解析的 data。"""
    try:
        merged = dict(headers) if headers else tools_headers(program)
    except ValueError as exc:
        return {'ok': False, 'status': 0, 'kind': 'auth', 'error': str(exc)}
    sender = transport or http_transport
    result = sender(tools_base(program) + path, payload, merged, timeout)
    if not isinstance(result, dict):
        return {'ok': False, 'status': 0, 'kind': 'bug', 'error': '传输没有返回结果'}
    status = int(result.get('status') or 0)
    if not result.get('ok'):
        return {'ok': False, 'status': status, 'kind': tools_error_kind(status),
                'error': str(result.get('error') or '请求失败')}
    data = result.get('data')
    return {'ok': True, 'status': status or 200, 'data': data if isinstance(data, dict) else {}}


def tools_search(query, count=10, ori_question=None, need_content=False, localization='',
                 timeout=TOOLS_TIMEOUT, transport=None, program=None, headers=None):
    """DeepSeek 网页搜索：返回 {ok,status,kind,data,results}；results 为空数组是正常结果。

    `transport`／`headers` 是自检注入点：不传时走真实传输与模型池里的密钥链。
    """
    text = str(query or '')
    if not text.strip() or len(text) > TOOLS_QUERY_LIMIT:
        return {'ok': False, 'status': 400, 'kind': 'invalid',
                'error': 'query 必须是 1～%d 个字符且不能全为空白' % TOOLS_QUERY_LIMIT}
    try:
        number = int(count)
    except (TypeError, ValueError):
        number = 10
    payload = {'query': text, 'count': max(TOOLS_COUNT_RANGE[0], min(TOOLS_COUNT_RANGE[1], number)),
               'need_content': bool(need_content)}
    question = str(ori_question or '').strip()
    if question:
        payload['ori_question'] = question[:TOOLS_QUERY_LIMIT]
    if localization:
        payload['localization'] = str(localization)
    result = _tools_request(TOOLS_SEARCH_PATH, payload, timeout, transport, program, headers)
    if result.get('ok'):
        rows = result['data'].get('results')
        result['results'] = list(rows) if isinstance(rows, list) else []
    return result


def tools_fetch(url, timeout=TOOLS_TIMEOUT, transport=None, program=None, headers=None):
    """DeepSeek 网页抓取：返回 {ok,status,kind,data,title,content}（正文为 Markdown）。"""
    text = str(url or '').strip()
    problem = _tools_url_problem(text)
    if problem:
        return {'ok': False, 'status': 400, 'kind': 'invalid', 'error': problem}
    result = _tools_request(TOOLS_FETCH_PATH, {'url': text}, timeout, transport, program, headers)
    if result.get('ok'):
        data = result['data']
        result['title'] = str(data.get('title') or '')
        result['content'] = str(data.get('content') or '')
    return result


def call_mode(value, model_id=''):
    """显式调用方式优先；旧本地记录按现有引擎兼容分类。"""
    mode = value.get('call_mode', '')
    if mode in ('Desktop', 'API', 'CLI'):
        return mode
    if value.get('provider') != 'desktop':
        return 'API'
    engine = desktop_engine(model_id) or desktop_engine(value.get('model')) or value.get('model')
    return 'CLI' if engine in ('claude', 'qwen', 'opencode', 'client-cli') else 'Desktop'

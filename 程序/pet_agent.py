"""父编排 Agent：规则优先路由、异常分级退避、预算硬限制、通知聚合、审批与免打扰。

对应架构设计 §7/§8：
- 确定性优先：进度、预算、重试、切页、暂停全部由 RULES 表算出来；只有规则未命中时才问一次
  pet_llm（Flash），且只接受一行严格 JSON。
- 异常分级是纯函数：classify(错误文本, HTTP 码) 给出分类与该做什么；退避 30/60/120 秒，上限 4 次。
- 预算五类硬限制：生图/首帧/视频/配音/Token；越线即暂停该阶段并上报 budget.exceeded。
- 通知先聚合后说话：同批事件合成一句（首帧完成，3 张重试成功，1 张需确认）。
- 免打扰 23:00-07:00（北京时间）：窗口内只记账，出了窗口补一条汇总。
- 审批三档：只提示 / 半自动（付费步骤先确认）/ 全自动；付费动作白名单固定。
- 幂等：idempotency_key = stage|shot|model|提示词散列，提交记录追加到事件日志.jsonl，重复键直接跳过。
本模块不导入 Tk、不直接联网（网络只在 pet_llm 里，且传输可注入），可离线单测。
第 15 期起这里还放宠物的人设（PET_NAME／PET_PERSONA）：名叫三虎，可爱、话少、帮用户把漫剧做完。
"""
import hashlib
import json
import re
import time
from pathlib import Path

import pet_llm
import pet_state
import stage_parallel
from agent.core import save
from pet_bus import SEEN_LIMIT, STAGE_NAMES, STAGES, emit_safe, read_json

LEVELS = ('hint', 'semi', 'auto')
# 第 23 期：三档的名字只有这一份（原来 pet_ui 另写了一份「只提醒」，同一档两个说法）。
# 用户第 21 期给的说法就是「只提醒」——界面小字、猫爪、面板、气泡统一用它。
LEVEL_NAMES = {'hint': '只提醒', 'semi': '半自动', 'auto': '全自动'}
# 第 64 期任务 7：默认档改成「只提醒」——用户报「打开软件默认三虎开启只提示模式」。
# 开机先只看着、只提示，不自己往下跑；用户点过「半自动／全自动」才自动推进（档位写进配置，
# 下次开机照他选的那一档来）。
DEFAULT_LEVEL = 'hint'
# 第 15 期：宠物自己的人设。名字只在这一份里定义——pet_llm 的固定前缀与 pet_cloud 的说话前缀都取它，
# 自检有用例盯着三处不许走偏；LEVEL_COLORS（pet_ui）管头像颜色：全自动红／半自动蓝／只提示黄。
PET_NAME = '三虎'
PET_PERSONA = '一只可爱的小猫，说话简洁，帮用户把漫剧做完'
DND = (23, 7)                                   # 免打扰：北京时间 23:00-07:00
PAID_ACTIONS = ('image.generate', 'firstframe.generate', 'video.generate', 'voice.generate')
BUDGET_KINDS = ('image', 'firstframe', 'video', 'voice', 'tokens')
BUDGET_NAMES = {'image': '生图', 'firstframe': '首帧', 'video': '视频', 'voice': '配音', 'tokens': 'Token'}
BUDGET_ALIASES = {'token': 'tokens', 'tokens_per_day': 'tokens', 'keyframe': 'firstframe',
                  'shots': 'video', 'tts': 'voice', 'img': 'image'}
DEFAULT_BUDGET = {'image': 200, 'firstframe': 200, 'video': 100, 'voice': 200, 'tokens': 2000000}
WARN_RATIO = 0.9                                # 用到九成先报一声
MAX_ATTEMPTS = 4
NOTICE_PATH = ('工作流任务', '宠物', '通知.json')
JOURNAL_PATH = ('工作流任务', '宠物', '事件日志.jsonl')
KEEP = 50
SUMMARY_LIMIT = 4
PROJECT_LIMIT = 12                              # 快照里最多带几个项目（第 37 期第 1 条）

SHORT_NAMES = {'script': '剧本', 'storyboard': '分镜', 'assets': '资产', 'final': '定稿', 'keyframe': '首帧',
               'previs': '白模', 'video': '视频', 'audio': '配音', 'edit': '剪辑', 'delivery': '交付'}
UNIT_OF = {'keyframe': '张', 'assets': '张', 'video': '个镜头', 'audio': '条', 'delivery': '个文件'}
OUTCOME_ORDER = ('success', 'retry_success', 'need_confirm', 'failed', 'skipped')
OUTCOME_WORDS = {'success': '完成', 'retry_success': '重试成功', 'need_confirm': '需确认',
                 'failed': '失败', 'skipped': '已跳过'}

# 规则表：先规则后模型。命中任何一条都不花 Token（策略：确定性优先）。
RULES = (
    (r'^\s*/(?:help|帮助)', 'help', None),
    (r'^\s*/(?:clear|compact)', 'context', None),
    # 第 23 期扩容：会话里最常说的几句都进了规则表——命中即答，不再花 Token 问一次模型，
    # 也少了「等模型回话」那一段延迟。顺序即优先级，越具体的越靠前。
    (r'(进度面板|面板|明细|详细进度)', 'panel', None),
    (r'(一键执行|一键收尾|全部做完|都做完|都干了|收个尾)', 'oneclick', None),
    (r'(周报|本周报表)', 'weekly', None),
    (r'(日报|今日报表|今天的报表)', 'report', None),
    (r'(?:运行|执行|开始|跑)(?:长列表|资产列表)(?:优化|性能)(?:检查|基准|测试)?', 'performance_list', None),
    (r'(?:运行|执行|开始|跑)(?:优化|性能)(?:检查|基准|测试)?', 'performance', None),
    (r'(?:运行|执行|开始|跑)(?:增量)?(?:自检|测试)(?:\s*\d+\s*次)?', 'test', None),
    (r'(换模型|切换模型|换个模型|模型档位)', 'model', None),
    (r'(详情|待确认|卡住的|要我确认)', 'details', None),
    (r'(进度|到哪|还要多久|要多久|还剩|百分比)', 'progress', None),
    (r'(暂停|停下|先停|别跑|停一下|停止自动)', 'pause', None),
    (r'(继续|接着跑|往下跑|恢复运行|接着做)', 'resume', None),
    (r'(重试|再试|重跑|再来一次)', 'retry', None),
    (r'(跳过|略过|不要这张|下一张)', 'skip', None),
    (r'(免打扰|勿扰|静音|别提醒)', 'silence', None),
    (r'(全自动|半自动|只提示|自动化等级)', 'level', None),
    (r'(用量|花费|成本|命中率|token)', 'usage', None),
    # 第 37 期第 1 条：三虎要「记住所有项目」。说法写成整词，免得把「剧本／分镜这些阶段词」
    # 抢过来（规则表按顺序比，越靠前越优先）。
    (r'(有哪些项目|项目列表|几个项目|别的项目|所有项目|项目都怎么样)', 'projects', None),
    (r'(导出|交付|打包|出片)', 'export', 'delivery'),
    (r'(生成|做|出)(?:所有|全部)?(?:首帧|关键帧)', 'generate', 'keyframe'),
    (r'(生成|做|出)(?:所有|全部)?(?:视频|镜头视频)', 'generate', 'video'),
    # 第 62 期任务 2：三虎要能自己把分镜做起来——「生成／做／出一版分镜」走 generate，
    # 排在下面那条 (分镜|镜头表) → goto 前面，免得又被当成「切到那一页」。
    (r'(生成|做|出|制作|来一版|跑一下)(?:所有|全部|批量)?(?:分镜|镜头表)', 'generate', 'storyboard'),
    (r'(配音|字幕)', 'goto', 'audio'),
    (r'(粗剪|剪辑|时间线)', 'goto', 'edit'),
    (r'(白模|预演|粗模)', 'goto', 'previs'),
    (r'(质检|检查成片)', 'goto', 'delivery'),
    (r'(资产|参考图|角色图|素材)', 'goto', 'assets'),
    (r'(定稿)', 'goto', 'final'),
    (r'(分镜|镜头表)', 'goto', 'storyboard'),
    (r'(剧本|大纲|人设)', 'goto', 'script'),
    (r'(首帧)', 'goto', 'keyframe'),
)
REPLIES = {
    'help': '我能做：查进度 / 继续 / 暂停 / 重试失败项 / 跳过 / 导出交付 / 切页 / 批量生成首帧 / 运行增量自检 / 运行优化检查。',
    'context': '本轮上下文本来就是一次性的：每次调用只带固定前缀＋当前快照，没有历史需要清理。',
    'progress': '好，把进度面板打开。',
    'pause': '已暂停自动执行，等您发话。',
    'resume': '继续往下跑。',
    'retry': '这就重试失败项。',
    'skip': '跳过这一项。',
    'silence': '好，这段时间不打扰您。',
    'level': '切换自动化等级。',
    'usage': '报一下用量与缓存命中率。',
    'export': '准备交付导出的清单。',
    'generate': '开始批量生成。',
    'goto': '切到对应页面。',
    # 第 23 期：新增的几条规则各自说话，别都回一句笼统的「好的」。
    'panel': '好，把进度面板打开。',
    'oneclick': '这就一键收尾：重试失败项 → 本地补首帧 → 出今日日报。',
    'report': '这就把今天的日报整出来。',
    'test': '开始运行增量自检，完成后汇报成功率与失败用例。',
    'performance': '开始运行离线优化检查，完成后只汇报超过阈值的耗时退化。',
    'performance_list': '开始运行长列表优化检查，完成后只汇报超过阈值的耗时退化。',
    'weekly': '这就把本周周报整出来。',
    'model': '换一档编排模型，下一次调用生效。',
    'details': '把待确认的几项列出来。',
    'projects': '把手上的项目报一遍。',
}
UNKNOWN_REPLY = '没听明白。可以直接说「继续」「暂停」「查进度」「重试失败项」，或者点页面上的按钮。'

# 错误分级表：错误文本或 HTTP 码命中即归类；顺序即优先级（余额/鉴权在参数之前）。
PATTERNS = (
    ('auth', ('401', '403', 'unauthorized', 'forbidden', '密钥', 'api key')),
    ('quota', ('402', '余额', '欠费', 'quota', 'insufficient', 'balance')),
    ('content', ('content', '审核', '敏感', '违规', 'policy', 'blocked', 'safety')),
    ('params', ('400', '参数', 'invalid', 'not valid', 'unsupported', '尺寸')),
    ('rate_limit', ('429', 'rate limit', '限流', 'too many', '太频繁')),
    ('timeout', ('timeout', 'timed out', '超时', '逾时')),
    ('server', ('500', '501', '502', '503', '504', 'server error', '服务不可用')),
)
VERDICTS = {
    'timeout': (True, 'backoff', '超时：按 30/60/120 秒退避重试'),
    'rate_limit': (True, 'backoff', '被限流：退避后重试，Pro 自动降级 Flash'),
    'server': (True, 'backoff', '服务端故障：退避后重试'),
    'params': (True, 'fix_params', '参数不合法：先归一尺寸/时长/模型名，再立即重试一次'),
    'content': (False, 'prompt_fix', '命中内容审核：改写提示词后再提，别原样重试'),
    'quota': (False, 'pause', '余额或配额不足：暂停该阶段并通知，不再消耗'),
    'auth': (False, 'notify', '接口密钥无效或没配：检查 .env 里的 Key'),
    'unknown': (False, 'notify', '没认出来：先按「重试失败项」，要细节看「查看待确认详情」'),
}
# 类目 → 中文名：日报／周报与气泡都要说人话，名字只有这一份。
CATEGORY_NAMES = {'timeout': '超时', 'rate_limit': '被限流', 'server': '服务端故障',
                  'params': '参数不合法', 'content': '内容审核', 'quota': '余额／配额不足',
                  'auth': '密钥问题', 'unknown': '未知错误'}
# 事件 → 通知口径：谁失败该找谁确认，谁完成该报一句。
NOTIFY_MAP = {'stage.completed': 'success', 'stage.failed': 'need_confirm',
              'asset.reference.found': 'success', 'firstframe.task.failed': 'need_confirm',
              'video.task.failed': 'need_confirm', 'voice.task.failed': 'need_confirm',
              'delivery.ready': 'success'}
EVENT_STAGE = {'firstframe.task.failed': 'keyframe', 'video.task.failed': 'video', 'voice.task.failed': 'audio'}

SIZES = ((1024, 1024), (1024, 768), (768, 1024), (1280, 720), (720, 1280), (2048, 2048))
MODEL_ALIASES = {'seedream': 'seedream-5.0', 'seedream5': 'seedream-5.0', 'seedream-5': 'seedream-5.0',
                 'deepseek': 'deepseek-v4-flash', 'deepseek-chat': 'deepseek-v4-flash',
                 'deepseek-reasoner': 'deepseek-v4-pro', 'wan': 'wan2.2', 'wan2.1': 'wan2.2'}
DURATION_KEYS = ('duration', 'seconds', 'length')
MIN_SECONDS, MAX_SECONDS = 1, 10


def _int(value):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def strip_space(text):
    return ' '.join(str(text or '').split())


# ── 意图路由 ────────────────────────────────────────────────────────────────
def level_in(text):
    """从一句话里认出要切到哪一档自动化等级；认不出返回 None。

    规则路由与「真的去切档」两处都要认这句话，认法只能有一份。
    """
    body = str(text or '')
    for level, name in sorted(LEVEL_NAMES.items(), key=lambda item: -len(item[1])):
        if name in body:
            return level
    return None


def rule_reply(intent, stage=None):
    """规则命中的那句人话：能报出具体对象的就报具体对象（切哪一页、生成什么）。

    第 23 期之前所有切页都回同一句「切到对应页面。」——用户看不出要去哪一页，
    还得自己去猜。现在直接写页面名。
    """
    name = SHORT_NAMES.get(stage, '') if stage else ''
    if intent == 'goto' and name:
        return '好，切到「' + name + '」这一步。'
    if intent == 'generate' and name:
        return '开始批量生成' + name + '。'
    return REPLIES.get(intent, '')


def match_rule(text):
    """规则匹配：返回 {intent, stage, params, reply, source}，未命中返回 None。"""
    body = strip_space(text)
    if not body:
        return None
    for pattern, intent, stage in RULES:
        found = re.search(pattern, body, re.IGNORECASE)
        if found:
            params = {'text': body}
            if intent == 'level':
                params['level'] = level_in(body)      # 「全自动」这句话本身就把档位说清楚了
            return {'intent': intent, 'stage': stage, 'params': params,
                    'reply': rule_reply(intent, stage), 'source': 'rule'}
    return None


# ── 自然语言 → SKILL（第 28 期第 7 条） ────────────────────────────────────
# 用户说「把首帧批量生成跑一下」这类话时，先按注册表对上 SKILL，再交给编排器；光提到名字
# （「首帧管理那一页」）不算——那是切页的活，规则里已经有。
SKILL_VERBS = ('执行', '跑一遍', '跑一下', '跑', '做一遍', '做一下', '来一遍', '开始做', '接着做',
               '批量做', '试一试', '走一遍')
SKILL_STOP = ('不用', '别跑', '先不', '不要')
# 「执行选中」是面板上原来那颗按钮的说法（第 54 期删了按钮，用户照着喊照旧管用）：当前这一步里勾上的那几个。
SKILL_SELECTED = ('执行选中', '执行勾选', '跑选中的', '跑勾选的', '执行选择')
# 「用 GPT 跑一遍」这种一句话里点名的编排模型：算「单次」覆盖，跑完不留痕迹。
ROUTER_MODELS = (('gpt', 'gpt-4o'), ('qwen', 'qwen-max'), ('通义', 'qwen-max'),
                 ('pro', 'deepseek-v4-pro'), ('flash', 'deepseek-v4-flash'))


def match_model(text):
    """一句话里点名的编排模型（单次覆盖）：认得出就返回模型 id，没提就是空串。

    十个阶段的模型入口在阶段配置面板上；这里只管「这一次」——规格里的三级覆盖，
    单次 ＞ 项目 ＞ 全局，这一声就是最上面那一层。英文别名按词边界认，别把 profile 当成 pro。"""
    body = str(text or '')
    if not body:
        return ''
    lowered = body.lower()
    for alias, model in ROUTER_MODELS:
        if alias.isascii():
            if re.search(r'(?<![a-z0-9])%s(?![a-z0-9])' % re.escape(alias), lowered):
                return model
        elif alias in body:
            return model
    return ''


def skill_names(item):
    """一个 SKILL 在自然语言里可能被叫的几种写法。"""
    name = str(getattr(item, 'name', '') or '')
    display = str(getattr(item, 'displayName', '') or '')
    return [text for text in (name, display, name.replace('-', '')) if text]


def match_skill(text, registry=None, current=None):
    """自然语言 → SKILL 计划：命中返回 {intent: skill, stage, params, reply}，没命中返回 None。

    current＝当前所在阶段（「执行选中」要知道是哪一页的勾选）；registry 可注入，自检里不碰真表。
    """
    body = strip_space(text)
    if not body or any(word in body for word in SKILL_STOP):
        return None
    if any(word in body for word in SKILL_SELECTED) and current in STAGES:
        return {'intent': 'skill', 'stage': current,
                'params': {'text': body, 'skills': [], 'model': match_model(body)},
                'reply': '好，执行「%s」这一步里您勾上的 SKILL。' % STAGE_NAMES.get(current, current),
                'source': 'skill'}
    lowered = body.lower()
    if 'skill' not in lowered and not any(word in body for word in SKILL_VERBS):
        return None
    import skill_registry
    reg = registry or skill_registry.default_registry()
    hits, stages, labels = [], [], []
    for item in reg.getAll():
        if any(name and name in body for name in skill_names(item)):
            hits.append(item.name)
            labels.append(item.displayName or item.name)
            if item.stage not in stages:
                stages.append(item.stage)
    for stage_id, label in STAGE_NAMES.items():
        if label and label in body and stage_id not in stages:
            stages.append(stage_id)
    if not hits and not stages:
        return None
    stage = stages[0] if stages else None
    names = list(dict.fromkeys(hits))
    if names:
        reply = '好，这就把「%s」跑起来。' % '、'.join(dict.fromkeys(labels))
    else:
        reply = '好，这就把「%s」这一步的 SKILL 按您勾上的跑起来。' % STAGE_NAMES.get(stage, stage)
    return {'intent': 'skill', 'stage': stage,
            'params': {'text': body, 'skills': names, 'model': match_model(body)},
            'reply': reply, 'source': 'skill'}


def extract_content(data):
    """兼容两种线协议：chat 取 choices[0].message.content，responses 取 output_text/output[].content[].text。"""
    if not isinstance(data, dict):
        return ''
    choices = data.get('choices')
    if isinstance(choices, list) and choices and isinstance(choices[0], dict):
        message = choices[0].get('message')
        if isinstance(message, dict) and message.get('content'):
            return str(message['content'])
        # 第 65 期任务 10：推理型模型只出思考不出正文时，思考那段就是唯一拿得到的字，
        # 丢掉它就等于告诉用户「空回复」——只出思考也算有回复。
        if isinstance(message, dict) and (message.get('reasoning_content') or message.get('reasoning')):
            return str(message.get('reasoning_content') or message.get('reasoning'))
    if isinstance(data.get('output_text'), str) and data['output_text']:
        return data['output_text']
    output = data.get('output')
    if isinstance(output, list):
        for block in output:
            content = block.get('content') if isinstance(block, dict) else None
            for piece in content if isinstance(content, list) else ():
                if isinstance(piece, dict) and piece.get('text'):
                    return str(piece['text'])
    return ''


def parse_intent(text):
    """严格解析模型回复：只认 intent/stage/params/reply，围栏与多余解释一律丢掉，解析不出来返回 None。"""
    body = str(text or '').strip()
    if body.startswith('```'):
        body = re.sub(r'^```[a-zA-Z]*\s*', '', body)
        body = re.sub(r'\s*```$', '', body).strip()
    start, end = body.find('{'), body.rfind('}')
    if start < 0 or end <= start:
        return None
    try:
        data = json.loads(body[start:end + 1])
    except ValueError:
        return None
    if not isinstance(data, dict):
        return None
    stage = data.get('stage') if data.get('stage') in STAGES else None
    params = data.get('params') if isinstance(data.get('params'), dict) else {}
    return {'intent': str(data.get('intent') or 'unknown'), 'stage': stage, 'params': params,
            'reply': str(data.get('reply') or ''), 'source': 'llm'}


def route(text, client=None, context=None):
    """先规则后模型：规则命中就不花 Token；未命中且给了客户端时才问一次 Flash 抽意图。

    第 28 期第 7 条：SKILL 点名放在规则前头——「把首帧批量生成跑一下」里的「首帧」会先把
    切页那条规则勾走，可用户要的是跑 SKILL 而不是翻页；能对上注册表的点名更具体，先问它。
    """
    hit = match_skill(text, current=(context or {}).get('stage'))
    if hit:
        return hit
    hit = match_rule(text)
    if hit:
        return hit
    body = strip_space(text)
    unknown = {'intent': 'unknown', 'stage': None, 'params': {'text': body},
               'reply': UNKNOWN_REPLY, 'source': 'none'}
    if client is None:
        return unknown
    result = client.ask('intent.route', body, context=context)
    if not result.get('ok'):
        unknown.update(source='llm-error', reply=UNKNOWN_REPLY + '（模型也不通：' + str(result.get('error') or '') + '）')
        return unknown
    parsed = parse_intent(extract_content(result.get('data')))
    if parsed is None:
        unknown.update(source='llm-unparsed')
        return unknown
    return parsed


def action_for(plan):
    """意图 → 动作名：这一份决定「要不要按等级审批」，所以它得先分清免费与付费。

    三类永远放行（见 FREE_ACTIONS）：
    - stage.goto：切页，只是把那一页翻开；
    - stage.inspect：只读，查进度、看明细、报用量；
    - stage.control：三虎自己的开关（切档位／静默／开关对话／暂停）。
    首帧单列成 keyframe.local：宠物这条路上它只走本机 ComfyUI（免费），付费的 Seedream
    通道只在页面里，宠物从不代按——所以半自动档下它该跑就跑。
    """
    intent, stage = (plan or {}).get('intent'), (plan or {}).get('stage')
    if intent == 'generate':
        if stage == 'keyframe':
            return 'keyframe.local'
        if stage == 'storyboard':
            # 第 62 期任务 2：分镜走「初步分镜」页那条 Agent 准备链——只在本机把任务派给自己
            # 配好的 Agent，不产生第三方生成费用，所以与 keyframe.local 一样算「不花钱的动作」。
            return 'storyboard.local'
        return {'video': 'video.generate', 'assets': 'image.generate',
                'audio': 'voice.generate'}.get(stage, 'stage.generate')
    if intent == 'skill':
        return 'skill.run'
    if intent == 'export':
        return 'delivery.export'
    if intent == 'goto':
        return 'stage.goto'
    # 第 37 期第 1 条：报项目清单也是「看一眼」的事（读登记表），哪一档都该立刻答出来。
    if intent in ('progress', 'panel', 'usage', 'details', 'help', 'context', 'projects', 'test', 'performance', 'performance_list'):
        return 'stage.inspect'
    if intent in ('level', 'silence', 'chat', 'pause', 'resume'):
        return 'stage.control'
    return 'stage.run'


# 第 23 期：不跑任务也不花钱的动作——切页、查进度、看详情、报用量、切档位、静默、
# 开关对话、暂停。这些哪一档都该立刻生效；挡在外面的只该是「会跑任务／会花钱」的动作。
# 之前不分青红皂白一律拦，用户随口问一句进度都被顶回来一句「只提示模式：只报告，不自动执行」
# ——既没帮上忙，又把对话拖长。
FREE_ACTIONS = ('stage.goto', 'stage.inspect', 'stage.control', 'keyframe.local', 'storyboard.local')


# ── 异常分级与退避 ──────────────────────────────────────────────────────────
def verdict(category, error='', status=None):
    retry, action, hint = VERDICTS.get(category, VERDICTS['unknown'])
    return {'category': category, 'retry': retry, 'action': action, 'hint': hint,
            'error': str(error or ''), 'status': status}


def classify(error, status=None):
    """错误分级（纯规则，不联网）：分类 + 是否可重试 + 该做什么 + 一句中文建议。"""
    text = str(error or '')
    code = ''
    if status not in (None, ''):
        number = _int(status)
        code = str(number) if number is not None else str(status)
    haystack = text.lower() + ' ' + ('http ' + code if code else '')
    for category, marks in PATTERNS:
        if any(_mark_hit(haystack, mark) for mark in marks):
            return verdict(category, error, status)
    return verdict('unknown', error, status)


def _mark_hit(haystack, mark):
    """这一条标记命中没命中。第 71 期任务 1：纯数字的标记（401／429…）只认
    「独立的一串数字」——退出码 4294967295 里的 429 曾经把 ComfyUI 退出当成「被限流」，
    于是真正的原因被误判而不报。"""
    mark = str(mark).lower()
    if mark.isdigit():
        return re.search(r'(?<!\d)' + mark + r'(?!\d)', haystack) is not None
    return mark in haystack


def backoff(attempt, delays=pet_llm.RETRY_DELAYS):
    """第 attempt 次重试前等多久：30/60/120 秒，表用完停在最后一档（不无限翻倍）。"""
    index = max(1, int(attempt)) - 1
    return float(delays[min(index, len(delays) - 1)])


def retry_plan(attempt, error, status=None, params=None, max_attempts=MAX_ATTEMPTS, delays=None):
    """已失败 attempt 次之后怎么办：给退避与次数；参数类错误先修正再立即重试；超上限转人工。"""
    delays = tuple(delays or pet_llm.RETRY_DELAYS)
    plan = classify(error, status)
    attempt = max(0, _int(attempt) or 0)
    plan.update(allow=False, attempt=attempt, next_attempt=attempt, delay=None)
    if not plan['retry']:
        return plan
    if attempt >= int(max_attempts):
        plan['hint'] = '已重试 ' + str(attempt) + ' 次仍未成功：交给您确认'
        return plan
    if plan['action'] == 'fix_params':
        plan.update(allow=True, next_attempt=attempt + 1, delay=0.0, params=fix_params(params or {}))
        return plan
    plan.update(allow=True, next_attempt=attempt + 1, delay=backoff(attempt + 1, delays))
    return plan


def snap_size(width, height, sizes=SIZES):
    """把任意尺寸吸到最近的合法档位：先看长宽比最接近，比例打平才比像素数量。
    比例优先是刻意的——按面积优先会把 1:4 的竖图吸成同像素的正方形。"""
    ratio = width / height
    best, best_key = sizes[0], None
    for candidate in sizes:
        key = (round(abs(candidate[0] / candidate[1] - ratio), 4),
               abs(candidate[0] * candidate[1] - width * height))
        if best_key is None or key < best_key:
            best, best_key = candidate, key
    return best


def fix_params(params, sizes=SIZES, aliases=MODEL_ALIASES):
    """参数归一：尺寸吸到合法档位、时长夹到 1-10 秒、模型名换规范名。返回新参数与改了哪几项。"""
    out = dict(params or {})
    fixed = []
    width, height = _int(out.get('width')), _int(out.get('height'))
    text = str(out.get('size') or '').lower()
    if (not width or not height) and 'x' in text:
        left, _, right = text.partition('x')
        width, height = _int(left), _int(right)
    if width and height and width > 0 and height > 0:
        target = snap_size(width, height, sizes)
        if (width, height) != target:
            out.pop('size', None)
            out['width'], out['height'] = target
            fixed.append('尺寸')
    for key in DURATION_KEYS:
        if key in out:
            raw = _int(out.get(key))
            value = max(MIN_SECONDS, min(MAX_SECONDS, raw if raw is not None else MIN_SECONDS))
            if raw != value:
                fixed.append('时长')
            out[key] = value
    if 'model' in out:
        name = str(out.get('model') or '').strip()
        canonical = aliases.get(name.lower(), name)
        if not name:
            out.pop('model')
            fixed.append('模型名')
        elif canonical != name:
            out['model'] = canonical
            fixed.append('模型名')
    return {'params': out, 'fixed': fixed}


# ── 五类配额硬限制 ──────────────────────────────────────────────────────────
def normalize_kind(kind):
    name = BUDGET_ALIASES.get(str(kind or '').strip().lower(), str(kind or '').strip().lower())
    if name not in BUDGET_KINDS:
        raise ValueError('未登记的配额类型：' + str(kind))
    return name


class Budget:
    """生图/首帧/视频/配音/Token 五类配额的硬限制：越线直接拒绝，不留「再试一次」的口子。"""

    def __init__(self, limits=None):
        self.limits = dict(DEFAULT_BUDGET)
        for kind, value in (limits or {}).items():
            try:
                name = normalize_kind(kind)
            except ValueError:
                continue
            number = _int(value)
            if number and number > 0:
                self.limits[name] = number
        self.used = {kind: 0 for kind in BUDGET_KINDS}

    def check(self, kind, amount=1):
        """只算不扣：够不够、还剩多少、要不要提前报警。"""
        name = normalize_kind(kind)
        count = max(0, _int(amount) or 0)
        limit, used = self.limits[name], self.used[name]
        ok = used + count <= limit
        ratio = (used + count) / limit if limit else 1.0
        return {'ok': ok, 'kind': name, 'used': used, 'limit': limit, 'amount': count,
                'remaining': max(0, limit - used - count), 'warning': ok and ratio >= WARN_RATIO,
                'exceeded': not ok}

    def spend(self, kind, amount=1):
        """扣减：越线时原样返回拒绝结果且不扣，调用方据此暂停。"""
        result = self.check(kind, amount)
        if result['ok']:
            self.used[result['kind']] += result['amount']
        return result

    def sync_tokens(self, ledger, at=None):
        """把 pet_llm 台账里当天的 Token 用量同步进来（Token 也是一类配额）。"""
        if ledger is None:
            return self.used['tokens']
        try:
            self.used['tokens'] = int(ledger.today_tokens(at))
        except Exception:
            return self.used['tokens']
        return self.used['tokens']

    def snapshot(self):
        return {'limits': dict(self.limits), 'used': dict(self.used)}


# ── 通知聚合与免打扰 ────────────────────────────────────────────────────────
def stage_sentence(stage, counts):
    """一个阶段一句话：首帧完成，3 张重试成功，1 张需确认。"""
    name = SHORT_NAMES.get(stage) or STAGE_NAMES.get(stage, stage or '任务')
    unit = UNIT_OF.get(stage, '项')
    order = [outcome for outcome in OUTCOME_ORDER if counts.get(outcome)]
    if not order:
        return ''
    pieces = [name + OUTCOME_WORDS[order[0]]]
    pieces.extend(str(counts[outcome]) + ' ' + unit + OUTCOME_WORDS[outcome] for outcome in order[1:])
    return '，'.join(pieces)


def summarize(items, limit=SUMMARY_LIMIT):
    """同批事件合成一句话；带 text 的条目（预算等）原样并入，用「；」分隔。"""
    groups = []
    raw = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        if item.get('text'):
            raw.append(str(item['text']))
            continue
        stage = item.get('stage') or ''
        bucket = None
        for name, counts in groups:
            if name == stage:
                bucket = counts
                break
        if bucket is None:
            bucket = {}
            groups.append((stage, bucket))
        outcome = item.get('outcome') or 'success'
        bucket[outcome] = bucket.get(outcome, 0) + max(1, _int(item.get('count')) or 1)
    parts = list(raw)
    parts.extend(stage_sentence(stage, counts) for stage, counts in groups[:limit])
    return '；'.join([part for part in parts if part])


class Notifier:
    """先攒后说：同一批只发一条；免打扰期内只记账，出了窗口补一条汇总。"""

    def __init__(self, project=None, clock=time.time, window=DND, persist=True):
        self.project = Path(project) if project else None
        self.clock = clock
        self.window = tuple(window)
        self.persist = persist
        self.pending = []
        self.recorded = []
        self.sent = []
        self.last_step = False       # 上一批是不是「清一色的操作步骤」（第 24 期第 5 条）

    def add(self, stage=None, outcome='success', count=1, text=None, at=None, step=False):
        """攒一条待说的通知。step=True＝这是「正在做的那一步」（状态栏原文，见 pet_ui.Pet.say）：

        它照旧进台账与进度面板（日报也照旧算它），只是不再进三虎的云朵记录——用户第 24 期
        第 5 条要的是「云朵对话框只记录三虎的播报与和用户的聊天，不记用户的操作步骤」。
        """
        item = {'at': float(self.clock() if at is None else at), 'stage': stage,
                'outcome': outcome, 'count': max(1, _int(count) or 1)}
        if text:
            item['text'] = str(text)
        if step:
            item['step'] = True
        self.pending.append(item)
        return item

    def quiet(self, at=None):
        """是否在免打扰窗口内（北京时间 23:00-07:00）。"""
        return pet_llm.in_off_peak(at, self.window)

    def flush(self, at=None):
        """该说话时发一条聚合文本；窗口内只记账并返回 None。

        last_step 记下这一批是不是清一色的操作步骤（见 add 的 step 参数）：是的话，调用方
        （pet_ui.pump）只把它写进状态栏与进度面板，不往云朵记录里塞（第 24 期第 5 条）。
        """
        if not self.pending:
            self.last_step = False
            return None
        self.last_step = all(item.get('step') for item in self.pending)
        if self.quiet(at):
            self.recorded.extend(self.pending)
            self.pending = []
            return None
        text = summarize(self.pending)
        self.pending = []
        if text:
            self.sent.append({'at': float(self.clock() if at is None else at), 'text': text})
            del self.sent[:-KEEP]
        return text or None

    def catch_up(self, at=None):
        """免打扰结束后补一条汇总（窗口内不打扰，出了窗口一次说完）。"""
        if not self.recorded or self.quiet(at):
            return None
        items, self.recorded = self.recorded, []
        self.last_step = bool(items) and all(item.get('step') for item in items)
        text = '免打扰期间 ' + str(len(items)) + ' 条更新：' + summarize(items)
        self.sent.append({'at': float(self.clock() if at is None else at), 'text': text})
        del self.sent[:-KEEP]
        return text

    def snapshot(self):
        return {'updated_at': self.clock(), 'window': list(self.window),
                'pending': self.pending, 'recorded': self.recorded, 'sent': self.sent[-KEEP:]}

    def save(self):
        if not self.persist or self.project is None:
            return None
        path = self.project.joinpath(*NOTICE_PATH)
        save(path, self.snapshot())
        return path

    def load(self):
        if self.project is None:
            return self
        data = read_json(self.project.joinpath(*NOTICE_PATH))
        if not isinstance(data, dict):
            return self
        window = data.get('window')
        if isinstance(window, list) and len(window) == 2:
            self.window = tuple(window)
        for key in ('pending', 'recorded', 'sent'):
            value = data.get(key)
            if isinstance(value, list):
                setattr(self, key, [item for item in value if isinstance(item, dict)])
        return self


# ── 父编排门面 ──────────────────────────────────────────────────────────────
def config_file(program=None):
    return pet_llm.config_path(program)


def load_settings(program=None, config=None):
    """父 Agent 的配置：与 pet_llm 共用同一个配置文件，但只认自己的键，坏值一律退回默认。"""
    data = config if config is not None else read_json(config_file(program))
    data = data if isinstance(data, dict) else {}
    level = data.get('level')
    window = data.get('dnd')
    limits = data.get('budget_limits') if isinstance(data.get('budget_limits'), dict) else {}
    attempts = _int(data.get('max_attempts'))
    delays = data.get('retry_delays')
    return {'level': level if level in LEVELS else DEFAULT_LEVEL,
            'dnd': tuple(window) if isinstance(window, (list, tuple)) and len(window) == 2 else DND,
            'budget_limits': {kind: value for kind, value in limits.items() if _int(value) and _int(value) > 0},
            'max_attempts': attempts if attempts and attempts > 0 else MAX_ATTEMPTS,
            'retry_delays': tuple(delays) if isinstance(delays, (list, tuple)) and delays else pet_llm.RETRY_DELAYS,
            # 第 44 期「设置 → 基础功能」：贴片动画开关。缺省开着（老配置没这把键＝照旧动）。
            'anim': True if data.get('anim') is None else bool(data.get('anim')),
            # 第 66 期「设置 → Token 节省」：推理降档／压缩阈值／子 Agent 那几档，原样带回。
            'token': dict(data['token']) if isinstance(data.get('token'), dict) else {}}


# 「设置」三页写得进的那几把键：等级、免打扰窗口、五类配额、动画开关（重试次数与退避留作内部调优，
# 界面不摆——写了也认，但不写就不会被界面覆盖掉）。
# 第 66 期：「设置 → Token 节省」那八档也存在这儿（一把 'token' 键，值是一张表）。
SETTING_KEYS = ('level', 'dnd', 'budget_limits', 'anim', 'max_attempts', 'retry_delays', 'token')


# 各键的规整函数：返回要写入的值，或 _SKIP（这一把键本次不写）。没登记的键原样带过。
_SKIP = object()


def _keep(value):
    return value


def _normalize_dnd(value):
    window = tuple(value) if isinstance(value, (list, tuple)) else ()
    if len(window) != 2:
        return _SKIP
    return [int(window[0]), int(window[1])]


def _normalize_retry_delays(value):
    if isinstance(value, (list, tuple)) and value:
        return [int(item) for item in value]
    return _SKIP


def _normalize_budget_limits(value):
    limits = {}
    for kind, amount in dict(value or {}).items():
        try:
            name = normalize_kind(kind)
        except ValueError:
            continue
        number = _int(amount)
        if number and number > 0:
            limits[name] = number
    return limits


def _normalize_max_attempts(value):
    number = _int(value)
    return number if number and number > 0 else _SKIP


_SETTING_NORMALIZERS = {
    'dnd': _normalize_dnd,
    'retry_delays': _normalize_retry_delays,
    'budget_limits': _normalize_budget_limits,
    'anim': bool,
    'max_attempts': _normalize_max_attempts,
}


def save_settings(values, program=None):
    """把这几把键并进全局配置（原子写）；返回落盘路径。

    第 44 期：设置页（自动化等级／基础功能／预算）必须真的落盘——否则用户改完，下一次开机又退回
    出厂那一档，设置页就成了哑键。只认 SETTING_KEYS 里的键，别的键（模型池、密钥名那些）原样带过；
    写不动／盘上那份是坏 JSON 也不抛：坏值过滤掉重写一份，救得回来。
    """
    path = config_file(program)
    data = read_json(path)
    data = dict(data) if isinstance(data, dict) else {}
    for key, value in dict(values or {}).items():
        if key not in SETTING_KEYS or value is None:
            continue
        normalized = _SETTING_NORMALIZERS.get(key, _keep)(value)
        if normalized is not _SKIP:
            data[key] = normalized
    save(path, data)
    return path


def prompt_hash(text):
    return hashlib.sha256(strip_space(text).encode('utf-8')).hexdigest()[:16]


def idempotency_key(stage, shot=None, model=None, prompt=''):
    """幂等键 = stage|shot|model|提示词散列：同一批同一张只跑一次。"""
    return '|'.join([str(stage or ''), str(shot or ''), str(model or ''), prompt_hash(prompt)])


def journal_path(project):
    return Path(project).joinpath(*JOURNAL_PATH)


class Agent:
    """父编排 Agent：路由 → 审批 → 预算 → 重试 → 通知，界面线程可直接调用，全部不抛异常。"""

    def __init__(self, project=None, settings=None, level=None, client=None, bus=None,
                 machine=None, clock=time.time, program=None, persist=True):
        self.settings = load_settings(program=program, config=settings)
        self.level = level if level in LEVELS else self.settings['level']
        self.project = Path(project) if project else None
        self.clock = clock
        self.client = client
        self.bus = bus
        self.machine = machine
        if self.machine is None and self.project is not None:
            self.machine = pet_state.Machine(self.project, persist=persist)
        self.budget = Budget(self.settings['budget_limits'])
        self.notifier = Notifier(self.project, clock=clock, window=self.settings['dnd'], persist=persist)
        self.failures = []
        self.decisions = []
        self.errors = []
        self.seen = []
        self._known = set()
        self.paused = False
        self.paused_reason = ''
        # 第 37 期第 1 条：宿主（pet_ui）把「手上所有项目」的只读快照供在这里，见 projects_snapshot。
        self.projects = None
        # 第 63 期任务 3.3／4.2：全局并发控制器（全局 ≤8、单阶段按并行配置收口、同资源串行）。
        # 拿的是全进程唯一的那一个（stage_parallel.shared），SKILL 编排器那条并行路也问它，
        # 免得「各家各建一个、各自放宽 8 路」。
        self.governor = stage_parallel.shared()
        self.agent_logs = []

    # ── 接缝 ────────────────────────────────────────────────────────────────
    def attach(self, bus, machine=None):
        """接到总线上：聚合通知；阶段事件各自订阅（状态机自己管自己）。"""
        if bus is not None:
            self.bus = bus
        if machine is not None:
            self.machine = machine
        if self.bus is not None:
            self.bus.subscribe('*', self.notify)
        return self

    def _emit(self, kind, **payload):
        return emit_safe(self.bus, self.errors, kind, **payload)

    # ── 审批与暂停 ──────────────────────────────────────────────────────────
    def approve(self, action, level=None, paid=None, confirmed=False):
        """审批：按自动化等级决定跑、等确认还是只提示；暂停期间只放行查看类动作。

        第 31 期第 6 条：confirmed=True 表示这一下是用户自己在对话框里按的「确认」——
        那就是他本人的决定（只提醒档的说明写的就是「做不做都由你来按」），等级不再挡，
        付费步骤也不必再问第二次；暂停仍是他自己按下的闸，照旧拦住。
        """
        level = level if level in LEVELS else self.level
        is_paid = bool(paid) if paid is not None else action in PAID_ACTIONS
        base = {'level': level, 'paid': is_paid, 'confirm': False, 'paused': bool(self.paused)}
        if self.paused and action not in ('pause', 'resume', 'progress'):
            base.update(run=False, reason=self.paused_reason or '已暂停自动执行')
            return base
        if action in FREE_ACTIONS:
            # 第 23 期：看一眼的动作不问等级——挡在外面的只有会跑任务／会花钱的动作。
            base.update(run=True, reason='')
            return base
        if confirmed:
            base.update(run=True, confirm=False, reason='')
            return base
        if level == 'hint':
            base.update(run=False, reason='只提醒模式：不自动执行')
            return base
        if level == 'semi' and is_paid:
            base.update(run=False, confirm=True, reason='半自动：付费步骤需您点一下确认')
            return base
        base.update(run=True, reason='')
        return base

    def set_level(self, level):
        if level in LEVELS:
            self.level = level
        return self.level

    def pause(self, reason='', stage=None):
        self.paused = True
        self.paused_reason = str(reason or '已暂停')
        if stage:
            self._emit('stage.failed', stage=stage, error=self.paused_reason)
        return self.paused

    def resume(self):
        self.paused = False
        self.paused_reason = ''
        return self.paused

    # ── 并行编排（第 63 期任务 3.1／3.2／3.3） ──────────────────────────────
    def parallel_plan(self, stage):
        """这一步怎么起子 Agent：并行单元／并行度／批内串行／并发上限／重试。

        附件那份「各阶段并行配置速查表」的出处只有 stage_parallel 一处，这里只是转述，
        界面与任务书都拿这一份，不另写一套。
        """
        return dict(stage_parallel.config(stage))

    def retry_limit(self, stage):
        """这一步最多重试几次：用户设的上限与阶段配置取小（任务 2.1～2.11）。"""
        try:
            return max(0, min(int(self.settings['max_attempts']), stage_parallel.retry_attempts(stage)))
        except Exception as exc:
            self.errors.append(('retry_limit', str(exc)))
            return max(0, int(self.settings['max_attempts']))

    def acquire(self, stage, resource='', at=None):
        """向全局并发控制器要一个号：拿不到就带一句为什么，拿得到就带票据。"""
        try:
            return self.governor.acquire(stage, resource=resource, at=at)
        except Exception as exc:
            self.errors.append(('acquire', str(exc)))
            return {'ok': True, 'reason': '', 'ticket': None}

    def release(self, ticket):
        try:
            return self.governor.release(ticket)
        except Exception as exc:
            self.errors.append(('release', str(exc)))
            return False

    def release_stage(self, stage):
        """某一步收场：把它手上的号全还了——成败都要还，不然闸门会一直卡着。"""
        try:
            return self.governor.release_stage(stage)
        except Exception as exc:
            self.errors.append(('release_stage', str(exc)))
            return 0

    def parallel_snapshot(self):
        """面板要的并发现状（读不出来给一份空表，绝不影响进度显示）。"""
        try:
            return self.governor.snapshot()
        except Exception as exc:
            self.errors.append(('parallel', str(exc)))
            return {'limit': stage_parallel.GLOBAL_LIMIT, 'running': 0, 'slowed': 0,
                    'stages': {}, 'tickets': ()}

    def gate(self, stage, *, mode=None):
        """进入某一步之前要过的门禁（上游真的做了却没做全才挡，见 stage_parallel）。

        默认浏览口径（上游没开始＝放行），旧项目／补录因此打得开；无人值守的自动链在
        pet_ui.gate_reason 里显式传 stage_parallel.PRODUCTION，上游没开始就当前置条件缺失，
        除非用户把那一步标成「已跳过」（O24：两种语义分开）。
        """
        chosen = str(mode or stage_parallel.BROWSE)
        try:
            return stage_parallel.evaluate(self.project, stage, mode=chosen)
        except Exception as exc:
            self.errors.append(('gate', str(exc)))
            return {'id': '', 'from': '', 'to': str(stage or ''), 'title': '门禁', 'ok': True,
                    'started': False, 'verdict': stage_parallel.PASS, 'mode': chosen, 'exempt': False,
                    'missing': (), 'detail': '门禁暂时读不出来：%s' % exc, 'problems': (), 'artifacts': ()}

    def blocked_reason(self, stage, *, mode=None):
        """被门禁挡住就返回一句人话（缺什么、去哪儿补）；没挡住返回空串。"""
        return stage_parallel.blocked_text(self.gate(stage, mode=mode))

    def log_stage(self, stage, task, status, detail='', at=None):
        """按统一格式记一条到 <阶段目录>/logs/agent_logs.jsonl（写不进去也不报错）。"""
        row = stage_parallel.log_row(stage, task, status, detail, at)
        self.agent_logs.append(row)
        del self.agent_logs[:-KEEP]
        return stage_parallel.log_write(self.project, stage, task, status, detail, at)

    # ── 预算 ────────────────────────────────────────────────────────────────
    def spend(self, kind, amount=1, stage=None, at=None):
        """扣配额：临近上限先 budget.warning，越线即暂停并 budget.exceeded。"""
        name = normalize_kind(kind)
        if name == 'tokens':
            self.budget.sync_tokens(getattr(self.client, 'ledger', None), at)
        result = self.budget.spend(name, amount)
        label = BUDGET_NAMES.get(name, name)
        if result['warning']:
            self._emit('budget.warning', budget=name, used=result['used'], limit=result['limit'])
            self.notifier.add(text=label + '配额已用 ' + str(result['used']) + '/' + str(result['limit']))
        if not result['ok']:
            reason = label + '配额已用完（' + str(result['used']) + '/' + str(result['limit']) + '）：已暂停自动执行'
            self.pause(reason, stage=stage)
            self._emit('budget.exceeded', budget=name, used=result['used'], limit=result['limit'])
            self.notifier.add(text=reason)
        return result

    # ── 失败与重试 ──────────────────────────────────────────────────────────
    def fail(self, stage, error, status=None, attempt=0, params=None, at=None):
        """失败分支：可重试就发 stage.retrying（带退避），否则发 stage.failed 并进失败清单。

        第 63 期任务 2.1～2.11：重试上限按这一步的并行配置取小（首帧／预演／视频各 2 次）；
        用尽之后怎么办由该阶段的 on_exhaust 说了算——block 记「已中断」，manual 记「待您处理」。
        """
        policy = stage_parallel.on_exhaust(stage)
        plan = retry_plan(attempt, error, status=status, params=params,
                          max_attempts=self.retry_limit(stage), delays=self.settings['retry_delays'])
        if plan['allow']:
            self._emit('stage.retrying', stage=stage, attempt=plan['next_attempt'], delay=plan['delay'])
        else:
            self._emit('stage.failed', stage=stage, error=str(error or ''))
            item = {'at': float(self.clock() if at is None else at), 'stage': stage,
                    'category': plan['category'], 'action': plan['action'],
                    'error': str(error or ''), 'hint': plan['hint'],
                    'policy': policy, 'manual': policy == stage_parallel.ON_MANUAL}
            self.failures.append(item)
            del self.failures[:-KEEP]
            self.notifier.add(stage=stage, outcome='need_confirm', at=at)
        return plan

    def clear_failures(self):
        self.failures = []
        return self.failures

    def skip_failure(self, item=None):
        """「跳过这张」：把一条待确认从清单里摘掉——不再等它，也不动别的记录。

        用户显式跳过就是不再等这一条了；摘掉之后清单变化，气泡按新指纹重新计一次
        （同一批里剩下的失败仍然会被提醒）。清单为空时返回 None，调用方据此说明一句。
        """
        if not self.failures:
            return None
        target = item if item in self.failures else self.failures[0]
        self.failures = [entry for entry in self.failures if entry is not target]
        self._journal({'kind': 'skip', 'at': float(self.clock()),
                       'stage': (target or {}).get('stage'), 'category': (target or {}).get('category')})
        return target

    # ── 幂等提交 ────────────────────────────────────────────────────────────
    def submit(self, stage, shot=None, model=None, prompt='', at=None, params=None):
        """幂等提交：同一个 stage|shot|model|提示词 只受理一次，重复键直接跳过并记在案。"""
        key = idempotency_key(stage, shot, model, prompt)
        if key in self._known:
            return {'accepted': False, 'key': key, 'reason': '重复提交：同一批只跑一次'}
        self._remember(key)
        self._journal({'kind': 'submit', 'at': float(self.clock() if at is None else at), 'id': key,
                       'stage': stage, 'shot': shot, 'model': model, 'params': params or {}})
        return {'accepted': True, 'key': key, 'reason': ''}

    def _remember(self, key):
        self.seen.append(key)
        self._known.add(key)
        if len(self.seen) > SEEN_LIMIT:
            self._known.discard(self.seen.pop(0))

    def _journal(self, item):
        if self.project is None:
            return None
        try:
            path = journal_path(self.project)
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open('a', encoding='utf-8') as handle:
                handle.write(json.dumps(item, ensure_ascii=False, sort_keys=True) + '\n')
        except OSError as exc:
            self.errors.append(('journal', str(exc)))
            return None
        return path

    # ── 通知 ────────────────────────────────────────────────────────────────
    def notify(self, item, at=None):
        """只入队不发声：同批事件攒在一起，由 flush() 一次说完（免打扰期只记账）。"""
        kind = (item or {}).get('kind')
        if kind in ('budget.warning', 'budget.exceeded'):
            name = (item or {}).get('budget')
            label = BUDGET_NAMES.get(name, str(name or '配额'))
            text = label + '配额已用 ' + str(item.get('used')) + '/' + str(item.get('limit'))
            if kind == 'budget.exceeded':
                text += '：已暂停自动执行'
            return self.notifier.add(text=text, at=at)
        outcome = NOTIFY_MAP.get(kind)
        if outcome is None:
            return None
        stage = EVENT_STAGE.get(kind) or (item or {}).get('stage')
        return self.notifier.add(stage=stage, outcome=outcome, count=(item or {}).get('count') or 1, at=at)

    def note(self, stage, outcome='success', count=1, at=None):
        """适配层的细粒度上报（例如「3 张重试成功」），与总线事件一起聚合。"""
        return self.notifier.add(stage=stage, outcome=outcome, count=count, at=at)

    def flush(self, at=None):
        """把攒下的通知说出去（一条聚合事件），返回文本；免打扰期内返回 None。"""
        text = self.notifier.flush(at=at)
        if text:
            self._emit('notify.aggregate', text=text)
        return text

    def catch_up(self, at=None):
        """免打扰结束后的汇总：一次性补上夜间积压。"""
        text = self.notifier.catch_up(at=at)
        if text:
            self._emit('notify.aggregate', text=text)
        return text

    # ── 进度与自动推进 ──────────────────────────────────────────────────────
    def projects_snapshot(self):
        """宿主供上来的所有项目（第 37 期第 1 条）：没有就空表，读不出来也绝不影响说话。"""
        provider = self.projects
        if not callable(provider):
            return []
        try:
            return [str(row) for row in (provider() or [])][:PROJECT_LIMIT]
        except Exception as exc:
            self.errors.append(('projects', str(exc)))
            return []

    def context(self):
        """给模型的固定形状快照（键固定，前缀缓存才不会被打破）。

        第 37 期第 1 条：用户要「给三虎记住所有项目」——宿主把项目清单供进来时一并带上，
        模型答「有哪些项目／别的项目做到哪了」就有据可依；没有项目时这一项不出现，
        快照的形状照旧只由当前项目决定。
        """
        out = {}
        if self.machine is not None:
            state = self.machine.progress()
            out = {'project': self.project.name if self.project else '', 'stage': state['stage'] or '',
                   'percent': state['percent'], 'level': self.level,
                   'failed': [item['stage'] for item in self.failures]}
        projects = self.projects_snapshot()
        if projects:
            out['projects'] = projects
        pending = getattr(self, 'pending_offer', '')
        if pending:
            # 三虎刚问过用户一句、还挂着：模型抽意图时要知道用户是在回哪个问题
            out['pending_offer'] = str(pending)
        return out

    def progress(self, at=None):
        """全局进度：阶段机 + 台账，面板要的数字全来自文件与计数，不编。"""
        ledger = getattr(self.client, 'ledger', None)
        state = self.machine.progress() if self.machine is not None else {
            'percent': 0.0, 'stage': None, 'stage_name': '', 'detail': None, 'eta_seconds': None}
        state['summary'] = self.machine.summary() if self.machine is not None else '还没有打开项目'
        state['hit_rate'] = ledger.hit_rate() if ledger is not None else 0.0
        state['flash_share'] = ledger.flash_share() if ledger is not None else 0.0
        state['tokens_today'] = ledger.today_tokens(at) if ledger is not None else 0
        state['paused'] = bool(self.paused)
        state['level'] = self.level
        return state

    def advance(self, level=None):
        """自动推进判断：返回下一个可自动触发的阶段（等级不允许 / 已暂停 / 做完了都不给）。"""
        if self.machine is None or self.level == 'hint':
            return None
        stage = self.machine.current()
        if stage is None:
            return None
        return stage if self.approve('stage.run', level=level)['run'] else None

    def dispatch(self, text, at=None, confirmed=False):
        """输入框一句话 → 规则/模型意图 → 审批 → 可执行动作。

        第 23 期：这里只出结论，不碰界面也不跑任务（它可能在后台线程被调用）；真的动手由
        Pet.run_plan 在界面线程按 action 落地——「听懂了」与「真的做了」就此接上。
        第 31 期第 6 条：confirmed=True＝用户自己按的「确认」，等级不再挡（见 approve）。
        """
        plan = route(text, client=self.client, context=self.context())
        action = action_for(plan)
        decision = self.approve(action, confirmed=confirmed)
        self.decisions.append({'at': float(self.clock() if at is None else at), 'text': str(text),
                               'intent': plan['intent'], 'stage': plan['stage'], 'run': decision['run']})
        del self.decisions[:-KEEP]
        reply = plan.get('reply') or decision.get('reason') or ''
        # 第 23 期：只有真的被拦下才补一句理由——能做的事不再拖一条尾巴。
        if not decision['run'] and decision.get('reason'):
            reply = reply + '（' + decision['reason'] + '）' if plan.get('reply') else decision['reason']
        return {'plan': plan, 'decision': decision, 'reply': reply, 'action': action}

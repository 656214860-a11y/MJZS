"""Shared preflight budget for workflow-engine and model requests.

这里的字符上限是"能不能发"的最后一道硬保护；模型相关预估（分项 token、模型上下文
窗口、输出预留）在硬保护之内做可解释判断，两者都不截断正文或 SKILL。
"""
import hashlib

# R1434：用户要求提高上限（原 96,000）。四个总控阶段 SKILL 连同引用最大约 13.5 万字，
# 字符上限只是最后一道硬保护；按模型真实上下文窗口的 token 判断另算，超窗口照样阻断。
REQUEST_CONTEXT_MAX_CHARS = 300_000
# 用户指定的应用保守默认：模型未填 context_length 时按 ID 前缀兜底，而非按 provider。
# 这不是官方窗口或各版本真实保证；消费处须优先使用显式窗口，表外要求用户填写，不猜值。
PRESET_CONTEXT_BY_PREFIX = (
    ('deepseek', 128_000), ('gemini', 128_000), ('qwen', 32_000),
    ('claude', 200_000), ('gpt', 128_000),
)
DEFAULT_OUTPUT_RESERVE_TOKENS = 4_096

# 分项名称 → 展示用中文标签；错误信息、预览与历史记录都按这份口径命名。
SECTION_LABELS = {
    'system': '系统提示/规则',
    'skills': 'SKILL/阶段指令',
    'attachments': '附件/参考资料',
    'history': '历史对话',
    'stage': '阶段文档/任务说明',
    'tools': '工具声明',
}
USAGE_NOTE = '输入为本地估算；服务端实报用量见 request_usage。'
CHAR_NOTE = '字符上限是硬保护，token 预估按模型窗口另算。'


def preset_context_length(model_id):
    """返回用户指定的应用默认窗口；无预设返回 ''，显式窗口应由消费处优先采用。

    接受完整家族名、数字版本及常见分隔符后缀，不把 deepseeker 等相似词识别为该家族。
    """
    model = str(model_id or '').strip().casefold()
    for prefix, context_length in PRESET_CONTEXT_BY_PREFIX:
        if not model.startswith(prefix):
            continue
        suffix = model[len(prefix):]
        if not suffix or suffix[0] in '-_.:0123456789':
            return context_length
    return ''


def estimate_tokens(text):
    """保守 token 预估：ASCII 约 1/3 字符一个 token，非 ASCII 按 1 字符 2 token。

    中文、日文在真实分词里常接近 1 字符 1 token；这里高估一倍，宁可提前提示压缩，
    也不让推理字段挤占可见输出。
    """
    text = str(text or '')
    ascii_count = sum(ord(char) < 128 for char in text)
    return (ascii_count + 2) // 3 + (len(text) - ascii_count) * 2


def skill_inline_token_budget(context_limit):
    """递归内联 SKILL 引用的体积预算（估算 token）。

    预算＝窗口 − 输出预留 − 余量 − 任务/历史/固定规则份额。
    0 表示窗口未知，调用方必须自行决定拒绝或取预设，不得据此放行。
    只约束 depth=-1 的递归展开：SKILL 正文与直接引用照常加载，超预算的嵌套引用记 skipped。
    """
    limit = int(context_limit or 0)
    if limit <= 0:
        return 0
    reserved = max(DEFAULT_OUTPUT_RESERVE_TOKENS, int(limit * 0.06))
    fixed_share = max(DEFAULT_OUTPUT_RESERVE_TOKENS, int(limit * 0.16))
    return max(0, limit - reserved - default_safety_margin(limit) - fixed_share)


def text_fingerprint(text):
    """正文摘要：预览与实际发送用同一快照时摘要一致，便于核对。"""
    return hashlib.sha256(str(text or '').encode('utf-8')).hexdigest()[:16]


def compact_repeated_context(prompt):
    """Keep one authoritative copy of repeated large context sections.

    This is deliberately lossless for unique text: only an exact duplicate
    paragraph of at least 1,024 characters may be replaced, and its first
    occurrence remains in the request.
    """
    parts = prompt.split('\n\n')
    kept = []
    seen = set()
    removed = 0
    for part in parts:
        key = part.strip()
        if len(key) >= 1_024 and key in seen:
            removed += 1
            continue
        kept.append(part)
        if len(key) >= 1_024:
            seen.add(key)
    if not removed:
        return prompt
    kept.append(f'【上下文去重摘要：已合并 {removed} 段与前文完全相同的大段内容，首份完整内容保留。】')
    return '\n\n'.join(kept)


def budget_sections(**parts):
    """按固定分项名称收集非空正文；未知名称直接报错，避免随手添键。"""
    sections = {}
    for name, value in parts.items():
        if name not in SECTION_LABELS:
            raise ValueError('未知上下文分项：' + str(name))
        if value:
            sections[name] = value
    return sections


def default_safety_margin(context_limit, floor=512, ratio=0.05):
    """模型窗口越大绝对余量越大，但至少留 floor token 兜住保守预估误差。"""
    limit = int(context_limit or 0)
    if limit <= 0:
        return 0
    return max(int(floor), int(limit * float(ratio)))


def dominant_sections(tokens):
    """按占用从大到小排（只列有内容的），用于说明"主要占用"。"""
    rows = [{'name': name, 'label': SECTION_LABELS.get(name, name), 'tokens': int(value)}
            for name, value in tokens.items()]
    rows.sort(key=lambda row: (-row['tokens'], row['name']))
    return rows


def budget_split_options(tokens):
    """超限时给出可选的拆分方向，只提示不代替用户删内容。"""
    options = []
    for row in dominant_sections(tokens)[:3]:
        name = row['name']
        if name == 'history' and row['tokens']:
            options.append('历史对话可只保留最近若干轮或先做成摘要，原文仍留在本地。')
        elif name in ('attachments', 'skills') and row['tokens']:
            options.append(row['label'] + '可拆成多次请求或改成按需读取的引用清单。')
        elif row['tokens']:
            options.append(row['label'] + '可缩短或拆到下一阶段。')
    return options


def context_budget_report(sections=None, *, context_limit=None, output_reserved=0,
                          safety_margin=None, stage='当前阶段', prompt=None):
    """分项 token 预估 + 模型窗口判断，不修改任何正文。"""
    sections = dict(sections or {})
    tokens = {name: estimate_tokens(text) for name, text in sections.items()}
    input_tokens = sum(tokens.values())
    reserved = max(0, int(output_reserved or 0))
    limit = int(context_limit or 0)
    margin = (int(safety_margin) if safety_margin is not None
              else default_safety_margin(limit))
    projected = input_tokens + reserved + margin
    report = {
        'estimated': True,
        'stage': str(stage),
        'sections': tokens,
        'dominant': dominant_sections(tokens),
        'input_tokens': input_tokens,
        'output_reserved': reserved,
        'safety_margin': margin,
        'projected_tokens': projected,
        'context_limit': limit or None,
        'token_remaining': (limit - projected) if limit else None,
        'char_limit': REQUEST_CONTEXT_MAX_CHARS,
        'exceeded': bool(limit) and projected > limit,
        'split_options': budget_split_options(tokens),
        'usage_note': USAGE_NOTE,
        'char_note': CHAR_NOTE,
    }
    if prompt is not None:
        size = len(str(prompt))
        report['characters'] = size
        report['fingerprint'] = text_fingerprint(prompt)
        if size > REQUEST_CONTEXT_MAX_CHARS:
            report['exceeded'] = True
    return report


def budget_advice(report):
    """把主要占用与可选拆分拼成一句，供错误信息与预览复用。"""
    parts = []
    dominant = report.get('dominant') or []
    if dominant:
        parts.append('主要占用：' + '、'.join(
            '%s %s token' % (row['label'], format(row['tokens'], ',')) for row in dominant[:3]) + '。')
    options = report.get('split_options') or []
    if options:
        parts.append('可选择：' + ' '.join(options))
    return ''.join(parts)


def context_budget_error(stage, prompt, sections=None, *, context_limit=None,
                         output_reserved=0, safety_margin=None):
    """超限时给出可解释的错误文案；字符超限与模型窗口超限分开说明。"""
    size = len(str(prompt or ''))
    report = context_budget_report(sections if sections is not None else {'stage': prompt},
                                   context_limit=context_limit, output_reserved=output_reserved,
                                   safety_margin=safety_margin, stage=stage, prompt=prompt)
    if size > REQUEST_CONTEXT_MAX_CHARS:
        return (f'{stage}请求上下文超过 {REQUEST_CONTEXT_MAX_CHARS:,} 字符（当前 {size:,}），'
                '请缩短输入、拆分任务或先生成摘要后重试。' + budget_advice(report))
    limit = report.get('context_limit')
    return (f'{stage}请求估算 {report["projected_tokens"]:,} token'
            f'（输入 {report["input_tokens"]:,} + 输出预留 {report["output_reserved"]:,}'
            f' + 余量 {report["safety_margin"]:,}）超过模型上下文 {limit:,}；'
            '已阻止发送且未截断正文或 SKILL。' + budget_advice(report))


def prepare_request_context(prompt, stage='当前阶段', strategy='', *, sections=None,
                            context_limit=None, output_reserved=0, safety_margin=None,
                            report=False):
    """Compact, limit and expose request-size metadata without retaining text.

    先做无损去重，再按字符上限硬保护；给了分项、模型窗口或 report=True 时，附上分项
    token 预估与模型相关判断，超限直接抛错（不静默截断）。
    """
    if not isinstance(prompt, str):
        raise ValueError(str(stage) + '请求内容格式无效，请重新生成任务。')
    prompt = compact_repeated_context(prompt)
    size = len(prompt)
    if size > REQUEST_CONTEXT_MAX_CHARS:
        raise ValueError(context_budget_error(stage, prompt, sections, context_limit=context_limit,
                                              output_reserved=output_reserved, safety_margin=safety_margin))
    budget = {
        'stage': str(stage),
        'strategy': str(strategy or 'unspecified'),
        'characters': size,
        'limit': REQUEST_CONTEXT_MAX_CHARS,
        'remaining': REQUEST_CONTEXT_MAX_CHARS - size,
    }
    if report or sections is not None or context_limit or output_reserved:
        detail = context_budget_report(sections if sections is not None else {'stage': prompt},
                                       context_limit=context_limit, output_reserved=output_reserved,
                                       safety_margin=safety_margin, stage=stage, prompt=prompt)
        budget.update(detail)
        budget['limit'] = REQUEST_CONTEXT_MAX_CHARS
        budget['remaining'] = REQUEST_CONTEXT_MAX_CHARS - size
        if detail['exceeded'] and detail.get('context_limit'):
            raise ValueError(context_budget_error(stage, prompt, sections, context_limit=context_limit,
                                                  output_reserved=output_reserved, safety_margin=safety_margin))
    return prompt, budget


def ensure_request_context(prompt, stage='当前阶段', *, sections=None, context_limit=None,
                           output_reserved=0, safety_margin=None, report=False):
    """Compact repeated context, then reject an oversized engine request."""
    prompt, _budget = prepare_request_context(prompt, stage, sections=sections,
                                              context_limit=context_limit,
                                              output_reserved=output_reserved,
                                              safety_margin=safety_margin, report=report)
    return prompt

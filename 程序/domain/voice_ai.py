"""语音识别文本的 AI 优化：模板化后处理（语音输入离线化任务书轮 4）。

模板对齐 vocotype「AI 智能优化」：纠错（同音字/错别字/口语赘词与自我修正）、
润色（口语转写→通顺书面语）、翻译、自定义提示词。``optimize_text`` 不直接发
请求——``chat`` 由调用方注入（通常是 ``writing_api.WritingRequestAdapter.chat``，
自带模型池路由、RPM 与计量），本模块只负责拼消息、调 chat、清洗结果。

L2 纪律：不 import ``writing_api``（L3），不碰 Tk、不碰网络。
"""

TEMPLATES = ('fix', 'polish', 'translate', 'custom')

_TEMPLATE_SYSTEM = {
    'fix': ('你是语音识别文本校对助手。输入是语音识别的原始文本，可能有同音字、'
            '错别字、口语赘词和自我修正（如“不对”“改成”“我是说”）。'
            '只输出修正后的文本本身：不解释、不加 Markdown、不加引号、不加前缀。'),
    'polish': ('你是文字润色助手。把口语化的语音转写整理成通顺的书面语，'
               '保留原意、关键信息与专有名词，不添加原文没有的内容。'
               '只输出润色后的文本本身。'),
    'translate': ('你是翻译助手。把以下语音识别文本翻译成英文，保留专有名词与数字，'
                  '只输出译文本身。'),
}

_MAX_RESULT_CHARS = 20000


def _template_system(config):
    template = str((config or {}).get('template') or 'fix').strip()
    if template == 'custom':
        prompt = str((config or {}).get('prompt') or '').strip()
        if not prompt:
            return '', '自定义提示词为空，请在「语音识别…」里填写或换其它模板'
        return prompt + '\n只输出处理后的文本本身，不要解释。', ''
    if template not in _TEMPLATE_SYSTEM:
        return '', 'AI 优化模板不认识：%s' % template
    return _TEMPLATE_SYSTEM[template], ''


def build_request(text, config=None):
    """拼 (messages, options, system)；模板/提示词不合法时返回 (None, None, None, 原因)。"""
    system, problem = _template_system(config)
    if problem:
        return None, None, None, problem
    messages = [{'role': 'user', 'content': str(text or '')}]
    return messages, {'max_tokens': 2048}, system, ''


def clean_result(text):
    """清洗模型返回：去首尾空白；整体被 ``` 围栏包住时拆掉。"""
    result = str(text or '').strip()
    if result.startswith('```') and result.endswith('```') and len(result) > 6:
        inner = result.split('\n', 1)
        if len(inner) == 2:
            result = inner[1].rsplit('```', 1)[0].strip()
    return result


def optimize_text(text, *, chat, model='', config=None):
    """对识别文本做一次模板化优化。

    ``chat`` 是注入的模型调用，签名与 ``WritingRequestAdapter.chat`` 一致：
    ``chat(messages, options=..., model=..., system=...)`` 返回 ``{'ok','text',...}``。
    返回 ``{'ok': bool, 'text': str, 'reason': str}``；任何失败都给中文原因、不抛错
    （未配模型由调用方在进入本函数前提示，本函数只管模板与结果）。
    """
    source = str(text or '').strip()
    if not source:
        return {'ok': False, 'text': '', 'reason': '没有可优化的文本'}
    messages, options, system, problem = build_request(source, config)
    if problem:
        return {'ok': False, 'text': source, 'reason': problem}
    try:
        result = chat(messages, options=options, model=model, system=system)
    except Exception as exc:  # noqa: BLE001 —— 模型调用失败不阻断听写结果
        return {'ok': False, 'text': source,
                'reason': 'AI 优化调用失败（%s）' % str(exc)[:120]}
    if not isinstance(result, dict):
        return {'ok': False, 'text': source, 'reason': 'AI 优化返回格式不正确'}
    if not result.get('ok'):
        detail = str(result.get('reason') or result.get('error') or '模型未返回结果')
        return {'ok': False, 'text': source, 'reason': 'AI 优化未完成：%s' % detail[:160]}
    cleaned = clean_result(result.get('text'))
    if not cleaned:
        return {'ok': False, 'text': source, 'reason': 'AI 优化返回为空，已保留原文'}
    if len(cleaned) > _MAX_RESULT_CHARS:
        return {'ok': False, 'text': source, 'reason': 'AI 优化结果过长，已保留原文'}
    return {'ok': True, 'text': cleaned, 'reason': ''}

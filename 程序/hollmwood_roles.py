# -*- coding: utf-8 -*-
"""HOLLMWOOD 四角色剧本协作（Round 4）。

本模块不选择模型、不读取密钥、不接触 Tk，也不落盘剧本；调用方必须把已经由
``model_router.PoolAdapter`` 配置好的适配器传入。它仅串行运行导演、编剧、编辑、演员，
并把每步模型输出写至 ``logs/hollmwood_step_N.log``。Round 6 的 ``writing_api`` 会在导演
最终通过后负责唯一允许的业务写入：``writing/script_raw.md``。
"""
from hollmwood_rules import (DIRECTOR_PLAN_RULES, WRITER_RULES, EDITOR_RULES, ACTOR_RULES, DIRECTOR_REVIEW_RULES)
from pathlib import Path
import json
import time
import logging
from functools import wraps

from model_router import ModelAdapter
from script_contract import RHYTHM_TEMPLATE_PATH
from service_contract import SystemError, success


ROLE_ORDER = ('director', 'writer', 'editor', 'actor')
MAX_REVISIONS = 1
DIRECTOR_RETRY_MAX_TOKENS = 8192
CONTENT_ROLE_MAX_TOKENS = 8192
# 这是请求正文的保守字符上限，而不是模型宣称的上下文窗口。中文通常接近一字一
# token，预留给 8192 输出 token 与协议开销；超过此值必须在调用前明确提示，不能
# 静默截断剧本后继续创作。
REQUEST_CONTEXT_MAX_CHARS = 96_000


class RoleExecutionError(RuntimeError):
    """某角色没有可用输出，或导演在允许次数内没有放行。"""


class RoleCancelledError(RoleExecutionError):
    """用户取消后在下一次安全边界停止，不再进入后续角色或落盘。"""


def _hollmwood_result(operation):
    """仅将日志发布等真实环境故障映射为可展示的服务结果。"""
    @wraps(operation)
    def run(*args, **kwargs):
        try:
            return success(operation(*args, **kwargs))
        except OSError as exc:
            logging.getLogger(__name__).exception('HOLLMWOOD 协作日志保存失败')
            return SystemError('HOLLMWOOD 日志未能保存，请检查磁盘或文件占用后重试。',
                               data={'cause': str(exc), 'operation': operation.__name__})
    return run


def _ensure_active(cancelled):
    if callable(cancelled) and cancelled():
        raise RoleCancelledError('HOLLMWOOD 调用已取消')


def _ensure_context_budget(role, system, prompt, log_folder, step, *, publish_log=None):
    """在模型调用前拒绝过长上下文，避免推理字段耗尽可见输出。"""
    size = len(str(system or '')) + len(str(prompt or ''))
    if size <= REQUEST_CONTEXT_MAX_CHARS:
        return
    error = ('上下文过长：%s 角色请求为 %d 字符，超过 %d 字符安全预算；'
             '请缩短简报、节奏模板或编剧角色 SKILL 指令后重试。' %
             (role, size, REQUEST_CONTEXT_MAX_CHARS))
    _write_log(log_folder, step, str(role) + '_context_rejected', error, publish=publish_log)
    raise RoleExecutionError('%s 角色执行失败：%s' % (role, error))


def load_rhythm_template(program=None):
    """读取项目内置节奏模板正文，供导演作为审核尺度使用。"""
    root = Path(program or Path(__file__).resolve().parent)
    path = root / RHYTHM_TEMPLATE_PATH
    return path.read_text(encoding='utf-8-sig')


def _body(value):
    """将已完成的简报或模板保留为可安全拼接的文本。"""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        import json
        return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)
    raise TypeError('brief_complete 和 rhythm_template 必须是 dict 或字符串')


def _write_log(folder, step, role, text, *, publish=None):
    """每次角色输出单独留痕，便于定位未通过的导演审核。"""
    directory = Path(folder)
    path = directory / ('hollmwood_step_%d.log' % int(step))
    if not callable(publish):
        raise TypeError('HOLLMWOOD 日志发布需要 L3 注入发布器')
    publish(path, '[%s]\n%s\n' % (role, text))
    return path


def _record_diagnostic(folder, result, role, step, *, elapsed_ms=None, request_chars=None):
    """诊断落盘失败不能掩盖原始模型结果或改变阶段状态。"""
    try:
        from model_diagnostics import record
        context = {'role': role, 'step': step, 'stage': 'script'}
        if elapsed_ms is not None:
            context['elapsed_ms'] = round(float(elapsed_ms), 3)
        if request_chars is not None:
            context['request_chars'] = int(request_chars)
        return record(folder, result, context)
    except (OSError, TypeError, ValueError):
        return None


def _empty_output_detail(result, retried=False):
    """只描述协议结构，不记录正文或推理内容，便于定位空审核回复。"""
    meta = dict((result or {}).get('response_meta') or {})
    data = (result or {}).get('data') if isinstance((result or {}).get('data'), dict) else {}
    if not meta:
        choices = data.get('choices') if isinstance(data.get('choices'), list) else []
        choice = choices[0] if choices and isinstance(choices[0], dict) else {}
        message = choice.get('message') if isinstance(choice.get('message'), dict) else {}
        meta = {'finish_reason': str(choice.get('finish_reason') or ''),
                'response_shape': sorted(str(key) for key in data.keys()),
                'message_fields': sorted(str(key) for key in message.keys()),
                'reasoning_fields': [key for key in ('reasoning_content', 'reasoning', 'analysis')
                                     if message.get(key) not in (None, '', [], {})],
                'reasoning_lengths': {key: len(str(message.get(key) or ''))
                                      for key in ('reasoning_content', 'reasoning', 'analysis')
                                      if message.get(key) not in (None, '', [], {})}}
    meta['retried_once'] = bool(retried)
    return meta


def _ask(adapter, model, role, system, prompt, log_folder, step, emit, cancelled=None, stream=None,
         *, publish_log=None):
    """通过既有 ModelAdapter 执行一次角色请求，并写出该步的结果日志。"""
    if not isinstance(adapter, ModelAdapter):
        raise TypeError('HOLLMWOOD 必须接收 model_router 的 ModelAdapter')
    _ensure_active(cancelled)
    _ensure_context_budget(role, system, prompt, log_folder, step, publish_log=publish_log)
    if emit:
        emit(role, step)
    # 首个导演规划和导演审核只要返回空正文才补发一次；网络/协议错误不重试，避免放大失败或费用。
    audit = str(role).startswith('director_review')
    empty_retry = audit or str(role) == 'director'
    result = None
    text = ''
    retried = False
    for attempt in range(2 if empty_retry else 1):
        retrying = bool(attempt and empty_retry)
        # DeepSeek Flash 的空回复常是推理字段占满输出额度、没有 content。第二次请求必须
        # 改变指令和额度；原样重发同一请求只会稳定复现同一个空结果。
        request_prompt = prompt
        request_system = system
        # Writer、Editor、Actor 都要输出完整剧本；4096 容易在推理型模型中被
        # reasoning 消耗完，导致没有可显示正文。修订角色沿用同一额度。
        max_tokens = (CONTENT_ROLE_MAX_TOKENS
                      if role in ('writer', 'editor', 'actor',
                                  'writer_revision', 'editor_revision', 'actor_revision')
                      else 4096)
        if retrying:
            request_prompt += ('\n\n上一次没有返回可见正文。请现在直接输出完整、可执行的导演节奏计划；'
                               '不要只输出推理字段、分析过程或空内容。')
            request_system += '\n\n本次必须在可见 content 中输出最终导演计划，禁止仅返回思考过程。'
            max_tokens = DIRECTOR_RETRY_MAX_TOKENS
        request_started = time.perf_counter()
        on_chunk = stream if role in ('actor', 'actor_revision') and callable(stream) else None
        result = (adapter.stream([{'role': 'user', 'content': request_prompt}], options={'max_tokens': max_tokens},
                                 model=model, system=request_system, on_chunk=on_chunk, cancelled=cancelled)
                  if on_chunk else adapter.chat([{'role': 'user', 'content': request_prompt}],
                                                 options={'max_tokens': max_tokens}, model=model, system=request_system))
        _record_diagnostic(
            log_folder, result, role, step,
            elapsed_ms=(time.perf_counter() - request_started) * 1000,
            request_chars=len(request_system) + len(request_prompt),
        )
        _ensure_active(cancelled)
        text = str((result or {}).get('text') or '').strip()
        if text or not (result or {}).get('ok'):
            break
        if attempt == 0:
            retried = True
            _write_log(log_folder, step, role + '_empty_retry',
                       json.dumps(_empty_output_detail(result, retried=True), ensure_ascii=False, sort_keys=True),
                       publish=publish_log)
    if not (result or {}).get('ok') or not text:
        if empty_retry and (result or {}).get('ok') and not text:
            detail = _empty_output_detail(result, retried=retried)
            finish = detail.get('finish_reason') or '未提供'
            reasoning = '；检测到推理字段：' + '、'.join(detail.get('reasoning_fields') or []) if detail.get('reasoning_fields') else ''
            body = '审核正文' if audit else '导演正文'
            error = ('模型未生成' + body + '（已受控重试 1 次；finish_reason=' + str(finish) + reasoning
                     + '）；响应诊断=' + json.dumps(detail, ensure_ascii=False, sort_keys=True))
        else:
            error = str((result or {}).get('error') or '模型未返回可显示正文')
        _write_log(log_folder, step, role + '_failed', error, publish=publish_log)
        raise RoleExecutionError('%s 角色执行失败：%s' % (role, error))
    _write_log(log_folder, step, role, text, publish=publish_log)
    return text


def _approved(review):
    """导演门禁只接受明确的 APPROVED 放行标记，避免模糊好评误放行。"""
    return str(review or '').strip().upper().startswith('APPROVED')


def _director_plan_system():
    return DIRECTOR_PLAN_RULES


def _writer_system():
    return WRITER_RULES


def _editor_system():
    return EDITOR_RULES


def _actor_system():
    return ACTOR_RULES


def _director_review_system():
    return DIRECTOR_REVIEW_RULES


def default_director_rules():
    """阶段配置弹窗可编辑的导演规则默认正文。"""
    return _director_plan_system() + '\n\n审核规则：\n' + _director_review_system()


def default_role_rules(role):
    """阶段配置弹窗的各角色内置规则。"""
    defaults = {'director': default_director_rules(), 'writer': _writer_system(),
                'editor': _editor_system(), 'actor': _actor_system()}
    return defaults.get(str(role), '')


def _revision(adapter, model, role, system, original, review, log_folder, step, emit, cancelled=None,
              *, publish_log=None):
    prompt = ('请根据导演退回意见重写完整剧本。\n\n<director_review>\n%s\n</director_review>'
              '\n\n<previous_script>\n%s\n</previous_script>' % (review, original))
    return _ask(adapter, model, role + '_revision', system, prompt, log_folder, step, emit, cancelled,
                publish_log=publish_log)


def _run(adapter, model, brief_complete, rhythm_template=None, log_folder='logs',
        max_revisions=MAX_REVISIONS, emit=None, skill_instructions='', cancelled=None,
        director_rules=None, role_rules=None, stream=None, *, publish_log=None):
    """串行运行导演、编剧、编辑、演员并执行三次导演门禁。

    返回包含 ``script``、``director_plan`` 与各角色最终正文的字典。最终正文仍只在内存；
    由 Round 6 的受控 API 层在本函数成功返回后写入 ``writing/script_raw.md``。
    """
    brief = _body(brief_complete)
    rhythm = _body(rhythm_template) if rhythm_template is not None else load_rhythm_template()
    director = _body(director_rules) if director_rules is not None else ''
    role_rules = role_rules if isinstance(role_rules, dict) else {}
    if not brief:
        raise ValueError('brief_complete 不能为空')
    if int(max_revisions) < 0:
        raise ValueError('max_revisions 不能小于 0')
    rhythm_constraints = '\n\n全局节奏模板（每个角色都必须遵守）：\n' + rhythm
    skill_constraints = ('\n\n本次编剧角色 SKILL 指令：\n' + str(skill_instructions).strip()
                         if str(skill_instructions).strip() else '')
    director_constraints = ('\n\n本项目导演角色规则（优先遵守）：\n' + director) if director else ''
    def role_constraints(role):
        value = _body(role_rules.get(role)) if role_rules.get(role) is not None else ''
        return ('\n\n本项目%s角色规则（优先遵守）：\n%s' % (role, value)) if value else ''
    director_system = _director_plan_system() + director_constraints + rhythm_constraints
    writer_system = _writer_system() + role_constraints('writer') + rhythm_constraints + skill_constraints
    editor_system = _editor_system() + role_constraints('editor') + rhythm_constraints
    actor_system = _actor_system() + role_constraints('actor') + rhythm_constraints
    review_system = _director_review_system() + director_constraints + rhythm_constraints
    step = 1
    plan = _ask(adapter, model, 'director', director_system,
                '<brief_complete>\n%s\n</brief_complete>' % brief,
                log_folder, step, emit, cancelled, publish_log=publish_log)
    step += 1
    writer = _ask(adapter, model, 'writer', writer_system,
                  '<director_instruction>\n%s\n</director_instruction>\n\n<brief_complete>\n%s\n</brief_complete>'
                  % (plan, brief), log_folder, step, emit, cancelled, publish_log=publish_log)

    stages = (('writer', writer, writer_system),
              ('editor', None, editor_system),
              ('actor', None, actor_system))
    outputs = {'director_plan': plan, 'writer': writer}
    current = writer
    for role, first, system in stages:
        if role != 'writer':
            step += 1
            current = _ask(adapter, model, role, system,
                           '<director_instruction>\n%s\n</director_instruction>\n\n<current_script>\n%s\n</current_script>'
                           % (plan, current), log_folder, step, emit, cancelled, stream,
                           publish_log=publish_log)
        attempts = 0
        while True:
            step += 1
            review = _ask(adapter, model, 'director_review_' + role, review_system,
                          ('请审核 %s 的候选剧本。\n\n<candidate>\n%s\n</candidate>' %
                           (role, current)),
                          log_folder, step, emit, cancelled, publish_log=publish_log)
            if _approved(review):
                outputs[role] = current
                break
            if attempts >= int(max_revisions):
                raise RoleExecutionError('导演未通过 %s：%s' % (role, review))
            attempts += 1
            step += 1
            current = _revision(adapter, model, role, system, current, review, log_folder, step, emit, cancelled,
                                publish_log=publish_log)
    outputs['script'] = outputs['actor']
    return outputs


@_hollmwood_result
def run(adapter, model, brief_complete, rhythm_template=None, log_folder='logs',
        max_revisions=MAX_REVISIONS, emit=None, skill_instructions='', cancelled=None,
        director_rules=None, role_rules=None, stream=None, *, publish_log=None):
    return _run(adapter, model, brief_complete, rhythm_template, log_folder, max_revisions,
                emit, skill_instructions, cancelled, director_rules, role_rules, stream,
                publish_log=publish_log)

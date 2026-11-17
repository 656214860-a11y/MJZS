# -*- coding: utf-8 -*-
"""消息 part 的分派渲染器（L4，唯一入口）。

借鉴 Open WebUI 的 ContentRenderer 与 AI Elements 的 ``Message.Part`` 分派：一条消息 =
有序 typed parts（``domain.message_parts``），不同 part 类型走不同渲染函数。非 TEXT 的
part 渲染进现有 Text 气泡：

- ``REASONING``：可折叠「思考过程」标题 + 正文（点标题切换，正文按需插入/删除）；
- ``ARTIFACT``：产物行「标题 · kind」，点行回调 ``host.open_artifact``；
- ``TOOL_CALL`` / ``TOOL_RESULT``：工具状态行（名称 · 状态 · 耗时）；
- ``SOURCE`` / ``FILE``：引用/附件行；
- ``DATA``：兜底一行提示。

只消费 ``ui_tokens`` 的颜色与间距；动作经 ``host`` 回调注入（不 import Desktop）。
"""
from __future__ import annotations

import tkinter as tk

from domain import message_parts
from ui_tokens import COLORS, SPACING

PART_FONT = ('Microsoft YaHei UI', 10)
PART_SMALL_FONT = ('Microsoft YaHei UI', 9)


def _prefix(name):
    return name + '_part'


def _insert(box, text, tag, **options):
    try:
        box.tag_configure(tag, **options)
    except tk.TclError:
        pass
    box.insert('end', text, tag)
    return tag


def _invoke(host, method, *args):
    """调用 host 上的可选回调；缺失或不可调用时静默跳过。"""
    callback = getattr(host, method, None)
    if callable(callback):
        try:
            return callback(*args)
        except Exception:
            return None
    return None


def render_text(box, name, part, host):
    """TEXT part 默认由气泡正文负责；独立渲染时补一段（供非气泡场景复用）。"""
    text = str((part.get('payload') or {}).get('text') or '')
    if not text:
        return False
    _insert(box, text + '\n', _prefix(name) + '_text',
            foreground=COLORS['text_primary'], font=PART_FONT, wrap='word')
    return True


def _reason_state(box):
    state = getattr(box, '_part_render_state', None)
    if state is None:
        state = {}
        box._part_render_state = state
    return state


def render_reasoning(box, name, part, host):
    """折叠思考卡：先只放标题，点开后插入正文；再点收起删除正文。"""
    text = message_parts.reasoning_of([part])
    if not text:
        return False
    prefix = _prefix(name)
    box.insert('end', '▸ 思考过程 · %d 字\n' % len(text), prefix + '_reason_title')
    box.tag_configure(prefix + '_reason_title', foreground=COLORS['text_secondary'],
                      font=PART_SMALL_FONT, spacing1=SPACING['xs'])
    mark = prefix + '_reason_body'
    box.mark_set(mark, 'end-1c')
    box.mark_gravity(mark, 'left')
    _reason_state(box)[name] = {'text': text, 'expanded': False, 'mark': mark}
    box.tag_bind(prefix + '_reason_title', '<Button-1>',
                 lambda event, b=box, n=name: toggle_reasoning(b, n))
    box.tag_bind(prefix + '_reason_title', '<Enter>', lambda event, b=box: b.configure(cursor='hand2'))
    box.tag_bind(prefix + '_reason_title', '<Leave>', lambda event, b=box: b.configure(cursor='xterm'))
    return True


def toggle_reasoning(box, name):
    """展开/收起思考正文；返回新的展开状态（找不到该卡返回 None）。"""
    state = _reason_state(box).get(name)
    if not state:
        return None
    mark = state['mark']
    if state['expanded']:
        box.delete(mark, '%s + %dc' % (mark, len(state['text'])))
        state['expanded'] = False
    else:
        prefix = _prefix(name)
        box.insert(mark, state['text'] + '\n', prefix + '_reason_body')
        box.tag_configure(prefix + '_reason_body', foreground=COLORS['text_secondary'],
                          font=PART_SMALL_FONT, wrap='word')
        state['expanded'] = True
    return state['expanded']


def render_artifact(box, name, part, host):
    artifact = message_parts.artifact_from_part(part)
    if artifact is None:
        return False
    label = artifact.title or artifact.identifier or '未命名产物'
    tag = _prefix(name) + '_artifact'
    box.insert('end', '📄 %s · %s  [打开]\n' % (label, artifact.kind), tag)
    box.tag_configure(tag, foreground=COLORS['text_primary'], font=PART_FONT, wrap='word')
    box.tag_bind(tag, '<Button-1>', lambda event, a=artifact: _invoke(host, 'open_artifact', a))
    box.tag_bind(tag, '<Enter>', lambda event, b=box: b.configure(cursor='hand2'))
    box.tag_bind(tag, '<Leave>', lambda event, b=box: b.configure(cursor='xterm'))
    return True


def render_tool_call(box, name, part, host):
    payload = part.get('payload') or {}
    tool = str(payload.get('name') or payload.get('tool') or '工具')
    state = str(part.get('state') or 'done')
    elapsed = payload.get('elapsed')
    line = '🔧 %s · %s' % (tool, state)
    if isinstance(elapsed, (int, float)):
        line += ' · %.1fs' % float(elapsed)
    _insert(box, line + '\n', _prefix(name) + '_tool_call',
            foreground=COLORS['text_secondary'], font=PART_SMALL_FONT, wrap='word')
    return True


def render_tool_result(box, name, part, host):
    payload = part.get('payload') or {}
    body = str(payload.get('text') or payload.get('result') or '')
    shown = body[:120] + ('…' if len(body) > 120 else '') if body else '（空）'
    _insert(box, '↳ 结果：' + shown + '\n', _prefix(name) + '_tool_result',
            foreground=COLORS['text_secondary'], font=PART_SMALL_FONT, wrap='word')
    return True


def render_source(box, name, part, host):
    payload = part.get('payload') or {}
    label = str(payload.get('title') or payload.get('label') or '引用')
    index = payload.get('index')
    marker = '[%s] ' % index if index is not None else ''
    _insert(box, marker + label + '\n', _prefix(name) + '_source',
            foreground=COLORS['text_secondary'], font=PART_SMALL_FONT, wrap='word')
    return True


def render_file(box, name, part, host):
    payload = part.get('payload') or {}
    label = str(payload.get('name') or payload.get('path') or '附件')
    _insert(box, '📎 ' + label + '\n', _prefix(name) + '_file',
            foreground=COLORS['text_secondary'], font=PART_SMALL_FONT, wrap='word')
    return True


def render_data(box, name, part, host):
    _insert(box, '（扩展数据）\n', _prefix(name) + '_data',
            foreground=COLORS['text_muted'], font=PART_SMALL_FONT)
    return True


PART_RENDERERS = {
    message_parts.PartType.TEXT.value: render_text,
    message_parts.PartType.REASONING.value: render_reasoning,
    message_parts.PartType.ARTIFACT.value: render_artifact,
    message_parts.PartType.TOOL_CALL.value: render_tool_call,
    message_parts.PartType.TOOL_RESULT.value: render_tool_result,
    message_parts.PartType.SOURCE.value: render_source,
    message_parts.PartType.FILE.value: render_file,
    message_parts.PartType.DATA.value: render_data,
}


def registered_types():
    return tuple(PART_RENDERERS)


def render_parts(box, name, parts, host, *, skip_text=False):
    """按 part 顺序分派渲染；返回实际渲染的 part 数。未知类型与非法项跳过。"""
    rendered = 0
    for part in parts or ():
        if not isinstance(part, dict):
            continue
        kind = str(part.get('type') or '')
        if skip_text and kind == message_parts.PartType.TEXT.value:
            continue
        renderer = PART_RENDERERS.get(kind)
        if renderer is None:
            continue
        if renderer(box, name, part, host):
            rendered += 1
    return rendered

# -*- coding: utf-8 -*-
"""引用溯源（L4）：把正文里的 ``[n]`` 标记着色并绑定点击定位。

引用上下文走独立字段（source part / ``markers``），不原地改历史消息；点击经
``on_open(index)`` 回调交给调用方定位原剧本或原设定。
"""
from __future__ import annotations

import re

from ui_tokens import COLORS

_CITE = re.compile(r'\[(\d+)\]')


def insert_citations(box, name, text, *, on_open=None, markers=None):
    """把 ``[n]`` 插进 Text 并绑定点击；返回标记数量。``markers`` 供回调定位。"""
    value = str(text or '')
    markers = dict(markers or {})
    count = 0
    last = 0
    for match in _CITE.finditer(value):
        if match.start() > last:
            box.insert('end', value[last:match.start()])
        index = int(match.group(1))
        tag = '%s_cite_%d' % (name, index)
        box.insert('end', match.group(0), tag)
        box.tag_configure(tag, foreground=COLORS['primary'], underline=True)
        box.tag_bind(tag, '<Button-1>',
                     lambda event, i=index: on_open(i) if on_open is not None else None)
        box.tag_bind(tag, '<Enter>', lambda event, b=box: b.configure(cursor='hand2'))
        box.tag_bind(tag, '<Leave>', lambda event, b=box: b.configure(cursor='xterm'))
        count += 1
        last = match.end()
    if last < len(value):
        box.insert('end', value[last:])
    return count


def citations_of(sources):
    """把 source part 列表转成 ``{序号: source}``；缺 ``index`` 时按位置补。"""
    rows = {}
    for position, item in enumerate(sources or ()):
        if not isinstance(item, dict):
            continue
        try:
            index = int(item.get('index', position + 1))
        except (TypeError, ValueError):
            index = position + 1
        rows[index] = dict(item)
    return rows

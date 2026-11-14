# -*- coding: utf-8 -*-
"""自然剧本的字段表格闸门（L0）。

从 `script_contract` 拆出：REQ-S01-16 规定自然剧本每集正文前必带「本集节拍表」，
而节拍表本身是一张 Markdown 管道表格，不能被 `natural_script_violations` 的
「字段表格」拦截误伤。这里只按六列表头识别节拍表并整块豁免，其余任何
``| … |`` 表格（分镜表／镜头表等结构化阶段产物）仍判「字段表格」。
"""
import re

# REQ-S01-16 规定的「本集节拍表」表头固定为
# 场次／节拍＃／情绪关键词／服务的剧本动作／权重／强度六列。
_BEAT_TABLE_HEADER = re.compile(
    r'^\s*\|?\s*场次\s*\|[^|]*节拍[^|]*\|[^|]*情绪关键词[^|]*\|'
    r'[^|]*服务的剧本动作[^|]*\|[^|]*权重[^|]*\|[^|]*强度\s*\|?\s*$')


def has_foreign_field_table(value):
    """是否存在「本集节拍表」以外的字段表格。

    节拍表整块（表头＋分隔行＋数据行，直到空行或非 ``|`` 起始行）豁免；
    其余任何 ``| … |`` 表格行仍算结构化阶段产物。
    """
    lines = value.splitlines()
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        if _BEAT_TABLE_HEADER.match(line):
            i += 1
            while i < n and re.match(r'^\s*\|', lines[i]):
                i += 1
            continue
        if re.match(r'^\s*\|.+\|\s*$', line):
            return True
        i += 1
    return False

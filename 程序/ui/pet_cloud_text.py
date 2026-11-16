# -*- coding: utf-8 -*-
"""三虎云朵框的无界面文本整理。"""
import re


_BLANK = re.compile(r'[ \t\r\f\v]+')


def tight(text):
    """压缩行内空白、去除空行，同时保留正文中的换行与不换行空格。"""
    rows = []
    for row in str(text or '').split('\n'):
        row = _BLANK.sub(' ', row).strip(' \t\r\f\v')
        if row:
            rows.append(row)
    return '\n'.join(rows)


REPLY_MAX_CHARS = 80   # 云朵里一条回答最多这么长；整段原文仍在 result 里，详情看进度面板
REPLY_MORE = '…（详情见进度面板）'


def clip_reply(text):
    """太长的回答收成一眼读得完的一句。"""
    return text if len(text) <= REPLY_MAX_CHARS else text[:REPLY_MAX_CHARS - len(REPLY_MORE)] + REPLY_MORE


def reply_lines(result, speaker, confirm_prefix):
    """把 Agent 的结构化回复转换为云朵框可直接显示的文案。"""
    result = result if isinstance(result, dict) else {}
    decision = result.get('decision') if isinstance(result.get('decision'), dict) else {}
    reply = clip_reply(' '.join(str(result.get('reply') or '').split()))
    lines = [speaker + '：' + (reply or '这句话我还没听懂，可以换个说法，或直接按右键菜单里的项。')]
    if not decision.get('run'):
        reason = ' '.join(str(decision.get('reason') or '').split())
        if reason:
            lines.append(speaker + '：' + confirm_prefix + reason)
    return lines

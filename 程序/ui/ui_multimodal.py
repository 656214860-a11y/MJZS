# -*- coding: utf-8 -*-
"""多模态参考上传（L4）：图片（垫图）/音频（参考音色）→ FILE part。

只做类型判定与 FILE part 构造（无 Tk、无网络、不读写盘）；拖拽/粘贴后由 L4 调用
本模块把路径转成 part，再交给对话状态机。
"""
from __future__ import annotations

from domain import message_parts

ALLOWED_KINDS = {
    'image': ('.png', '.jpg', '.jpeg', '.webp', '.gif', '.bmp'),
    'audio': ('.mp3', '.wav', '.m4a', '.flac', '.ogg'),
}


def classify(path):
    """按扩展名判定参考类型：image/audio；不支持返回空串。"""
    value = str(path or '').lower()
    suffix = '.' + value.rsplit('.', 1)[-1] if '.' in value else ''
    for kind, suffixes in ALLOWED_KINDS.items():
        if suffix in suffixes:
            return kind
    return ''


def reference_part(path, *, kind=''):
    """把参考文件变成 FILE part；不支持的扩展名返回 None。"""
    value = str(path or '')
    resolved = str(kind or classify(value))
    if not value or not resolved:
        return None
    return message_parts.part(message_parts.PartType.FILE,
                              {'name': value.replace('\\', '/').rsplit('/', 1)[-1],
                               'path': value, 'kind': resolved})


def attach_references(paths, *, kind=''):
    """批量转 FILE part；返回 ``(parts, rejected)``。"""
    parts, rejected = [], []
    for path in paths or ():
        part = reference_part(path, kind=kind)
        if part is None:
            rejected.append(str(path))
        else:
            parts.append(part)
    return parts, rejected

# -*- coding: utf-8 -*-
"""图片/分镜缩略图卡 + Lightbox + 多候选对比 + 收藏（L4）。

只消费 ``ui_tokens``；缩略图经 ``asset_thumbs`` 专用缓存，弹窗经 ``BaseDialog``；
收藏/打开经回调注入（真实入库走 `asset_batch` / 回收语义由调用方负责）。
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

import asset_thumbs
from ui_tokens import COLORS, SPACING
from ui_widgets import BaseDialog, PrimaryButton, SecondaryButton


def _photo(master, path):
    """经资产缩略图缓存取图；后台未就绪/格式不支持时返回 None（退回占位文字）。"""
    return asset_thumbs.thumbnail(master, path)


def open_lightbox(parent, path):
    """轻量 Lightbox：``BaseDialog`` 置顶窗口 + 缩略图或占位文字。返回窗口。"""
    window = BaseDialog(parent, '预览', modal=False)
    photo = _photo(window.content, path)
    if photo is not None:
        label = tk.Label(window.content, image=photo)
        label.image = photo
    else:
        label = tk.Label(window.content, text='无法预览：%s' % path)
    label.pack(padx=SPACING['md'], pady=SPACING['md'])
    SecondaryButton(window.content, text='关闭', command=window.close).pack(pady=SPACING['xs'])
    return window


def build_thumbnail_card(parent, paths, *, title='', on_favorite=None, on_open=None):
    """缩略图卡：候选一排 + 上一张/下一张/收藏入库/放大预览。返回 Frame。"""
    items = [str(path) for path in (paths or ())]
    frame = ttk.Frame(parent)
    frame.pack(fill='x', padx=SPACING['sm'], pady=SPACING['xs'])
    if title:
        ttk.Label(frame, text=str(title), foreground=COLORS['text_primary']).pack(anchor='w')
    state = {'index': 0}
    preview = ttk.Label(frame, text='', foreground=COLORS['text_secondary'])
    preview.pack(anchor='w', pady=SPACING['xs'])

    def select(index):
        if not items:
            return
        state['index'] = index % len(items)
        preview.configure(text='候选 %d/%d：%s' % (state['index'] + 1, len(items),
                                                  items[state['index']]))
        if on_open is not None:
            on_open(items[state['index']])

    strip = ttk.Frame(frame)
    strip.pack(anchor='w')
    for index, _path in enumerate(items):
        SecondaryButton(strip, text=str(index + 1), width=0,
                        command=lambda i=index: select(i)).pack(side='left', padx=SPACING['xs'])
    if items:
        select(0)

    actions = ttk.Frame(frame)
    actions.pack(anchor='w', pady=SPACING['xs'])
    if items:
        SecondaryButton(actions, text='上一张',
                        command=lambda: select(state['index'] - 1)).pack(
            side='left', padx=SPACING['xs'])
        SecondaryButton(actions, text='下一张',
                        command=lambda: select(state['index'] + 1)).pack(
            side='left', padx=SPACING['xs'])
        if on_favorite is not None:
            PrimaryButton(actions, text='收藏入库',
                          command=lambda: on_favorite(items[state['index']])).pack(
                side='left', padx=SPACING['xs'])
        SecondaryButton(actions, text='放大预览',
                        command=lambda: open_lightbox(frame, items[state['index']])).pack(
            side='left', padx=SPACING['xs'])
    return frame


def draw_media_placeholder(image, kind, width, height):
    """把播放或波形标记画在缩略图缓存分配的画布上。"""
    image.put(COLORS['surface_pressed'], to=(0, 0, width, height))
    border = COLORS['border_default']
    image.put(border, to=(0, 0, width, 1))
    image.put(border, to=(0, height - 1, width, height))
    image.put(border, to=(0, 0, 1, height))
    image.put(border, to=(width - 1, 0, width, height))
    ink = COLORS['text_muted']
    if kind == 'audio':
        _draw_bars(image, width, height, ink)
    else:
        _draw_play(image, width, height, ink)


def _draw_play(image, width, height, color):
    """居中右向三角：上尖下尖、左底右顶点。"""
    reach = max(2, min(width, height) // 3)
    cx, cy = width // 2 - reach // 3, height // 2
    for dy in range(-reach, reach + 1):
        half = (reach - abs(dy)) // 2
        y = cy + dy
        x0, x1 = max(0, cx), min(width, cx + half + 1)
        if 0 <= y < height and x0 < x1:
            image.put(color, to=(x0, y, x1, y + 1))


def _draw_bars(image, width, height, color):
    """居中几根高低不一的竖条，示意音频波形。"""
    bar = max(1, width // 18)
    for index, frac in enumerate((0.45, 0.85, 0.6, 0.95, 0.35)):
        x0 = width // 5 + index * max(2, width // 8)
        bh = max(1, int(height * frac))
        image.put(color, to=(x0, (height - bh) // 2, x0 + bar, (height - bh) // 2 + bh))

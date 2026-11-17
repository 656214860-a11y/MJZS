# -*- coding: utf-8 -*-
"""视频/音频卡片（L4）：封面 + 外部播放器 + 确认采用/重新生成 + 导出 SRT + 静态波形。

播放/导出/确认经回调注入（播放默认走调用方的 ``platform_tools.open_target``）。
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

import asset_thumbs
from ui_tokens import COLORS, SPACING
from ui_widgets import PrimaryButton, SecondaryButton

WAVEFORM_WIDTH = 220
WAVEFORM_HEIGHT = 48
DEFAULT_WAVEFORM = (0.2, 0.6, 0.9, 0.4, 0.7, 0.3, 0.8, 0.5, 0.2, 0.6)


def _waveform(canvas, values, width=WAVEFORM_WIDTH, height=WAVEFORM_HEIGHT):
    """静态波形近似：把 0..1 的采样画成竖条（不做真实音频解码）。"""
    bars = max(1, len(values) or 1)
    step = max(1, width // bars)
    middle = height // 2
    for index, value in enumerate(values):
        x = index * step + step // 2
        amplitude = int(max(0.0, min(1.0, float(value))) * (height - 4) / 2)
        canvas.create_line(x, middle - amplitude, x, middle + amplitude,
                           fill=COLORS['primary'], width=max(1, step - 2))
    return canvas


def build_audio_card(parent, path, *, title='配音', hooks=None, waveform=DEFAULT_WAVEFORM):
    """音频卡：标题 + 静态波形 + 试听 + 确认采用/重新生成 + 导出 SRT。返回 Frame。"""
    hooks = dict(hooks or {})
    on_play = hooks.get('play')
    on_confirm = hooks.get('confirm')
    on_regenerate = hooks.get('regenerate')
    on_export = hooks.get('export')
    frame = ttk.Frame(parent)
    frame.pack(fill='x', padx=SPACING['sm'], pady=SPACING['xs'])
    ttk.Label(frame, text=str(title), foreground=COLORS['text_primary']).pack(anchor='w')
    canvas = tk.Canvas(frame, width=WAVEFORM_WIDTH, height=WAVEFORM_HEIGHT,
                       highlightthickness=0, bg=COLORS['background_card'])
    canvas.pack(anchor='w', pady=SPACING['xs'])
    _waveform(canvas, waveform)
    row = ttk.Frame(frame)
    row.pack(anchor='w', pady=SPACING['xs'])
    SecondaryButton(row, text='试听',
                    command=lambda: on_play(path) if on_play is not None else None).pack(
        side='left', padx=SPACING['xs'])
    if on_export is not None:
        SecondaryButton(row, text='导出 SRT', command=lambda: on_export(path)).pack(
            side='left', padx=SPACING['xs'])
    if on_confirm is not None:
        PrimaryButton(row, text='确认采用', command=lambda: on_confirm(path)).pack(
            side='left', padx=SPACING['xs'])
    if on_regenerate is not None:
        SecondaryButton(row, text='重新生成', command=lambda: on_regenerate(path)).pack(
            side='left', padx=SPACING['xs'])
    return frame


def build_video_card(parent, path, *, title='视频片段', cover='', on_play=None,
                     on_confirm=None, on_regenerate=None):
    """视频卡：封面（asset_thumbs）+ 播放（外部播放器）+ 确认采用/重新生成。返回 Frame。"""
    frame = ttk.Frame(parent)
    frame.pack(fill='x', padx=SPACING['sm'], pady=SPACING['xs'])
    ttk.Label(frame, text=str(title), foreground=COLORS['text_primary']).pack(anchor='w')
    photo = asset_thumbs.thumbnail(frame, cover or path)
    if photo is not None:
        label = ttk.Label(frame, image=photo)
        label.image = photo
    else:
        label = ttk.Label(frame, text='🎬 视频封面')
    label.pack(anchor='w', pady=SPACING['xs'])
    row = ttk.Frame(frame)
    row.pack(anchor='w', pady=SPACING['xs'])
    SecondaryButton(row, text='播放',
                    command=lambda: on_play(path) if on_play is not None else None).pack(
        side='left', padx=SPACING['xs'])
    if on_confirm is not None:
        PrimaryButton(row, text='确认采用', command=lambda: on_confirm(path)).pack(
            side='left', padx=SPACING['xs'])
    if on_regenerate is not None:
        SecondaryButton(row, text='重新生成', command=lambda: on_regenerate(path)).pack(
            side='left', padx=SPACING['xs'])
    return frame

"""视频和音频缩略图共用的占位图绘制。"""
import tkinter as tk

from ui_tokens import COLORS


def draw_media_placeholder(master, kind, width, height):
    image = tk.PhotoImage(master=master, width=width, height=height)
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
    return image


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

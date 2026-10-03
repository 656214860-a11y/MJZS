"""L4 UI 图标入口：集中管理 Tk 图像的构建、缩放规格与按宿主缓存。"""
from __future__ import annotations

import tkinter as tk


class IconLoader:
    """页面图标的唯一构建入口。

    图像必须由对应 Tk 宿主持有；缓存也挂在宿主上，避免跨 Tk 根复用失效图像。
    新图标以稳定名称加入本类，页面不能再直接创建 ``PhotoImage``。
    """

    _CACHE_ATTR = "_ui_icon_cache"

    @classmethod
    def _cache(cls, master):
        cache = getattr(master, cls._CACHE_ATTR, None)
        if cache is None:
            cache = {}
            setattr(master, cls._CACHE_ATTR, cache)
        return cache

    @classmethod
    def return_arrow(cls, master, *, width: int = 48, height: int = 32):
        """返回生成方式的箭头；尺寸是唯一缩放规格，结果按宿主和尺寸缓存。"""
        key = ("return_arrow", int(width), int(height))
        cache = cls._cache(master)
        if key in cache:
            return cache[key]
        image = tk.PhotoImage(master=master, width=key[1], height=key[2])
        # 中心 36×28 箭头按目标尺寸等比定位，不依赖符号字体的字形差异。
        scale_x = key[1] / 48
        scale_y = key[2] / 32
        for y in range(round(2 * scale_y), round(30 * scale_y)):
            x = round((6 + abs(15.5 - y / scale_y)) * scale_x)
            image.put("#ffffff", to=(x, y, x + max(1, round(6 * scale_x)), y + 1))
        image.put("#ffffff", to=(round(9 * scale_x), round(13 * scale_y),
                                 round(42 * scale_x), round(19 * scale_y)))
        cache[key] = image
        return image

    @classmethod
    def check_indicator(cls, master, *, size: int, selected: bool = False,
                        disabled: bool = False, accent: str = '#2b78c5'):
        """返回统一复选框图元，按宿主、状态与尺寸缓存。"""
        size = max(1, int(size))
        key = ('check_indicator', size, bool(selected), bool(disabled), accent)
        cache = cls._cache(master)
        if key in cache:
            return cache[key]
        image = tk.PhotoImage(master=master, width=size, height=size)
        border = '#aab6c6' if disabled else accent
        image.put(border, to=(0, 0, size, size))
        image.put('#edf1f5' if disabled else '#ffffff', to=(1, 1, size - 1, size - 1))
        if selected:
            points = [(round(size * .20), round(size * .51)),
                      (round(size * .42), round(size * .73)),
                      (round(size * .80), round(size * .25))]
            for (x0, y0), (x1, y1) in zip(points, points[1:]):
                steps = max(abs(x1 - x0), abs(y1 - y0), 1)
                for index in range(steps + 1):
                    x = round(x0 + (x1 - x0) * index / steps)
                    y = round(y0 + (y1 - y0) * index / steps)
                    image.put(border, to=(max(1, x - 1), max(1, y - 1),
                                          min(size - 1, x + 1), min(size - 1, y + 1)))
        cache[key] = image
        return image

"""L4 UI 图标入口：集中管理 Tk 图像的构建、缩放规格与按宿主缓存。"""
from __future__ import annotations

import tkinter as tk
from pathlib import Path

from ui_tokens import COLORS

_NAV_DIR = Path(__file__).resolve().parents[1] / 'assets' / 'nav'
_NAV_IMAGES = []   # (PhotoImage, 源 PNG 路径, 目标尺寸或 None)：切换主题时就地重染色


_STAGE_BADGE_BOX = (16, 16, 28, 28)   # 与 scripts/build_nav_icons.STAGE_FILE_BADGE_POS/SIZE 一致


def _hex_rgb(color):
    value = str(color).lstrip('#')
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


def _is_stage_file_icon(path):
    stem = Path(path).stem
    return stem.endswith('_files') and stem != 'project_files'


def _tint_stage_file_image(image, size=None):
    """阶段文件复合图标分三层重染色：阶段主字形走正文色、描边走背景色、右下角文件夹走柔和灰色。"""
    from PIL import Image
    src = image.convert('RGBA')
    ink = _hex_rgb(COLORS['text_primary'])
    ring = _hex_rgb(COLORS['background_primary'])
    folder = _hex_rgb(COLORS['text_secondary'])
    highlight = _hex_rgb(COLORS['background_card'])
    bx0, by0, bx1, by1 = _STAGE_BADGE_BOX
    out = Image.new('RGBA', src.size, (0, 0, 0, 0))
    px_in = src.load()
    px_out = out.load()
    w, h = src.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = px_in[x, y]
            if a == 0:
                continue
            if bx0 <= x < bx1 and by0 <= y < by1:
                # 角标区内：高亮度像素（>=240）为外圈描边或折痕，其余为灰色文件夹主体。
                if r >= 250 and g >= 250 and b >= 250:
                    px_out[x, y] = (*highlight, a)
                elif r >= 235 and g >= 235 and b >= 235:
                    px_out[x, y] = (*ring, a)
                else:
                    px_out[x, y] = (*folder, a)
            else:
                px_out[x, y] = (*ink, a)
    if size is not None:
        target = (max(1, int(size)), max(1, int(size)))
        if out.size != target:
            resample = getattr(getattr(Image, 'Resampling', Image), 'LANCZOS', Image.BICUBIC)
            out = out.resize(target, resample)
    return out


def _tinted_png(path, color, size=None):
    """把单色 PNG 图标染成 color 并保留透明度；复合阶段文件图标保留灰色文件夹角标与描边。"""
    try:
        import base64
        import io
        from PIL import Image
        image = Image.open(path).convert('RGBA')
        if _is_stage_file_icon(path):
            tinted = _tint_stage_file_image(image, size=size)
        else:
            alpha = image.getchannel('A')
            if size is not None:
                target = (max(1, int(size)), max(1, int(size)))
                if alpha.size != target:
                    resample = getattr(getattr(Image, 'Resampling', Image), 'LANCZOS', Image.BICUBIC)
                    alpha = alpha.resize(target, resample)
            tinted = Image.new('RGBA', alpha.size, color)
            tinted.putalpha(alpha)
        buffer = io.BytesIO()
        tinted.save(buffer, format='PNG')
        return base64.b64encode(buffer.getvalue())
    except Exception:
        return None


def _nav_image(master, path, size=None):
    data = _tinted_png(path, COLORS['text_primary'], size=size) if size is not None else _tinted_png(path, COLORS['text_primary'])
    if data is not None:
        try:
            return tk.PhotoImage(master=master, data=data)
        except tk.TclError:
            pass
    return tk.PhotoImage(master=master, file=str(path))


def retint_nav_icons():
    """主题切换后把已建的侧栏图标就地换成新主题的文字色；使用这些图的按钮无需重建。"""
    for entry in list(_NAV_IMAGES):
        image, path, size = entry if len(entry) == 3 else (entry[0], entry[1], None)
        data = _tinted_png(path, COLORS['text_primary'], size=size) if size is not None else _tinted_png(path, COLORS['text_primary'])
        if data is None:
            continue
        try:
            image.configure(data=data)
        except (tk.TclError, AttributeError):
            _NAV_IMAGES.remove(entry)


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
    def return_arrow(cls, master, *, width: int = 48, height: int = 32,
                     color: str = COLORS["background_card"]):
        """返回箭头按宿主、尺寸和颜色缓存；默认白色兼容既有深色按钮。"""
        key = ("return_arrow", int(width), int(height), color)
        cache = cls._cache(master)
        if key in cache:
            return cache[key]
        image = tk.PhotoImage(master=master, width=key[1], height=key[2])
        # 中心 36×28 箭头按目标尺寸等比定位，不依赖符号字体的字形差异。
        scale_x = key[1] / 48
        scale_y = key[2] / 32
        for y in range(round(2 * scale_y), round(30 * scale_y)):
            x = round((6 + abs(15.5 - y / scale_y)) * scale_x)
            image.put(color, to=(x, y, x + max(1, round(6 * scale_x)), y + 1))
        image.put(color, to=(round(9 * scale_x), round(13 * scale_y),
                                 round(42 * scale_x), round(19 * scale_y)))
        cache[key] = image
        return image

    @classmethod
    def nav_icon(cls, master, name, *, size=None):
        """返回 ``assets/nav/<name>.png`` 侧栏图标，按宿主、名称与目标尺寸缓存；缺资源时返回 None。

        PNG 由 ``scripts/build_nav_icons.py`` 用 Fluent System Icons（Filled，MIT）
        开发期栅格化，运行时不依赖字体或第三方库；页面只按语义名取图。
        """
        if not name:
            return None
        path = _NAV_DIR / f'{name}.png'
        if not path.is_file():
            return None
        target = max(1, int(size)) if size is not None else None
        key = ('nav_icon', str(path)) if target is None else ('nav_icon', str(path), target)
        cache = cls._cache(master)
        if key in cache:
            return cache[key]
        try:
            image = _nav_image(master, path, size=target)
        except tk.TclError:
            return None
        _NAV_IMAGES.append((image, path, target))
        cache[key] = image
        return image

    @classmethod
    def check_indicator(cls, master, *, size: int, selected: bool = False,
                        disabled: bool = False, accent: str | None = None):
        """返回统一复选框图元，按宿主、状态、尺寸与主题底色缓存。"""
        size = max(1, int(size))
        if accent is None:
            accent = COLORS['primary']
        fill = COLORS['surface_hover'] if disabled else COLORS['background_card']
        border = COLORS['border_input_hover'] if disabled else accent
        key = ('check_indicator', size, bool(selected), bool(disabled), border, fill)
        cache = cls._cache(master)
        if key in cache:
            return cache[key]
        image = tk.PhotoImage(master=master, width=size, height=size)
        image.put(border, to=(0, 0, size, size))
        image.put(fill, to=(1, 1, size - 1, size - 1))
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

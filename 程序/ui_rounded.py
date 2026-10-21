"""圆角控件底图：标准库生成带 alpha 通道的圆角 PNG，再做成 ``tk.PhotoImage``（无 PIL）。

只负责「画图＋按 (颜色, 半径, 尺寸) 缓存」；哪个控件用哪张图、样式布局都在
``ui_widgets.setup_styles()`` 定义。图对象缓存在 Tk 根窗口上，保持永久引用（图元持有的
图一旦被回收就再也画不出来，同 ``ui_theme.install_tick_indicators`` 的教训）。

底图的中心区域不能小：ttk 的 image 元素对 ``border`` 切出的中心区是按**平铺**重绘的，
中心只有 2×2 像素时，一个 500 像素宽的卡片每次重绘要铺几万次，实测整页慢 20 倍。
因此调用方传入的尺寸必须带一块足够大的中心区（见 ``ui_tokens.ROUND_TILE_*``）；
生成时按行结构复用字节，大图也只花微秒级。
"""
import tkinter as tk


def _png_chunk(tag, data):
    import struct
    import zlib
    return (struct.pack(">I", len(data)) + tag + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))


def _hex_rgb(color):
    return tuple(int(color[i:i + 2], 16) for i in (1, 3, 5))


def rounded_png_bytes(fill, radius, width, height, border=None, border_width=0):
    # 标准库 struct+zlib+base64 生成带 alpha 的圆角矩形 PNG（尺寸已按 DPI 取整），不依赖 PIL。
    import base64
    import struct
    import zlib
    fill_rgb = _hex_rgb(fill)
    edge_rgb = fill_rgb if border is None else _hex_rgb(border)

    def pixel(x, y):
        px, py = x + 0.5, y + 0.5
        cx = min(max(px, radius), width - radius)
        cy = min(max(py, radius), height - radius)
        dist = ((px - cx) ** 2 + (py - cy) ** 2) ** 0.5 - radius
        if dist <= -border_width:
            return bytes(fill_rgb) + b"\xff"
        if dist <= 0:
            return bytes(edge_rgb) + b"\xff"
        if dist < 1:
            return bytes(edge_rgb) + bytes((int(255 * (1 - dist)),))
        return b"\x00\x00\x00\x00"

    def row(y):
        # 只有左右各 radius 列随 x 变化，中间整段同色：算一次再按列数复制字节。
        side = min(radius, width // 2)
        left = b"".join(pixel(x, y) for x in range(side))
        right = b"".join(pixel(x, y) for x in range(width - side, width))
        return b"\x00" + left + pixel(side, y) * (width - 2 * side) + right

    scan = bytearray()
    middle = None
    for y in range(height):
        if radius <= y < height - radius:
            if middle is None:
                middle = row(y)  # 上下圆角带之外的行彼此相同
            scan += middle
        else:
            scan += row(y)
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    raw = (b"\x89PNG\r\n\x1a\n" + _png_chunk(b"IHDR", ihdr)
           + _png_chunk(b"IDAT", zlib.compress(bytes(scan)))
           + _png_chunk(b"IEND", b""))
    return base64.encodebytes(raw).decode("ascii")


def rounded_photo(root, fill, radius, width, height, border=None, border_width=0):
    factor = float(root.tk.call("tk", "scaling")) / (96.0 / 72.0)
    pr = max(1, round(radius * factor))
    w = max(2 * pr + 2, round(width * factor))
    h = max(2 * pr + 2, round(height * factor))
    cache = getattr(root, "_drama_rounded_cache", None)
    if cache is None:
        cache = root._drama_rounded_cache = {}
    key = (fill, radius, w, h, border, border_width)
    image = cache.get(key)
    if image is None:
        image = cache[key] = tk.PhotoImage(
            master=root, format="png",
            data=rounded_png_bytes(fill, pr, w, h, border=border, border_width=border_width))
    return image, pr


def empty_icon_photo(root, size, background, foreground, line, radius):
    """空态图标：圆角底上叠三道文字线（长、长、短），缩放与缓存规则同 ``rounded_photo``。"""
    base, pr = rounded_photo(root, background, radius, size, size)
    cache = root._drama_rounded_cache
    side = base.width()
    thick = max(1, round(line * pr / radius))
    key = ("empty-icon", background, foreground, thick, side)
    image = cache.get(key)
    if image is None:
        image = cache[key] = base.copy()  # 在副本上画线，缓存里的纯底图不被污染
        left = side // 4
        for index, length in enumerate((side // 2, side // 2, side // 4)):
            top = side // 3 + index * thick * 3
            image.put(foreground, to=(left, top, left + length, top + thick))
    return image

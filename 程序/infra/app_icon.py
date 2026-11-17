# -*- coding: utf-8 -*-
"""第 30 期：助手软件安装后的图标（三虎的**符号化头像**）。

- 不引第三方库、不读位图文件：图标按一套固定的色板**算**出来，再写成 Windows 的 .ico。
- 画法：先在放大 4 倍的大图上落笔（圆、多边形、贝塞尔折线全是纯算术），再按 4×4 取平均缩回
  目标尺寸——小图标才不会一口锯齿。
- 第 49 期第 2 条（用户要「重新设计桌面图标：清晰轮廓、鲜艳色彩、潮流元素、极简符号」）
  整张图重画了一版：**方块画布**（桌面图标本来就是方块，原来那张 8:5 的宽图放上桌面会被缩成
  小小一条）＋ 平涂的虎皮橙 ＋ 一笔到底的粗墨轮廓 ＋ 七笔五官（三道额纹、两只菱形眼、一枚
  鼻、一张嘴）＋ 右上角一颗青色的 ✦（与界面上那句「✦ 把灵感变成故事」是同一颗）。
  上一版的冷蓝配色、冰白高光、胡须、钟形脸全部作废：极简符号要的是「一眼认出、缩到 16 像素
  也不糊」，笔画越多越糊。
- 第 26 期第 9 条：装完还要刷新 Windows 的图标缓存（见 app_shortcut.refresh_shell），
  不然资源管理器拿旧缓存画桌面，看着就像「导入失败」。
- 用处：主窗口标题栏／任务栏图标（apply）、桌面快捷方式的图标（ensure 出来的 .ico 文件）。
- 用户要求（2026-11-02）：assets/app_icon.ico 与根目录 漫剧制作助手.ico 换成三虎头像
  sanhu_chibi_avatar.png 缩成的多尺寸 ICO（成品入库）；--force 会改回算出来的简笔图，别随手跑。
运行：python app_icon.py --force 会把 ico 与一张 png 预览重写进程序目录下的 assets。
"""
import infra.app_logging as app_logging
import hashlib
import os
import math
import struct
import zlib
from pathlib import Path

from agent.core import save_bytes

PROGRAM = Path(__file__).resolve().parents[1]
ASSETS = PROGRAM / 'assets'
ICON_NAME = 'app_icon.ico'
PREVIEW_NAME = 'app_icon_preview.png'
ASPECT = 1.0                        # 画布的长宽比（第 49 期第 2 条：桌面图标改成正方形）
SIZES = ((16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256))
SS = 4                              # 超采样倍数
# 第 49 期第 2 条：一套平涂的鲜艳色板（对比拉满、颜色数量压到最少＝「极简符号」）。
FUR = (255, 138, 61, 255)           # 虎皮橙：脸与耳朵的主色（整张图最醒目的一块）
EAR_IN = (255, 146, 146, 255)       # 耳朵内侧：一抹暖粉，缩到 16 像素也知道那是耳朵
MUZZLE = (255, 242, 217, 255)       # 口鼻那块奶白：给鼻子与嘴垫一块亮底（带一点暖黄，不是灰白）
INK = (26, 28, 42, 255)             # 轮廓与五官：深墨（不是纯黑，缩到任务栏那么小也不糊）
ACCENT = (34, 211, 238, 255)        # 潮流点缀：右上角那颗 ✦（与界面上那句「✦ 把灵感变成故事」同色）
CLEAR = (0, 0, 0, 0)                # 透明
# 描边加粗一档（16 像素高时约 0.9 像素，256 像素时约 14 像素）——极简的造型靠这条粗轮廓立住，
# 缩到任务栏那么小也不散。
EDGE_W = 0.055                      # 描边宽度（身高单位）

def line(img, x0, y0, x1, y1, color, width=1.0):
    """在大图上画一条线（按点到线段的距离判断，超采样之后边缘自然就平了）。"""
    dx, dy = x1 - x0, y1 - y0
    span = dx * dx + dy * dy
    half = max(0.5, width / 2.0)
    xs = range(max(0, int(min(x0, x1) - half - 1)), min(len(img[0]), int(max(x0, x1) + half + 2)))
    ys = range(max(0, int(min(y0, y1) - half - 1)), min(len(img), int(max(y0, y1) + half + 2)))
    for y in ys:
        for x in xs:
            if span <= 0:
                far = ((x - x0) ** 2 + (y - y0) ** 2) ** 0.5
            else:
                along = max(0.0, min(1.0, ((x - x0) * dx + (y - y0) * dy) / span))
                far = ((x - (x0 + along * dx)) ** 2 + (y - (y0 + along * dy)) ** 2) ** 0.5
            if far <= half:
                img[y][x] = color


def disc(img, cx, cy, radius, color, ring=None, ring_width=1.0):
    """实心圆；给了 ring 就再描一圈（描边比填充晚画，压在上面）。"""
    for y in range(max(0, int(cy - radius - 1)), min(len(img), int(cy + radius + 2))):
        for x in range(max(0, int(cx - radius - 1)), min(len(img[0]), int(cx + radius + 2))):
            far = ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5
            if far <= radius:
                img[y][x] = color
    if ring is not None:
        for y in range(max(0, int(cy - radius - ring_width - 1)), min(len(img), int(cy + radius + ring_width + 2))):
            for x in range(max(0, int(cx - radius - ring_width - 1)), min(len(img[0]), int(cx + radius + ring_width + 2))):
                far = ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5
                if radius - ring_width <= far <= radius:
                    img[y][x] = ring


def poly(img, points, color):
    """实心多边形（扫描线填充）：剪影、眼睛与鼻子用它。

    一条扫描线只跟每条边算一次交点，再成对填中间——比逐像素射线法快两个数量级
    （4 倍超采样的大图上是几十万次运算与几千万次的差别）。
    """
    if not points:
        return None
    edges = []
    for index in range(len(points)):
        x0, y0 = points[index]
        x1, y1 = points[(index + 1) % len(points)]
        if y0 != y1:
            edges.append((x0, y0, x1, y1))
    if not edges:
        return None
    rows = [y for _x, y in points]
    top = max(0, int(min(rows)))
    bottom = min(len(img) - 1, int(max(rows)) + 1)
    width = len(img[0])
    for y in range(top, bottom + 1):
        line_y = y + 0.5
        cuts = []
        for x0, y0, x1, y1 in edges:
            if (y0 > line_y) != (y1 > line_y):
                cuts.append(x0 + (line_y - y0) * (x1 - x0) / (y1 - y0))
        if len(cuts) < 2:
            continue
        cuts.sort()
        for index in range(0, len(cuts) - 1, 2):
            start = max(0, int(cuts[index] + 0.5))
            stop = min(width - 1, int(cuts[index + 1] - 0.5))
            for x in range(start, stop + 1):
                img[y][x] = color
    return None


def stroke(img, points, color, width):
    """把一串点连成折线描出来（贝塞尔折线就是这么落笔的）。"""
    for index in range(len(points) - 1):
        (x0, y0), (x1, y1) = points[index], points[index + 1]
        line(img, x0, y0, x1, y1, color, width)
    return None


def shape(img, points, fill, edge, width):
    """一块剪影：先填色，再沿着边界描一圈（描边压在填充上，轮廓才干净）。"""
    poly(img, points, fill)
    stroke(img, list(points) + [points[0]], edge, width)
    return None


def bez(p0, p1, p2, p3, steps=16):
    """三次贝塞尔采样（不含起点）：侧脸那些弧线全靠它。"""
    out = []
    for index in range(1, steps + 1):
        t = float(index) / steps
        u = 1.0 - t
        out.append((u * u * u * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t * t * t * p3[0],
                    u * u * u * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t * t * t * p3[1]))
    return out


def portrait(big_w, big_h):
    """在大图上落笔：**三虎的符号**（第 49 期第 2 条重画的那一版）。

    用户要的四件事对应到这张图上：
    - 清晰轮廓：整张剪影用一条粗墨线一笔勾出（耳朵 → 头顶 → 两颊 → 下巴），中间不打断；
    - 鲜艳色彩：平涂的虎皮橙 ＋ 奶白口鼻 ＋ 暖粉耳窝 ＋ 青色 ✦，不用渐变也不用阴影；
    - 潮流元素：方块画布上贴一枚「贴纸感」的猫头，右上角那颗 ✦ 用的是界面上那句
      「✦ 把灵感变成故事」同一颗记号；
    - 极简符号：全身只有七笔——一对耳朵、一张脸、三道额纹（极简的「三」，也是三虎的记号）、
      两只菱形眼、一枚鼻子、一张嘴。

    坐标一律用「画布比例」（0..1，横向 0..1 就是整个宽度），与具体尺寸无关：16 像素那一档
    也是同一份算式算出来的，只是超采样之后小了一号。
    """
    img = [[CLEAR for _ in range(big_w)] for _ in range(big_h)]
    on = lambda x, y: (x * big_w, y * big_h)
    unit = min(big_w, big_h)
    edge = EDGE_W * unit
    # ① 耳朵：两个尖角，先落笔（脸随后压住它们的根部）
    for left in (True, False):
        flip = (lambda x: x) if left else (lambda x: 1.0 - x)
        shape(img, [on(flip(0.215), 0.115), on(flip(0.140), 0.415), on(flip(0.330), 0.340)],
              FUR, INK, edge)
        # 第 49 期第 2 条：耳窝那块暖粉往上挪一挪（原来大半压在脸底下，缩到 64 像素就看不见了）
        poly(img, [on(flip(0.212), 0.170), on(flip(0.180), 0.300), on(flip(0.286), 0.262)], EAR_IN)
    # ② 脸：一笔到底的圆顶 ＋ 收窄的下巴（四段贝塞尔，缩到 16 像素也不留折角）
    head = [on(0.155, 0.430)]
    head += [on(*p) for p in bez((0.155, 0.430), (0.155, 0.290), (0.245, 0.245), (0.340, 0.245))]
    head += [on(*p) for p in bez((0.340, 0.245), (0.425, 0.222), (0.575, 0.222), (0.660, 0.245))]
    head += [on(*p) for p in bez((0.660, 0.245), (0.755, 0.245), (0.845, 0.290), (0.845, 0.430))]
    head += [on(*p) for p in bez((0.845, 0.430), (0.845, 0.640), (0.720, 0.815), (0.500, 0.885))]
    head += [on(*p) for p in bez((0.500, 0.885), (0.280, 0.815), (0.155, 0.640), (0.155, 0.430))]
    shape(img, head, FUR, INK, edge)
    # ③ 口鼻那块奶白：两瓣圆并成一颗心形（鼻子与嘴垫在上面）
    for cx in (0.395, 0.605):
        disc(img, *on(cx, 0.708), 0.108 * unit, MUZZLE)
    # ④ 额纹：三道墨线，极简的「三」
    for y, half, thick in ((0.318, 0.058, 0.026), (0.382, 0.078, 0.028), (0.446, 0.058, 0.026)):
        stroke(img, [on(0.5 - half, y), on(0.5 + half, y)], INK, thick * unit)
    # ⑤ 眼睛：两只上挑的菱形（外眼角高），一眼就是猫
    for left in (True, False):
        flip = (lambda x: x) if left else (lambda x: 1.0 - x)
        poly(img, [on(flip(0.280), 0.565), on(flip(0.352), 0.505), on(flip(0.425), 0.548),
                   on(flip(0.352), 0.608)], INK)
    # ⑥ 鼻子与嘴：一枚墨三角 ＋ 两道小弧
    poly(img, [on(0.464, 0.652), on(0.536, 0.652), on(0.500, 0.704)], INK)
    for side in (-1.0, 1.0):
        mouth = [on(0.500, 0.704)]
        mouth += [on(*p) for p in bez((0.500, 0.704), (0.500 + side * 0.020, 0.762),
                                      (0.500 + side * 0.058, 0.766), (0.500 + side * 0.080, 0.726))]
        stroke(img, mouth, INK, 0.024 * unit)
    # ⑦ ✦：右上角那颗潮流点缀（四角星：四个长尖 ＋ 四个短腰）
    cx, cy, outer, inner = 0.872, 0.128, 0.100, 0.030
    star = []
    for index in range(8):
        angle = index * math.pi * 2.0 / 8.0
        radius = outer if index % 2 == 0 else inner
        star.append(on(cx + radius * math.cos(angle), cy + radius * math.sin(angle) * 0.72))
    poly(img, star, ACCENT)
    return img


def join(pixels, factor=SS):
    """把大图按 factor×factor 取平均缩回去（每个像素输出 (r, g, b, a)）。"""
    height = len(pixels) // factor
    width = len(pixels[0]) // factor
    rows = []
    for y in range(height):
        row = []
        for x in range(width):
            r = g = b = a = 0
            for dy in range(factor):
                for dx in range(factor):
                    pr, pg, pb, pa = pixels[y * factor + dy][x * factor + dx]
                    # 透明像素按 alpha 加权求和，边缘才不会泛黑
                    r += pr * pa
                    g += pg * pa
                    b += pb * pa
                    a += pa
            if a:
                row.append((int(r / a), int(g / a), int(b / a), int(a / (factor * factor))))
            else:
                row.append((0, 0, 0, 0))
        rows.append(row)
    return rows


def pair(size):
    """把尺寸写成 (宽, 高)：给一个数就是正方形那一档，给一对就用那一对；零或负一律拒绝。"""
    if isinstance(size, (tuple, list)):
        width, height = int(size[0]), int(size[1])
    else:
        width = height = int(size)
    if width <= 0 or height <= 0:
        raise ValueError('图标尺寸得是正整数：%r' % (size,))
    return width, height


def cat_pixels(size=(256, 256)):
    """这一尺寸的 RGBA 像素（行 × 列）。"""
    width, height = pair(size)
    return join(portrait(width * SS, height * SS))


def dib(size, pixels):
    """一张 宽×高 的 32 位 DIB：BITMAPINFOHEADER ＋ 自下而上的 BGRA ＋ 全零 AND 掩码。"""
    width, height = pair(size)
    mask_row = ((width + 31) // 32) * 4
    mask = b'\x00' * (mask_row * height)
    rows = []
    for y in range(height - 1, -1, -1):
        row = bytearray()
        for x in range(width):
            red, green, blue, alpha = pixels[y][x]
            row += bytes((blue, green, red, alpha))
        rows.append(bytes(row))
    body = b''.join(rows)
    header = struct.pack('<IiiHHIIiiII', 40, width, height * 2, 1, 32, 0,
                         len(body) + len(mask), 0, 0, 0, 0)
    return header + body + mask


def ico_bytes(sizes=SIZES):
    """整份 .ico：目录（16 字节一项）＋ 一张张 DIB；宽或高满 256 的那一项按规矩写 0。"""
    pairs = [pair(size) for size in sizes]
    images = [dib(one, cat_pixels(one)) for one in pairs]
    head = struct.pack('<HHH', 0, 1, len(pairs))
    offset = 6 + 16 * len(pairs)
    entries = b''
    for (width, height), data in zip(pairs, images):
        entries += struct.pack('<BBBBHHII', 0 if width >= 256 else width, 0 if height >= 256 else height,
                               0, 0, 1, 32, len(data), offset)
        offset += len(data)
    return head + entries + b''.join(images)


def png_bytes(pixels):
    """把像素写成 PNG（只为自检／预览用，主程序不依赖它）。"""
    height = len(pixels)
    width = len(pixels[0])
    raw = b''.join(b'\x00' + b''.join(bytes(pixel) for pixel in row) for row in pixels)

    def chunk(tag, data):
        return (struct.pack('>I', len(data)) + tag + data
                + struct.pack('>I', zlib.crc32(tag + data) & 0xffffffff))

    header = struct.pack('>IIBBBBB', width, height, 8, 6, 0, 0, 0)
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', header)
            + chunk(b'IDAT', zlib.compress(raw, 9)) + chunk(b'IEND', b''))


def icon_path():
    """图标该放哪：程序目录下 assets/app_icon.ico。"""
    return ASSETS / ICON_NAME


def ensure(path=None, sizes=SIZES, force=False):
    """把 .ico 写出来（已经有了、又没说要重画就原样返回）；写不出来返回 None，绝不抛。"""
    target = Path(path) if path is not None else icon_path()
    if target.is_file() and target.stat().st_size > 0 and not force:
        return target
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        save_bytes(target, ico_bytes(sizes))
    except Exception:
        return None
    return target


APP_ID = 'MangaAssistant.Desktop'
ICON_HOME = Path(os.environ.get('LOCALAPPDATA') or os.path.expanduser('~')) / 'MangaAssistant'


def ascii_icon(icon, home=None):
    """中文路径的 .ico 在 Windows 任务栏、快捷方式上会显示成空白：复制一份到英文路径再用。"""
    icon = Path(icon)
    if str(icon).isascii():
        return icon
    try:
        data = icon.read_bytes()
        target = Path(home or ICON_HOME) / ('app_%s.ico' % hashlib.sha256(data).hexdigest()[:8])
        if not (target.is_file() and target.read_bytes() == data):
            save_bytes(target, data)
        return target
    except Exception:
        return icon


_APP_ID_SET = []


def set_app_id(app_id=APP_ID):
    """让任务栏把本程序当独立应用（用本窗口图标），而不是归到 pythonw.exe 名下。

    须在第一个窗口创建前调用才生效（启动器里就是这么做的）；同一进程只设一次。"""
    if app_id in _APP_ID_SET:
        return True
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
        _APP_ID_SET.append(app_id)
        return True
    except Exception:
        return False


def apply(window, path=None):
    """把图标挂到窗口上（Windows 的 .ico 走 iconbitmap）；拿不到能力就返回 None。

    同一扇窗挂过就直接返回（启动器与 desktop 都会调用），不重复读文件、算哈希。"""
    done = getattr(window, '_app_icon_applied', None)
    if path is None and done is not None:
        return done
    target = ensure() if path is None else Path(path)
    if target is None or not Path(target).is_file():
        return None
    target = ascii_icon(target)
    set_app_id()
    try:
        window.iconbitmap(default=str(target))     # 以后新建的子窗口都用它
    except Exception:
        app_logging.swallowed()
    try:
        # default= 不会挂到已建好的这扇窗上（实测 WM_GETICON 为空，标题栏仍是 Python 图标），必须再设一次。
        window.iconbitmap(str(target))
    except Exception:
        return None
    try:
        window._app_icon_applied = target
    except Exception:
        app_logging.swallowed()
    return target


def write_preview(path=None, size=(256, 256)):
    """写一张 PNG 预览（自检与肉眼检查用）。"""
    target = Path(path) if path is not None else (ASSETS / PREVIEW_NAME)
    target.parent.mkdir(parents=True, exist_ok=True)
    save_bytes(target, png_bytes(cat_pixels(size)))
    return target


def main(argv=None):
    force = '--force' in list(sys.argv[1:] if argv is None else argv)
    icon = ensure(force=force)
    preview = write_preview()
    print('图标：%s（%s）' % (icon or '写不出来', '重画' if force else '已有'))
    print('预览：%s' % preview)
    return icon


import sys  # noqa: E402  （main 里要用；放这儿是为了让上面的纯算法部分不依赖它）

if __name__ == '__main__':
    main()

# -*- coding: utf-8 -*-
"""提示浮层不当对话框（R1976）；R2946 起兼管图标下方的无边框选择浮层 Flyout。"""
import tkinter as tk

from ui_tokens import COLORS, SPACING

_MEASURE_FONTS = {}


def text_measure_font(font, root=None):
    """``FONTS``/token 字体规格（元组或字符串）或已建好的 ``tkfont.Font`` → 可测宽字体。

    规格形态按 ``(root, 规格)`` 缓存 ``tkfont.Font``：自检里每个用例重建 ``tk.Tk``，
    跨解释器复用 Font 会拿到已销毁的 Tcl 解释器；``root`` 缺省取默认根（主程序恒有，
    测试在 setUp 建根之后调用）。须在 Tk 根存在之后调用。
    """
    if hasattr(font, 'measure'):
        return font
    import tkinter
    from tkinter import font as tkfont
    root = root or tkinter._get_default_root('text_measure_font')
    key = (root, str(font))
    cached = _MEASURE_FONTS.get(key)
    if cached is None:
        if len(_MEASURE_FONTS) > 512:
            _MEASURE_FONTS.clear()
        cached = _MEASURE_FONTS[key] = tkfont.Font(root=root, font=font)
    return cached


def measure_text_width(font, texts, max_width=None, root=None):
    """共享测宽入口（U1）：返回 ``texts`` 中最长文本的真实字体像素宽度。

    ``font`` 取 ``FONTS``/token 规格或 ``tkfont.Font``；``texts`` 逐项 ``str()``；
    ``max_width`` 给出像素上限时把结果钳到该值；``root`` 缺省用默认根。
    用 Tk 真实字体 ``measure``，不做全角×2／ASCII×1 的字符数近似；新代码一律走这里
    （门禁 ``test_text_measure_boundary``），不直接调 ``font.measure``。
    """
    face = text_measure_font(font, root)
    width = max([face.measure(str(text)) for text in texts] or [0])
    if max_width is not None:
        width = min(width, int(max_width))
    return width


def char_unit_px(font, root=None):
    """ttk 控件 ``-width``「字符」单位折合的像素宽：以 '0' 实测宽作平均字符代理。"""
    return max(1, text_measure_font(font, root).measure('0'))


def text_units_width(font, texts, root=None):
    """像素测宽折算成 ttk ``-width`` 字符单位数（向上取整，保证不截断）。"""
    px = measure_text_width(font, texts, root=root)
    return -(-px // char_unit_px(font, root)) if px else 0


class Flyout(tk.Toplevel):
    """锚点控件下方的无边框选择浮层：1px 描边壳＋内容体（``self.body``）。

    第 R2946 期：侧栏「资产清单」「项目选择」等二级入口共用的弹出选择层。
    定位、点外部关闭与 Esc 由宿主（desktop_page_nav）负责；本类只管窗体与描边。
    """

    def __init__(self, master):
        super().__init__(master)
        self.overrideredirect(True)
        make_passive_popup(self)
        self.configure(bg=COLORS['border_default'])
        shell = tk.Frame(self, bg=COLORS['border_default'], bd=0)
        shell.pack(fill='both', expand=True)
        # 内容体四周让出 xs 刻度的四分之一（＝1px），border_default 壳显成一圈细描边。
        self.body = tk.Frame(shell, bg=COLORS['background_primary'],
                             padx=SPACING['xs'], pady=SPACING['xs'])
        self.body.pack(fill='both', expand=True,
                       padx=SPACING['xs'] // 4, pady=SPACING['xs'] // 4)


def make_passive_popup(window):
    """ui_theme.install_window_placement 给每个新 Toplevel 设 -alpha 0、<Map> 时 grab_set 并居中。

    提示浮层一旦抓了 grab，鼠标还停在表格上就会被判成「离开」，卡片刚出现就被自己收掉；点击也会被
    吞给浮层。这里在 <Map> 之前把它摘出来：标记已定位、去掉绑定的 Map／Unmap、直接显形。
    """
    window._positioned_once = True
    window.unbind("<Map>")
    window.unbind("<Unmap>")
    window.attributes("-alpha", 1)


def monitor_bounds(window, x=None, y=None):
    """浮层该落在哪块显示器：返回 (left, top, right, bottom) 屏幕坐标。

    ``winfo_screenwidth/height`` 永远是主屏尺寸，软件放在副屏时拿它钳位会把浮层拽回主屏。
    给了 (x, y) 就取该点所在显示器（悬停卡片跟鼠标），否则取 window 所在显示器（聊天框跟主窗口）。
    非 Windows／接口不可用时退回 ``(0, 0, 屏宽, 屏高)``，与单屏旧行为一致。
    """
    try:
        import ctypes
        from ctypes import wintypes

        class MONITORINFO(ctypes.Structure):
            _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT),
                        ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD)]

        api = ctypes.windll.user32
        api.MonitorFromPoint.argtypes = [wintypes.POINT, wintypes.DWORD]
        api.MonitorFromPoint.restype = wintypes.HANDLE
        api.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
        api.MonitorFromWindow.restype = wintypes.HANDLE
        api.GetMonitorInfoW.argtypes = [wintypes.HANDLE, ctypes.POINTER(MONITORINFO)]
        info = MONITORINFO()
        info.cbSize = ctypes.sizeof(info)
        if x is not None and y is not None:
            monitor = api.MonitorFromPoint(wintypes.POINT(int(x), int(y)), 2)   # 2＝取最近的显示器
        else:
            monitor = api.MonitorFromWindow(window.winfo_id(), 2)
        if monitor and api.GetMonitorInfoW(monitor, ctypes.byref(info)):
            r = info.rcMonitor
            return int(r.left), int(r.top), int(r.right), int(r.bottom)
    except (AttributeError, OSError, ValueError, TypeError):
        pass
    return 0, 0, int(window.winfo_screenwidth()), int(window.winfo_screenheight())

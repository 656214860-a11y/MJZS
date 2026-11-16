# -*- coding: utf-8 -*-
"""提示浮层不当对话框（R1976）。"""


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

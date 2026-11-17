# -*- coding: utf-8 -*-
"""拖动改主窗口大小时合并整页布局（性能轮 RESIZE）。

拖动窗口边框时 Windows 连续送 WM_SIZE，Tk 的每个空闲周期都会把内容框、表头、侧栏行数、
响应式表格整页重排一遍，画面看起来混乱、卡。这里把「是否正在拖动」与「静默多久算停止」
收成一处，交给主窗口级的布局处理者共用：

* **拖动判定**：尺寸变化时用 Win32 读光标位置与顶层窗口矩形——光标落在外框的调整边上、
  且左键按着，才算出在拖。标题栏在内侧，不会被当成上边框；最大化时没有可拖的边框，
  直接判否。页面里的表格、气泡在拖动中跟着重排时，那一帧光标同样捏在边框上，一并合并。
* **合并**：拖动中只把静默时钟往后推，不重排；松手后静默到点补做一次。
  布局仍走既有 after_idle 路径，最终结果与改前同尺寸一致。
* **降级**：非 Windows、探测失败、拿不到光标或按键状态时返回「未知」，按纯静默合并处理
  （连续尺寸变化合并成一次，静默后补做），不抛异常、不卡死。

换页冻结绘制（``PaintFreeze``）也在这里：同样是 Win32 下「布局期间不让半成品上屏」。

零第三方依赖。规格见 ``ui_tokens.DESKTOP_LAYOUT['resize_quiet_ms']`` 与
``['resize_edge_px']``。
"""
import sys

import tkinter as tk

import infra.app_logging as app_logging
from ui_tokens import DESKTOP_LAYOUT, PAGE_FREEZE_MAX_MS

#: 拿不到系统边框宽时的命中圈宽度（token，不写死像素）。
_EDGE_PX = int(DESKTOP_LAYOUT['resize_edge_px'])
_SM_CXSIZEFRAME = 32
_SM_CYSIZEFRAME = 33
_SM_CXPADDEDBORDER = 92
_VK_LBUTTON = 0x01


class _NativeProbe:
    """只读少量 Win32 查询；初始化失败即标记不可用，之后不再重试。"""

    def __init__(self):
        self.available = False
        if sys.platform != 'win32':
            return
        try:
            import ctypes
            from ctypes import wintypes
            user32 = ctypes.windll.user32
            user32.GetWindowRect.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.RECT))
            user32.GetWindowRect.restype = wintypes.BOOL
            user32.GetParent.argtypes = (wintypes.HWND,)
            user32.GetParent.restype = wintypes.HWND
            user32.GetCursorPos.argtypes = (ctypes.POINTER(wintypes.POINT),)
            user32.GetCursorPos.restype = wintypes.BOOL
            user32.GetAsyncKeyState.argtypes = (ctypes.c_int,)
            user32.GetAsyncKeyState.restype = ctypes.c_short
            user32.GetSystemMetrics.argtypes = (ctypes.c_int,)
            user32.GetSystemMetrics.restype = ctypes.c_int
            self._ctypes = ctypes
            self._wintypes = wintypes
            self._user32 = user32
            self.available = True
        except Exception:
            app_logging.swallowed()

    def top_level(self, winfo_id):
        """Tk ``winfo_id`` → 顶层窗口句柄；取不到返回 None。"""
        if not self.available:
            return None
        handle = int(winfo_id)
        for _ in range(8):
            parent = self._user32.GetParent(handle)
            if not parent:
                break
            handle = parent
        return handle or None

    def frame_rect(self, handle):
        """顶层窗口在屏幕上的矩形（含非客户区）。"""
        rect = self._wintypes.RECT()
        if not self._user32.GetWindowRect(handle, self._ctypes.byref(rect)):
            return None
        return rect.left, rect.top, rect.right, rect.bottom

    def cursor(self):
        point = self._wintypes.POINT()
        if not self._user32.GetCursorPos(self._ctypes.byref(point)):
            return None
        return point.x, point.y

    def left_button_down(self):
        """左键是否按着；读不到返回 None。"""
        if not self.available:
            return None
        try:
            return bool(self._user32.GetAsyncKeyState(_VK_LBUTTON) & 0x8000)
        except Exception:
            app_logging.swallowed()
            return None

    def edge(self):
        """外框调整边的命中宽度：系统边框加内补边，读不到时退回 token。"""
        try:
            size = int(self._user32.GetSystemMetrics(_SM_CXSIZEFRAME))
            padded = int(self._user32.GetSystemMetrics(_SM_CXPADDEDBORDER))
            vertical = int(self._user32.GetSystemMetrics(_SM_CYSIZEFRAME))
            # 取横纵较大者，让上下边框和左右一样好抓；再兜底到 token。
            width = max(size, vertical) + max(0, padded)
            return max(1, min(width or _EDGE_PX, _EDGE_PX * 4))
        except Exception:
            app_logging.swallowed()
            return _EDGE_PX


_PROBE = _NativeProbe()


class ResizeCoalescer:
    """一个顶层窗口的拖动合并器；回调只在主线程里被调。

    ``schedule(apply, event=...)`` 返回 True 表示已被这里接管，调用方不要立即重排；
    False 表示照旧立即布局。拖动中多次登记的回调按首次登记顺序去重，静默后各补做一次。
    """

    def __init__(self, window, quiet_ms=None, freeze=None, thaw=None):
        # freeze/thaw：确认「正在拖外框」时收起内容区只画外层框架，松手（补做重排之前）再放回。
        self.freeze = freeze
        self.thaw = thaw
        self._frozen = False
        self.window = window
        self.probe = _PROBE
        self.quiet_ms = int(DESKTOP_LAYOUT['resize_quiet_ms']) if quiet_ms is None else int(quiet_ms)
        self._job = None
        self._pending = []
        self._waiting = False

    def cancel(self):
        """窗口销毁前撤销挂起任务；可重复调用。"""
        self._drop()

    def is_waiting(self):
        return self._waiting

    def _thaw(self):
        if not self._frozen:
            return
        self._frozen = False
        if self.thaw is not None:
            try:
                self.thaw()
            except tk.TclError:
                pass
            except Exception:
                app_logging.swallowed()

    def _freeze_once(self):
        if self._frozen or self.freeze is None:
            return
        self._frozen = True
        try:
            self.freeze()
        except tk.TclError:
            pass
        except Exception:
            self._frozen = False
            app_logging.swallowed()

    def _drop(self):
        self._thaw()
        self._pending = []
        self._waiting = False
        job, self._job = self._job, None
        if job is not None:
            try:
                self.window.after_cancel(job)
            except tk.TclError:
                pass

    # ---- 拖动判定 ---------------------------------------------------------
    def _on_edge(self, point, rect, edge):
        """光标在窗口外框的调整边内（标题栏、客户区都算否）。"""
        left, top, right, bottom = rect
        x, y = point
        if not (left - edge <= x <= right + edge and top - edge <= y <= bottom + edge):
            return False
        return (x <= left + edge or x >= right - edge
                or y <= top + edge or y >= bottom - edge)

    def drag_active(self):
        """光标此刻是否正捏着本窗口外框在拖；不可判定时返回 None。"""
        try:
            handle = self.probe.top_level(self.window.winfo_id())
            if not handle:
                return None
            if str(self.window.tk.call('wm', 'state', self.window)) == 'zoomed':
                return False
            # 左键没按着就不可能在拖；先看按键，光标读不到（非交互桌面、锁屏）时也不误判成「未知」。
            if self.probe.left_button_down() is False:
                return False
            rect = self.probe.frame_rect(handle)
            point = self.probe.cursor() if rect else None
            if rect is None or point is None:
                return None
            if not self._on_edge(point, rect, self.probe.edge()):
                return False
            return self.probe.left_button_down()
        except Exception:
            app_logging.swallowed()
            return None

    # ---- 调度 -------------------------------------------------------------
    def schedule(self, apply, *, event=None):
        """尺寸变化：在拖边框就推迟并返回 True；其它情况返回 False 让调用方立即布局。

        作为 Tk 绑定直接使用时首个参数是 tk.Event，此时没有可补做的回调，直接放行。
        """
        if isinstance(apply, tk.Event) or apply is None:
            return False
        drag = self.drag_active()
        if drag is False:
            return False
        if drag is True:
            self._freeze_once()  # 只有确认在拖外框才收起内容；探测不到的降级路径不动画面
        if not any(callback is apply for callback in self._pending):
            self._pending.append(apply)
        self._waiting = True
        self._rearm()
        return True

    def flush(self):
        """调用方要立即重排（页面切换、主动布局、最小化恢复）：把补做交给这次布局。"""
        self._drop()

    def _rearm(self):
        job, self._job = self._job, None
        if job is not None:
            try:
                self.window.after_cancel(job)
            except tk.TclError:
                pass
        try:
            self._job = self.window.after(self.quiet_ms, self._fire)
        except tk.TclError:
            self._waiting = False

    def _fire(self):
        """静默到点：仍捏着边框就继续等；松手后把登记过的重排各补做一次。"""
        self._job = None
        try:
            drag = self.drag_active()
        except Exception:
            app_logging.swallowed()
            drag = None
        if drag is True:
            self._rearm()
            return
        pending, self._pending = self._pending, []
        self._waiting = False
        self._thaw()  # 先放回内容，补做的整页重排才量得到真实尺寸
        for apply in pending:
            try:
                apply()
            except Exception:
                # Tk 回调里的异常会被 report_callback_exception 吞掉，补做不能因此挂丢。
                app_logging.swallowed()


_WM_SETREDRAW = 0x000B
_SW_HIDE = 0
_RDW_INVALIDATE = 0x0001
_RDW_ERASE = 0x0004
_RDW_ALLCHILDREN = 0x0080
_RDW_UPDATENOW = 0x0100
_USER32 = []


def _user32():
    """按需载入一次 user32 并声明用到的签名；非 Windows 或载入失败返回 None。"""
    if not _USER32:
        user32 = None
        if sys.platform == 'win32':
            try:
                import ctypes
                from ctypes import wintypes
                user32 = ctypes.windll.user32
                user32.SendMessageW.argtypes = (wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
                user32.SendMessageW.restype = ctypes.c_ssize_t
                user32.RedrawWindow.argtypes = (wintypes.HWND, ctypes.c_void_p, ctypes.c_void_p, wintypes.UINT)
                user32.RedrawWindow.restype = wintypes.BOOL
                user32.ShowWindow.argtypes = (wintypes.HWND, ctypes.c_int)
                user32.ShowWindow.restype = wintypes.BOOL
            except Exception:
                user32 = None
                app_logging.swallowed()
        _USER32.append(user32)
    return _USER32[0]


def repaint_area(widget):
    """整块擦底重画一块区域（含子窗口）：清掉控件挪位后留在空隙里的旧像素。

    Windows 上控件移动时只重画新露出的部分，框背景偶尔没被失效，旧文字会留成重影。
    非 Windows、控件不可见时什么也不做，返回 False。
    """
    user32 = _user32()
    if user32 is None:
        return False
    try:
        if not widget.winfo_viewable():
            return False
        user32.RedrawWindow(int(widget.winfo_id()), None, None,
                            _RDW_INVALIDATE | _RDW_ERASE | _RDW_ALLCHILDREN | _RDW_UPDATENOW)
    except tk.TclError:
        return False
    except Exception:
        app_logging.swallowed()
        return False
    return True


class PaintFreeze:
    """换页期间冻结一块区域的绘制：旧页像素留在屏幕上，新页排好后一次画出。

    Tk 在 Windows 上边排版边直接往屏幕画：新控件先画在初始位置，请求尺寸逐层上传后又被挪动，
    用户看到的是零件陆续冒出、位置乱跳。``WM_SETREDRAW`` 关掉后这块区域（含子窗口）的绘制
    全被裁掉；``thaw`` 打开并整块失效重画。最长冻 ``max_ms``，超时照常解冻，异常路径不会卡住画面。
    非 Windows、控件不可见（隐藏窗口、测试里 withdraw 的根窗口）时什么也不做。
    """

    def __init__(self, widget, max_ms=None):
        self.widget = widget
        self.max_ms = int(PAGE_FREEZE_MAX_MS if max_ms is None else max_ms)
        self.frozen = False
        self._job = None
        self._user32 = _user32()

    def freeze(self):
        if self.frozen or self._user32 is None:
            return False
        try:
            if not self.widget.winfo_viewable():
                return False
            self._user32.SendMessageW(int(self.widget.winfo_id()), _WM_SETREDRAW, 0, 0)
            self.frozen = True
            self._job = self.widget.after(self.max_ms, self.thaw)
        except tk.TclError:
            return False
        except Exception:
            app_logging.swallowed()
            return False
        return True

    def thaw(self):
        if not self.frozen:
            return False
        self.frozen = False
        job, self._job = self._job, None
        try:
            if job is not None:
                self.widget.after_cancel(job)
            if not self.widget.winfo_exists():
                return False
            handle = int(self.widget.winfo_id())
            self._user32.SendMessageW(handle, _WM_SETREDRAW, 1, 0)
            # 打开重画会把窗口标成可见；冻结期间 Tk 若已把它收起，照样收回去。
            if not self.widget.winfo_ismapped():
                self._user32.ShowWindow(handle, _SW_HIDE)
                return True
            self._user32.RedrawWindow(handle, None, None, _RDW_INVALIDATE | _RDW_ALLCHILDREN | _RDW_UPDATENOW)
        except tk.TclError:
            pass
        except Exception:
            app_logging.swallowed()
        return True

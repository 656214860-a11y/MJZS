# -*- coding: utf-8 -*-
"""云朵框的拖窗让路（R1976）：用户正按住标题栏拖动窗口时，自动冒出来的云先排队，松手再出。

Windows 的拖动是系统的模态循环，Tk 的定时器在里面照常走；这时新开／显示别的窗口（deiconify、
lift、置顶）会让系统换了活动窗，拖动当场中断——用户看到的就是「三虎突然弹窗，移动被打断」。
用户自己点开云（focus=True）不拦；只拦程序自动播报（focus=False）。
"""
import sys

import app_logging

GUI_INMOVESIZE = 0x2        # GUITHREADINFO.flags：前台线程正处在移动／缩放的模态循环里
MOVE_RETRY_MS = 120         # 等松手的轮询间隔
MOVE_RETRY_MAX = 400        # 约 48 秒封顶：再长就当拖动已异常结束，别让云永远排队


def in_move_size():
    """前台窗口是否正被用户拖动或拉伸；非 Windows 或查询失败一律当「没有」。"""
    if sys.platform != 'win32':
        return False
    try:
        import ctypes
        from ctypes import wintypes

        class GUITHREADINFO(ctypes.Structure):
            _fields_ = [('cbSize', wintypes.DWORD), ('flags', wintypes.DWORD),
                        ('hwndActive', wintypes.HWND), ('hwndFocus', wintypes.HWND),
                        ('hwndCapture', wintypes.HWND), ('hwndMenuOwner', wintypes.HWND),
                        ('hwndMoveSize', wintypes.HWND), ('hwndCaret', wintypes.HWND),
                        ('rcCaret', wintypes.RECT)]

        info = GUITHREADINFO()
        info.cbSize = ctypes.sizeof(GUITHREADINFO)
        if not ctypes.windll.user32.GetGUIThreadInfo(0, ctypes.byref(info)):
            return False
        return bool(info.flags & GUI_INMOVESIZE)
    except Exception:
        return False


class CloudMoveGuardMixin:
    """Cloud 的拖窗让路：show() 开头问一句，在拖就排队，松手后用最新的一份参数补显示。"""

    move_probe = staticmethod(in_move_size)

    def _defer_while_moving(self, **shown):
        """自动显示碰上拖窗：记下参数（后来的覆盖先来的）并挂轮询；返回 True＝这次先不显示。"""
        if getattr(self, '_move_forced', False) or not self.move_probe():
            return False
        self._move_pending = shown
        if getattr(self, '_move_job', None) is None:
            self._move_waits = 0
            self._move_callback = self._move_retry     # 持有闭包，免得 Tcl 命令被 GC 先删
            try:
                self._move_job = self.parent.after(MOVE_RETRY_MS, self._move_callback)
            except Exception:
                self._move_job = None
                self._move_pending = None
                return False
        return True

    def _move_retry(self):
        self._move_job = None
        self._move_waits = getattr(self, '_move_waits', 0) + 1
        if self.move_probe() and self._move_waits < MOVE_RETRY_MAX:
            try:
                self._move_job = self.parent.after(MOVE_RETRY_MS, self._move_callback)
                return None
            except Exception:
                app_logging.swallowed()
        shown, self._move_pending = getattr(self, '_move_pending', None), None
        if shown is None:
            return None
        self._move_forced = True            # 封顶后的这一次不再让路，免得无限排队
        try:
            return self.show(**shown)
        finally:
            self._move_forced = False

    def _cancel_move_wait(self):
        job, self._move_job = getattr(self, '_move_job', None), None
        self._move_pending = None
        if job is not None:
            try:
                self.parent.after_cancel(job)
            except Exception:
                app_logging.swallowed()

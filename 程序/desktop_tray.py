# -*- coding: utf-8 -*-
"""桌面系统托盘：最小化到托盘 + 右键菜单（恢复窗口／强制重启／退出），零第三方。

Tkinter 没有内置托盘支持，这里用 ctypes 调 Win32 ``Shell_NotifyIcon``，托盘点击回调经
子类化主窗 WNDPROC 捕获。仅 Windows 生效；非 Windows 上 ``setup_tray`` 直接跳过。

从 ``Desktop`` 迁出的 L4 桌面部件，``Desktop`` 通过继承 ``TrayMixin`` 获得方法。
"""
from __future__ import annotations

import ctypes
import os
import subprocess
import tkinter as tk
from ctypes import wintypes
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PYTHONW = REPO_ROOT / '运行环境' / 'Python' / 'pythonw.exe'
LAUNCHER = REPO_ROOT / '启动漫剧制作助手.pyw'
APP_ICON = REPO_ROOT / '程序' / 'assets' / 'app_icon.ico'

# ---- Win32 常量 ----
NIM_ADD = 0x00000000
NIM_MODIFY = 0x00000001
NIM_DELETE = 0x00000002
NIF_MESSAGE = 0x00000001
NIF_ICON = 0x00000002
NIF_TIP = 0x00000004
WM_APP = 0x8000
WM_TRAYICON = WM_APP + 1
WM_LBUTTONUP = 0x0202
WM_LBUTTONDBLCLK = 0x0203
WM_RBUTTONUP = 0x0205
LR_LOADFROMFILE = 0x00000010
IMAGE_ICON = 1
LR_DEFAULTSIZE = 0x00000040
GWL_WNDPROC = -4
IDI_APPLICATION = 32512
DETACHED_PROCESS = 0x00000008

# WPARAM／LPARAM／LRESULT 都是指针宽度整数；WNDPROC 签名 LRESULT(HWND, UINT, WPARAM, LPARAM)。
_PTR = ctypes.c_ssize_t
_WNDPROC = ctypes.WINFUNCTYPE(_PTR, wintypes.HWND, ctypes.c_uint, _PTR, _PTR)


class _NOTIFYICONDATAW(ctypes.Structure):
    _fields_ = [
        ('cbSize', wintypes.DWORD),
        ('hWnd', wintypes.HWND),
        ('uID', wintypes.UINT),
        ('uFlags', wintypes.UINT),
        ('uCallbackMessage', wintypes.UINT),
        ('hIcon', wintypes.HICON),
        ('szTip', wintypes.WCHAR * 128),
        ('dwState', wintypes.DWORD),
        ('dwStateMask', wintypes.DWORD),
        ('szInfo', wintypes.WCHAR * 256),
        ('uVersion', wintypes.UINT),
        ('szInfoTitle', wintypes.WCHAR * 64),
        ('dwInfoFlags', wintypes.DWORD),
        ('guidItem', wintypes.BYTE * 16),
        ('hBalloonIcon', wintypes.HICON),
    ]


class TrayIcon:
    """主窗的系统托盘图标；左键恢复窗口，右键弹出菜单。"""

    def __init__(self, window, *, on_restore, on_quit, on_force_restart, icon_path=APP_ICON):
        self.window = window
        self.on_restore = on_restore
        self.on_quit = on_quit
        self.on_force_restart = on_force_restart
        self.icon_path = Path(icon_path)
        self._user32 = ctypes.windll.user32
        self._shell32 = ctypes.windll.shell32
        self._hwnd = None
        self._icon_handle = None
        self._original_wndproc = None
        self._wndproc = None  # 持有引用，防止 WINFUNCTYPE 被 GC 后回调段错误
        self._menu = None
        self._active = False

    def _load_icon(self):
        if self.icon_path.is_file():
            handle = self._user32.LoadImageW(
                None, str(self.icon_path), IMAGE_ICON, 0, 0,
                LR_LOADFROMFILE | LR_DEFAULTSIZE)
            if handle:
                return handle
        return self._user32.LoadIconW(None, ctypes.c_void_p(IDI_APPLICATION))

    def add(self):
        if self._active:
            return
        try:
            self._hwnd = int(self.window.winfo_id())
        except tk.TclError:
            return
        self._icon_handle = self._load_icon()
        self._subclass()
        self._notify(NIM_ADD)
        self._active = True

    def remove(self):
        if not self._active:
            return
        self._notify(NIM_DELETE)
        self._restore_wndproc()
        self._active = False
        self._icon_handle = None

    def _notify(self, action):
        data = _NOTIFYICONDATAW()
        data.cbSize = ctypes.sizeof(_NOTIFYICONDATAW)
        data.hWnd = self._hwnd
        data.uID = 1
        data.uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP
        data.uCallbackMessage = WM_TRAYICON
        data.hIcon = self._icon_handle
        data.szTip = '漫剧助手'
        if not self._shell32.Shell_NotifyIconW(action, ctypes.byref(data)):
            raise ctypes.WinError()

    def _subclass(self):
        set_ptr = self._user32.SetWindowLongPtrW
        set_ptr.restype = _PTR
        set_ptr.argtypes = (wintypes.HWND, ctypes.c_int, _PTR)
        call_proc = self._user32.CallWindowProcW
        call_proc.restype = _PTR
        call_proc.argtypes = (_PTR, wintypes.HWND, ctypes.c_uint, _PTR, _PTR)
        user32 = self._user32

        def wndproc(hwnd, msg, wparam, lparam):
            if msg == WM_TRAYICON:
                if lparam in (WM_LBUTTONUP, WM_LBUTTONDBLCLK):
                    self.window.after_idle(self.on_restore)
                elif lparam == WM_RBUTTONUP:
                    self.window.after_idle(self._show_menu)
                return 0
            return user32.CallWindowProcW(self._original_wndproc, hwnd, msg, wparam, lparam)

        self._wndproc = _WNDPROC(wndproc)
        self._original_wndproc = set_ptr(
            self._hwnd, GWL_WNDPROC, ctypes.cast(self._wndproc, ctypes.c_void_p).value)

    def _restore_wndproc(self):
        if self._original_wndproc is not None and self._hwnd is not None:
            set_ptr = self._user32.SetWindowLongPtrW
            set_ptr.restype = _PTR
            set_ptr.argtypes = (wintypes.HWND, ctypes.c_int, _PTR)
            set_ptr(self._hwnd, GWL_WNDPROC, self._original_wndproc)
        self._original_wndproc = None
        self._wndproc = None

    def _show_menu(self):
        try:
            if not self.window.winfo_exists():
                return
        except tk.TclError:
            return
        if self._menu is None:
            menu = tk.Menu(self.window, tearoff=0)
            menu.add_command(label='恢复窗口', command=self.on_restore)
            menu.add_command(label='强制重启', command=self.on_force_restart)
            menu.add_separator()
            menu.add_command(label='退出', command=self.on_quit)
            self._menu = menu
        point = wintypes.POINT()
        self._user32.GetCursorPos(ctypes.byref(point))
        try:
            self._menu.tk_popup(point.x, point.y)
        finally:
            try:
                self._menu.grab_release()
            except tk.TclError:
                pass


def force_restart():
    """杀进程并重开：先派一个脱离的辅助进程稍候拉起启动器，避开单实例互斥量竞态。

    托盘菜单跑在 Tk 主线程上，只在界面还活着时可用；主线程真卡死仍需修根因或看门狗。
    """
    helper = (
        "import subprocess,sys,time;"
        "time.sleep(0.8);"
        "subprocess.Popen([sys.argv[1],'-I',sys.argv[2]])"
    )
    subprocess.Popen(
        [str(PYTHONW), '-c', helper, str(PYTHONW), str(LAUNCHER)],
        creationflags=DETACHED_PROCESS, close_fds=True,
    )
    os._exit(0)


class TrayMixin:
    """Desktop 的最小化到托盘集成。"""

    def setup_tray(self):
        """窗口就绪后建立托盘图标，并把最小化拦到托盘。"""
        if sys_platform_non_windows():
            return
        if getattr(self, 'tray_icon', None) is not None:
            return
        self._tray_minimized = False
        self.tray_icon = TrayIcon(
            self.win,
            on_restore=self.restore_from_tray,
            on_quit=self.close,
            on_force_restart=force_restart,
        )
        self.tray_icon.add()
        self.win.bind('<Unmap>', self._on_minimize_to_tray, add='+')
        self.win.bind('<Destroy>', self._on_tray_destroy, add='+')

    def _on_tray_destroy(self, event=None):
        if event is not None and getattr(event, 'widget', None) is not self.win:
            return None
        self.close_tray()
        return None

    def _on_minimize_to_tray(self, event=None):
        if event is not None and getattr(event, 'widget', None) is not self.win:
            return None
        if getattr(self, '_tray_minimized', False):
            return None
        try:
            if self.win.state() == 'iconic':
                # 标准标题栏最小化 → 收进托盘，任务栏不再显示。
                self._tray_minimized = True
                self.win.withdraw()
        except tk.TclError:
            pass
        return None

    def restore_from_tray(self):
        self._tray_minimized = False
        try:
            self.win.deiconify()
            self.win.lift()
            self.win.focus_force()
        except tk.TclError:
            pass

    def close_tray(self):
        tray = getattr(self, 'tray_icon', None)
        if tray is not None:
            tray.remove()
            self.tray_icon = None


def sys_platform_non_windows():
    import sys
    return sys.platform != 'win32'

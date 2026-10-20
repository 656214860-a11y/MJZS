# -*- coding: utf-8 -*-
"""桌面系统托盘：最小化到托盘 + 右键菜单（恢复窗口／强制重启／退出），零第三方。

Tkinter 没有内置托盘支持，这里用 ctypes 调 Win32 ``Shell_NotifyIcon``。仅 Windows 生效；
非 Windows 上 ``setup_tray`` 直接跳过。

线程模型（R1775 定稿，不要改回去）：托盘图标挂在**独立线程**上的一个隐藏原生窗口，
该线程跑自己的 ``GetMessage`` 循环，收到托盘点击后只把命令压进队列；Tk 主线程用
``after`` 定时器排空队列再调 Tk。R1773／R1774 把 Python WNDPROC 直接子类化到 Tk 主窗上，
Windows 会在 Tcl 事件循环内部、甚至在 ``withdraw()`` 这类 Tk 调用中途同步重入该回调，
此时 ``_tkinter`` 已释放 GIL，回调里一碰 Tk 解释器就 Fatal（表现为最小化或点托盘时闪退）。

从 ``Desktop`` 迁出的 L4 桌面部件，``Desktop`` 通过继承 ``TrayMixin`` 获得方法。
"""
from __future__ import annotations

import ctypes
import os
import sys
import threading
import tkinter as tk
from ctypes import wintypes
from pathlib import Path

import platform_tools

REPO_ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = REPO_ROOT / '启动漫剧制作助手.pyw'
APP_ICON = REPO_ROOT / '程序' / 'assets' / 'app_icon.ico'


def _pythonw_path() -> Path:
    """强制重启用的无控制台解释器：优先当前解释器旁的 pythonw.exe，其次仓库随附的。"""
    beside = Path(sys.executable).with_name('pythonw.exe')
    if beside.is_file():
        return beside
    return REPO_ROOT / '运行环境' / 'Python' / 'pythonw.exe'


PYTHONW = _pythonw_path()

# ---- Win32 常量 ----
NIM_ADD = 0x00000000
NIM_MODIFY = 0x00000001
NIM_DELETE = 0x00000002
NIF_MESSAGE = 0x00000001
NIF_ICON = 0x00000002
NIF_TIP = 0x00000004
WM_APP = 0x8000
WM_TRAYICON = WM_APP + 1
WM_DESTROY = 0x0002
WM_CLOSE = 0x0010
WM_LBUTTONUP = 0x0202
WM_LBUTTONDBLCLK = 0x0203
WM_RBUTTONUP = 0x0205
LR_LOADFROMFILE = 0x00000010
IMAGE_ICON = 1
LR_DEFAULTSIZE = 0x00000040
IDI_APPLICATION = 32512
ERROR_CLASS_ALREADY_EXISTS = 1410
# 托盘右键菜单（Win32 TrackPopupMenu，不依赖主窗是否 withdrawn）
MF_STRING = 0x00000000
MF_SEPARATOR = 0x00000800
TPM_RIGHTBUTTON = 0x0002
TPM_RETURNCMD = 0x0100
TPM_NONOTIFY = 0x0080
WM_NULL = 0x0000
_CMD_RESTORE = 1
_CMD_RESTART = 2
_CMD_QUIT = 3
# Tk 侧排空托盘命令队列的周期（毫秒）；托盘线程只入队，不碰 Tk。
TRAY_POLL_MS = 120
# 托盘线程建窗／收摊的等待上限（秒）。
TRAY_THREAD_TIMEOUT_S = 5.0
_WINDOW_CLASS = 'DramaStudioTrayWindow'

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


class _WNDCLASSW(ctypes.Structure):
    _fields_ = [
        ('style', wintypes.UINT),
        ('lpfnWndProc', _WNDPROC),
        ('cbClsExtra', ctypes.c_int),
        ('cbWndExtra', ctypes.c_int),
        ('hInstance', wintypes.HINSTANCE),
        ('hIcon', wintypes.HICON),
        ('hCursor', wintypes.HANDLE),
        ('hbrBackground', wintypes.HBRUSH),
        ('lpszMenuName', wintypes.LPCWSTR),
        ('lpszClassName', wintypes.LPCWSTR),
    ]


def _bind_user32(user32):
    """给本模块用到的 user32 函数补齐 argtypes／restype（64 位下句柄不能按 int 截断）。"""
    user32.DefWindowProcW.argtypes = (wintypes.HWND, ctypes.c_uint, _PTR, _PTR)
    user32.DefWindowProcW.restype = _PTR
    user32.RegisterClassW.argtypes = (ctypes.POINTER(_WNDCLASSW),)
    user32.RegisterClassW.restype = wintypes.ATOM
    user32.UnregisterClassW.argtypes = (wintypes.LPCWSTR, wintypes.HINSTANCE)
    user32.UnregisterClassW.restype = wintypes.BOOL
    user32.CreateWindowExW.argtypes = (
        wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
        ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
        wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID)
    user32.CreateWindowExW.restype = wintypes.HWND
    user32.DestroyWindow.argtypes = (wintypes.HWND,)
    user32.DestroyWindow.restype = wintypes.BOOL
    user32.PostMessageW.argtypes = (wintypes.HWND, ctypes.c_uint, _PTR, _PTR)
    user32.PostMessageW.restype = wintypes.BOOL
    user32.GetMessageW.argtypes = (ctypes.POINTER(wintypes.MSG), wintypes.HWND, ctypes.c_uint, ctypes.c_uint)
    user32.GetMessageW.restype = ctypes.c_int
    user32.TranslateMessage.argtypes = (ctypes.POINTER(wintypes.MSG),)
    user32.DispatchMessageW.argtypes = (ctypes.POINTER(wintypes.MSG),)
    user32.DispatchMessageW.restype = _PTR
    user32.PostQuitMessage.argtypes = (ctypes.c_int,)
    user32.LoadImageW.argtypes = (wintypes.HINSTANCE, wintypes.LPCWSTR, wintypes.UINT,
                                  ctypes.c_int, ctypes.c_int, wintypes.UINT)
    user32.LoadImageW.restype = wintypes.HANDLE
    user32.LoadIconW.argtypes = (wintypes.HINSTANCE, wintypes.LPCWSTR)
    user32.LoadIconW.restype = wintypes.HICON
    user32.CreatePopupMenu.restype = wintypes.HMENU
    user32.AppendMenuW.argtypes = (wintypes.HMENU, wintypes.UINT, ctypes.c_size_t, wintypes.LPCWSTR)
    user32.AppendMenuW.restype = wintypes.BOOL
    user32.TrackPopupMenu.argtypes = (wintypes.HMENU, wintypes.UINT, ctypes.c_int, ctypes.c_int,
                                      ctypes.c_int, wintypes.HWND, ctypes.c_void_p)
    user32.TrackPopupMenu.restype = ctypes.c_int
    user32.DestroyMenu.argtypes = (wintypes.HMENU,)
    user32.DestroyMenu.restype = wintypes.BOOL
    user32.SetForegroundWindow.argtypes = (wintypes.HWND,)
    user32.SetForegroundWindow.restype = wintypes.BOOL
    user32.GetCursorPos.argtypes = (ctypes.POINTER(wintypes.POINT),)
    user32.GetCursorPos.restype = wintypes.BOOL


class TrayIcon:
    """主窗的系统托盘图标；左键恢复窗口，右键弹出菜单。

    ``window`` 只用来挂 ``after`` 定时器；托盘图标本身属于托盘线程的隐藏窗口。
    三个回调都在 Tk 主线程里被调用。
    """

    def __init__(self, window, *, on_restore, on_quit, on_force_restart, icon_path=APP_ICON):
        self.window = window
        self.on_restore = on_restore
        self.on_quit = on_quit
        self.on_force_restart = on_force_restart
        self.icon_path = Path(icon_path)
        # 私有 DLL 实例：本模块要改 argtypes／restype，不能污染全局 ctypes.windll.user32。
        self._user32 = ctypes.WinDLL('user32', use_last_error=True)
        self._shell32 = ctypes.WinDLL('shell32', use_last_error=True)
        self._kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
        _bind_user32(self._user32)
        self._kernel32.GetModuleHandleW.argtypes = (wintypes.LPCWSTR,)
        self._kernel32.GetModuleHandleW.restype = wintypes.HMODULE
        self._shell32.Shell_NotifyIconW.argtypes = (wintypes.DWORD, ctypes.c_void_p)
        self._shell32.Shell_NotifyIconW.restype = wintypes.BOOL
        self._hwnd = None
        self._icon_handle = None
        self._wndproc = None  # 持有引用，防止 WINFUNCTYPE 被 GC 后回调段错误
        self._class_registered = False
        self._thread = None
        self._ready = threading.Event()
        self._error = None
        self._lock = threading.Lock()
        self._pending = []  # 托盘线程产出的命令（_CMD_*），等 Tk 侧 _drain 分发
        self._poll_id = None
        self._active = False

    # ---------------- Tk 主线程侧 ----------------
    def add(self):
        if self._active:
            return
        self._ready.clear()
        self._error = None
        self._thread = threading.Thread(target=self._run, name='tray-icon', daemon=True)
        self._thread.start()
        if not self._ready.wait(TRAY_THREAD_TIMEOUT_S) or self._hwnd is None:
            raise RuntimeError(self._error or '托盘窗口创建超时')
        self._active = True
        self._schedule_drain()

    def remove(self):
        if not self._active:
            return
        self._cancel_drain()
        self._active = False
        hwnd, self._hwnd = self._hwnd, None
        if hwnd:
            self._user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
        thread, self._thread = self._thread, None
        if thread is not None and thread is not threading.current_thread():
            thread.join(TRAY_THREAD_TIMEOUT_S)
        with self._lock:
            self._pending.clear()
        self._wndproc = None
        self._icon_handle = None

    def _schedule_drain(self):
        try:
            self._poll_id = self.window.after(TRAY_POLL_MS, self._drain)
        except tk.TclError:
            self._poll_id = None

    def _cancel_drain(self):
        if self._poll_id is not None:
            try:
                self.window.after_cancel(self._poll_id)
            except tk.TclError:
                pass
        self._poll_id = None

    def _drain(self):
        """在 Tk 事件循环里分发托盘命令；这是托盘消息唯一允许触发 Tk 调用的地方。"""
        self._poll_id = None
        if not self._active:
            return
        with self._lock:
            pending, self._pending = self._pending, []
        try:
            for command in pending:
                self._dispatch(command)
        finally:
            if self._active:
                self._schedule_drain()

    def _dispatch(self, command):
        if command == _CMD_RESTORE:
            self.on_restore()
        elif command == _CMD_RESTART:
            self.on_force_restart()
        elif command == _CMD_QUIT:
            self.on_quit()

    def _enqueue(self, command):
        if not command:
            return
        with self._lock:
            self._pending.append(command)

    # ---------------- 托盘线程侧 ----------------
    def _load_icon(self):
        if self.icon_path.is_file():
            handle = self._user32.LoadImageW(
                None, str(self.icon_path), IMAGE_ICON, 0, 0,
                LR_LOADFROMFILE | LR_DEFAULTSIZE)
            if handle:
                return handle
        return self._user32.LoadIconW(None, ctypes.c_wchar_p(IDI_APPLICATION))

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
            raise ctypes.WinError(ctypes.get_last_error())

    def _run(self):
        """托盘线程主体：建隐藏窗口、挂图标、跑消息循环，收到 WM_CLOSE 后收摊。"""
        user32 = self._user32
        hinstance = self._kernel32.GetModuleHandleW(None)
        hwnd = None
        try:
            self._wndproc = _WNDPROC(self._window_proc)
            wndclass = _WNDCLASSW()
            wndclass.lpfnWndProc = self._wndproc
            wndclass.hInstance = hinstance
            wndclass.lpszClassName = _WINDOW_CLASS
            if user32.RegisterClassW(ctypes.byref(wndclass)):
                self._class_registered = True
            elif ctypes.get_last_error() != ERROR_CLASS_ALREADY_EXISTS:
                raise ctypes.WinError(ctypes.get_last_error())
            hwnd = user32.CreateWindowExW(0, _WINDOW_CLASS, '漫剧助手托盘', 0,
                                          0, 0, 0, 0, None, None, hinstance, None)
            if not hwnd:
                raise ctypes.WinError(ctypes.get_last_error())
            self._hwnd = hwnd
            self._icon_handle = self._load_icon()
            self._notify(NIM_ADD)
        except Exception as exc:  # 建窗失败只报给 add()，不让线程异常刷屏
            self._error = f'{type(exc).__name__}: {exc}'
            self._hwnd = None
            if hwnd:
                user32.DestroyWindow(hwnd)
            self._ready.set()
            return
        self._ready.set()
        msg = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))
        if self._class_registered:
            user32.UnregisterClassW(_WINDOW_CLASS, hinstance)
            self._class_registered = False

    def _window_proc(self, hwnd, msg, wparam, lparam):
        # 只在托盘线程上被调用；这里绝不能碰 Tk。
        if msg == WM_TRAYICON:
            if lparam in (WM_LBUTTONUP, WM_LBUTTONDBLCLK):
                self._enqueue(_CMD_RESTORE)
            elif lparam == WM_RBUTTONUP:
                self._show_menu()
            return 0
        if msg == WM_CLOSE:
            try:
                self._notify(NIM_DELETE)
            except OSError:
                pass
            self._user32.DestroyWindow(hwnd)
            return 0
        if msg == WM_DESTROY:
            self._user32.PostQuitMessage(0)
            return 0
        return self._user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def _show_menu(self):
        """弹出托盘右键菜单，把用户选的命令压进队列（由 Tk 侧 _drain 执行）。返回命令号。"""
        user32 = self._user32
        menu = user32.CreatePopupMenu()
        if not menu:
            return 0
        command = 0
        try:
            user32.AppendMenuW(menu, MF_STRING, _CMD_RESTORE, '恢复窗口')
            user32.AppendMenuW(menu, MF_STRING, _CMD_RESTART, '强制重启')
            user32.AppendMenuW(menu, MF_SEPARATOR, 0, None)
            user32.AppendMenuW(menu, MF_STRING, _CMD_QUIT, '退出')
            # 关键：先把菜单属主窗口设为前台，菜单才会在点别处时正确收起；
            # 否则菜单僵住、图标可能被 Shell 移除。
            user32.SetForegroundWindow(self._hwnd)
            point = wintypes.POINT()
            user32.GetCursorPos(ctypes.byref(point))
            command = user32.TrackPopupMenu(
                menu, TPM_RIGHTBUTTON | TPM_RETURNCMD | TPM_NONOTIFY,
                point.x, point.y, 0, self._hwnd, None)
        finally:
            user32.DestroyMenu(menu)
            user32.PostMessageW(self._hwnd, WM_NULL, 0, 0)
        self._enqueue(command)
        return command


def force_restart():
    """杀进程并重开：先派一个脱离的辅助进程稍候拉起启动器，避开单实例互斥量竞态。

    托盘菜单命令在 Tk 主线程上执行，只在界面还活着时可用；主线程真卡死仍需修根因或看门狗。
    """
    helper = (
        "import subprocess,sys,time;"
        "time.sleep(0.8);"
        "subprocess.Popen([sys.argv[1],'-I',sys.argv[2]])"
    )
    # 走平台层统一的后台进程入口（无控制台窗口）；子进程不随本进程退出。
    platform_tools.launch_background([str(PYTHONW), '-c', helper, str(PYTHONW), str(LAUNCHER)])
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
            on_force_restart=self._force_restart_from_tray,
        )
        self.tray_icon.add()
        self.win.bind('<Unmap>', self._on_minimize_to_tray, add='+')
        self.win.bind('<Destroy>', self._on_tray_destroy, add='+')

    def _force_restart_from_tray(self):
        # 先摘图标再 os._exit，不然托盘会留一个鼠标划过才消失的幽灵图标。
        self.close_tray()
        force_restart()

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
    return sys.platform != 'win32'

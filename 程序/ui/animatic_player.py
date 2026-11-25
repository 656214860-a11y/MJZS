"""分镜预演页的原位影音播放。Windows Media Foundation 同步输出音画到 Tk 宿主 HWND。"""
import ctypes
import os
import time
from pathlib import Path
import tkinter as tk
from tkinter import ttk

import asset_thumbs
from ui_tokens import COLORS


class EmbeddedVideo:
    """持有一个 IMFPMediaPlayer；所有方法在创建 Tk 窗口的线程调用。"""

    # mfplay.h 中 IMFPMediaPlayerVtbl 的槽位，含 IUnknown 的三个方法。
    RELEASE, PLAY, PAUSE, STATE, UPDATE, SHUTDOWN = 2, 3, 4, 13, 32, 38
    PLAYING = 2

    def __init__(self, path, hwnd):
        if os.name != 'nt':
            raise OSError('当前系统没有 Windows 内嵌播放器')
        self.ptr = ctypes.c_void_p()
        self.ole = ctypes.windll.ole32
        result = self.ole.CoInitializeEx(None, 2)
        self.uninit = result in (0, 1)
        if result < 0 and result != -2147417850:  # RPC_E_CHANGED_MODE 表示线程已有 COM apartment。
            raise OSError('初始化播放器失败 (%#x)' % (result & 0xffffffff))
        try:
            create = ctypes.windll.mfplay.MFPCreateMediaPlayer
            create.argtypes = (ctypes.c_wchar_p, ctypes.c_int, ctypes.c_uint32, ctypes.c_void_p,
                               ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p))
            self._check(create(str(Path(path).resolve()), False, 0, None, hwnd, ctypes.byref(self.ptr)))
        except (AttributeError, OSError):
            self.close()
            raise

    @staticmethod
    def _check(result):
        if result < 0:
            raise OSError('播放失败 (%#x)' % (result & 0xffffffff))

    def _call(self, index, *args):
        table = ctypes.cast(self.ptr, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
        function = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, *(type(arg) for arg in args))
        return function(table[index])(self.ptr, *args)

    def state(self):
        state = ctypes.c_int()
        self._check(self._call(self.STATE, ctypes.pointer(state)))
        return state.value

    def toggle(self):
        self._check(self._call(self.PAUSE if self.state() == self.PLAYING else self.PLAY))

    def resize(self):
        self._call(self.UPDATE)

    def close(self):
        if self.ptr:
            self._call(self.SHUTDOWN)
            self._call(self.RELEASE)
            self.ptr = ctypes.c_void_p()
        if self.uninit:
            self.uninit = False
            self.ole.CoUninitialize()


class VideoPreview(tk.Frame):
    """点击或空格播放/暂停，离开页面释放视频与音轨。"""

    def __init__(self, master, path, status, context_menu):
        super().__init__(master, height=196, background=COLORS['background_card'], takefocus=True)
        self.pack_propagate(False)
        self.path, self.status, self.player = path, status, None
        self.ready_job = None
        self.cover = ttk.Label(self, text='播放分镜预演', compound='top', anchor='center')
        self.cover.image = asset_thumbs.media_thumbnail(self, path, size=160)
        if self.cover.image:
            self.cover.configure(image=self.cover.image)
        self.cover.pack(fill='both', expand=True)
        for target in (self, self.cover):
            target.bind('<Button-1>', self.toggle)
            target.bind('<Button-3>', context_menu)
        self.bind('<space>', self.toggle)
        self.bind('<Return>', self.toggle)
        self.bind('<Unmap>', self._release)
        self.bind('<Destroy>', self._release)
        self.bind('<Configure>', self._resize)
        self.bind('<Expose>', self._resize)

    def toggle(self, _event=None):
        self.focus_set()
        try:
            if self.player is None:
                self.player = EmbeddedVideo(self.path, self.winfo_id())
            self.player.toggle()
            if self.cover.winfo_manager() and self.ready_job is None:
                self._wait_for_picture(time.monotonic() + 6)
        except (AttributeError, OSError) as exc:
            self._release()
            self.status.set('无法在页面播放，可右键选择外部播放器。%s' % exc)
        return 'break'

    def _wait_for_picture(self, deadline):
        self.ready_job = None
        if self.player is None:
            return
        try:
            if self.player.state() in (2, 3):
                self.cover.pack_forget()
                return
            if time.monotonic() >= deadline:
                raise OSError('未能解码此视频')
            self.ready_job = self.after(60, self._wait_for_picture, deadline)
        except OSError as exc:
            self._release()
            self.status.set('无法在页面播放，可右键选择外部播放器。%s' % exc)

    def _resize(self, _event):
        if self.player is not None:
            self.player.resize()

    def _release(self, event=None):
        if event is not None and event.widget is not self:
            return
        if self.ready_job is not None:
            self.after_cancel(self.ready_job)
            self.ready_job = None
        if self.player is not None:
            self.player.close()
            self.player = None
            if event is None or event.type != tk.EventType.Destroy:
                self.cover.pack(fill='both', expand=True)


def fit_video_preview(view, state, metrics):
    default_height = getattr(view, '_animatic_default_height', 0)
    height = metrics.get('player_height') or default_height
    if height:
        view.configure(height=height)
    if state.get('video') is None:
        return
    adjusted = getattr(view, '_animatic_cover_adjusted', False)
    if metrics.get('player_height') is None and not adjusted:
        return
    image = asset_thumbs.media_thumbnail(view, state['video'], size=metrics['cover_size'])
    if image is not None:
        view.cover.image = image
        view.cover.configure(image=image)
    view._animatic_cover_adjusted = bool(metrics.get('player_height'))

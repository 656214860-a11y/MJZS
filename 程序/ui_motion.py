"""L4 微交互组件：表格行悬停淡入、加载转圈、空态提示。

只负责「动起来／空了怎么提示」；颜色、尺寸、节奏全部来自 ``ui_tokens``。
页面通过 ``ui_widgets.DataTable`` / ``BusyState`` 间接使用，普通 ``ttk.Treeview``
（如项目首页）可直接调用 ``bind_row_hover``。
"""
import os
import sys
import tkinter as tk
from tkinter import ttk

from ui_rounded import empty_icon_photo
from ui_tokens import (COLORS, EMPTY_ICON_LINE, EMPTY_ICON_SIZE, EMPTY_TEXT_GAP, RADIUS,
                       ROW_HOVER_FRAME_MS, ROW_HOVER_STEPS, ROW_HOVER_TAG, SPINNER_EXTENT,
                       SPINNER_FRAME_MS, SPINNER_MARGIN, SPINNER_SIZE, SPINNER_STEP, SPINNER_WIDTH)


REDUCE_MOTION_ENV = 'DRAMA_REDUCE_MOTION'   # '1' 强制减少动效，'0' 强制保留；不设则跟随系统
_SPI_GETCLIENTAREAANIMATION = 0x1042
_reduce_cache = None


def reduce_motion():
    """要不要省掉淡入淡出：环境变量优先，否则跟随 Windows「显示动画」（设置 → 辅助功能 → 视觉效果）。"""
    global _reduce_cache
    value = os.environ.get(REDUCE_MOTION_ENV)
    if value in ('0', '1'):
        return value == '1'
    if _reduce_cache is None:
        _reduce_cache = False
        if sys.platform == 'win32':
            try:
                import ctypes
                enabled = ctypes.c_int(1)
                if ctypes.windll.user32.SystemParametersInfoW(_SPI_GETCLIENTAREAANIMATION, 0,
                                                              ctypes.byref(enabled), 0):
                    _reduce_cache = not enabled.value
            except (AttributeError, OSError):
                _reduce_cache = False
    return _reduce_cache


def blend(start, end, ratio):
    """十六进制色在 start→end 之间按 ratio(0..1) 线性插值。"""
    a = [int(start[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(end[i:i + 2], 16) for i in (1, 3, 5)]
    return "#%02x%02x%02x" % tuple(round(x + (y - x) * ratio) for x, y in zip(a, b))


class RowHover:
    """给 ``ttk.Treeview`` 加鼠标划过的浅色高亮：背景在几帧内淡入，离开即撤。

    只加减一个标签，保留行上原有标签；选中行不加（选中色优先）。
    """

    def __init__(self, tree):
        self.tree = tree
        self.row = ""
        self._step = 0
        self._job = None
        self._base = self._field_background()
        tree.bind("<Motion>", self._moved, add="+")
        tree.bind("<Leave>", self._left, add="+")
        tree.bind("<<TreeviewSelect>>", self._clear, add="+")
        tree.bind("<Destroy>", self._destroyed, add="+")
        tree.tag_configure(ROW_HOVER_TAG, background=self._base)

    def _field_background(self):
        style = ttk.Style(self.tree)
        return (style.lookup(self.tree.cget("style") or "Treeview", "fieldbackground")
                or style.lookup("Treeview", "fieldbackground") or COLORS["background_card"])

    def _moved(self, event):
        row = self.tree.identify_row(event.y)
        if row == self.row:
            return
        self._clear()
        if row and row not in self.tree.selection():
            self.row = row
            self._tag(row, True)
            self._step = 0
            self._advance()

    def _left(self, _event=None):
        self._clear()

    def _tag(self, row, on):
        try:
            tags = [t for t in self.tree.item(row, "tags") if t != ROW_HOVER_TAG]
            self.tree.item(row, tags=tags + [ROW_HOVER_TAG] if on else tags)
        except tk.TclError:
            pass  # 行已被刷新删除

    def _advance(self):
        self._job = None
        self._step += 1
        try:
            self.tree.tag_configure(
                ROW_HOVER_TAG,
                background=blend(self._base, COLORS["surface_hover"], self._step / ROW_HOVER_STEPS))
            if self._step < ROW_HOVER_STEPS:
                self._job = self.tree.after(ROW_HOVER_FRAME_MS, self._advance)
        except tk.TclError:
            pass

    def _clear(self, _event=None):
        if self._job is not None:
            try:
                self.tree.after_cancel(self._job)
            except tk.TclError:
                pass
            self._job = None
        if self.row:
            self._tag(self.row, False)
            self.row = ""

    def _destroyed(self, event):
        if event.widget is self.tree:
            self._clear()


def bind_row_hover(tree):
    """幂等：同一棵树只装一次。"""
    hover = getattr(tree, "_row_hover", None)
    if hover is None:
        hover = tree._row_hover = RowHover(tree)
    return hover


class Spinner(tk.Canvas):
    """极简加载转圈：一段主色圆弧，每帧转 ``SPINNER_STEP`` 度；停止时不占事件循环。"""

    def __init__(self, master, background=None, host=None):
        # host：忙碌时叠放在该控件右端（place），停止即撤；背景随 host 的样式底色。
        self.host = host
        super().__init__(master, width=SPINNER_SIZE, height=SPINNER_SIZE, highlightthickness=0,
                         bd=0, bg=background or COLORS["background_primary"])
        inset = SPINNER_WIDTH
        box = (inset, inset, SPINNER_SIZE - inset, SPINNER_SIZE - inset)
        self.create_oval(*box, outline=COLORS["border_input"], width=SPINNER_WIDTH, tags="track")
        self.create_arc(*box, start=0, extent=SPINNER_EXTENT, style="arc",
                        outline=COLORS["primary"], width=SPINNER_WIDTH, tags="arc")
        self._angle = 0
        self._job = None
        self.bind("<Destroy>", lambda event: self.stop() if event.widget is self else None, add="+")

    @property
    def running(self):
        return self._job is not None

    def start(self, background=None):
        if self.host is not None:
            style = ttk.Style(self)
            background = background or style.lookup(self.host.cget("style"), "background")
            self.place(in_=self.host, relx=1.0, x=-SPINNER_MARGIN, rely=0.5, anchor="e")
            tk.Misc.lift(self)  # Canvas.lift 是画布图元的 tag_raise，这里要抬的是控件本身
        if background:
            self.configure(bg=background)
        if self._job is None:
            self._job = self.after(SPINNER_FRAME_MS, self._tick)

    def stop(self):
        if self.host is not None:
            try:
                self.place_forget()
            except tk.TclError:
                pass
        if self._job is not None:
            try:
                self.after_cancel(self._job)
            except tk.TclError:
                pass
            self._job = None

    def _tick(self):
        self._angle = (self._angle - SPINNER_STEP) % 360
        try:
            self.itemconfigure("arc", start=self._angle)
            self._job = self.after(SPINNER_FRAME_MS, self._tick)
        except tk.TclError:
            self._job = None


def empty_icon(widget):
    """空态图标（缓存在根窗口上，调用方无需自己保留引用）。"""
    return empty_icon_photo(widget._root(), EMPTY_ICON_SIZE, COLORS["surface_hover"],
                            COLORS["border_input"], EMPTY_ICON_LINE, RADIUS["lg"])


class EmptyState(ttk.Frame):
    """空列表提示：柔和图标＋一行文字，居中盖在列表上；``show(False)`` 即撤。"""

    def __init__(self, master, text, *, anchor_widget=None):
        super().__init__(master)
        self.anchor_widget = anchor_widget if anchor_widget is not None else master
        self.label = ttk.Label(self, text=text, style="Muted.TLabel", image=empty_icon(self),
                               compound="top", justify="center")
        self.label.pack(padx=EMPTY_TEXT_GAP, pady=EMPTY_TEXT_GAP)

    def set_text(self, text):
        self.label.configure(text=text)

    def show(self, visible=True):
        if visible:
            self.place(in_=self.anchor_widget, relx=0.5, rely=0.5, anchor="center")
            self.lift()
        else:
            self.place_forget()

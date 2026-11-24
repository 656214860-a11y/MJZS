"""L4 按钮悬停渐变：鼠标进出时底色在 ``HOVER_FADE_MS`` 内分 ``HOVER_FADE_STEPS`` 档淡入／淡出。

ttk 的 hover 是状态映射，一进 ``active`` 就瞬间换成悬停图。这里的做法：进出的那一刻把按钮临时
切到派生样式 ``Fade<k>.<原样式>``（继承原样式的字体、内边距、文字色映射），派生样式的底图是
「常态色→悬停色」之间第 k 档的混色圆角图（只保留按下、禁用两态的原图，按下反馈不丢）；
每档停 ``HOVER_FADE_MS / HOVER_FADE_STEPS`` 毫秒，走完立即还原成原样式，由原样式的 active/!active
映射给出最终颜色。

* 混色图与派生样式按需生成并缓存在根窗口上；一个样式至多多出 STEPS+1 张小图，从不预建。
* 动画期间别处改了该按钮的 ``style``（如导航选中态切换）、按钮被禁用或销毁：立即停，
  不覆盖别人写的样式。
* 中途反向（进入未完又离开）从当前档继续；定时器随控件销毁取消，静止时不占事件循环。
* 只对登记过圆角规格的 ``ttk.Button`` 样式生效，其它按钮（含未登记样式）保持原行为。
"""
import tkinter as tk


from ui.ui_motion import blend, reduce_motion
from ui.ui_rounded import button_specs, rounded_layout, rounded_photo
from ui_tokens import BUTTON_RADIUS, HOVER_FADE_MS, HOVER_FADE_STEPS, current_theme


def _derived(base, level):
    return "Fade%d.%s" % (level, base)


def _ensure_level_style(widget, base, level):
    """第 level 档派生样式（0=常态色，STEPS=悬停色）；按当前主题区分图元，切回日间不沿用夜间旧图。"""
    from tkinter import ttk
    root = widget._root()
    spec = button_specs(root)[base]
    name = _derived(base, level)
    style = ttk.Style(root)
    element = "Drama.RoundedFade%d.%s.%s" % (level, current_theme(), base.replace(".", "_"))
    bound = getattr(root, "_drama_fade_bound", None)
    if bound is None:
        bound = root._drama_fade_bound = {}
    if element not in style.element_names():
        colors = spec["colors"]
        tile_w, tile_h = spec["size"]
        border, border_width = spec["border"]
        mixed = blend(colors["normal"], colors["active"], level / HOVER_FADE_STEPS)
        image, pr = rounded_photo(root, mixed, BUTTON_RADIUS,
                                  width=BUTTON_RADIUS * 2 + tile_w, height=BUTTON_RADIUS * 2 + tile_h,
                                  border=border, border_width=border_width)
        style.element_create(element, "image", image,
                             ("pressed", spec["images"]["pressed"]),
                             ("disabled", spec["images"]["disabled"]),
                             border=(pr, pr, pr, pr), padding=(0, 0, 0, 0),
                             width=1, height=1, sticky="nsew")
    if bound.get(name) != element:
        rounded_layout(style, name, element)
        bound[name] = element
    return name


class _Fade:
    def __init__(self, widget):
        self.widget = widget
        self.job = None
        self.base = None
        self.level = 0
        self.direction = 0
        self.expected = None
        widget.bind("<Destroy>", self._destroyed, add="+")

    def go(self, direction):
        widget = self.widget
        if reduce_motion():
            return                          # 减少动效：不走渐变，由 active 映射直接给出悬停色
        if direction > 0 and widget.instate(["disabled"]):
            return
        if self.job is not None:
            # 动画进行中反向：沿用当前档，只换方向；样式被别处改过就放弃。
            if str(widget.cget("style")) != self.expected:
                self.stop(restore=False)
                return
            self.direction = direction
            return
        base = str(widget.cget("style") or "TButton")
        if base not in button_specs(widget._root()):
            return
        self.base = base
        self.direction = direction
        self.level = 0 if direction > 0 else HOVER_FADE_STEPS
        self._show()
        self.job = widget.after(max(1, HOVER_FADE_MS // HOVER_FADE_STEPS), self._tick)

    def _show(self):
        name = _ensure_level_style(self.widget, self.base, self.level)
        self.expected = name
        self.widget.configure(style=name)

    def _tick(self):
        self.job = None
        widget = self.widget
        try:
            if str(widget.cget("style")) != self.expected:
                self.stop(restore=False)  # 别处改了样式：不覆盖
                return
            if widget.instate(["disabled"]):
                self.stop(restore=True)
                return
            self.level += self.direction
            if self.level >= HOVER_FADE_STEPS or self.level <= 0:
                self.stop(restore=True)  # 到端：还原原样式，由 active 映射给出最终色
                return
            self._show()
            self.job = widget.after(max(1, HOVER_FADE_MS // HOVER_FADE_STEPS), self._tick)
        except tk.TclError:
            self.job = None

    def stop(self, restore):
        job, self.job = self.job, None
        if job is not None:
            try:
                self.widget.after_cancel(job)
            except tk.TclError:
                pass
        if restore and self.base is not None:
            try:
                self.widget.configure(style=self.base)
            except tk.TclError:
                pass
        self.expected = None

    def _destroyed(self, event):
        if event.widget is self.widget:
            self.stop(restore=False)


def _fade(widget):
    fade = getattr(widget, "_hover_fade", None)
    if fade is None:
        fade = widget._hover_fade = _Fade(widget)
    return fade


def _enter(event):
    widget = event.widget
    if isinstance(widget, str):
        return
    try:
        _fade(widget).go(+1)
    except tk.TclError:
        pass


def _leave(event):
    widget = event.widget
    if isinstance(widget, str) or getattr(widget, "_hover_fade", None) is None:
        return
    try:
        widget._hover_fade.go(-1)
    except tk.TclError:
        pass


def install_hover_fade(root):
    """幂等：给所有 ``ttk.Button``（类绑定 TButton）装进出渐变。"""
    if getattr(root, "_drama_hover_fade", False):
        return
    root._drama_hover_fade = True
    root.bind_class("TButton", "<Enter>", _enter, add="+")
    root.bind_class("TButton", "<Leave>", _leave, add="+")

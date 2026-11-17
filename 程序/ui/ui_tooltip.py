# -*- coding: utf-8 -*-
"""统一悬停浮层 Tooltip／TreeRowTooltip（L4，自 ui_widgets 拆出；``ui_widgets`` 仍转出同名符号）。

R2997 起从「一次性弹出框」升级为完整悬停状态机（蓝本：ttkbootstrap widgets/tooltip.py，MIT；
reshow／grace 语义参考 Radix Tooltip/HoverCard，数值登记在 ``ui_tokens``）：排程先取消旧计时
器、tip 移出立即隐藏、card 移出 ``close_delay_ms`` 后隐藏并复核指针、关闭后 ``reshow_ms`` 窗口
内再进入跳过延迟；点击不拦原动作但抑制重弹直到指针离开再进入；卡片模式可 ``pin_on_click``
点击钉住（钉住期间悬停不触发，点空白处／Escape／再点解除）。所有浮层都过
``make_passive_popup``：不抢 grab、不抢焦点，R1976/R1982「卡片被自己收掉／反复弹出」一类
问题不再复发。
"""
import time
import tkinter as tk

from ui.ui_popup import make_passive_popup, monitor_bounds
from ui_tokens import (TOOLTIP_BACKGROUND, TOOLTIP_BORDER, TOOLTIP_BORDER_WIDTH,
                       TOOLTIP_CLOSE_DELAY_MS, TOOLTIP_DELAY_MS, TOOLTIP_FONT,
                       TOOLTIP_FOREGROUND, TOOLTIP_OFFSET, TOOLTIP_PADDING,
                       TOOLTIP_RESHOW_MS, TOOLTIP_WRAPLENGTH)

# 同一时刻只留一张可见卡片：新卡显示前 withdraw 旧卡（R2993 漏洞 21：多实例叠窗）。
_VISIBLE_TIP = None

# Tooltip 的可选项关键字集合：__init__ 收 **opts（参数棘轮），未知关键字照旧 TypeError。
_TOOLTIP_OPTION_KEYS = frozenset((
    'delay_ms', 'mode', 'close_delay_ms', 'reshow_ms',
    'pin_on_click', 'wraplength', 'place'))


def _set_visible(tip):
    """登记当前可见浮层；旧的先 withdraw，不抢事件、不叠加。"""
    global _VISIBLE_TIP
    if _VISIBLE_TIP is not None and _VISIBLE_TIP is not tip:
        try:
            if _VISIBLE_TIP.winfo_exists():
                _VISIBLE_TIP.withdraw()
        except tk.TclError:
            pass
    _VISIBLE_TIP = tip


def _is_descendant(widget, ancestor):
    while widget is not None:
        if widget is ancestor:
            return True
        widget = getattr(widget, 'master', None)
    return False


class Tooltip:
    """统一的短说明浮层，鼠标和键盘焦点都可触发且不会取得输入 grab。

    ``mode='tip'``（默认）：纯文字短说明——出现延迟 ``delay_ms``，移出立即隐藏，点击控件
    执行原动作并抑制重弹，直到指针离开再进入。``mode='card'``：悬停卡片——移出后
    ``close_delay_ms`` 才隐藏（期间指针进入卡片或回到控件即保留）；``pin_on_click=True``
    时点击控件在「钉住常驻／解除」之间切换，点空白处、Escape 或再点控件解除。``place`` 可
    传自定义定位回调 ``(tip) -> (x, y)``（仍按所在显示器钳位），默认指针＋偏移。
    """

    def __init__(self, widget, text, **opts):
        unknown = sorted(set(opts) - _TOOLTIP_OPTION_KEYS)
        if unknown:
            raise TypeError('__init__() got an unexpected keyword argument %r' % unknown[0])
        self.widget = widget
        self.text = str(text or "")
        self.delay_ms = opts.get('delay_ms', TOOLTIP_DELAY_MS)
        self.mode = opts.get('mode', 'tip')
        self.close_delay_ms = opts.get('close_delay_ms', TOOLTIP_CLOSE_DELAY_MS)
        self.reshow_ms = opts.get('reshow_ms', TOOLTIP_RESHOW_MS)
        self.pin_on_click = opts.get('pin_on_click', False)
        self.wraplength = opts.get('wraplength', TOOLTIP_WRAPLENGTH)
        self.place = opts.get('place')
        self.pinned = False
        self._job = None            # 待执行的显示回调
        self._hide_job = None       # 待执行的隐藏回调（card 的 closeDelay）
        self._window = None
        self._label = None
        self._position = None
        self._suppress = False      # 点击后抑制重弹，直到指针离开／失焦
        self._closed_at = None      # 上次隐藏时刻（monotonic），reshow 窗口判定
        self._pin_binds = ()        # (root, press_funcid, escape_funcid)
        widget.bind("<Enter>", self._schedule_from_pointer, add="+")
        widget.bind("<Leave>", self._leave, add="+")
        widget.bind("<FocusIn>", self._schedule_from_focus, add="+")
        widget.bind("<FocusOut>", self._focus_out, add="+")
        widget.bind("<Button-1>", self._press, add="+")
        widget.bind("<Destroy>", self._on_widget_destroyed, add="+")

    # ── 事件入口 ─────────────────────────────────────────────
    def _schedule_from_pointer(self, event):
        self._position = (event.x_root + TOOLTIP_OFFSET,
                          event.y_root + TOOLTIP_OFFSET)
        self.schedule()

    def _schedule_from_focus(self, _event=None):
        try:
            self._position = (self.widget.winfo_rootx() + TOOLTIP_OFFSET,
                              self.widget.winfo_rooty() + self.widget.winfo_height()
                              + TOOLTIP_OFFSET)
        except tk.TclError:
            return
        self.schedule()

    def _leave(self, _event=None):
        self._suppress = False      # 指针离开＝一次交互结束，恢复悬停
        if self.pinned:
            return                  # 钉住期间悬停不触发
        self._cancel_jobs()
        if self.mode == 'card' and self._window is not None:
            self._arm_hide(self.close_delay_ms)
        else:
            self.hide()

    def _focus_out(self, _event=None):
        self._suppress = False
        if not self.pinned:
            self.hide()

    def _press(self, _event=None):
        """点击不拦原动作；抑制重弹直到离开；卡片模式可切换钉住。"""
        self._suppress = True
        if self.mode == 'card' and self.pin_on_click:
            if self.pinned:
                self.unpin()
            else:
                self.pin()
            return
        self.hide()

    # ── 排程与状态机 ─────────────────────────────────────────
    def schedule(self):
        """延迟显示；重复进入只留最新一次；抑制／钉住期间不排程。"""
        if not self.text or self.pinned or self._suppress:
            return
        self._cancel_jobs()
        if self._window is not None:
            self.refresh()
            return
        if self._closed_at is not None and time.monotonic() - self._closed_at <= self.reshow_ms:
            self.show()             # reshow 窗口：跳过延迟立即显示
            return
        try:
            self._job = self.widget.after(self.delay_ms, self.show)
        except tk.TclError:
            self._job = None

    def show(self):
        self._job = None
        self._cancel_hide()
        if self._window is not None:
            self.refresh()
            return self._window
        if not self.text or self._suppress:
            return None
        tip = None
        try:
            if not self.widget.winfo_exists():
                return None
            tip = tk.Toplevel(self.widget)
            tip.overrideredirect(True)
            make_passive_popup(tip)
            tip.configure(background=TOOLTIP_BORDER)
            self._label = self._populate(tip)
            if self.place is not None:
                x, y = self.place(tip)
            else:
                x, y = self._position or (self.widget.winfo_rootx() + TOOLTIP_OFFSET,
                                          self.widget.winfo_rooty() + TOOLTIP_OFFSET)
            # 贴近屏幕底边／右边的控件（如页面底部状态栏）改向上／向左展开，浮层不出屏。
            try:
                tip.update_idletasks()
                width, height = tip.winfo_reqwidth(), tip.winfo_reqheight()
                # 按鼠标（或控件）所在显示器钳位：软件在副屏时不能拿主屏尺寸去夹。
                left, top, right, bottom = monitor_bounds(tip, x, y)
                if y + height > bottom:
                    y = max(top, y - height - 2 * TOOLTIP_OFFSET)
                x = max(left, min(x, right - width))
            except AttributeError:
                pass        # 测试替身不提供几何查询时保持原定位。
            tip.geometry("+%d+%d" % (x, y))
            self._window = tip
            if self.mode == 'card':
                tip.bind("<Enter>", self._card_enter, add="+")
                tip.bind("<Leave>", self._card_leave, add="+")
            if self.pinned:
                self._arm_pin_binds()
            _set_visible(tip)
            return tip
        except tk.TclError:
            if tip is not None:
                try:
                    tip.destroy()
                except tk.TclError:
                    pass
            return None

    def refresh(self):
        """可见时按当前文本刷新并重新显形（可能被别的卡片 withdraw 过）。"""
        if self._window is None:
            return
        try:
            if not self._window.winfo_exists():
                self._window = None
                self._label = None
                return
            if self._label is not None:
                self._label.configure(text=self.text)
            self._window.deiconify()
            _set_visible(self._window)
        except tk.TclError:
            pass

    def hide(self, _event=None):
        self._cancel_jobs()
        if not self.pinned:
            self._closed_at = time.monotonic()
        tip, self._window = self._window, None
        self._label = None
        global _VISIBLE_TIP
        if _VISIBLE_TIP is tip:
            _VISIBLE_TIP = None
        if tip is not None:
            try:
                if tip.winfo_exists():
                    tip.destroy()
            except tk.TclError:
                pass

    def _arm_hide(self, delay):
        self._cancel_hide()
        try:
            self._hide_job = self.widget.after(delay, self._hide_after_grace)
        except tk.TclError:
            self._hide_job = None

    def _hide_after_grace(self):
        self._hide_job = None
        if self.pinned or self._window is None:
            return
        if self._pointer_over(self.widget) or self._pointer_over(self._window):
            return      # 指针在控件或卡片上：保留，等下一次 Leave
        self.hide()

    def _pointer_over(self, target):
        try:
            x, y = self.widget.winfo_pointerxy()
            w = self.widget.winfo_containing(x, y)
        except (tk.TclError, KeyError):
            return False
        return w is not None and (w is target or _is_descendant(w, target))

    def _card_enter(self, _event=None):
        if not self.pinned:
            self._cancel_hide()

    def _card_leave(self, _event=None):
        if not self.pinned and self._window is not None:
            self._arm_hide(self.close_delay_ms)

    # ── 钉住 ─────────────────────────────────────────────────
    def pin(self):
        self.pinned = True
        self._suppress = False
        self._cancel_jobs()
        self.show()
        if self._window is not None:
            self._arm_pin_binds()

    def unpin(self):
        self.pinned = False
        self._release_pin_binds()
        self.hide()

    def _arm_pin_binds(self):
        if self._pin_binds:
            return
        try:
            root = self.widget.winfo_toplevel()
        except tk.TclError:
            return
        press = root.bind("<Button-1>", self._pin_outside_press, add="+")
        escape = root.bind("<Escape>", self._pin_escape, add="+")
        # 焦点可能在浮层窗口上（按键事件只经焦点窗口的 bindtags），浮层上也挂一条 Escape。
        win = self._window
        if win is not None:
            try:
                win.bind("<Escape>", self._pin_escape, add="+")
            except tk.TclError:
                pass
        self._pin_binds = (root, press, escape)

    def _release_pin_binds(self):
        if not self._pin_binds:
            return
        root, press, escape = self._pin_binds
        self._pin_binds = ()
        for seq, funcid in (("<Button-1>", press), ("<Escape>", escape)):
            try:
                root.unbind(seq, funcid)
            except tk.TclError:
                pass

    def _pin_outside_press(self, event):
        w = None
        try:
            w = event.widget.winfo_containing(event.x_root, event.y_root)
        except (tk.TclError, KeyError):
            pass
        if w is not None and (_is_descendant(w, self.widget)
                              or (self._window is not None
                                  and _is_descendant(w, self._window))):
            return      # 点在控件或卡片上：放行
        self.unpin()

    def _pin_escape(self, _event=None):
        if self.pinned:
            self.unpin()
            return "break"
        return None

    # ── 窗口与生命周期 ───────────────────────────────────────
    def _populate(self, tip):
        """浮层内容；子类（预览卡片）重写，边框与定位仍由 show 统一处理。返回文本标签供刷新。"""
        label = tk.Label(tip, text=self.text, font=TOOLTIP_FONT,
                         fg=TOOLTIP_FOREGROUND, bg=TOOLTIP_BACKGROUND,
                         padx=TOOLTIP_PADDING[0], pady=TOOLTIP_PADDING[1],
                         wraplength=self.wraplength, justify="left")
        label.pack(padx=TOOLTIP_BORDER_WIDTH, pady=TOOLTIP_BORDER_WIDTH)
        return label

    def _cancel_jobs(self):
        self._cancel_job()
        self._cancel_hide()

    def _cancel_job(self):
        if self._job is None:
            return
        try:
            self.widget.after_cancel(self._job)
        except tk.TclError:
            pass
        self._job = None

    def _cancel_hide(self):
        if self._hide_job is None:
            return
        try:
            self.widget.after_cancel(self._hide_job)
        except tk.TclError:
            pass
        self._hide_job = None

    def _on_widget_destroyed(self, _event=None):
        self.pinned = False
        self.hide()


class TreeRowTooltip(Tooltip):
    """树表逐行说明；调用方提供已加载的数据，悬停不读磁盘。"""

    def __init__(self, tree, text_for):
        self.text_for = text_for
        self._row = None
        super().__init__(tree, '')
        tree.bind('<Motion>', self._schedule_from_pointer, add='+')
        tree.bind('<MouseWheel>', self.hide, add='+')

    def _schedule_from_pointer(self, event):
        row = self.widget.identify_row(event.y)
        text = str(self.text_for(row) or '') if row else ''
        if row == self._row and text == self.text and (self._job or self._window):
            return
        self.hide()
        self._row, self.text = row, text
        super()._schedule_from_pointer(event)

    def _schedule_from_focus(self, event=None):
        selected = self.widget.selection()
        self.text = str(self.text_for(selected[0]) or '') if selected else ''
        super()._schedule_from_focus(event)

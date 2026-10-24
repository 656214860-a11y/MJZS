"""统一短说明浮层 Tooltip／TreeRowTooltip（L4，自 ui_widgets 拆出；``ui_widgets`` 仍转出同名符号）。"""
import tkinter as tk
from ui_popup import make_passive_popup, monitor_bounds
from ui_tokens import TOOLTIP_BACKGROUND, TOOLTIP_BORDER, TOOLTIP_BORDER_WIDTH, TOOLTIP_DELAY_MS, TOOLTIP_FONT, TOOLTIP_FOREGROUND, TOOLTIP_OFFSET, TOOLTIP_PADDING, TOOLTIP_WRAPLENGTH


class Tooltip:
    """统一的短说明浮层，鼠标和键盘焦点都可触发且不会取得输入 grab。"""

    def __init__(self, widget, text, *, delay_ms=TOOLTIP_DELAY_MS):
        self.widget = widget
        self.text = str(text or "")
        self.delay_ms = delay_ms
        self._job = None
        self._window = None
        self._position = None
        widget.bind("<Enter>", self._schedule_from_pointer, add="+")
        widget.bind("<Leave>", self.hide, add="+")
        widget.bind("<FocusIn>", self._schedule_from_focus, add="+")
        widget.bind("<FocusOut>", self.hide, add="+")
        widget.bind("<Destroy>", self._on_widget_destroyed, add="+")

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

    def schedule(self):
        """延迟显示；重复进入只保留最新的一次回调。"""
        if not self.text:
            return
        self._cancel_job()
        try:
            self._job = self.widget.after(self.delay_ms, self.show)
        except tk.TclError:
            self._job = None

    def show(self):
        self._job = None
        if self._window is not None or not self.text:
            return self._window
        try:
            if not self.widget.winfo_exists():
                return None
            tip = tk.Toplevel(self.widget)
            tip.overrideredirect(True)
            make_passive_popup(tip)
            tip.configure(background=TOOLTIP_BORDER)
            self._populate(tip)
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
                pass  # 测试替身不提供几何查询时保持原定位。
            tip.geometry("+%d+%d" % (x, y))
            self._window = tip
            return tip
        except tk.TclError:
            try:
                tip.destroy()
            except (UnboundLocalError, tk.TclError):
                pass
            return None

    def _populate(self, tip):
        """浮层内容；子类（预览卡片）重写，边框与定位仍由 show 统一处理。"""
        label = tk.Label(tip, text=self.text, font=TOOLTIP_FONT,
                         fg=TOOLTIP_FOREGROUND, bg=TOOLTIP_BACKGROUND,
                         padx=TOOLTIP_PADDING[0], pady=TOOLTIP_PADDING[1],
                         wraplength=TOOLTIP_WRAPLENGTH, justify="left")
        label.pack(padx=TOOLTIP_BORDER_WIDTH, pady=TOOLTIP_BORDER_WIDTH)

    def _cancel_job(self):
        if self._job is None:
            return
        try:
            self.widget.after_cancel(self._job)
        except tk.TclError:
            pass
        self._job = None

    def hide(self, _event=None):
        self._cancel_job()
        tip, self._window = self._window, None
        if tip is not None:
            try:
                tip.destroy()
            except tk.TclError:
                pass

    def _on_widget_destroyed(self, _event=None):
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
        if row == self._row and text == self.text and (self._job or self._window):return
        self.hide()
        self._row, self.text = row, text
        super()._schedule_from_pointer(event)

    def _schedule_from_focus(self, event=None):
        selected = self.widget.selection()
        self.text = str(self.text_for(selected[0]) or '') if selected else ''
        super()._schedule_from_focus(event)

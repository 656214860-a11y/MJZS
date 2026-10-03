"""遵循 ui_components.md 的 Tk 组件入口。"""
import tkinter as tk
from tkinter import messagebox, ttk

from ui_tokens import (COLORS, COMBOBOX_ARROW_COLOR, COMBOBOX_FIELD_BACKGROUND,
                       COMBOBOX_FONT, COMBOBOX_FOREGROUND, COMBOBOX_PADDING,
                       COMBOBOX_WIDTH, FONTS, SPACING, TEXT_DESC, TEXT_HINT,
                       TEXT_PROGRESS, DIALOG_ACTION_GAP, DIALOG_ACTION_HEIGHT,
                       DIALOG_CONTENT_PADDING, DIALOG_TITLE_FONT,
                       TOOLTIP_BACKGROUND, TOOLTIP_BORDER, TOOLTIP_BORDER_WIDTH, TOOLTIP_DELAY_MS,
                       TOOLTIP_FONT, TOOLTIP_FOREGROUND, TOOLTIP_OFFSET,
                       TOOLTIP_PADDING,
                       TABLE_EMPTY_PADDING, TABLE_HEADER_FONT, TABLE_ROW_FONT,
                       TABLE_ROW_HEIGHT, INPUT_BACKGROUND, INPUT_BORDER,
                       INPUT_BORDER_WIDTH, INPUT_ERROR_BORDER, INPUT_FONT,
                       INPUT_FOREGROUND, INPUT_PADDING_X, INPUT_PADDING_Y,
                       INPUT_PLACEHOLDER_FOREGROUND)


def setup_styles(root):
    """Install the compact, readable button styles shared by every Tk page.

    ``ttk.Style`` is scoped to the root Tcl interpreter, so configuring it once
    after the application theme also covers legacy direct ``ttk.Button`` calls.
    """
    style = ttk.Style(root)
    button_options = {
        "font": FONTS["body"],
        "padding": (SPACING["md"], SPACING["xs"]),
    }
    active_map = {
        "background": [("active", COLORS["primary_subtle"]),
                       ("disabled", COLORS["border_default"])],
        "foreground": [("active", COLORS["primary"]),
                       ("disabled", COLORS["text_muted"])],
    }

    style.configure("TButton", **button_options)
    style.map("TButton", **active_map)
    style.configure("Primary.TButton", background=COLORS["primary"],
                    foreground=COLORS["background_card"], borderwidth=1,
                    **button_options)
    style.map("Primary.TButton", **active_map)
    style.configure("Secondary.TButton", background=COLORS["background_card"],
                    foreground=COLORS["text_primary"], borderwidth=1,
                    **button_options)
    style.map("Secondary.TButton", **active_map)

    style.configure("Tokens.Primary.TButton", background=COLORS["primary"],
                    foreground=COLORS["background_card"], font=FONTS["body"],
                    padding=(SPACING["md"], SPACING["xs"]), borderwidth=1)
    style.map("Tokens.Primary.TButton",
              background=[("active", COLORS["primary_subtle"]),
                          ("disabled", COLORS["border_default"])],
              # 浅色悬停底必须切回主色文字；保留白字会使标签近乎不可见。
              foreground=[("active", COLORS["primary"]),
                          ("disabled", COLORS["text_muted"])])
    style.configure("Tokens.Secondary.TButton", background=COLORS["background_card"],
                    foreground=COLORS["text_primary"], font=FONTS["body"],
                    padding=(SPACING["md"], SPACING["xs"]), borderwidth=1)
    style.map("Tokens.Secondary.TButton",
              background=[("active", COLORS["primary_subtle"]),
                          ("disabled", COLORS["border_default"])],
              foreground=[("active", COLORS["primary"]),
                          ("disabled", COLORS["text_muted"])])
    style.configure("Tokens.Danger.TButton", background=COLORS["danger"],
                    foreground=COLORS["background_card"], font=FONTS["body"],
                    padding=(SPACING["md"], SPACING["xs"]), borderwidth=1)
    style.map("Tokens.Danger.TButton",
              background=[("active", COLORS["primary_subtle"]),
                          ("disabled", COLORS["border_default"])],
              foreground=[("active", COLORS["danger"]),
                          ("disabled", COLORS["text_muted"])])
    style.configure("Tokens.Card.TFrame", background=COLORS["background_card"],
                    bordercolor=COLORS["border_default"], borderwidth=1, relief="solid")
    style.configure("Tokens.Title.TLabel", font=FONTS["title"],
                    foreground=COLORS["text_primary"])
    style.configure("Tokens.Dialog.Title.TLabel", font=DIALOG_TITLE_FONT,
                    foreground=COLORS["text_primary"])
    style.configure("Tokens.DataTable.Treeview", font=TABLE_ROW_FONT,
                    rowheight=TABLE_ROW_HEIGHT,
                    background=COLORS["background_card"],
                    fieldbackground=COLORS["background_card"],
                    foreground=COLORS["text_primary"])
    style.configure("Tokens.DataTable.Treeview.Heading", font=TABLE_HEADER_FONT,
                    foreground=COLORS["text_primary"])
    input_options = {
        "font": INPUT_FONT,
        "foreground": INPUT_FOREGROUND,
        "fieldbackground": INPUT_BACKGROUND,
        "background": INPUT_BACKGROUND,
        "bordercolor": INPUT_BORDER,
        "padding": (INPUT_PADDING_X, INPUT_PADDING_Y),
    }
    style.configure("Tokens.LineInput.TEntry", **input_options)
    placeholder_options = dict(input_options, foreground=INPUT_PLACEHOLDER_FOREGROUND)
    style.configure("Tokens.LineInput.Placeholder.TEntry", **placeholder_options)
    error_options = dict(input_options, bordercolor=INPUT_ERROR_BORDER)
    style.configure("Tokens.LineInput.Error.TEntry", **error_options)

    # TCombobox 的唯一权威样式入口：所有页面与弹窗共用，不在业务页复制视觉参数。
    combo_options = {
        "fieldbackground": COMBOBOX_FIELD_BACKGROUND,
        "background": COMBOBOX_FIELD_BACKGROUND,
        "foreground": COMBOBOX_FOREGROUND,
        "font": COMBOBOX_FONT,
        "padding": COMBOBOX_PADDING,
        "bordercolor": COLORS["border_default"],
    }
    style.configure("TCombobox", **combo_options)
    style.map("TCombobox",
              fieldbackground=[("readonly", COMBOBOX_FIELD_BACKGROUND),
                               ("disabled", COLORS["border_default"])],
              foreground=[("disabled", COLORS["text_muted"])])
    # ttk 的箭头色是 Tcl 层的主题选项；不支持该选项的旧主题安全忽略，
    # 其余视觉规格仍由上面的标准 Style 配置统一。
    try:
        root.tk.call("ttk::style", "configure", "TCombobox",
                     "-arrowcolor", COMBOBOX_ARROW_COLOR)
    except Exception:
        pass
    # Popdown Listbox 不属于 ttk Style，须在同一入口通过 option database 统一。
    root.option_add("*TCombobox*Listbox.font", COMBOBOX_FONT)
    root.option_add("*TCombobox*Listbox.background", COMBOBOX_FIELD_BACKGROUND)
    root.option_add("*TCombobox*Listbox.foreground", COMBOBOX_FOREGROUND)
    root.option_add("*TCombobox*Listbox.selectBackground", COLORS["primary"])
    root.option_add("*TCombobox*Listbox.selectForeground", COLORS["background_card"])
    root.option_add("*TCombobox.width", COMBOBOX_WIDTH)


class DataTable(ttk.Frame):
    """统一的可滚动表格壳；页面只提供列、数据和领域内的单元格行为。"""

    def __init__(self, master, *, columns, height=4, selectmode="browse",
                 show="headings", empty_text="暂无数据", on_select=None,
                 auto_hide_scrollbars=False, **kwargs):
        setup_styles(master)
        # 表格壳只负责表格本身，不能成为业务页的一张额外 Card；
        # 页面已有 Card 时保留其原有信息层级和间距。
        super().__init__(master)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self._sort_descending = {}
        tree_style = kwargs.pop("style", "Tokens.DataTable.Treeview")
        self.tree = ttk.Treeview(
            self, columns=[column[0] for column in columns], show=show,
            height=height, selectmode=selectmode, style=tree_style,
            **kwargs)
        self.vertical_scrollbar = ttk.Scrollbar(self, orient="vertical",
                                                command=self.tree.yview)
        self.horizontal_scrollbar = ttk.Scrollbar(self, orient="horizontal",
                                                  command=self.tree.xview)
        self._auto_hide_scrollbars = auto_hide_scrollbars
        self.tree.configure(
            yscrollcommand=lambda first, last: self._scroll_state(
                self.vertical_scrollbar, first, last),
            xscrollcommand=lambda first, last: self._scroll_state(
                self.horizontal_scrollbar, first, last))
        self.tree.grid(row=0, column=0, sticky="nsew")
        self.vertical_scrollbar.grid(row=0, column=1, sticky="ns")
        self.horizontal_scrollbar.grid(row=1, column=0, sticky="ew")
        self.empty_label = ttk.Label(self, text=empty_text, style="Muted.TLabel",
                                     padding=TABLE_EMPTY_PADDING)
        self.empty_label.grid(row=0, column=0, sticky="nsew")
        self.empty_label.lift()
        for name, label, width in columns:
            self.tree.heading(name, text=label,
                              command=lambda column=name: self.sort_by(column))
            self.tree.column(name, width=width, minwidth=0, stretch=True)
        self.tree.bind("<<TreeviewSelect>>", self._selected, add="+")
        self.tree.bind("<Map>", lambda _event: self.refresh_empty_state(), add="+")
        # 兼容仍接收 Treeview 的页面 API，同时让填表函数能刷新统一空态。
        self.tree._data_table = self
        self._on_select = on_select
        self.refresh_empty_state()

    def _selected(self, _event=None):
        if self._on_select is not None:
            self._on_select(self.selected_items())

    def selected_items(self):
        return self.tree.selection()

    def refresh_empty_state(self):
        if self.tree.get_children():
            self.empty_label.grid_remove()
        else:
            self.empty_label.grid()

    def _scroll_state(self, scrollbar, first, last):
        scrollbar.set(first, last)
        if not self._auto_hide_scrollbars:
            return
        if float(first) <= 0 and float(last) >= 1:
            scrollbar.grid_remove()
        else:
            scrollbar.grid()

    def sort_by(self, column):
        """按显示文本排序；领域页可覆写 heading 命令实现专用排序。"""
        descending = self._sort_descending.get(column, False)
        rows = [(str(self.tree.set(item, column)), item)
                for item in self.tree.get_children("")]
        rows.sort(key=lambda row: row[0], reverse=descending)
        for index, (_value, item) in enumerate(rows):
            self.tree.move(item, "", index)
        self._sort_descending[column] = not descending


class LineInput(ttk.Entry):
    """单行文本入口，统一占位、只读和错误态而不改变 Entry 的取值语义。"""

    NORMAL_STYLE = "Tokens.LineInput.TEntry"
    PLACEHOLDER_STYLE = "Tokens.LineInput.Placeholder.TEntry"
    ERROR_STYLE = "Tokens.LineInput.Error.TEntry"

    def __init__(self, master=None, *, placeholder="", **kwargs):
        _styles(master)
        kwargs.setdefault("style", self.NORMAL_STYLE)
        super().__init__(master, **kwargs)
        self._placeholder = placeholder
        self._placeholder_active = False
        self.error_message = None
        self.bind("<FocusIn>", self._remove_placeholder, add="+")
        self.bind("<FocusOut>", self._restore_placeholder, add="+")
        self._restore_placeholder()

    def _set_style(self):
        if self.error_message:
            self.configure(style=self.ERROR_STYLE)
        elif self._placeholder_active:
            self.configure(style=self.PLACEHOLDER_STYLE)
        else:
            self.configure(style=self.NORMAL_STYLE)

    def _remove_placeholder(self, _event=None):
        if self._placeholder_active:
            super().delete(0, "end")
            self._placeholder_active = False
            self._set_style()

    def _restore_placeholder(self, _event=None):
        if (self._placeholder and not self._placeholder_active and not super().get()
                and "readonly" not in self.state() and "disabled" not in self.state()):
            super().insert(0, self._placeholder)
            self._placeholder_active = True
            self._set_style()

    def get(self):
        return "" if self._placeholder_active else super().get()

    def insert(self, index, string):
        self._remove_placeholder()
        return super().insert(index, string)

    def delete(self, first, last=None):
        self._remove_placeholder()
        return super().delete(first) if last is None else super().delete(first, last)

    def set_error(self, message=""):
        self.error_message = message or "输入有误"
        self._set_style()

    def clear_error(self):
        self.error_message = None
        self._set_style()

    def set_readonly(self, readonly=True):
        self.state(["readonly"] if readonly else ["!readonly"])
        if not readonly:
            self._restore_placeholder()


class TextArea(tk.Text):
    """多行文本入口，统一视觉、占位、只读和错误态。"""

    def __init__(self, master=None, *, placeholder="", **kwargs):
        _styles(master)
        options = {
            "bg": INPUT_BACKGROUND,
            "fg": INPUT_FOREGROUND,
            "insertbackground": COLORS["primary"],
            "font": INPUT_FONT,
            "relief": "solid",
            "bd": INPUT_BORDER_WIDTH,
            "highlightthickness": INPUT_BORDER_WIDTH,
            "highlightbackground": INPUT_BORDER,
            "highlightcolor": INPUT_BORDER,
            "padx": INPUT_PADDING_X,
            "pady": INPUT_PADDING_Y,
        }
        options.update(kwargs)
        super().__init__(master, **options)
        self._placeholder = placeholder
        self._placeholder_active = False
        self.error_message = None
        self.bind("<FocusIn>", self._remove_placeholder, add="+")
        self.bind("<FocusOut>", self._restore_placeholder, add="+")
        self._restore_placeholder()

    def _remove_placeholder(self, _event=None):
        if self._placeholder_active:
            super().delete("1.0", "end")
            self._placeholder_active = False
            self.configure(fg=INPUT_FOREGROUND)

    def _restore_placeholder(self, _event=None):
        if (self._placeholder and not self._placeholder_active
                and not super().get("1.0", "end-1c")
                and str(self.cget("state")) == "normal"):
            super().insert("1.0", self._placeholder)
            self._placeholder_active = True
            self.configure(fg=INPUT_PLACEHOLDER_FOREGROUND)

    def get(self, index1="1.0", index2=None):
        if self._placeholder_active:
            return ""
        return super().get(index1, index2) if index2 is not None else super().get(index1)

    def insert(self, index, chars, *tags):
        self._remove_placeholder()
        return super().insert(index, chars, *tags)

    def set_error(self, message=""):
        self.error_message = message or "输入有误"
        self.configure(highlightbackground=INPUT_ERROR_BORDER,
                       highlightcolor=INPUT_ERROR_BORDER)

    def clear_error(self):
        self.error_message = None
        self.configure(highlightbackground=INPUT_BORDER,
                       highlightcolor=INPUT_BORDER)

    def set_readonly(self, readonly=True):
        self.configure(state="disabled" if readonly else "normal")
        if not readonly:
            self._restore_placeholder()


def _styles(master):
    """Backward-compatible private alias for component construction."""
    setup_styles(master)


class NotificationDispatcher:
    """UI 唯一通知分发器：先落状态栏，必要时再复用系统确认框。

    它不拥有业务文案，也不记录日志；调用方仍决定消息、严重级别和是否需要
    模态确认。这样页面不必各自拼装“状态栏 + messagebox”的两条反馈路径。
    """

    _DIALOGS = {
        "error": "showerror",
        "warning": "showwarning",
        "success": "showinfo",
        "info": "showinfo",
    }

    def __init__(self, status, parent=None, dialogs=messagebox):
        self.status = status
        self.parent = parent
        self.dialogs = dialogs

    def notify(self, message, *, level="info", title=None, modal=False):
        """显示一条可行动提示，并返回标准化后的原文。"""
        if level not in self._DIALOGS:
            raise ValueError("未知通知级别：%s" % level)
        text = " ".join(str(message or "").split())
        if not text:
            return ""
        setter = getattr(self.status, "set", None)
        if callable(setter):
            setter(text)
        if modal:
            dialog = getattr(self.dialogs, self._DIALOGS[level])
            dialog(title or "操作提示", text, parent=self.parent)
        return text

    def error(self, message, *, title="操作提示", modal=True):
        return self.notify(message, level="error", title=title, modal=modal)

    def warning(self, message, *, title="操作提示", modal=False):
        return self.notify(message, level="warning", title=title, modal=modal)

    def success(self, message, *, title="操作完成", modal=False):
        return self.notify(message, level="success", title=title, modal=modal)

    def info(self, message, *, title="操作提示", modal=False):
        return self.notify(message, level="info", title=title, modal=modal)


class _NotificationStatusSink:
    """没有状态栏宿主时仍让通知走同一分发器的最小适配器。"""

    def set(self, _message):
        return None


def notify(parent, message, *, level="info", title=None, modal=True, status=None):
    """页面级通知入口，避免业务模块直接操作 ``messagebox``。

    有宿主状态栏时调用方传入其 ``StringVar``；独立设置窗没有状态栏时仍经
    ``NotificationDispatcher`` 统一级别、标题和模态行为。
    """
    if status is None:
        status = getattr(parent, "status", None)
    if status is None:
        status = _NotificationStatusSink()
    return NotificationDispatcher(status, parent=parent).notify(
        message, level=level, title=title, modal=modal)


class BusyState:
    """共享主任务的忙碌／加载态，不拥有后台任务或取消语义。"""

    def __init__(self, status, progress=None):
        self.status = status
        self.progress = progress
        self.busy = False
        self._controls = ()

    def set_busy(self, busy, *, message=None, controls=(), progress=True, progress_interval=15):
        """成对切换状态、进度条与可选控件；重复调用安全。"""
        if busy:
            self.busy = True
            self._controls = tuple(controls)
            for control in self._controls:
                control.state(['disabled'])
            if progress and self.progress is not None:
                self.progress.start(progress_interval)
            if message and callable(getattr(self.status, 'set', None)):
                self.status.set(message)
            return True
        if self.progress is not None:
            self.progress.stop()
        for control in self._controls:
            control.state(['!disabled'])
        self._controls = ()
        self.busy = False
        return False


class ContextMenu:
    """右键菜单的唯一构建、定位和抓取释放入口。"""

    def __init__(self, owner, menu_factory=tk.Menu):
        self.menu = menu_factory(owner, tearoff=False)

    def __getattr__(self, name):
        """兼容仍需读取 Tk 菜单状态的旧调用与测试。"""
        return getattr(self.menu, name)

    def command(self, label, command):
        self.menu.add_command(label=label, command=command)
        return self

    def disabled(self, label):
        self.menu.add_command(label=label, state="disabled")
        return self

    def radio(self, label, variable, value, command):
        self.menu.add_radiobutton(label=label, variable=variable, value=value,
                                  command=command)
        return self

    def separator(self):
        self.menu.add_separator()
        return self

    def submenu(self):
        """创建受统一入口管理的子菜单。"""
        child = self.__class__.__new__(self.__class__)
        child.menu = tk.Menu(self.menu, tearoff=False)
        return child

    def cascade(self, label, submenu):
        self.menu.add_cascade(label=label, menu=submenu.menu)
        return self

    def clear(self):
        self.menu.delete(0, "end")
        return self

    def index(self, index):
        return self.menu.index(index)

    def configure_entry(self, index, **kwargs):
        self.menu.entryconfigure(index, **kwargs)
        return self

    def popup_at(self, x, y):
        try:
            # 经代理调用，保留业务代码和测试对菜单弹出时机的可观测性。
            self.tk_popup(int(x), int(y))
        finally:
            try:
                self.grab_release()
            except tk.TclError:
                pass
        return self

    def popup(self, event):
        try:
            self.menu.tk_popup(event.x_root, event.y_root)
        finally:
            try:
                self.menu.grab_release()
            except tk.TclError:
                pass
        return 'break'


class PrimaryButton(ttk.Button):
    def __init__(self, master=None, **kwargs):
        _styles(master)
        kwargs.setdefault("style", "Tokens.Primary.TButton")
        super().__init__(master, **kwargs)


class SecondaryButton(ttk.Button):
    def __init__(self, master=None, **kwargs):
        _styles(master)
        kwargs.setdefault("style", "Tokens.Secondary.TButton")
        super().__init__(master, **kwargs)


class Card(ttk.Frame):
    def __init__(self, master=None, **kwargs):
        _styles(master)
        kwargs.setdefault("style", "Tokens.Card.TFrame")
        kwargs.setdefault("padding", SPACING["lg"])
        super().__init__(master, **kwargs)


class BaseDialog(tk.Toplevel):
    """统一的模态弹窗骨架；业务页面不可再直接创建 ``tk.Toplevel``。"""

    def __init__(self, parent, title, *, geometry=None, minsize=None, modal=True,
                 on_close=None, chrome=True):
        super().__init__(parent)
        _styles(self)
        self._closed = False
        self._modal = modal
        self._chrome = chrome
        self._owns_grab = False
        self._on_close = on_close
        self.title(title)
        self.transient(parent)
        if geometry:
            self.geometry(geometry)
        if minsize:
            self.minsize(*minsize)
        if chrome:
            self.header = ttk.Frame(self, padding=(DIALOG_CONTENT_PADDING,
                                                    DIALOG_CONTENT_PADDING,
                                                    DIALOG_CONTENT_PADDING, 0))
            self.header.pack(fill="x")
            ttk.Label(self.header, text=title,
                      style="Tokens.Dialog.Title.TLabel").pack(anchor="w")
            self.content = ttk.Frame(self, padding=DIALOG_CONTENT_PADDING)
            self.content.pack(fill="both", expand=True)
            self.actions = ttk.Frame(self, height=DIALOG_ACTION_HEIGHT,
                                     padding=(DIALOG_CONTENT_PADDING, 0,
                                              DIALOG_CONTENT_PADDING, DIALOG_ACTION_GAP))
            self.actions.pack(fill="x", side="bottom")
            # 动作区的 token 高度只是空状态下的下限；不能锁死它。Windows 主题下
            # 标准 ttk 按钮的请求高度会高于这个值，锁死后会把文字裁成一条色块。
            # 保持 geometry propagation，让「保存并发送／取消」始终完整可读。
        else:
            # 兼容旧有的透明浮窗、画布预览窗和自绘气泡：窗口生命周期仍由统一
            # 基类接管，但不强行注入标题栏或动作区，也不改变其现有子控件层级。
            self.header = None
            self.content = self
            self.actions = None
        self.bind("<Escape>", self._on_escape, add="+")
        self.protocol("WM_DELETE_WINDOW", self.close)
        if modal:
            self.grab_set()
            self._owns_grab = True
        # 无 chrome 的旧式浮窗过去并不会在创建后抢走焦点；保留这一语义，
        # 只有标准对话框才自动聚焦第一个可交互控件。
        self._focus_after = (self.after_idle(self._focus_first_interactive)
                             if chrome else None)

    def _on_escape(self, _event=None):
        self.close()
        return "break"

    def _focus_first_interactive(self):
        for widget in self._descendants(self.content):
            if isinstance(widget, (tk.Entry, tk.Text, ttk.Entry, ttk.Combobox, ttk.Button, tk.Button)):
                try:
                    if "disabled" not in widget.state() if isinstance(widget, ttk.Widget) else str(widget.cget("state")) != "disabled":
                        widget.focus_set()
                        return
                except tk.TclError:
                    return

    @staticmethod
    def _descendants(widget):
        for child in widget.winfo_children():
            yield child
            yield from BaseDialog._descendants(child)

    def add_action(self, text, command, *, primary=False, dangerous=False):
        """将动作放入唯一底部按钮区；危险主操作复用 danger token。"""
        if self.actions is None:
            raise RuntimeError("无 chrome 的 BaseDialog 没有统一动作区")
        if dangerous:
            button = ttk.Button(self.actions, text=text, command=command,
                                style="Tokens.Danger.TButton")
        elif primary:
            button = PrimaryButton(self.actions, text=text, command=command)
        else:
            button = SecondaryButton(self.actions, text=text, command=command)
        button.pack(side="right", padx=(DIALOG_ACTION_GAP, 0))
        return button

    def close(self):
        if self._closed:
            return
        self._closed = True
        if self._focus_after is not None:
            try:
                self.after_cancel(self._focus_after)
            except (AttributeError, tk.TclError):
                pass
        if self._owns_grab:
            # Tk 的 grab_release 只会释放调用它的窗口；若此窗口的后代
            # （或后来打开的模态窗）成为当前 grab，则从当前持有者释放，
            # 避免 close 后遗留一个无主输入锁。重复 close 仍由 _closed
            # 保持幂等。
            try:
                holder=self.grab_current()
                if holder is not None:
                    holder.grab_release()
                self.grab_release()
            except tk.TclError:
                pass
            finally:
                self._owns_grab = False
        try:
            self.destroy()
        finally:
            if self._on_close:
                self._on_close()


class FormDialog(BaseDialog):
    """承载字段编辑的标准弹窗，统一提交／取消按钮与关闭语义。"""

    def add_form_actions(self, submit_text, on_submit, cancel_text="取消"):
        self.add_action(cancel_text, self.close)
        return self.add_action(submit_text, on_submit, primary=True)


class ConfirmDialog(BaseDialog):
    """询问或危险确认的标准弹窗；结果通过 ``result`` 和回调给调用方。"""

    def __init__(self, parent, title, message, *, dangerous=False, on_result=None, **kwargs):
        self.result = None
        self._on_result = on_result
        super().__init__(parent, title, **kwargs)
        DescriptionBlock(self.content, text=message).pack(fill="x")
        self.add_action("取消", self._cancel)
        self.add_action("确认", self._confirm, primary=not dangerous, dangerous=dangerous)

    def _confirm(self):
        self.result = True
        self._finish()

    def _cancel(self):
        self.result = False
        self._finish()

    def _finish(self):
        callback = self._on_result
        self.close()
        if callback:
            callback(self.result)

    def close(self):
        if self.result is None:
            self.result = False
        super().close()


def ask_confirmation(parent, title, message, *, dangerous=False):
    """以统一确认窗提供旧式同步布尔语义。

    业务确认过去大多依赖 ``messagebox.askyesno`` 的同步返回值；在调用点
    尚未全部改为回调前，使用此入口可统一弹窗外观并保留 ``True``／``False``
    语义。关闭、Esc 与取消都稳定返回 ``False``。
    """
    dialog = ConfirmDialog(parent, title, message, dangerous=dangerous)
    try:
        dialog.wait_window()
    except tk.TclError:
        # 父窗口在确认期间已销毁时，按“未确认”处理，绝不继续危险操作。
        return False
    return bool(dialog.result)


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
            tip.configure(background=TOOLTIP_BORDER)
            label = tk.Label(tip, text=self.text, font=TOOLTIP_FONT,
                             fg=TOOLTIP_FOREGROUND, bg=TOOLTIP_BACKGROUND,
                             padx=TOOLTIP_PADDING[0], pady=TOOLTIP_PADDING[1])
            label.pack(padx=TOOLTIP_BORDER_WIDTH, pady=TOOLTIP_BORDER_WIDTH)
            x, y = self._position or (self.widget.winfo_rootx() + TOOLTIP_OFFSET,
                                      self.widget.winfo_rooty() + TOOLTIP_OFFSET)
            tip.geometry("+%d+%d" % (x, y))
            self._window = tip
            return tip
        except tk.TclError:
            try:
                tip.destroy()
            except (UnboundLocalError, tk.TclError):
                pass
            return None

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


class _TextLabel(ttk.Label):
    """三类辅助文字的共同构造器；页面不可覆写其视觉规格。"""

    TOKENS = None

    def __init__(self, master=None, **kwargs):
        _styles(master)
        tokens = self.TOKENS
        kwargs.update(font=tokens["font"], foreground=tokens["foreground"],
                      wraplength=tokens["wraplength"], anchor=tokens["anchor"],
                      justify=tokens["justify"], padding=tokens["padding"])
        super().__init__(master, **kwargs)
        # ttk.Label 没有独立的 linespace 选项；该 token 由统一的垂直 padding
        # 表达，并保留在实例上供布局/回归检查读取。
        self.linespace = tokens["linespace"]
        self.max_chars = tokens["max_chars"]


class HintLabel(_TextLabel):
    """短提示：输入空态、图标旁辅助信息，默认不超过 20 字。"""

    TOKENS = TEXT_HINT


class DescriptionBlock(_TextLabel):
    """可折行的功能说明：按钮下方或区块底部，默认不超过 60 字。"""

    TOKENS = TEXT_DESC


class ProgressLabel(_TextLabel):
    """单行优先的状态/进度文字，默认不超过 40 字。"""

    TOKENS = TEXT_PROGRESS


def _release_stage_popup_jobs(window, event=None):
    if event is not None and event.widget is not window:
        return
    for job in tuple(getattr(window, '_stage_popup_jobs', ())):
        try:
            window.after_cancel(job)
        except tk.TclError:
            pass
    window._stage_popup_jobs = set()


def _schedule_stage_popup_job(window, delay, callback):
    jobs = getattr(window, '_stage_popup_jobs', None)
    if jobs is None:
        jobs = set()
        window._stage_popup_jobs = jobs
        window.bind('<Destroy>', lambda event, owner=window: _release_stage_popup_jobs(owner, event), add='+')
    job = None

    def run():
        jobs.discard(job)
        callback()

    job = window.after(delay, run)
    jobs.add(job)
    return job


def _activate_stage_popup(window):
    try:
        window.attributes('-topmost', True)
        window.lift()
        window.focus_force()
        _schedule_stage_popup_job(window, 1200,
                                  lambda: window.winfo_exists() and window.attributes('-topmost', False))
    except tk.TclError:
        pass


def _show_stage_execution(desktop, stage, *, parent, title, names, runner, failed_rows, progress, on_back):
    """L4 承载执行页控件；L3 通过显式回调提供执行和结果解释。"""
    host = parent if parent is not None else getattr(desktop, 'win', None)
    standalone = host is None
    window = tk.Tk() if standalone else BaseDialog(host, '', modal=False, chrome=False)
    window.title(title)
    if not standalone:
        window.transient(host)
    window.resizable(True, True)
    window.minsize(520, 360)
    body = ttk.Frame(window, padding=10)
    body.pack(fill='both', expand=True)
    ttk.Label(body, text=title,
              font=('Microsoft YaHei UI', 11, 'bold')).pack(anchor='w')
    ttk.Label(body, text='本阶段 SKILL：' + ('、'.join(names) if names else '（还没勾上）'),
              style='Muted.TLabel', wraplength=520, justify='left').pack(anchor='w', pady=(4, 0))
    progress_label = ttk.Label(body, text='还没开始', style='Muted.TLabel')
    progress_label.pack(anchor='w', pady=(6, 0))
    log = TextArea(body, height=10, wrap='word')
    log.pack(fill='both', expand=True, pady=(6, 0))
    row = ttk.Frame(body)
    row.pack(fill='x', pady=(6, 0))
    handle = {'window': window, 'stage': stage, 'run': None, 'log': log, 'names': names,
              'failures': [], 'progress': progress_label}

    def start(only=None):
        try:
            result = runner(desktop, stage, only=only)
        except Exception as exc:
            result = {'results': [], 'text': str(exc), 'failed': []}
        handle['run'] = result
        handle['failures'] = [item.get('skill') for item in failed_rows(result)]
        try:
            log.delete('1.0', 'end')
            log.insert('end', str(result.get('text') or result.get('errors') or ''))
        except tk.TclError:
            pass
        progress_label.configure(text=progress(result))
        retry.configure(state='normal' if handle['failures'] else 'disabled')
        return result

    def go_back():
        try:
            on_back()
        except Exception:
            pass
        window.destroy()

    retry = ttk.Button(row, text='重试失败项', style='Compact.TButton',
                       command=lambda: start(only=handle['failures']))
    retry.pack(side='left')
    retry.configure(state='disabled')
    ttk.Button(row, text='返回阶段页面', style='Compact.TButton', command=go_back).pack(side='left', padx=(6, 0))
    ttk.Button(row, text='关闭', style='Compact.TButton', command=window.destroy).pack(side='left', padx=(6, 0))
    handle['retry'] = lambda: start(only=handle['failures'])
    handle['start'] = start
    handle['back'] = go_back
    start()
    if standalone:
        window.mainloop()
    return handle


def _show_manual_plan(host, title, lines, blocked):
    """L4 承载手动制作精简窗；L3 已在调用前完成业务判定。"""
    choice = []
    window = BaseDialog(host, '', modal=False, chrome=False)
    window.title(title)
    window.transient(host)
    window.resizable(False, False)
    body = ttk.Frame(window, padding=12)
    body.pack(fill='both', expand=True)
    ttk.Label(body, text=title, font=('Microsoft YaHei UI', 11, 'bold')).pack(anchor='w')
    for line in lines:
        ttk.Label(body, text=line, style='Muted.TLabel').pack(anchor='w', pady=(2, 0))
    buttons = ttk.Frame(body)
    buttons.pack(fill='x', pady=(10, 0))

    def pick(value):
        choice.append(value)
        window.destroy()

    ttk.Button(buttons, text='修改配置', style='Compact.TButton', command=lambda: pick('configure')).pack(side='left')
    run_button = ttk.Button(buttons, text='直接执行', style='Primary.TButton', command=lambda: pick('run'))
    run_button.pack(side='left', padx=(6, 0))
    if blocked:
        run_button.configure(state='disabled')
    ttk.Button(buttons, text='取消', style='Compact.TButton', command=lambda: pick(None)).pack(side='left', padx=(6, 0))
    window.protocol('WM_DELETE_WINDOW', lambda: pick(None))
    window.bind('<Escape>', lambda event: pick(None))
    try:
        window.update_idletasks()
        window.geometry('+%d+%d' % (max(0, host.winfo_rootx() + (host.winfo_width() - window.winfo_width()) // 2),
                                    max(0, host.winfo_rooty() + (host.winfo_height() - window.winfo_height()) // 2)))
        window.grab_set()
        window.lift()
        window.focus_force()
        _schedule_stage_popup_job(window, 60, lambda: _activate_stage_popup(window))
    except tk.TclError:
        pass
    try:
        window.wait_window()
    except tk.TclError:
        pass
    return choice[0] if choice else None


def install_stage_presenters():
    """在 L4 组合根登记阶段 UI 呈现器；依赖方向始终是 UI → 阶段。"""
    from ui_plugin_registry import module
    module('stage_exec').install_ui_presenters(_show_stage_execution, _show_manual_plan)


install_stage_presenters()

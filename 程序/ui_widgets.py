"""遵循 ui_components.md 的 Tk 组件入口。"""
import tkinter as tk
from tkinter import ttk

from ui_tokens import (COLORS, COMBOBOX_ARROW_COLOR, COMBOBOX_FIELD_BACKGROUND,
                       COMBOBOX_FONT, COMBOBOX_FOREGROUND, COMBOBOX_PADDING,
                       COMBOBOX_WIDTH, FONTS, SPACING, TEXT_DESC, TEXT_HINT,
                       TEXT_PROGRESS, DIALOG_ACTION_GAP, DIALOG_ACTION_HEIGHT,
                       DIALOG_CONTENT_PADDING, DIALOG_TITLE_FONT)


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


def _styles(master):
    """Backward-compatible private alias for component construction."""
    setup_styles(master)


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
                 on_close=None):
        super().__init__(parent)
        _styles(self)
        self._closed = False
        self._modal = modal
        self._on_close = on_close
        self.title(title)
        self.transient(parent)
        if geometry:
            self.geometry(geometry)
        if minsize:
            self.minsize(*minsize)
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
        self.actions.pack_propagate(False)
        self.bind("<Escape>", self._on_escape, add="+")
        self.protocol("WM_DELETE_WINDOW", self.close)
        if modal:
            self.grab_set()
        self._focus_after = self.after_idle(self._focus_first_interactive)

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
        try:
            self.after_cancel(self._focus_after)
        except (AttributeError, tk.TclError):
            pass
        try:
            if self._modal and self.grab_current() == self:
                self.grab_release()
        except tk.TclError:
            pass
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

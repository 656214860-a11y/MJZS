"""遵循 ui_components.md 的 Tk 组件入口。"""
import app_logging
import os
import tkinter as tk
from tkinter import messagebox, ttk
from app_metadata import APP_NAME

from ui_tokens import (COLORS, COMBOBOX_ARROW_COLOR, COMBOBOX_CONTROL_PADDING,
                       COMBOBOX_FIELD_BACKGROUND, COMBOBOX_FONT,
                       COMBOBOX_FOREGROUND, COMBOBOX_PADDING,
                       COMBOBOX_WIDTH, COMBOBOX_POPDOWN_HEIGHT, COMBOBOX_MAX_WIDTH,
                       CONTROL_HEIGHT, CONTROL_PADDING_Y, FONTS, RADIUS, SPACING,
                       TEXT_DESC, TEXT_HINT, TEXT_PROGRESS, DIALOG_ACTION_GAP,
                       DIALOG_ACTION_HEIGHT, DIALOG_CONTENT_PADDING, DIALOG_TITLE_FONT,
                       TOOLTIP_BACKGROUND, TOOLTIP_BORDER, TOOLTIP_BORDER_WIDTH, TOOLTIP_DELAY_MS,
                       TOOLTIP_FONT, TOOLTIP_FOREGROUND, TOOLTIP_OFFSET,
                       TOOLTIP_PADDING, TOOLTIP_WRAPLENGTH,
                       TABLE_EMPTY_PADDING, TABLE_HEADER_FONT, TABLE_ROW_FONT, TABLE_COMPACT_HEADER_PADDING,
                       TABLE_ROW_HEIGHT, INPUT_BACKGROUND, INPUT_BORDER,
                       INPUT_BORDER_HOVER, INPUT_BORDER_WIDTH, INPUT_ERROR_BORDER,
                       INPUT_FOCUS_BORDER, INPUT_FONT, INPUT_FOREGROUND,
                       INPUT_PADDING_X, INPUT_PADDING_Y, INPUT_PLACEHOLDER_FOREGROUND,
                       ICON_FONT, BUTTON_RADIUS, CONTROL_CORNER_SURFACE,
                       ROUND_TILE_BUTTON, ROUND_TILE_CARD,
                       SCROLLBAR_THUMB, SCROLLBAR_THUMB_ACTIVE, SCROLLBAR_TROUGH,
                       SCROLLBAR_BORDER_WIDTH, SCROLLBAR_WIDTH)
from ui_motion import bind_row_hover, empty_icon
from ui_hover_fade import install_hover_fade
from ui_rounded import (button_specs, rounded_layout, rounded_photo as _rounded_photo,
                        rounded_png_bytes as _rounded_png_bytes)


def _configure_button(style, name, *, background, foreground,
                      active_background, active_foreground,
                      pressed_background=None,
                      disabled_background=COLORS["disabled_bg"],
                      disabled_foreground=COLORS["disabled_text"],
                      padding=(SPACING["md"], CONTROL_PADDING_Y),
                      font=None, anchor=None, border_color=None, border_width=0):
    """圆角按钮：底图是带 alpha 的圆角 PNG，四态各一张；按钮自身的 ``fill`` 选项记录填充色。

    ttk 把圆角透明处露出的是样式的 ``background``，所以 ``background`` 必须是按钮背后的
    表面色（``CONTROL_CORNER_SURFACE``），而不是按钮的填充色，否则四个角会被填成实心方角。
    """
    root = style.master
    pressed_background = pressed_background or active_background
    states = (("normal", background), ("active", active_background),
              ("pressed", pressed_background), ("disabled", disabled_background))
    images = {}
    tile_w, tile_h = ROUND_TILE_BUTTON
    for state, color in states:
        images[state], pr = _rounded_photo(root, color, BUTTON_RADIUS,
                                           width=BUTTON_RADIUS * 2 + tile_w,
                                           height=BUTTON_RADIUS * 2 + tile_h,
                                           border=border_color, border_width=border_width)
    element = "Drama.Rounded." + name.replace(".", "_")
    if element not in style.element_names():
        style.element_create(element, "image", images["normal"],
                             ("active", images["active"]), ("pressed", images["pressed"]),
                             ("disabled", images["disabled"]),
                             border=(pr, pr, pr, pr), padding=(0, 0, 0, 0),
                             width=1, height=1, sticky="nsew")
    rounded_layout(style, name, element)
    button_specs(root)[name] = {
        "colors": dict(states), "images": images,
        "border": (border_color, border_width), "size": (tile_w, tile_h)}
    options = {"font": font or FONTS["body"], "padding": padding,
               "background": CONTROL_CORNER_SURFACE, "fill": background,
               "foreground": foreground, "focuscolor": COLORS["focus"]}
    if anchor is not None:
        options["anchor"] = anchor
    style.configure(name, **options)
    # 按下时文字下移 1px、上下合计高度不变（上加下减），按钮不会因按下而抖动整行。
    style.map(name,
              fill=[("pressed", pressed_background),
                    ("active", active_background),
                    ("disabled", disabled_background)],
              foreground=[("active", active_foreground),
                          ("disabled", disabled_foreground)],
              padding=[("pressed", (padding[0], padding[1] + 1,
                                    padding[0], max(0, padding[1] - 1)))])


def _install_button_styles(style, root):
    solid = dict(foreground=COLORS["background_card"],
                 active_background=COLORS["primary_hover"],
                 active_foreground=COLORS["background_card"],
                 pressed_background=COLORS["primary_pressed"])
    _configure_button(style, "Primary.TButton", background=COLORS["primary"], **solid)
    _configure_button(style, "Tokens.Primary.TButton", background=COLORS["primary"], **solid)
    _configure_button(style, "Send.TButton", background=COLORS["primary"], **solid)
    _configure_button(style, "Selected.Compact.TButton", background=COLORS["primary"], **solid)
    _configure_button(style, "Selected.Nav.TButton", background=COLORS["primary"], anchor="w", **solid)
    _configure_button(style, "Selected.Sub.Nav.TButton", background=COLORS["primary"],
                      anchor="w", padding=(SPACING["xl"], CONTROL_PADDING_Y), **solid)
    _configure_button(style, "Highlight.TButton", background=COLORS["primary_pressed"],
                      foreground=COLORS["background_card"],
                      active_background=COLORS["primary_pressed"],
                      active_foreground=COLORS["background_card"],
                      pressed_background=COLORS["primary_pressed"],
                      font=FONTS["body_bold"])
    secondary = dict(background=COLORS["secondary_bg"],
                     foreground=COLORS["secondary_text"],
                     active_background=COLORS["secondary_hover"],
                     active_foreground=COLORS["secondary_text"],
                     pressed_background=COLORS["secondary_pressed"])
    _configure_button(style, "TButton", **secondary)
    _configure_button(style, "Compact.TButton", **secondary)
    _configure_button(style, "Asset.TButton", **secondary)
    _configure_button(style, "ProjectAction.TButton", **secondary)
    ghost = dict(background=COLORS["background_card"],
                 foreground=COLORS["text_primary"],
                 active_background=COLORS["surface_hover"],
                 active_foreground=COLORS["text_primary"],
                 pressed_background=COLORS["surface_pressed"],
                 border_color=COLORS["border_input"], border_width=1)
    _configure_button(style, "Secondary.TButton", **ghost)
    _configure_button(style, "Tokens.Secondary.TButton", **ghost)
    _configure_button(style, "Tokens.Icon.TButton", font=ICON_FONT,
                      padding=(SPACING["sm"], CONTROL_PADDING_Y), **ghost)
    _configure_button(style, "Tokens.Danger.TButton", background=COLORS["danger"],
                      foreground=COLORS["background_card"],
                      active_background=COLORS["danger_hover"],
                      active_foreground=COLORS["background_card"],
                      pressed_background=COLORS["danger_pressed"])
    nav = dict(background=COLORS["background_primary"],
               foreground=COLORS["text_primary"],
               active_background=COLORS["surface_hover"],
               active_foreground=COLORS["text_primary"],
               pressed_background=COLORS["surface_pressed"])
    _configure_button(style, "Nav.TButton", anchor="w", **nav)
    _configure_button(style, "Sub.Nav.TButton", anchor="w",
                      padding=(SPACING["xl"], CONTROL_PADDING_Y), **nav)
    _configure_button(style, "Tokens.Text.TButton",
                      background=COLORS["background_primary"],
                      foreground=COLORS["primary"],
                      active_background=COLORS["surface_hover"],
                      active_foreground=COLORS["primary"],
                      pressed_background=COLORS["surface_pressed"])


def _install_card_style(style, root):
    factor = float(root.tk.call("tk", "scaling")) / (96.0 / 72.0)
    pr = max(1, round(RADIUS["lg"] * factor))
    tile_w, tile_h = ROUND_TILE_CARD
    image, _ = _rounded_photo(root, COLORS["background_card"], RADIUS["lg"],
                              width=RADIUS["lg"] * 2 + tile_w, height=RADIUS["lg"] * 2 + tile_h,
                              border=COLORS["border_default"], border_width=1)
    element = "Drama.Card"
    if element not in style.element_names():
        # width/height=1：否则 ttk 把控件最小尺寸撑成整张底图（大中心区会让按钮高 80px）。
        style.element_create(element, "image", image, border=(pr, pr, pr, pr),
                             padding=(0, 0, 0, 0), width=1, height=1, sticky="nsew")
    style.layout("Tokens.Card.TFrame", [(element, {"sticky": "nsew", "children": [
        ("Button.padding", {"sticky": "nsew"})]})])
    # 控件自身的 padding（Card 默认 lg）之外，再由样式补一档 sm，卡片内容离圆角边更透气。
    style.configure("Tokens.Card.TFrame", background=CONTROL_CORNER_SURFACE,
                    padding=SPACING["sm"])


def _configure_combobox(style, name, padding):
    style.configure(name, fieldbackground=COMBOBOX_FIELD_BACKGROUND,
                    background=COMBOBOX_FIELD_BACKGROUND,
                    foreground=COMBOBOX_FOREGROUND, font=COMBOBOX_FONT,
                    padding=padding, bordercolor=INPUT_BORDER,
                    lightcolor=COMBOBOX_FIELD_BACKGROUND,
                    darkcolor=COMBOBOX_FIELD_BACKGROUND)
    style.map(name,
              fieldbackground=[("readonly", COMBOBOX_FIELD_BACKGROUND),
                               ("disabled", COLORS["disabled_bg"])],
              foreground=[("disabled", COLORS["disabled_text"])],
              bordercolor=[("focus", INPUT_FOCUS_BORDER)])


def _install_input_styles(style, root):
    input_options = {
        "font": INPUT_FONT,
        "foreground": INPUT_FOREGROUND,
        "fieldbackground": INPUT_BACKGROUND,
        "background": INPUT_BACKGROUND,
        "bordercolor": INPUT_BORDER,
        "padding": (INPUT_PADDING_X, CONTROL_PADDING_Y),
    }
    style.configure("TEntry", **input_options)
    style.map("TEntry", bordercolor=[("focus", INPUT_FOCUS_BORDER),
                                     ("hover", INPUT_BORDER_HOVER)])
    style.configure("Tokens.LineInput.TEntry", **input_options)
    style.configure("Tokens.LineInput.Placeholder.TEntry",
                    **dict(input_options, foreground=INPUT_PLACEHOLDER_FOREGROUND))
    style.configure("Tokens.LineInput.Error.TEntry",
                    **dict(input_options, bordercolor=INPUT_ERROR_BORDER))
    for name in ("Tokens.LineInput.TEntry", "Tokens.LineInput.Placeholder.TEntry",
                 "Tokens.LineInput.Error.TEntry"):
        style.map(name, bordercolor=[("focus", INPUT_FOCUS_BORDER),
                                     ("hover", INPUT_BORDER_HOVER)])
    style.configure("TSpinbox", font=INPUT_FONT, foreground=INPUT_FOREGROUND,
                    fieldbackground=INPUT_BACKGROUND,
                    background=INPUT_BACKGROUND, bordercolor=INPUT_BORDER,
                    padding=(INPUT_PADDING_X, CONTROL_PADDING_Y),
                    borderwidth=INPUT_BORDER_WIDTH)
    style.map("TSpinbox", bordercolor=[("focus", INPUT_FOCUS_BORDER),
                                       ("hover", INPUT_BORDER_HOVER)])

    _configure_combobox(style, "TCombobox", COMBOBOX_PADDING)
    _configure_combobox(style, "Tokens.Combobox.TCombobox", COMBOBOX_CONTROL_PADDING)
    for name in ("TCombobox", "Tokens.Combobox.TCombobox"):
        try:
            root.tk.call("ttk::style", "configure", name,
                         "-arrowcolor", COMBOBOX_ARROW_COLOR)
        except Exception:
            app_logging.swallowed()
    root.option_add("*TCombobox*Listbox.font", COMBOBOX_FONT)
    root.option_add("*TCombobox*Listbox.background", COMBOBOX_FIELD_BACKGROUND)
    root.option_add("*TCombobox*Listbox.foreground", COMBOBOX_FOREGROUND)
    root.option_add("*TCombobox*Listbox.selectBackground", COLORS["primary"])
    root.option_add("*TCombobox*Listbox.selectForeground", COLORS["background_card"])
    root.option_add("*TCombobox.width", COMBOBOX_WIDTH)


def _install_scrollbar_styles(style):
    for name in ("Vertical.TScrollbar", "Horizontal.TScrollbar"):
        style.configure(name, background=SCROLLBAR_THUMB, troughcolor=SCROLLBAR_TROUGH,
                        arrowsize=SCROLLBAR_WIDTH, borderwidth=SCROLLBAR_BORDER_WIDTH,
                        bordercolor=SCROLLBAR_TROUGH, lightcolor=SCROLLBAR_THUMB,
                        darkcolor=SCROLLBAR_THUMB, relief="flat", gripcount=0)
        style.map(name, background=[("active", SCROLLBAR_THUMB_ACTIVE)],
                  lightcolor=[("active", SCROLLBAR_THUMB_ACTIVE)],
                  darkcolor=[("active", SCROLLBAR_THUMB_ACTIVE)])
    style.layout("Vertical.TScrollbar", [
        ("Vertical.Scrollbar.trough", {"sticky": "ns", "children": [
            ("Vertical.Scrollbar.thumb", {"sticky": "nswe"})]})])
    style.layout("Horizontal.TScrollbar", [
        ("Horizontal.Scrollbar.trough", {"sticky": "we", "children": [
            ("Horizontal.Scrollbar.thumb", {"sticky": "nswe"})]})])


def setup_styles(root):
    """按钮/输入/下拉框/数值框/卡片/滚动条样式的唯一定义处；ui_theme.apply() 装主题后调用它。"""
    style = ttk.Style(root)
    # 同一主题下样式已装好就不再重配；换主题后重新安装。
    interp = style.tk
    theme = style.theme_use()
    try:
        if str(interp.globalgetvar("drama_styles_theme")) == str(theme):
            return
    except tk.TclError:
        pass
    _install_button_styles(style, root)
    install_hover_fade(root)
    _install_card_style(style, root)
    _install_input_styles(style, root)
    _install_scrollbar_styles(style)
    # 表单的普通标签、分组标题和勾选项必须与按钮／输入框同用正文 token。
    style.configure("TLabel", font=FONTS["body"])
    style.configure("TCheckbutton", font=FONTS["body"])
    style.configure("TLabelframe.Label", font=FONTS["body"])
    style.configure("Tokens.Title.TLabel", font=FONTS["title"],
                    foreground=COLORS["text_primary"])
    style.configure("Tokens.Dialog.Title.TLabel", font=DIALOG_TITLE_FONT,
                    foreground=COLORS["text_primary"])
    style.configure("Tokens.DataTable.Treeview", font=TABLE_ROW_FONT,
                    rowheight=TABLE_ROW_HEIGHT,
                    background=COLORS["background_card"],
                    fieldbackground=COLORS["background_card"],
                    foreground=COLORS["text_primary"])
    # 表头去掉 clam 的凸起斜面：平底、只留一条弱分隔线。
    heading_flat = dict(relief="flat", background=COLORS["header_bg"],
                        bordercolor=COLORS["border_default"],
                        lightcolor=COLORS["header_bg"], darkcolor=COLORS["header_bg"])
    style.configure("Treeview", bordercolor=COLORS["border_default"],
                    lightcolor=COLORS["background_card"], darkcolor=COLORS["background_card"])
    style.configure("Treeview.Heading", **heading_flat)
    style.configure("Tokens.DataTable.Treeview.Heading", font=TABLE_HEADER_FONT,
                    foreground=COLORS["text_primary"], **heading_flat)
    style.configure("Compact.Tokens.DataTable.Treeview.Heading",
                    padding=TABLE_COMPACT_HEADER_PADDING)
    interp.globalsetvar("drama_styles_theme", theme)


class DataTable(ttk.Frame):
    """统一的可滚动表格壳；页面只提供列、数据和领域内的单元格行为。"""

    def __init__(self, master, *, columns, height=4, selectmode="browse",
                 show="headings", empty_text="暂无数据", on_select=None,
                 auto_hide_scrollbars=False, horizontal=True, **kwargs):
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
        # 单列且 stretch 的表格永远不横向溢出；此时不建横向滚动条，省掉底部一整行。
        self.horizontal_scrollbar = (
            ttk.Scrollbar(self, orient="horizontal", command=self.tree.xview)
            if horizontal else None)
        self._auto_hide_scrollbars = auto_hide_scrollbars
        self.tree.configure(
            yscrollcommand=lambda first, last: self._scroll_state(
                self.vertical_scrollbar, first, last),
            xscrollcommand=(lambda first, last: self._scroll_state(
                self.horizontal_scrollbar, first, last)) if horizontal
            else (lambda first, last: None))
        self.tree.grid(row=0, column=0, sticky="nsew")
        self.vertical_scrollbar.grid(row=0, column=1, sticky="ns")
        if horizontal:
            self.horizontal_scrollbar.grid(row=1, column=0, sticky="ew")
        # 柔和图标在文字上方（compound=top）；文本为空时本标签不显示，图标也随之不出现。
        self.empty_label = ttk.Label(self, text=empty_text, style="Muted.TLabel",
                                     padding=TABLE_EMPTY_PADDING, image=empty_icon(self),
                                     compound="top", anchor="center", justify="center")
        self.empty_label.grid(row=0, column=0, sticky="nsew")
        self.empty_label.lift()
        for name, label, width in columns:
            self.tree.heading(name, text=label,
                              command=lambda column=name: self.sort_by(column))
            self.tree.column(name, width=width, minwidth=0, stretch=True)
        self.tree.bind("<<TreeviewSelect>>", self._selected, add="+")
        bind_row_hover(self.tree)
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
        # 空文案表示保留原生列头和空行，不用标签覆盖整张表。
        if not self.empty_label.cget('text') or self.tree.get_children():
            self.empty_label.grid_remove()
        else:
            self.empty_label.grid()

    def _scroll_state(self, scrollbar, first, last):
        scrollbar.set(first, last)
        if not self._auto_hide_scrollbars:
            return
        should_hide = float(first) <= 0 and float(last) >= 1
        hidden = not bool(scrollbar.winfo_manager())
        # 只在可见性真的变化时改布局：反复 grid/grid_remove 会让表格宽度来回抖，
        # 拖动窗口时与各 Configure 回调互相喂，放大成持续重排。
        if should_hide and not hidden:
            scrollbar.grid_remove()
        elif not should_hide and hidden:
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


def _display_width(value):
    """全角按 2 计、ASCII 按 1 计，近似下拉框可视宽度。"""
    return sum(2 if ord(ch) > 0x2E80 else 1 for ch in str(value))


class SelectBox(ttk.Combobox):
    """统一下拉框：只读默认、自适应宽度封顶、弹出高度受限。

    保持 Combobox 的 textvariable/current/get 语义。
    ``fit=True`` 时即使可编辑（state='normal'）也按全部选项＋当前值自适应宽度，
    选项列表或当前值变化后可用 ``refit()`` 重算。
    """

    def __init__(self, master=None, *, values=(), height=COMBOBOX_POPDOWN_HEIGHT,
                 width=None, state="readonly", fit=False, accent_values=(), **kwargs):
        setup_styles(master)
        values = tuple(values)
        self._fit = bool(fit)
        self.accent_values = tuple(accent_values)  # 弹出列表里用主色突出的特殊项（如「+ 添加模型…」）
        # 显式给了 width：框体宽度固定（统一尺寸），不随选项重算；弹出列表仍按最长选项加宽。
        self._fixed_width = width is not None
        if width is None:
            width = self._fit_width(values) if (self._fit or state == "readonly") else COMBOBOX_WIDTH
        # 统一的下拉框控件样式（32±2px）；页面仍只负责选项和内容宽度。
        kwargs.setdefault("style", "Tokens.Combobox.TCombobox")
        user_post = kwargs.pop("postcommand", None)

        def post():
            if user_post:
                user_post()
            self._fit_popdown()
            if self.accent_values:
                self.after_idle(self._accent_popdown)

        super().__init__(master, values=values, height=height, width=width,
                         state=state, postcommand=post, **kwargs)

    def _accent_popdown(self):
        """列表载入后把特殊项染成主色：弹出窗的列表框在 postcommand 之后才填充，故延后一拍。"""
        try:
            listbox = '%s.f.l' % self.tk.call('ttk::combobox::PopdownWindow', self)
            for index, value in enumerate(self.cget('values')):
                if value in self.accent_values:
                    self.tk.call(listbox, 'itemconfigure', index, '-foreground', COLORS['primary'])
        except tk.TclError:
            pass

    def _fit_popdown(self):
        """弹出前把列表加宽到最长选项：ttk 的列表宽度跟随框体，靠样式 postoffset 补差。"""
        try:
            from tkinter import font as tkfont
            spec = self.cget("font") or ttk.Style(self).lookup(self.cget("style") or "TCombobox", "font")
            font = tkfont.Font(root=self, font=spec or "TkDefaultFont")
            texts = [str(v) for v in self.cget("values")] if self.cget("values") else []
            longest = max([font.measure(text) for text in texts] or [0])
            extra = max(0, longest + 28 - self.winfo_width())  # 28 ≈ 内边距＋滚动条
            ttk.Style(self).configure(self.cget("style") or "TCombobox",
                                      postoffset=(0, 0, extra, 0))
        except tk.TclError:
            pass

    @staticmethod
    def _fit_width(values, current=''):
        """全部选项＋当前值的最长显示宽度（CJK 按 2 计），封顶 COMBOBOX_MAX_WIDTH。"""
        widths = [_display_width(v) for v in values]
        if current:
            widths.append(_display_width(current))
        if not widths:
            return COMBOBOX_WIDTH
        return min(COMBOBOX_MAX_WIDTH, max(widths))

    def refit(self):
        """按当前选项与当前值重算宽度；可编辑框在用户输入长文本后调用。"""
        if self._fixed_width:
            return
        self.configure(width=self._fit_width(tuple(self.cget('values')), self.get()))

    def set_values(self, values, *, refit=True):
        values = tuple(values)
        self.configure(values=values)
        if refit and not self._fixed_width and (self._fit or "readonly" in self.state()):
            self.configure(width=self._fit_width(values))


class LineInput(ttk.Entry):
    """单行文本入口，统一占位、只读和错误态而不改变 Entry 的取值语义。"""

    NORMAL_STYLE = "Tokens.LineInput.TEntry"
    PLACEHOLDER_STYLE = "Tokens.LineInput.Placeholder.TEntry"
    ERROR_STYLE = "Tokens.LineInput.Error.TEntry"

    def __init__(self, master=None, *, placeholder="", **kwargs):
        setup_styles(master)
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
        setup_styles(master)
        options = {
            "bg": INPUT_BACKGROUND,
            "fg": INPUT_FOREGROUND,
            "insertbackground": COLORS["primary"],
            "font": INPUT_FONT,
            "relief": "flat",
            "bd": 0,
            "highlightthickness": INPUT_BORDER_WIDTH,
            "highlightbackground": INPUT_BORDER,
            "highlightcolor": INPUT_FOCUS_BORDER,
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
                       highlightcolor=INPUT_FOCUS_BORDER)

    def set_readonly(self, readonly=True):
        self.configure(state="disabled" if readonly else "normal")
        if not readonly:
            self._restore_placeholder()


SUPPRESS_MODAL_ENV = "DRAMA_SUPPRESS_MODAL"
# 手动／自动化测试运行真实界面时设为 1：与 SUPPRESS_MODAL 同效，提示只落状态栏、不等人点「确定」。
AUTO_CONFIRM_ENV = "DRAMA_AUTO_CONFIRM"


_REAL_DIALOGS = {name: getattr(messagebox, name) for name in ("showerror", "showwarning", "showinfo")}


class _SilentDialogs:
    """自检／CI 无人值守时的系统确认框替身：只走状态栏，不弹出阻塞的模态框。

    用例若已把 ``messagebox.showerror`` 等替换成记录函数，仍调用该替换以便断言；
    只有真实的 tkinter 系统框才被静默。
    """

    def __getattr__(self, name):
        current = getattr(messagebox, name)
        if current is _REAL_DIALOGS.get(name):
            return lambda *_args, **_kwargs: "ok"
        return current


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
        # 自检与本地 CI 设置 DRAMA_SUPPRESS_MODAL=1：默认系统框改为静默，避免模态框卡住整轮测试；
        # 用例显式注入的 dialogs 不受影响，仍可断言弹窗行为。
        if dialogs is messagebox and "1" in (os.environ.get(SUPPRESS_MODAL_ENV), os.environ.get(AUTO_CONFIRM_ENV)):
            dialogs = _SilentDialogs()
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

    def error(self, message, *, title="操作提示", modal=False):
        """可恢复错误默认只落状态栏；确需阻断的调用方显式传 ``modal=True``。

        删除／覆盖等破坏性确认不走本函数，仍由 ConfirmDialog 承担。
        """
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

    def __init__(self, status, progress=None, *, idle_determinate=False, spinner=None):
        self.status = status
        self.progress = progress
        self.spinner = spinner  # 可选 ui_motion.Spinner：忙碌时显示并转圈
        self.idle_determinate = idle_determinate
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
                if self.idle_determinate:self.progress.configure(mode='indeterminate')
                self.progress.start(progress_interval)
            if message and callable(getattr(self.status, 'set', None)):
                self.status.set(message)
            if self.spinner is not None:
                self.spinner.start()
            return True
        if self.spinner is not None:
            self.spinner.stop()
        if self.progress is not None:
            self.progress.stop()
            if self.idle_determinate:self.progress.configure(mode='determinate', value=0)
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
        setup_styles(master)
        kwargs.setdefault("style", "Tokens.Primary.TButton")
        super().__init__(master, **kwargs)


class SecondaryButton(ttk.Button):
    def __init__(self, master=None, **kwargs):
        setup_styles(master)
        kwargs.setdefault("style", "Tokens.Secondary.TButton")
        super().__init__(master, **kwargs)


class Card(ttk.Frame):
    def __init__(self, master=None, **kwargs):
        setup_styles(master)
        kwargs.setdefault("style", "Tokens.Card.TFrame")
        kwargs.setdefault("padding", SPACING["lg"])
        super().__init__(master, **kwargs)


class BaseDialog(tk.Toplevel):
    """统一的模态弹窗骨架；业务页面不可再直接创建 ``tk.Toplevel``。"""

    def __init__(self, parent, title, *, geometry=None, minsize=None, modal=True,
                 on_close=None, chrome=True):
        super().__init__(parent)
        setup_styles(self)
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


class StringDialog(FormDialog):
    """单行文本输入的标准弹窗；结果通过 ``result`` 给调用方。

    确认返回输入内容（空串表示用户明确留空）；取消、Esc 与关闭都保持
    ``result is None``，与空串严格区分。
    """

    def __init__(self, parent, title, prompt, *, initialvalue="", **kwargs):
        self.result = None
        super().__init__(parent, title, **kwargs)
        DescriptionBlock(self.content, text=prompt).pack(fill="x", pady=(0, SPACING["md"]))
        self.entry = LineInput(self.content)
        self.entry.pack(fill="x")
        if initialvalue:
            self.entry.insert(0, initialvalue)
        self.entry.bind("<Return>", self._confirm, add="+")
        self.add_form_actions("确定", self._confirm)

    def _confirm(self, _event=None):
        self.result = self.entry.get()
        self.close()
        return "break"

    def cancel(self, _event=None):
        """等价关闭语义：取消输入，``result`` 保持 ``None``（与关闭／Esc 一致）。"""
        self.close()


def ask_string(parent, title, prompt, *, initialvalue=""):
    """以统一文本输入窗提供旧式同步文本输入的语义。

    确认返回输入内容（空串表示用户明确留空），取消、Esc 与关闭窗口都稳定返回
    ``None``，两者必须区分。父窗口在等待期间已销毁时按“未确认”返回 ``None``。
    """
    dialog = StringDialog(parent, title, prompt, initialvalue=initialvalue)
    try:
        dialog.wait_window()
    except tk.TclError:
        # 父窗口在确认期间已销毁时，按“未确认”处理，绝不继续后续写入。
        return None
    return dialog.result


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
            self._populate(tip)
            x, y = self._position or (self.widget.winfo_rootx() + TOOLTIP_OFFSET,
                                      self.widget.winfo_rooty() + TOOLTIP_OFFSET)
            # 贴近屏幕底边／右边的控件（如页面底部状态栏）改向上／向左展开，浮层不出屏。
            try:
                tip.update_idletasks()
                width, height = tip.winfo_reqwidth(), tip.winfo_reqheight()
                if y + height > tip.winfo_screenheight():
                    y = max(0, y - height - 2 * TOOLTIP_OFFSET)
                x = max(0, min(x, tip.winfo_screenwidth() - width))
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


class EllipsisLabel(ttk.Label):
    """单行摘要按实际宽度省略，鼠标和键盘焦点说明保留全文。"""

    def __init__(self, master, *, text='', **kwargs):
        super().__init__(master, text='', width=1, anchor='w', **kwargs)
        self.full_text = str(text)
        self.tooltip = Tooltip(self, self.full_text)
        self.bind('<Configure>', self._render, add='+')

    def set_text(self, text):
        self.full_text = str(text)
        self.tooltip.text = self.full_text
        self._render()

    def _render(self, _event=None):
        from tkinter.font import Font
        font = Font(root=self, font=self.cget('font') or ttk.Style(self).lookup(self.cget('style') or 'TLabel', 'font'))
        room = max(0, self.winfo_width() - SPACING['xs'])
        text = self.full_text
        if font.measure(text) > room:
            lo, hi = 0, len(text)
            while lo < hi:
                mid = (lo + hi + 1) // 2
                if font.measure(text[:mid] + '…') <= room:lo = mid
                else:hi = mid - 1
            text = text[:lo] + '…' if font.measure('…') <= room else ''
        if self.cget('text') != text:self.configure(text=text)


class _TextLabel(ttk.Label):
    """三类辅助文字的共同构造器；页面不可覆写其视觉规格。"""

    TOKENS = None

    def __init__(self, master=None, **kwargs):
        setup_styles(master)
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
            app_logging.swallowed()
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
    module('stage_exec').install_ui_presenters(_show_stage_execution, _show_manual_plan, ask_confirmation)


install_stage_presenters()


import time as _time
import ui_tokens as T

# 进度按真实启动阶段推进：每段有目标百分比，段内匀速爬向下一段，爬到头就停等。
SPLASH_STAGES = (('正在加载组件…', 0.15), ('正在构建工作台…', 0.45), ('正在打开项目…', 0.75),
                 ('正在渲染页面…', 0.92), ('准备就绪', 1.0))


class Splash:
    """启动画面：整块盖住主窗口所在位置，加载完、进度条走满的那一刻才揭开主窗口。

    主线程被搭建工作占住时画面会停，所以 step() 都主动推一帧；空闲时由 wait() 轮询就绪。"""

    def __init__(self, master, rect):
        self.win = tk.Toplevel(master)
        self.win.overrideredirect(True)
        self.win.attributes('-topmost', True)
        self.win.configure(bg=T.SPLASH_BACKGROUND)
        self.canvas = tk.Canvas(self.win, bg=T.SPLASH_BACKGROUND, highlightthickness=0, bd=0)
        self.canvas.pack(fill='both', expand=True)
        self.start = _time.perf_counter()
        self.stage = 0
        self.progress = 0.0
        self._job = None
        self._size = None
        # 各段与收尾的耗时（毫秒，距 Splash 创建）；收起时交给 on_finish，由调用方决定落到哪。
        self.marks = {}
        self.on_finish = None
        self.cover(rect)
        self._tick()
        self.win.update()

    def cover(self, rect):
        """把画面挪到 rect=(x, y, w, h)，尺寸变了就按新尺寸重画。"""
        x, y, width, height = (int(v) for v in rect)
        self.win.geometry(f'{width}x{height}+{x}+{y}')
        if self._size != (width, height):
            self._size = (width, height)
            self._draw(width, height)

    def _draw(self, w, h):
        c = self.canvas
        c.delete('all')
        cx, cy = w // 2, h // 2 - T.SPACING['2xl']
        r = T.SPACING['2xl'] + T.SPACING['sm']
        self.ring = c.create_arc(cx - r, cy - r, cx + r, cy + r, start=90, extent=300,
                                 style='arc', outline=T.SPLASH_ACCENT, width=3)
        tri = r // 2
        c.create_polygon(cx - tri // 2, cy - tri, cx - tri // 2, cy + tri, cx + tri, cy,
                         fill=T.SPLASH_ACCENT_ALT, outline='')
        title_y = cy + r + T.SPACING['2xl']
        c.create_text(cx, title_y, text=APP_NAME, fill=T.SPLASH_TITLE, font=T.SPLASH_TITLE_FONT)
        c.create_text(cx, title_y + T.SPACING['2xl'] + T.SPACING['xs'], text='AI 漫剧 · 从剧本到成片',
                      fill=T.SPLASH_SUBTITLE, font=T.SPLASH_SUBTITLE_FONT)
        half = min(w // 3, T.SPLASH_BAR_HALF)
        bar_y = title_y + T.SPACING['2xl'] * 3
        self.bar_box = (cx - half, bar_y, cx + half)
        c.create_line(cx - half, bar_y, cx + half, bar_y, fill=T.SPLASH_FILM, width=3, capstyle='round')
        self.bar = c.create_line(cx - half, bar_y, cx - half, bar_y, fill=T.SPLASH_ACCENT, width=3,
                                 capstyle='round')
        self.status = c.create_text(cx, bar_y + T.SPACING['lg'] + T.SPACING['xs'],
                                    text=SPLASH_STAGES[self.stage][0],
                                    fill=T.SPLASH_SUBTITLE, font=T.SPLASH_SUBTITLE_FONT)
        self._paint()

    def _paint(self):
        c = self.canvas
        c.itemconfigure(self.ring, start=(90 - (_time.perf_counter() - self.start) * 240) % 360)
        left, y, right = self.bar_box
        c.coords(self.bar, left, y, left + (right - left) * min(1.0, self.progress), y)

    def _advance(self, dt):
        floor = SPLASH_STAGES[self.stage - 1][1] if self.stage else 0.0
        ceiling = SPLASH_STAGES[self.stage][1]
        # 段内爬到上限的 95% 就停等，不让进度条在没加载完时假装走满。
        self.progress = max(self.progress, floor)
        self.progress = min(ceiling - (ceiling - floor) * 0.05, self.progress + dt * T.SPLASH_CREEP)

    def _tick(self):
        if not self.win.winfo_exists():
            return
        self._advance(T.SPLASH_FRAME_MS / 1000)
        self._paint()
        self._job = self.win.after(T.SPLASH_FRAME_MS, self._tick)

    def _mark(self, name):
        self.marks.setdefault(name, round((_time.perf_counter() - self.start) * 1000, 1))

    def _report(self):
        callback, self.on_finish = self.on_finish, None
        if callback is None:
            return
        try:
            callback(dict(self.marks))
        except Exception:   # 计时只是诊断，绝不能挡住揭开主窗口
            app_logging.swallowed()

    def step(self, index):
        """进入第 index 段（0 起），并立刻刷一帧。"""
        if not self.win.winfo_exists():
            return
        self.stage = max(self.stage, min(index, len(SPLASH_STAGES) - 1))
        self._mark('stage_%d' % self.stage)
        self.progress = max(self.progress, SPLASH_STAGES[self.stage - 1][1] if self.stage else 0.0)
        self.canvas.itemconfigure(self.status, text=SPLASH_STAGES[self.stage][0])
        self._paint()
        # 只刷布局与重绘，不能用 update()：它会把已到期的 after 任务（项目加载、建页）整队排空，
        # 全吞进这一次调用里，Splash 的动画帧就没机会执行，进度条冻结。加载交给主循环按拍推进。
        self.win.update_idletasks()

    def wait(self, ready, done, track=None, timeout=T.SPLASH_MAX_SECONDS):
        """轮询 ready()；连续两拍就绪（或超时）后把进度条走满，再调 done() 并收起画面。

        track() 返回主窗口当前外框时，画面跟着它挪，保证始终整块盖住。"""
        deadline = _time.perf_counter() + timeout
        hits = [0]

        def finish(start, begin):
            if not self.win.winfo_exists():
                return done()
            t = min(1.0, (_time.perf_counter() - start) / (T.SPLASH_FINISH_MS / 1000))
            self.progress = begin + (1.0 - begin) * t
            self._paint()
            if t < 1.0:
                self.win.after(T.SPLASH_FRAME_MS, finish, start, begin)
                return
            self._mark('total')
            try:
                done()
            finally:
                self.close()
                self._report()

        def poll():
            if not self.win.winfo_exists():
                return done()
            if track is not None:
                rect = track()
                if rect:
                    self.cover(rect)
            hits[0] = hits[0] + 1 if ready() else 0
            if hits[0] >= 2 or _time.perf_counter() > deadline:
                self.stage = len(SPLASH_STAGES) - 1
                self._mark('ready')
                # 收尾动画自己推进度，停掉逐帧爬升，免得两边抢着改进度条往回跳。
                if self._job is not None:
                    self.win.after_cancel(self._job)
                    self._job = None
                self.canvas.itemconfigure(self.status, text=SPLASH_STAGES[-1][0])
                finish(_time.perf_counter(), self.progress)
                return
            self.win.after(T.SPLASH_POLL_MS, poll)

        self.win.after(T.SPLASH_POLL_MS, poll)

    def close(self):
        if self._job is not None:
            try:
                self.win.after_cancel(self._job)
            except tk.TclError:
                pass
            self._job = None
        try:
            self.win.destroy()
        except tk.TclError:
            pass

"""遵循 ui_components.md 的 Tk 组件入口。"""
import infra.app_logging as app_logging
import os
import tkinter as tk
from tkinter import messagebox, ttk

from ui.ui_icons import IconLoader
from ui_tokens import (COLORS, NAV_SECONDARY_ICON_SIZE, COMBOBOX_ARROW_COLOR, COMBOBOX_CONTROL_PADDING,
                       COMBOBOX_FIELD_BACKGROUND, COMBOBOX_FONT,
                       COMBOBOX_FOREGROUND, COMBOBOX_PADDING,
                       COMBOBOX_PLACEHOLDER, COMBOBOX_PLACEHOLDER_COLOR,
                       COMBOBOX_WIDTH, COMBOBOX_POPDOWN_HEIGHT, COMBOBOX_MAX_WIDTH,
                       BUTTON_MIN_WIDTH, CONTROL_PADDING_Y, FONTS, RADIUS, SPACING,
                       TEXT_DESC, TEXT_HINT, TEXT_PROGRESS, current_theme, DIALOG_ACTION_GAP,
                       DIALOG_ACTION_HEIGHT, DIALOG_CONTENT_PADDING, DIALOG_TITLE_FONT,
                       TABLE_EMPTY_PADDING, TABLE_HEADER_FONT, TABLE_ROW_FONT, TABLE_COMPACT_HEADER_PADDING,
                       TABLE_ROW_HEIGHT, INPUT_BACKGROUND, INPUT_BORDER,
                       INPUT_BORDER_HOVER, INPUT_BORDER_WIDTH, INPUT_ERROR_BORDER,
                       INPUT_FOCUS_BORDER, INPUT_FONT, INPUT_FOREGROUND,
                       INPUT_PADDING_X, INPUT_PADDING_Y, INPUT_PLACEHOLDER_FOREGROUND,
                       ICON_FONT, BUTTON_RADIUS, CONTROL_CORNER_SURFACE, ROUND_TILE_BUTTON, ROUND_TILE_CARD,
                       NAV_SUB_PADDING_X,
                       SCROLLBAR_THUMB, SCROLLBAR_THUMB_ACTIVE, SCROLLBAR_TROUGH, SCROLLBAR_BORDER_WIDTH, SCROLLBAR_WIDTH)
from ui.ui_motion import BusyState, bind_row_hover, empty_icon
from ui.ui_hover_fade import install_hover_fade
from ui.ui_composer_style import install_composer_styles
from ui.ui_popup import register_menu, text_units_width
from ui.ui_rounded import (button_specs, pressed_padding, rounded_layout, set_button_padding, rounded_photo as _rounded_photo,
                        rounded_png_bytes as _rounded_png_bytes)
from ui.ui_tooltip import EllipsisLabel, Tooltip, TreeRowTooltip  # noqa: F401  转出，旧导入路径不变
from ui.ui_status_bus import deliver_notice  # R3056：通知分级逻辑迁至 ui_status_bus，本模块守住行数棘轮


def _configure_button(style, name, *, background, foreground,
                      active_background, active_foreground,
                      pressed_background=None,
                      disabled_background=None,
                      disabled_foreground=None,
                      padding=(SPACING["md"], CONTROL_PADDING_Y),
                      font=None, anchor=None, border_color=None, border_width=0):
    """圆角按钮：底图是带 alpha 的圆角 PNG，四态各一张；按钮自身的 ``fill`` 选项记录填充色。

    ttk 把圆角透明处露出的是样式的 ``background``，所以 ``background`` 必须是按钮背后的
    表面色（``CONTROL_CORNER_SURFACE``），而不是按钮的填充色，否则四个角会被填成实心方角。
    """
    root = style.master
    pressed_background = pressed_background or active_background
    disabled_background = COLORS["disabled_bg"] if disabled_background is None else disabled_background
    disabled_foreground = COLORS["disabled_text"] if disabled_foreground is None else disabled_foreground
    states = (("normal", background), ("active", active_background),
              ("pressed", pressed_background), ("disabled", disabled_background))
    images = {}
    tile_w, tile_h = ROUND_TILE_BUTTON
    for state, color in states:
        images[state], pr = _rounded_photo(root, color, BUTTON_RADIUS,
                                           width=BUTTON_RADIUS * 2 + tile_w,
                                           height=BUTTON_RADIUS * 2 + tile_h,
                                           border=border_color, border_width=border_width)
    element = "Drama.Rounded." + name.replace(".", "_") + "." + current_theme()
    if element not in style.element_names():
        style.element_create(element, "image", images["normal"], ("disabled", images["disabled"]),
                             ("pressed", images["pressed"]), ("active", images["active"]),
                             border=(pr, pr, pr, pr), padding=(0, 0, 0, 0), width=1, height=1, sticky="nsew")
    rounded_layout(style, name, element)
    button_specs(root)[name] = {
        "colors": dict(states), "images": images,
        "border": (border_color, border_width), "size": (tile_w, tile_h)}
    options = {"font": font or FONTS["body"], "padding": padding,
               "background": CONTROL_CORNER_SURFACE, "fill": background,
               "foreground": foreground, "focuscolor": COLORS["focus"],
               "width": -BUTTON_MIN_WIDTH}
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
              padding=pressed_padding(padding))


def _install_button_styles(style, root):
    solid = dict(foreground=COLORS["on_accent"],
                 active_background=COLORS["primary_hover"],
                 active_foreground=COLORS["on_accent"],
                 pressed_background=COLORS["primary_pressed"])
    _configure_button(style, "Primary.TButton", background=COLORS["primary"], **solid)
    _configure_button(style, "Tokens.Primary.TButton", background=COLORS["primary"], **solid)
    _configure_button(style, "Send.TButton", background=COLORS["primary"], **solid)
    _configure_button(style, "Selected.Compact.TButton", background=COLORS["primary"], **solid)
    # 侧栏选中态＝浅灰胶囊＋深色内容（X 桌面风格），不再用主色实心块。
    pill = dict(background=COLORS["surface_pressed"], foreground=COLORS["text_primary"],
                active_background=COLORS["border_input"], active_foreground=COLORS["text_primary"], pressed_background=COLORS["border_input_hover"])
    _configure_button(style, "Selected.Nav.TButton", anchor="w", **pill)
    _configure_button(style, "Selected.Sub.Nav.TButton", anchor="w",
                      padding=(NAV_SUB_PADDING_X, CONTROL_PADDING_Y), **pill)
    _configure_button(style, "Highlight.TButton", background=COLORS["primary_pressed"],
                      foreground=COLORS["on_accent"],
                      active_background=COLORS["primary_pressed"],
                      active_foreground=COLORS["on_accent"],
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
                      foreground=COLORS["on_accent"],
                      active_background=COLORS["danger_hover"],
                      active_foreground=COLORS["on_accent"],
                      pressed_background=COLORS["danger_pressed"])
    nav = dict(background=COLORS["background_primary"],
               foreground=COLORS["text_primary"],
               active_background=COLORS["surface_hover"],
               active_foreground=COLORS["text_primary"],
               pressed_background=COLORS["surface_pressed"])
    _configure_button(style, "Nav.TButton", anchor="w",
                      padding=(SPACING["xs"], CONTROL_PADDING_Y), **nav)
    _configure_button(style, "Sub.Nav.TButton", anchor="w",
                      padding=(NAV_SUB_PADDING_X, CONTROL_PADDING_Y), **nav)
    # 纯图标小按钮（项目分组筛选／新建／打开目录）：居中、最小横向内边距，一行放两颗。
    _configure_button(style, "RailIcon.TButton", anchor="center", padding=(SPACING["xs"], SPACING["xs"]), **nav)
    _configure_button(style, "Selected.RailIcon.TButton", anchor="center", padding=(SPACING["xs"], SPACING["xs"]), **pill)
    _configure_button(style, "Tokens.Text.TButton",
                      background=COLORS["background_primary"],
                      foreground=COLORS["primary_text"],
                      active_background=COLORS["surface_hover"],
                      active_foreground=COLORS["primary_text"],
                      pressed_background=COLORS["surface_pressed"])


def _install_card_style(style, root):
    factor = float(root.tk.call("tk", "scaling")) / (96.0 / 72.0)
    pr = max(1, round(RADIUS["lg"] * factor))
    tile_w, tile_h = ROUND_TILE_CARD
    image, _ = _rounded_photo(root, COLORS["background_card"], RADIUS["lg"],
                              width=RADIUS["lg"] * 2 + tile_w, height=RADIUS["lg"] * 2 + tile_h,
                              border=COLORS["border_default"], border_width=1)
    element = "Drama.Card." + current_theme()
    if element not in style.element_names():
        # width/height=1：否则 ttk 把控件最小尺寸撑成整张底图（大中心区会让按钮高 80px）。
        style.element_create(element, "image", image, border=(pr, pr, pr, pr),
                             padding=(0, 0, 0, 0), width=1, height=1, sticky="nsew")
    if "Drama.Card" not in style.element_names(): style.element_create("Drama.Card", "image", image, border=(pr, pr, pr, pr), padding=(0, 0, 0, 0), width=1, height=1, sticky="nsew")  # 裸名登记兼容（test_ui_modern_system 按名断言）
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
    root.option_add("*TCombobox*Listbox.selectBackground", COLORS["selection_bg"])
    root.option_add("*TCombobox*Listbox.selectForeground", COLORS["selection_text"])
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
    # 同一主题同一明暗下样式已装好就不再重配；换主题（含日间／夜间切换）后重新安装。
    marker = '%s|%s' % (style.theme_use(), current_theme())
    try:
        if str(style.tk.globalgetvar("drama_styles_theme")) == marker:
            return
    except tk.TclError:
        pass
    _install_button_styles(style, root)
    install_hover_fade(root)
    _install_card_style(style, root)
    install_composer_styles(style, root, _configure_button)
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
    style.configure("Tokens.Dialog.Danger.TLabel", font=FONTS["body"],
                    foreground=COLORS["danger_text"], background=COLORS["danger_subtle"],
                    padding=(SPACING["md"], SPACING["sm"]))
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
    style.tk.globalsetvar("drama_styles_theme", marker)


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
    """选项显示宽度（ttk 字符单位）：真实字体测宽换算，不再用全角×2/ASCII×1 近似。"""
    return text_units_width(COMBOBOX_FONT, (value,))


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

        if state == "readonly" and kwargs.get("textvariable") is None:
            kwargs["textvariable"] = tk.StringVar(master)  # 占位提示要跟随取值，自管一个变量
        super().__init__(master, values=values, height=height, width=width,
                         state=state, postcommand=post, **kwargs)
        self._hint = None
        if state == "readonly" and hasattr(kwargs.get("textvariable"), "trace_add"):
            self._install_placeholder(kwargs["textvariable"])

    def _install_placeholder(self, variable):
        """取值为空时在框内显示灰色“请选择”；取值本身仍是空串，页面逻辑不受影响。"""
        self._hint = tk.Label(self, text=COMBOBOX_PLACEHOLDER, font=COMBOBOX_FONT, bd=0,
                              fg=COMBOBOX_PLACEHOLDER_COLOR, bg=COMBOBOX_FIELD_BACKGROUND)
        self._hint.bind("<Button-1>", lambda event: self._post_from_hint())
        self._hint_variable = variable
        variable.trace_add("write", lambda *args: self._sync_placeholder())
        self.bind("<Map>", lambda event: self._sync_placeholder(), add="+")
        self._sync_placeholder()

    def _sync_placeholder(self):
        try:
            if str(self._hint_variable.get()) == "":
                self._hint.place(x=COMBOBOX_PADDING[0], rely=0.5, anchor="w")
                self._hint.lift()
            else:
                self._hint.place_forget()
        except tk.TclError:
            pass

    def _post_from_hint(self):
        if "disabled" not in self.state():
            self.focus_set()
            self.tk.call("ttk::combobox::Post", self)

    def _accent_popdown(self):
        """列表载入后把特殊项染成主色：弹出窗的列表框在 postcommand 之后才填充，故延后一拍。"""
        try:
            listbox = '%s.f.l' % self.tk.call('ttk::combobox::PopdownWindow', self)
            for index, value in enumerate(self.cget('values')):
                if value in self.accent_values:
                    self.tk.call(listbox, 'itemconfigure', index, '-foreground', COLORS['primary_text'])
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
        """全部选项＋当前值的最长显示宽度（真实字体测宽），封顶 COMBOBOX_MAX_WIDTH。"""
        texts = [str(v) for v in values]
        if current:
            texts.append(str(current))
        return min(COMBOBOX_MAX_WIDTH, text_units_width(COMBOBOX_FONT, texts) or COMBOBOX_WIDTH)

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
    """单行文本入口，统一占位、只读和错误态；``mask``（密码）只遮输入，不遮占位文字。"""

    NORMAL_STYLE = "Tokens.LineInput.TEntry"
    PLACEHOLDER_STYLE = "Tokens.LineInput.Placeholder.TEntry"
    ERROR_STYLE = "Tokens.LineInput.Error.TEntry"

    def __init__(self, master=None, *, placeholder="", mask="", **kwargs):
        setup_styles(master)
        kwargs.setdefault("style", self.NORMAL_STYLE)
        super().__init__(master, **kwargs)
        self._placeholder, self._mask = placeholder, mask or kwargs.get("show", "")
        self._placeholder_active = False
        self.error_message = None
        self.bind("<FocusIn>", self._remove_placeholder, add="+")
        self.bind("<FocusOut>", self._restore_placeholder, add="+")
        self._restore_placeholder()

    def _set_style(self):
        style = self.ERROR_STYLE if self.error_message else self.PLACEHOLDER_STYLE if self._placeholder_active else self.NORMAL_STYLE
        self.configure(style=style, show="" if self._placeholder_active else self._mask)

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

    def set_mask(self, mask):
        self._mask = mask
        self._set_style()

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
            "insertbackground": COLORS["text_primary"],
            "selectbackground": COLORS["selection_bg"],
            "selectforeground": COLORS["selection_text"],
            "inactiveselectbackground": COLORS["selection_bg"],
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
            self.configure(fg=COLORS["text_primary"])

    def _restore_placeholder(self, _event=None):
        if (self._placeholder and not self._placeholder_active
                and not super().get("1.0", "end-1c")
                and str(self.cget("state")) == "normal"):
            super().insert("1.0", self._placeholder)
            self._placeholder_active = True
            self.configure(fg=COLORS["text_muted"])

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

    def __init__(self, status, parent=None, dialogs=messagebox, bus=None):
        self.status = status
        self.parent = parent
        self.bus = bus  # R2989 P1：注入统一状态栏总线时走四级消息生命周期
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
        deliver_notice(self.bus, self.status, level, text)
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


class ContextMenu:
    """右键菜单的唯一构建、定位和抓取释放入口。"""

    def __init__(self, owner, menu_factory=tk.Menu):
        self.menu = menu_factory(owner, tearoff=False)
        register_menu(self.menu)

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
        register_menu(child.menu)
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

    icon_name = "project_files"

    def __init__(self, parent, title, *, geometry=None, minsize=None, modal=True,
                 on_close=None, chrome=True):
        super().__init__(parent)
        self.configure(bg=COLORS["background_primary"])
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
            icon = IconLoader.nav_icon(self._root(), self.icon_name, size=NAV_SECONDARY_ICON_SIZE)
            ttk.Label(self.header, text=title, image=icon, compound="left",
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
        input_types = (tk.Entry, tk.Text, ttk.Entry, ttk.Combobox)
        button_types = (ttk.Button, tk.Button)
        interactive_types = input_types + button_types + (
            ttk.Checkbutton, ttk.Radiobutton, tk.Checkbutton, tk.Radiobutton,
            tk.Listbox, ttk.Treeview)
        content = list(self._descendants(self.content))
        for widget in content:
            if isinstance(widget, input_types) and self._enabled(widget):
                widget.focus_set()
                return
        for widget in content:
            if isinstance(widget, interactive_types) and self._enabled(widget):
                widget.focus_set()
                return
        if self.actions is None:
            return
        buttons = [widget for widget in self._descendants(self.actions)
                   if isinstance(widget, button_types) and self._enabled(widget)]
        for preferred in (True, False):
            for widget in buttons:
                primary = bool(getattr(widget, "_dialog_primary", False))
                dangerous = bool(getattr(widget, "_dialog_dangerous", False))
                if preferred and primary and not dangerous:
                    widget.focus_set()
                    return
                if not preferred and not primary and not dangerous:
                    widget.focus_set()
                    return
        if buttons:
            buttons[0].focus_set()

    @staticmethod
    def _enabled(widget):
        try:
            if isinstance(widget, ttk.Widget):
                return "disabled" not in widget.state()
            return str(widget.cget("state")) != "disabled"
        except tk.TclError:
            return False

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
            button = PrimaryButton(self.actions, text=text, command=command,
                                   style="Tokens.Danger.TButton")
        elif primary:
            button = PrimaryButton(self.actions, text=text, command=command)
        else:
            button = SecondaryButton(self.actions, text=text, command=command)
        button._dialog_primary = bool(primary)
        button._dialog_dangerous = bool(dangerous)
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

    icon_name = "edit"

    def add_form_actions(self, submit_text, on_submit, cancel_text="取消"):
        self.add_action(cancel_text, self.close)
        return self.add_action(submit_text, on_submit, primary=True)


class ConfirmDialog(BaseDialog):
    """询问或危险确认的标准弹窗；结果通过 ``result`` 和回调给调用方。"""

    icon_name = "lock"

    def __init__(self, parent, title, message, *, dangerous=False, on_result=None,
                 confirm_text="确认", cancel_text="取消", **kwargs):
        self.result = None
        self._on_result = on_result
        super().__init__(parent, title, **kwargs)
        if dangerous:
            ttk.Label(self.content, text=message, style="Tokens.Dialog.Danger.TLabel",
                      wraplength=TEXT_DESC["wraplength"], justify="left").pack(fill="x")
        else:
            DescriptionBlock(self.content, text=message).pack(fill="x")
        self.add_action(cancel_text, self._cancel)
        self.add_action(confirm_text, self._confirm, primary=not dangerous, dangerous=dangerous)

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


class NoticeDialog(BaseDialog):
    """只告知、不需决定的提示窗（保留换行，适合多行摘要）；只有一个“知道了”。"""

    def __init__(self, parent, title, message, **kwargs):
        super().__init__(parent, title, **kwargs)
        DescriptionBlock(self.content, text=message).pack(fill="x")
        self.add_action("知道了", self.close, primary=True)


def ask_confirmation(parent, title, message, *, dangerous=False, confirm_text="确认", cancel_text="取消"):
    """以统一确认窗提供旧式同步布尔语义。

    业务确认过去大多依赖 ``messagebox.askyesno`` 的同步返回值；在调用点
    尚未全部改为回调前，使用此入口可统一弹窗外观并保留 ``True``／``False``
    语义。关闭、Esc 与取消都稳定返回 ``False``。
    """
    dialog = ConfirmDialog(parent, title, message, dangerous=dangerous,
                           confirm_text=confirm_text, cancel_text=cancel_text)
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

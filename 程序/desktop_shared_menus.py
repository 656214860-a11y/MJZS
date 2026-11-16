"""共享输入框的图标下拉面板（R2971）：✦ 技能选择与 ＋ 添加菜单。

与 ``/`` 补全同一套浮层语言——输入盒正上方的卡片（``background_card`` 底＋
``border_input_hover`` 1px 描边、与输入盒同宽左对齐），``place`` 锚定、窗口重排跟随；
不再弹 ``BaseDialog``／Toplevel。面板只做呈现：技能清单、默认勾选、说明卡与
导入／模型动作全部回调宿主 ``SharedStageInput``（duck-typed，不反向 import）。
"""
from __future__ import annotations

import tkinter as tk

import app_logging
from ui_icons import IconLoader
from ui_tokens import COLORS, FONTS, SPACING

# 与 CompletionPopup.MAX_ITEMS 同量级：当前阶段技能在前，超出截断。
MAX_ROWS = 12
# 默认勾选框边长（像素常量）。
CHECK_SIZE = 14


class AnchoredPanel(tk.Frame):
    """输入盒正上方的下拉面板：与 ``/`` 补全同一卡片描边与锚定几何。"""

    def __init__(self, host):
        super().__init__(host, bg=COLORS['background_card'],
                         highlightthickness=1,
                         highlightbackground=COLORS['border_input_hover'])
        self.host = host
        self.open = False

    # ── 开合 ──────────────────────────────────────────────────────────
    def is_open(self):
        return bool(self.open) and self.winfo_exists()

    def show(self):
        """重建内容并展开；``refresh`` 由子类给出。"""
        self.refresh()
        self.open = True
        self.place_panel()

    def hide(self):
        self.open = False
        try:
            self.place_forget()
        except tk.TclError:
            app_logging.swallowed()

    def toggle(self):
        if self.is_open():
            self.hide()
        else:
            self.show()

    def refresh(self):
        """子类重建行；面板开着时顺带按新内容重贴几何。"""

    def anchor_widgets(self):
        """点这些控件不算「点到面板外」（各面板的触发图标钮）。"""
        return ()

    # ── 几何：与 CompletionPopup.place 同一套锚定 ──────────────────────
    def place_panel(self):
        """下缘悬在输入盒上沿、左缘对齐、同宽；顶出屏幕才退回贴顶。"""
        if not self.is_open():
            return
        try:
            card = self.host.input_card
            self.update_idletasks()
            height = self.winfo_reqheight()
            width = max(SPACING['md'] * 8, card.winfo_width())
            x = card.winfo_x()
            root_y = self.host.winfo_rooty() + card.winfo_y() - height - SPACING['xs']
            y = 0 if root_y < 0 else card.winfo_y() - height - SPACING['xs']
            self.place(x=x, y=y, width=width)
        except tk.TclError:
            app_logging.swallowed()

    # ── 行 ────────────────────────────────────────────────────────────
    def clear(self):
        for child in self.winfo_children():
            child.destroy()

    def _hover_bg(self, widgets, on):
        bg = COLORS['surface_hover'] if on else COLORS['background_card']
        for widget in widgets:
            try:
                widget.configure(bg=bg)
            except tk.TclError:
                app_logging.swallowed()

    def _bind_hover(self, target, widgets):
        target.bind('<Enter>', lambda _e: self._hover_bg(widgets, True))
        target.bind('<Leave>', lambda _e: self._hover_bg(widgets, False))

    def _activate(self, command, *, close=True):
        if close:
            self.hide()
        command()

    def _text_row(self, text, command, *, close=True):
        """一行可点文字：悬停底色跟随、点击执行（``close`` 时先收面板）。"""
        row = tk.Frame(self, bg=COLORS['background_card'])
        row.pack(fill='x')
        label = tk.Label(row, text=text, anchor='w', justify='left',
                         bg=COLORS['background_card'], fg=COLORS['text_primary'],
                         font=FONTS['body'], padx=SPACING['md'], pady=SPACING['xs'],
                         cursor='hand2')
        label.pack(fill='x')
        self._bind_hover(label, (row, label))
        label.bind('<Button-1>', lambda _e: self._activate(command, close=close))
        return row


class SkillPickPanel(AnchoredPanel):
    """✦ 技能下拉：点名插入 ``/名称``、勾选＝本阶段默认、悬停看说明卡。"""

    def __init__(self, host):
        super().__init__(host)
        self._check_images = []

    def anchor_widgets(self):
        button = getattr(self.host, 'skill_button', None)
        return (button,) if button is not None else ()

    def refresh(self):
        self.clear()
        self._check_images = []
        host = self.host
        defaults = set(host._default_skills() or ())
        items = host._skill_list_items()
        if not items:
            tk.Label(self, text='（暂无可用技能）', anchor='w',
                     bg=COLORS['background_card'], fg=COLORS['text_muted'],
                     font=FONTS['hint'], padx=SPACING['md'],
                     pady=SPACING['xs']).pack(fill='x')
        for item in items[:MAX_ROWS]:
            self._skill_row(item, defaults)
        if self.open:
            self.place_panel()

    def _skill_row(self, item, defaults):
        host = self.host
        name = host._skill_name(item)
        row = tk.Frame(self, bg=COLORS['background_card'])
        row.pack(fill='x')
        widgets = [row]
        hoverables = []
        if host.project is not None:
            image = IconLoader.check_indicator(self, size=CHECK_SIZE,
                                               selected=name in defaults)
            self._check_images.append(image)
            check = tk.Label(row, image=image, bg=COLORS['background_card'],
                             cursor='hand2')
            check.pack(side='left', padx=(SPACING['sm'], SPACING['xs']))
            widgets.append(check)
            hoverables.append(check)
            check.bind('<Button-1>',
                       lambda _e, n=name: host._toggle_skill_default(n))
        label = tk.Label(row, text=host._skill_display(item), anchor='w',
                         bg=COLORS['background_card'], fg=COLORS['text_primary'],
                         font=FONTS['body'], pady=SPACING['xs'], cursor='hand2')
        label.pack(side='left', fill='x', expand=True)
        widgets.append(label)
        hoverables.append(label)
        label.bind('<Button-1>', lambda _e, it=item: host._pick_skill(it))
        for target in hoverables:
            # 先挂悬停底色，再以 add='+' 追加说明卡——同序列裸 bind 会互相覆盖。
            self._bind_hover(target, widgets)
            target.bind('<Enter>', lambda _e, it=item: host._show_skill_card(it, self),
                        add='+')
            target.bind('<Leave>', lambda _e: host._hide_skill_card(), add='+')


class AddMenuPanel(AnchoredPanel):
    """＋ 添加下拉：附件、模型管理、技能导入（仓库／本地）三合一入口。"""

    def __init__(self, host):
        super().__init__(host)
        self._drilled = False

    def anchor_widgets(self):
        button = getattr(self.host, 'attachment_button', None)
        return (button,) if button is not None else ()

    def show(self):
        self._drilled = False
        super().show()

    def refresh(self):
        self.clear()
        host = self.host
        if self._drilled:
            self._text_row('‹ 返回', self._drill_out, close=False)
            self._text_row('从仓库导入', host._import_skill_repo)
            self._text_row('本地安装', host._import_skill_local)
        else:
            self._text_row('添加附件', host.open_attachments)
            self._text_row('添加模型…', host.open_model_manager)
            self._text_row('添加技能…', self._drill_in, close=False)
        if self.open:
            self.place_panel()

    def _drill_in(self):
        self._drilled = True
        self.refresh()

    def _drill_out(self):
        self._drilled = False
        self.refresh()

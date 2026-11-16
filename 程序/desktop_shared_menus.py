"""共享输入框的图标下拉面板与候选浮层（R2971／R2980）。

``AnchoredPanel`` 系：输入盒正上方的卡片（``background_card`` 底＋
``border_input_hover`` 1px 描边、与输入盒同宽左对齐），``place`` 锚定、窗口重排跟随；
不再弹 ``BaseDialog``／Toplevel。面板只做呈现：技能清单、默认勾选、说明卡与
导入／模型动作全部回调宿主 ``SharedStageInput``（duck-typed，不反向 import）。

``CandidatePopup``（R2980）：``/`` 命令与 ``@`` 引用共用的光标级候选浮层——
锚在文本光标正下方、不足翻上、屏幕四边钳制；自绘行带类别徽标与匹配子串高亮，
上下键／Tab／点击／悬停导航，采纳经宿主 ``_apply_candidate``。
"""
from __future__ import annotations

import tkinter as tk

import app_logging
from ui_icons import IconLoader
from ui_tokens import COLORS, FONTS, ICON_DOCUMENT, ICON_FONT, SPACING
from ui_widgets import Tooltip

# 与 CompletionPopup.MAX_ITEMS 同量级：当前阶段技能在前，超出截断。
MAX_ROWS = 12
# 默认勾选框边长（像素常量）。
CHECK_SIZE = 14
# 候选浮层行数上限、类别徽标文案与行首图标（R2980）。
CANDIDATE_MAX_ROWS = 12
KIND_BADGES = {'skill': '技能', 'stage': '阶段', 'engine': '子引擎', 'attachment': '附件'}
KIND_ICONS = {'attachment': ICON_DOCUMENT}


class AnchoredPanel(tk.Frame):
    """输入盒正上方的下拉面板：与 ``/`` 补全同一卡片描边与锚定几何。

    必须挂在窗口（``winfo_toplevel``）下：Tk 的 ``place`` 画不出 master 边界，
    挂在 ``SharedStageInput`` 上、y 为负的面板会被整体裁掉（R2971 实测）。
    """

    def __init__(self, host):
        super().__init__(host.winfo_toplevel(), bg=COLORS['background_card'],
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
        """下缘悬在输入盒上沿、左缘对齐、同宽；顶出屏幕才退回贴顶。

        坐标换算到窗口（master）相对系：卡片屏幕坐标减窗口原点；
        ``lift`` 保证面板压在页面内容之上（同级兄弟后建者居上）。
        """
        if not self.is_open():
            return
        try:
            card = self.host.input_card
            top = self.master
            self.update_idletasks()
            height = self.winfo_reqheight()
            # 宽高随内容自适应（REQ-S01-90 定版）：宽取行内容自然宽，封顶输入盒宽。
            width = max(SPACING['md'] * 8,
                        min(self.winfo_reqwidth(), card.winfo_width()))
            x = card.winfo_rootx() - top.winfo_rootx()
            screen_top = card.winfo_rooty() - height - SPACING['xs']
            y = (0 if screen_top < 0
                 else card.winfo_rooty() - top.winfo_rooty() - height - SPACING['xs'])
            self.place(x=x, y=y, width=width)
            self.lift()
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
        self._check_rows = {}
        host = self.host
        items = host._skill_list_items()
        if not items:
            tk.Label(self, text='（暂无可用技能）', anchor='w',
                     bg=COLORS['background_card'], fg=COLORS['text_muted'],
                     font=FONTS['hint'], padx=SPACING['md'],
                     pady=SPACING['xs']).pack(fill='x')
        for item in items[:MAX_ROWS]:
            self._skill_row(item)
        if self.open:
            self.place_panel()

    def sync_check(self, name):
        """勾选落盘后只刷这一行的勾选像：不整版重建（重建会把未点行也弹回未勾选）。"""
        check = self._check_rows.get(name)
        if check is None:
            return
        try:
            selected = name in set(self.host._default_skills() or ())
        except Exception:
            selected = False
        image = IconLoader.check_indicator(self, size=CHECK_SIZE, selected=selected)
        self._check_images.append(image)
        try:
            check.configure(image=image)
        except tk.TclError:
            app_logging.swallowed()

    def _skill_row(self, item):
        host = self.host
        name = host._skill_name(item)
        row = tk.Frame(self, bg=COLORS['background_card'])
        row.pack(fill='x')
        widgets = [row]
        hoverables = []
        if host.project is not None:
            # 面板每次打开一律未勾选（用户 2026-11-16 定版）：勾选＝本阶段默认的
            # 写回语义不变，但默认态不预填，点了才由 sync_check 体现。
            image = IconLoader.check_indicator(self, size=CHECK_SIZE, selected=False)
            self._check_images.append(image)
            check = tk.Label(row, image=image, bg=COLORS['background_card'],
                             cursor='hand2')
            check.pack(side='left', padx=(SPACING['sm'], SPACING['xs']))
            widgets.append(check)
            hoverables.append(check)
            self._check_rows[name] = check
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
            target.bind('<Enter>', lambda _e, it=item: host._show_skill_card(it, row),
                        add='+')
            target.bind('<Leave>', lambda _e: host._schedule_skill_card_hide(), add='+')


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


class CandidatePopup:
    """``/`` 命令与 ``@`` 引用共用的光标级候选浮层（R2980，REQ-S01-91）。

    与 ``AnchoredPanel`` 同一张卡片描边，但锚点是**文本光标**而非输入盒：
    优先摆在光标正下方，底部空间不足翻到光标上方，再不行钳到屏幕内；
    宿主几何变化（``<Configure>``）与文本改动后由 ``place`` 重贴。
    行为契约沿用旧 ``CompletionPopup``：上下键移动、Tab／点击采纳、
    失焦收掉；Enter 由宿主 ``_on_return`` 统一拦截（候选优先于发送）。
    """

    def __init__(self, host):
        self.host = host
        self.open = False
        self.entries = ()
        self.query = ''
        self.index = 0
        self._rows = []
        # 与 AnchoredPanel 同理挂顶层窗：光标上方空间不足时浮层 y 为负，
        # 挂在 SharedStageInput 上会被 master 边界裁掉（R2971 实测）。
        self.frame = tk.Frame(host.winfo_toplevel(), bg=COLORS['background_card'],
                              highlightthickness=1,
                              highlightbackground=COLORS['border_input_hover'])

    # ── 内容 ──────────────────────────────────────────────────────────
    def refresh(self, entries, query=''):
        """重建候选行并展开；空候选直接收掉。``query`` 用于匹配子串高亮。"""
        self.entries = tuple(entries or ())
        self.query = str(query or '')
        self._rows = []
        for child in self.frame.winfo_children():
            child.destroy()
        if not self.entries:
            self.close()
            return
        for index, entry in enumerate(self.entries[:CANDIDATE_MAX_ROWS]):
            self._row(entry, index)
        extra = len(self.entries) - CANDIDATE_MAX_ROWS
        if extra > 0:
            tk.Label(self.frame, text='… 还有 %d 项' % extra, anchor='w',
                     bg=COLORS['background_card'], fg=COLORS['text_muted'],
                     font=FONTS['hint'], padx=SPACING['md'],
                     pady=SPACING['xs']).pack(fill='x')
        self.index = 0
        self._paint()
        self.open = True
        self.place()

    def _segments(self, label):
        """按 ``query`` 子串切 ``label`` 为 (文本, 是否命中) 段；无命中返回单段。"""
        text = str(label or '')
        needle = self.query.strip().lower()
        if not needle:
            return ((text, False),)
        hit = text.lower().find(needle)
        if hit < 0:
            return ((text, False),)
        return ((text[:hit], False), (text[hit:hit + len(needle)], True),
                (text[hit + len(needle):], False))

    def _row(self, entry, index):
        row = tk.Frame(self.frame, bg=COLORS['background_card'])
        row.pack(fill='x')
        widgets = [row]
        badge = KIND_BADGES.get(str(entry.get('kind') or ''), '')
        if badge:
            tag = tk.Label(row, text=badge, anchor='e',
                           bg=COLORS['background_card'], fg=COLORS['text_muted'],
                           font=FONTS['hint'], padx=SPACING['md'])
            tag.pack(side='right')
            widgets.append(tag)
        icon_text = KIND_ICONS.get(str(entry.get('kind') or ''))
        if icon_text:
            icon = tk.Label(row, text=icon_text, anchor='w',
                            bg=COLORS['background_card'], fg=COLORS['text_muted'],
                            font=ICON_FONT, padx=SPACING['md'])
            icon.pack(side='left')
            widgets.append(icon)
        body = tk.Frame(row, bg=COLORS['background_card'])
        body.pack(side='left', fill='x', expand=True,
                  padx=(SPACING['xs'] if icon_text else SPACING['md'], SPACING['md']))
        widgets.append(body)
        marks = []
        for chunk, matched in self._segments(entry.get('label')):
            if not chunk:
                continue
            if matched:
                label = tk.Label(body, text=chunk, anchor='w',
                                 bg=COLORS['primary_subtle'],
                                 fg=COLORS['selection_text'],
                                 font=FONTS['body'])
                marks.append(label)
            else:
                label = tk.Label(body, text=chunk, anchor='w',
                                 bg=COLORS['background_card'],
                                 fg=COLORS['text_primary'],
                                 font=FONTS['body'])
            label.pack(side='left')
            widgets.append(label)
        hint = str(entry.get('hint') or '')
        if hint:
            for widget in widgets[1:]:
                try:
                    Tooltip(widget, hint)
                except Exception:
                    app_logging.swallowed()
        record = {'index': index, 'entry': entry, 'widgets': widgets,
                  'marks': marks}
        self._rows.append(record)
        for widget in widgets:
            widget.bind('<Button-1>',
                        lambda _e, it=entry: self.host._apply_candidate(it))
            widget.bind('<Enter>',
                        lambda _e, i=index: self._select(i), add='+')

    # ── 选中与按键 ────────────────────────────────────────────────────
    def _select(self, index):
        if index == self.index:
            return
        self.index = index
        self._paint()

    def _paint(self):
        for record in self._rows:
            on = record['index'] == self.index
            bg = COLORS['surface_hover'] if on else COLORS['background_card']
            marks = set(record.get('marks') or ())
            for widget in record['widgets']:
                if widget in marks:
                    continue  # 命中段保留 primary_subtle 底纹，不被行底色盖掉
                try:
                    widget.configure(bg=bg)
                except tk.TclError:
                    app_logging.swallowed()

    def selected(self):
        if 0 <= self.index < len(self.entries):
            return self.entries[self.index]
        return None

    def move(self, delta):
        count = min(len(self.entries), CANDIDATE_MAX_ROWS)
        if not count:
            return
        index = max(0, min(count - 1, self.index + delta))
        if index != self.index:
            self.index = index
            self._paint()

    def key(self, event):
        """候选开着时：上下键移动高亮、Tab 采纳当前项；否则放行默认行为。"""
        if not self.open or not self.entries:
            return None
        if event.keysym == 'Up':
            self.move(-1)
            return 'break'
        if event.keysym == 'Down':
            self.move(1)
            return 'break'
        if event.keysym == 'Tab':
            entry = self.selected()
            if entry is not None:
                self.host._apply_candidate(entry)
                return 'break'
        return None

    # ── 几何：锚在文本光标 ────────────────────────────────────────────
    def place(self):
        """光标正下方优先；下方空间不足翻到光标上方；最后钳到可视区四边。

        可视区＝顶层窗矩形与屏幕矩形的交集——``place`` 画不出窗口外，
        输入框贴窗口底部时「下方」实际只有图标行与状态栏，必须按窗口底边判翻转。
        """
        if not self.open:
            return
        try:
            self.frame.update_idletasks()
            height = self.frame.winfo_reqheight()
            top = self.frame.winfo_toplevel()
            hx = top.winfo_rootx()
            hy = top.winfo_rooty()
            left = max(SPACING['xs'], hx)
            right = min(hx + top.winfo_width(),
                        self.frame.winfo_screenwidth() - SPACING['xs'])
            bottom = min(hy + top.winfo_height(),
                         self.frame.winfo_screenheight() - SPACING['xs'])
            top_edge = max(SPACING['xs'], hy)
            width = min(self.frame.winfo_reqwidth(),
                        max(SPACING['md'] * 8, self.host.winfo_width()),
                        max(SPACING['md'] * 4, right - left))
            anchor = self._cursor_anchor()
            if anchor is None:
                return
            cursor_x, cursor_top, cursor_bottom = anchor
            gap = SPACING['xs'] // 2
            y = cursor_bottom + gap
            if y + height > bottom:
                y = cursor_top - height - gap
            y = max(top_edge, min(y, bottom - height))
            x = max(left, min(cursor_x, right - width))
            self.frame.place(x=x - hx, y=y - hy, width=width)
        except tk.TclError:
            app_logging.swallowed()

    def _cursor_anchor(self):
        """光标锚点（屏幕绝对坐标）：(x, 行顶, 行底)；量不到退回输入区顶中。"""
        try:
            box = self.host.input.bbox('insert')
        except tk.TclError:
            box = None
        if box:
            return (self.host.input.winfo_rootx() + box[0],
                    self.host.input.winfo_rooty() + box[1],
                    self.host.input.winfo_rooty() + box[1] + box[3])
        try:
            x = self.host.input.winfo_rootx() + self.host.input.winfo_width() // 2
            y = self.host.input.winfo_rooty()
            return (x, y, y)
        except tk.TclError:
            return None

    # ── 开合 ──────────────────────────────────────────────────────────
    def focus_out(self, _event=None):
        """焦点离开输入框：等下一次空闲看落在哪，没落在输入/候选上就收掉。"""
        if not self.open:
            return None
        try:
            self.host.after_idle(self.close_if_focus_away)
        except Exception:
            app_logging.swallowed()
        return None

    def close_if_focus_away(self):
        if not self.open:
            return
        try:
            focus = self.host.winfo_toplevel().focus_get()
        except Exception:
            return
        if focus is not self.host.input:
            self.close()

    def close(self):
        if self.open:
            self.frame.place_forget()
            self.open = False
            return 'break'
        return None

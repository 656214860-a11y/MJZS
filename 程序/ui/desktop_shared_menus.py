"""共享输入框的图标下拉面板与候选浮层（R2971／R2980）。

``AnchoredPanel`` 系：输入盒正上方的卡片（``background_card`` 底＋
``border_input_hover`` 1px 描边、与输入盒同宽左对齐），``place`` 锚定、窗口重排跟随；
不再弹 ``BaseDialog``／Toplevel。面板只做呈现：技能清单、默认勾选、说明卡与
导入／模型动作全部回调宿主 ``SharedStageInput``（duck-typed，不反向 import）。

``CandidatePopup``（R2980）：``/`` 命令与 ``@`` 引用共用的光标级候选浮层——
锚在文本光标正下方、不足翻上、屏幕四边钳制；自绘行带类别徽标与匹配子串高亮，
上下键／Tab／点击／悬停导航，采纳经宿主 ``_apply_candidate``。

``_MenuFlow``（REQ-S01-107）：宿主 ``SharedStageInput`` 的菜单侧辅助——面板
开合与外部点击、悬停说明卡生命周期、技能行内容与输入区行高自适应。与
``_CandidateFlow`` 同属一条宿主契约；拆到本模块只为把宿主模块压回行数棘轮
线以内，不新增同层依赖边（行高换算就地展开 Tk 原语，不引 ``responsive_ui``）。
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

import infra.app_logging as app_logging
from ui.ui_icons import IconLoader
from ui_popup import monitor_bounds
from ui_tokens import COLORS, FONTS, ICON_DOCUMENT, ICON_FONT, SPACING, TEXT_ROWS
from ui_widgets import HintLabel

# 与 CompletionPopup.MAX_ITEMS 同量级：当前阶段技能在前，超出截断。
MAX_ROWS = 12
# 默认勾选框边长（像素常量）。
CHECK_SIZE = 14
# 候选浮层行数上限、类别徽标文案与行首图标（R2980）。
CANDIDATE_MAX_ROWS = 12
SKILL_DESC_PREVIEW_CHARS = 24
KIND_BADGES = {'skill': '技能', 'stage': '阶段', 'engine': '子引擎', 'attachment': '附件',
               'report_outline': '大纲', 'report_setting': '设定', 'report_character': '角色卡', 'report': '报告'}
KIND_ICONS = {'attachment': ICON_DOCUMENT, 'report_outline': ICON_DOCUMENT,
              'report_setting': ICON_DOCUMENT, 'report_character': ICON_DOCUMENT, 'report': ICON_DOCUMENT}


def _short_desc(text, limit=SKILL_DESC_PREVIEW_CHARS):
    """行内简短用途预览：去掉换行、超长截断；完整说明仍由右侧说明卡展示。"""
    cleaned = ' '.join(str(text or '').split())
    if not cleaned:
        return ''
    return cleaned if len(cleaned) <= limit else cleaned[:limit - 1] + '…'


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

    # ── 几何：面板底边悬在图标行上沿一行（R3031：原锚输入盒上沿，
    #    整个 TextArea 隔在面板与图标之间） ──────────────────────────────
    def place_panel(self):
        """下缘贴图标行上沿、左缘对齐输入盒、同宽封顶；顶出窗口才退回贴顶。

        坐标换算到窗口（master）相对系：锚点屏幕坐标减窗口原点；
        ``lift`` 保证面板压在页面内容之上（同级兄弟后建者居上）。
        """
        if not self.is_open():
            return
        try:
            card = self.host.input_card
            row = getattr(self.host, 'icon_row', None)
            anchor_top = row.winfo_rooty() if row is not None else card.winfo_rooty()
            top = self.master
            self.update_idletasks()
            height = self.winfo_reqheight()
            # 宽高随内容自适应（REQ-S01-91 定版）：宽取行内容自然宽，封顶输入盒宽。
            width = max(SPACING['md'] * 8,
                        min(self.winfo_reqwidth(), card.winfo_width()))
            x = card.winfo_rootx() - top.winfo_rootx()
            # place 画不出窗口（master）外：y 负值会被整体裁掉，贴顶兜底看相对坐标。
            y = max(0, anchor_top - top.winfo_rooty() - height - SPACING['xs'])
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
        desc_style = 'SkillDescHover.TLabel' if on else 'SkillDesc.TLabel'
        for widget in widgets:
            try:
                if isinstance(widget, ttk.Label):
                    widget.configure(style=desc_style)
                else:
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
    """✦ 技能下拉：点名插入 ``/名称``、勾选＝本阶段默认、行内简述＋右侧悬停说明卡。"""

    def __init__(self, host):
        super().__init__(host)
        self._check_images = []
        self._skill_rows = []
        self._initial_card_job = None

    def anchor_widgets(self):
        button = getattr(self.host, 'skill_button', None)
        return (button,) if button is not None else ()

    def show(self):
        self._cancel_initial_card()
        super().show()
        try:
            self._initial_card_job = self.after_idle(self._show_initial_card)
        except tk.TclError:
            app_logging.swallowed()

    def hide(self):
        self._cancel_initial_card()
        super().hide()

    def _cancel_initial_card(self):
        job = getattr(self, '_initial_card_job', None)
        self._initial_card_job = None
        if job:
            try:
                self.after_cancel(job)
            except tk.TclError:
                app_logging.swallowed()

    def _show_initial_card(self):
        """打开 ✦ 面板时默认展示首行技能的右侧说明卡，避免用户找不到说明入口。"""
        self._initial_card_job = None
        if not self.winfo_exists() or not self.is_open() or not self._skill_rows:
            return
        if getattr(self.host, '_skill_card', None) is not None:
            return
        item, row = self._skill_rows[0]
        try:
            if row.winfo_exists():
                self.host._show_skill_card(item, row)
        except tk.TclError:
            app_logging.swallowed()

    def refresh(self):
        self.clear()
        self._check_images = []
        self._check_rows = {}
        self._skill_rows = []
        # 勾选＝本阶段默认的真实状态（R3040 所见即真）：打开按 stage_config 预填，
        # 点击由 _toggle_skill_default → sync_check 即时取反写回。
        self._defaults = set(self.host._default_skills() or ())
        host = self.host
        items = host._skill_list_items()
        if not items:
            HintLabel(self, text='（暂无可用技能）').pack(fill='x', padx=SPACING['md'])
        for item in items[:MAX_ROWS]:
            self._skill_row(item)
        if self.open:
            self.place_panel()

    def sync_check(self, name):
        """勾选落盘后只刷这一行的勾选像：不整版重建，避免整列闪动。"""
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
        hoverables = [row]
        if host._skill_defaultable(item):
            # 仅本阶段技能给勾选框：跨阶段/判不出阶段的行配置写不进，画出来是死控件
            # （R3040）；名称点击插入 /名称 的路径不受影响。
            image = IconLoader.check_indicator(
                self, size=CHECK_SIZE, selected=name in self._defaults)
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
        label.pack(side='left', padx=(SPACING['xs'], SPACING['sm']))
        widgets.append(label)
        hoverables.append(label)
        label.bind('<Button-1>', lambda _e, it=item: host._pick_skill(it))
        summary = _short_desc(host._skill_description(item))
        if summary:
            desc = ttk.Label(row, text=summary, style='SkillDesc.TLabel',
                             anchor='e', cursor='hand2')
            desc.pack(side='right', padx=(SPACING['sm'], SPACING['md']))
            widgets.append(desc)
            hoverables.append(desc)
            desc.bind('<Button-1>', lambda _e, it=item: host._pick_skill(it))
        self._skill_rows.append((item, row))
        for target in hoverables:
            # 先挂悬停底色，再以 add='+' 追加说明卡——同序列裸 bind 会互相覆盖。
            self._bind_hover(target, widgets)
            target.bind('<Enter>', lambda _e, it=item, r=row: host._show_skill_card(it, r),
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
    """``/`` 命令与 ``@`` 引用共用的光标级候选浮层（R2980，REQ-S01-92）。

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
        # 可见行窗口起点：首屏最多 CANDIDATE_MAX_ROWS 行，全部候选经
        # 键盘/滚轮滚达（REQ-S01-107），不再截断成「… 还有 N 项」。
        self._top = 0
        # 与 AnchoredPanel 同理挂顶层窗：光标上方空间不足时浮层 y 为负，
        # 挂在 SharedStageInput 上会被 master 边界裁掉（R2971 实测）。
        self.frame = tk.Frame(host.winfo_toplevel(), bg=COLORS['background_card'],
                              highlightthickness=1,
                              highlightbackground=COLORS['border_input_hover'])
        self.frame.bind('<MouseWheel>', self._on_wheel, add='+')
        # 宿主销毁时回收浮层与说明卡：载体挂顶层窗下，不随宿主自动消失（REQ-S01-106）。
        host.bind('<Destroy>', self._on_host_destroy, add='+')

    # ── 内容 ──────────────────────────────────────────────────────────
    def refresh(self, entries, query=''):
        """刷新候选并展开；空候选直接收掉。``query`` 用于匹配子串高亮。

        REQ-S01-107：同 token/query/数据不变时不销毁重建行、不重置选择；
        数据变了重建，但原 (kind,name) 仍在列表里则保持选中，消失才回首项。"""
        entries = tuple(entries or ())
        query = str(query or '')
        if not entries:
            self.entries, self.query = entries, query
            self.close()
            return
        if (self.open and entries == self.entries and query == self.query):
            self.place()
            return
        keep = self.selected() if self.open else None
        keep_key = ((keep.get('kind'), keep.get('name'))
                    if isinstance(keep, dict) else None)
        self.entries, self.query = entries, query
        self._top = 0
        self._rebuild_rows()
        self.index = 0
        if keep_key is not None:
            for i, entry in enumerate(self.entries):
                if (entry.get('kind'), entry.get('name')) == keep_key:
                    self.index = i
                    break
        self._ensure_visible(self.index)
        self._paint()
        self.open = True
        self.place()
        # 唤出 / 候选时立即在右侧同步展示当前高亮项的用途说明卡（REQ-S01-106）。
        self._show_card(self.index)

    def _build_rows(self):
        """只建可见窗口 ``[self._top, self._top+MAX)`` 内的行；窗口外候选
        靠键盘/滚轮滚入，不整屏重建。"""
        stop = min(len(self.entries), self._top + CANDIDATE_MAX_ROWS)
        for index in range(self._top, stop):
            self._row(self.entries[index], index)

    def _rebuild_rows(self):
        for child in self.frame.winfo_children():
            child.destroy()
        self._rows = []
        self._build_rows()
        self._paint()

    def _scroll_to(self, top):
        """把可见窗口起点钳到合法范围并（窗口变了才）重建行。"""
        top = max(0, min(int(top), max(0, len(self.entries) - CANDIDATE_MAX_ROWS)))
        if top == self._top and self._rows:
            return
        self._top = top
        self._rebuild_rows()
        self.place()

    def _scroll(self, delta):
        """滚轮滚动可见窗口（±行）：首屏之外的候选全部滚达。"""
        self._scroll_to(self._top + delta)

    def _on_wheel(self, event):
        delta = -1 if getattr(event, 'delta', 0) > 0 else 1
        self._scroll(delta)
        return 'break'

    def _ensure_visible(self, index):
        """高亮项滚进可见窗口。"""
        if index < self._top:
            self._scroll_to(index)
        elif index >= self._top + CANDIDATE_MAX_ROWS:
            self._scroll_to(index - CANDIDATE_MAX_ROWS + 1)

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
        summary = _short_desc(entry.get('hint'))
        if summary and str(entry.get('kind') or '') != 'attachment':
            desc = ttk.Label(row, text=summary, style='SkillDesc.TLabel', anchor='e')
            desc.pack(side='right', padx=(SPACING['sm'], SPACING['none']))
            widgets.append(desc)
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
        record = {'index': index, 'entry': entry, 'widgets': widgets,
                  'marks': marks}
        self._rows.append(record)
        for widget in widgets:
            widget.bind('<Button-1>',
                        lambda _e, it=entry: self.host._apply_candidate(it))
            # 整行（含徽标与留白）悬停：跟随高亮并显示同行用途卡（REQ-S01-106）；
            # 离开走宿主延迟收，移入卡取消——与技能面板同一套 200ms 状态机。
            widget.bind('<Enter>',
                        lambda _e, i=index: self._hover(i), add='+')
            widget.bind('<Leave>',
                        lambda _e: self.host._schedule_skill_card_hide(), add='+')
            widget.bind('<MouseWheel>', self._on_wheel, add='+')

    def _hover(self, index):
        """行悬停：高亮跟随＋用途卡。重复进入同一行也要重挂卡（取消待收）。"""
        self._select(index)
        self._show_card(index)

    def _show_card(self, index):
        """按当前高亮行显示一张被动用途卡：复用宿主 ``_show_skill_card``，
        锚在行右侧、不足翻左、钳当前显示器；正文只取条目 ``hint``，
        无说明显示「暂无用途说明」，不抢焦点、不 grab。
        ``index`` 是全局候选序号：行被滚出窗口时不发卡。"""
        record = next((r for r in self._rows if r['index'] == index), None)
        if record is None:
            return
        entry = record['entry']
        item = {'name': entry.get('name'),
                'description': str(entry.get('hint') or '') or '暂无用途说明'}
        self.host._show_skill_card(item, record['widgets'][0])

    def _on_host_destroy(self, event):
        """宿主销毁：清说明卡与延迟计时器，并销毁候选浮层载体，不留幽灵窗口。"""
        if event.widget is not self.host:
            return
        self.host._hide_skill_card()
        self.teardown()

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
            desc_style = 'SkillDescHover.TLabel' if on else 'SkillDesc.TLabel'
            marks = set(record.get('marks') or ())
            for widget in record['widgets']:
                if widget in marks:
                    continue  # 命中段保留 primary_subtle 底纹，不被行底色盖掉
                try:
                    if isinstance(widget, ttk.Label):
                        widget.configure(style=desc_style)
                    else:
                        widget.configure(bg=bg)
                except tk.TclError:
                    app_logging.swallowed()

    def selected(self):
        if 0 <= self.index < len(self.entries):
            return self.entries[self.index]
        return None

    def move(self, delta):
        """上下键移动高亮：全量候选可达（REQ-S01-107），越出可见窗口自动滚入。"""
        count = len(self.entries)
        if not count:
            return
        index = max(0, min(count - 1, self.index + delta))
        if index != self.index:
            self.index = index
            self._ensure_visible(index)
            self._paint()
            # 键盘高亮变更同步说明（REQ-S01-106），焦点仍留在文本区。
            self._show_card(index)

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

        可视区＝顶层窗矩形与**光标所在显示器**矩形的交集——``place`` 画不出
        窗口外，输入框贴窗口底部时「下方」实际只有图标行与状态栏，必须按窗口
        底边判翻转；``winfo_screenwidth/height`` 恒为主屏尺寸，副屏上会把浮层
        钳成窄缝（R3031），显示器边界走 ``monitor_bounds``（ui_popup 同口径）。
        """
        if not self.open:
            return
        try:
            self.frame.update_idletasks()
            height = self.frame.winfo_reqheight()
            top = self.frame.winfo_toplevel()
            anchor = self._cursor_anchor()
            if anchor is None:
                return
            cursor_x, cursor_top, cursor_bottom = anchor
            hx = top.winfo_rootx()
            hy = top.winfo_rooty()
            mleft, mtop, mright, mbottom = monitor_bounds(top, cursor_x, cursor_top)
            left = max(SPACING['xs'], hx, mleft)
            right = min(hx + top.winfo_width(), mright - SPACING['xs'])
            bottom = min(hy + top.winfo_height(), mbottom - SPACING['xs'])
            top_edge = max(SPACING['xs'], hy, mtop)
            width = min(self.frame.winfo_reqwidth(),
                        max(SPACING['md'] * 8, self.host.winfo_width()),
                        max(SPACING['md'] * 4, right - left))
            gap = SPACING['xs'] // 2
            y = cursor_bottom + gap
            if y + height > bottom:
                y = cursor_top - height - gap
            y = max(top_edge, min(y, bottom - height))
            x = max(left, min(cursor_x, right - width))
            self.frame.place(x=x - hx, y=y - hy, width=width)
            self.frame.lift()
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
            # 收候选同时收同行用途卡并取消延迟计时器（采纳／Esc／失焦／切页共用）。
            self.host._hide_skill_card()
            return 'break'
        return None

    def teardown(self):
        """宿主销毁：收浮层并销毁载体，不在顶层窗上留幽灵窗口（REQ-S01-106）。"""
        self.open = False
        try:
            self.frame.destroy()
        except tk.TclError:
            app_logging.swallowed()


def _widget_path(widget):
    """控件的 Tk 路径：Widget 取 ``_w``；``event.widget`` 在被点控件随绑定销毁时
    回退成路径字符串（R3040），两种形态统一成路径再比较。"""
    if widget is None:
        return ''
    path = getattr(widget, '_w', None)
    return str(path) if path else str(widget)


def _widget_within(widget, ancestor):
    """widget 是否落在 ancestor 子树内（place 出去的浮层也是它的子孙）。

    按路径判：``wpath == apath`` 或以 ``apath + '.'`` 开头；ancestor 为根 ``.``
    时恒真。销毁控件的事件回退字符串与活控件走同一规则，不再依赖 ``.master`` 链
    （字符串没有 master，旧写法对它恒 False，曾把面板内点击误判成外部点击）。
    """
    wpath = _widget_path(widget)
    apath = _widget_path(ancestor)
    if not wpath or not apath:
        return False
    if apath == '.':
        return True
    return wpath == apath or wpath.startswith(apath + '.')


def _display_rows(box, limit):
    """可见软换行数，量到 ``limit`` 行即停（口径同 ``responsive_ui.display_lines``；
    L4 同层边未登记，这里就地展开 Tk 原语）。"""
    try:
        stop = box.index('1.0 + %d displaylines' % max(1, int(limit)))
        if box.compare(stop, '<', 'end-1c'):
            return max(1, int(limit))
        counted = box.count('1.0', 'end-1c', 'displaylines')
    except (tk.TclError, AttributeError):
        return 1
    lines = counted[0] if isinstance(counted, (tuple, list)) else counted
    if lines is None:
        lines = 1
    try:
        return max(1, int(lines))
    except (TypeError, ValueError):
        return 1


def _line_px(widget, fallback=18):
    """输入区一行像素高（口径同 ``responsive_ui.font_linespace``，只量默认字体档）。"""
    from tkinter import font as tkfont
    try:
        return max(8, int(tkfont.Font(root=widget, font='TkDefaultFont').metrics('linespace')))
    except Exception:
        return fallback


class _MenuFlow:
    """``SharedStageInput`` 的菜单侧辅助：候选与 ✦／＋ 图标面板的开合、
    悬停说明卡生命周期、技能行内容与输入区行高自适应（REQ-S01-107）。

    与 ``_CandidateFlow`` 同属一条宿主契约（``input``／``stage``／``status``／
    ``candidates``／``skill_panel``／``add_panel`` 已由宿主建好，面板动作经
    ``host`` 回调）；拆出只为把宿主模块压回行数棘轮线以内。
    """

    # ── 输入区行高与宿主 ``<Configure>`` ────────────────────────────────
    def _on_input_configure(self, event=None):
        if event is not None and getattr(event, 'widget', None) is not self:
            return
        if self.candidates.open:
            try:
                self.after_idle(self.candidates.place)
            except Exception:
                app_logging.swallowed()
        for panel in (getattr(self, 'skill_panel', None),
                      getattr(self, 'add_panel', None)):
            if panel is not None and panel.is_open():
                try:
                    self.after_idle(panel.place_panel)
                except Exception:
                    app_logging.swallowed()

    def _fit_input_height(self):
        """行高随实际可见软换行：``TEXT_ROWS.sm``→``xl``，矮窗再按可用内容区
        钳制；超限靠框内滚动，工具行始终可见（REQ-S01-107）。"""
        try:
            shown = _display_rows(self.input, TEXT_ROWS['xl'])
            # displaylines 在布局没算到的段落会少计：与 fit_composer 同款
            # 取「逻辑行∨显示行」，换行符给出的下界永不少报。
            logical = int(str(self.input.index('end-1c')).split('.')[0])
            rows = min(TEXT_ROWS['xl'], max(TEXT_ROWS['sm'], shown, logical))
            rows = min(rows, self._input_room_rows())
            if int(self.input.cget('height')) != rows:
                self.input.configure(height=rows)
        except (tk.TclError, ValueError):
            app_logging.swallowed()

    def _input_room_rows(self):
        """矮窗钳制：输入区最多吃〔窗口高 − 卡内不变装饰（工具行＋边距）
        − dock 内兄弟控件〕折合的行数，最少 1 行。"""
        try:
            top = self.winfo_toplevel()
            win_h = top.winfo_height()
            if win_h <= 1:
                return TEXT_ROWS['xl']
            line = max(1, _line_px(self.input))
            chrome = max(0, self.input_card.winfo_reqheight()
                         - self.input.winfo_reqheight())
            siblings = 0
            for child in self.master.winfo_children():
                if child is self:
                    continue
                try:
                    siblings += child.winfo_reqheight()
                except tk.TclError:
                    pass
            return max(1, (win_h - chrome - siblings) // line)
        except tk.TclError:
            return TEXT_ROWS['xl']

    # ── 悬停说明卡生命周期（卡片本体由宿主 ``_show_skill_card`` 绘制） ──
    def _hide_skill_card(self):
        self._cancel_skill_card_hide()
        card = getattr(self, '_skill_card', None)
        self._skill_card = None
        if card is not None:
            try:
                card.destroy()
            except Exception:
                app_logging.swallowed()

    def _schedule_skill_card_hide(self):
        """离开技能行延迟收说明卡：给鼠标移向卡片留 200ms 窗口。"""
        self._cancel_skill_card_hide()
        try:
            self._skill_card_hide_id = self.after(200, self._hide_skill_card)
        except Exception:
            app_logging.swallowed()

    def _cancel_skill_card_hide(self):
        job = getattr(self, '_skill_card_hide_id', None)
        self._skill_card_hide_id = None
        if job:
            try:
                self.after_cancel(job)
            except Exception:
                app_logging.swallowed()

    # ── ✦／＋ 图标下拉开合（面板本体见 AnchoredPanel 系） ──────────────
    def _show_panel(self, panel):
        """图标下拉互斥展开：先收 / 补全与另一个面板；已开着再点图标＝收起。"""
        # 排队中的重扫先跑完：它的「输入即收面板」规则若在面板摆位里的
        # update_idletasks 中触发，会把刚开的面板又收掉（REQ-S01-107）。
        self._flush_pending_refresh()
        self.candidates.close()
        self._active_token = None
        other = self.add_panel if panel is self.skill_panel else self.skill_panel
        if other.is_open():
            other.hide()
        panel.toggle()
        self._hide_skill_card()

    def _hide_panels(self):
        """收掉 ✦／＋ 两个图标下拉与悬停说明卡；返回是否有面板原本开着。"""
        hidden = False
        for panel in (getattr(self, 'skill_panel', None),
                      getattr(self, 'add_panel', None)):
            if panel is not None and panel.is_open():
                panel.hide()
                hidden = True
        self._hide_skill_card()
        return hidden

    def _panel_outside_click(self, event):
        """点在面板与它的图标钮之外：收掉开着的下拉（图标钮开合走 command）。"""
        widget = getattr(event, 'widget', None)
        for panel in (getattr(self, 'skill_panel', None),
                      getattr(self, 'add_panel', None)):
            if panel is None or not panel.is_open():
                continue
            if _widget_within(widget, panel):
                continue
            anchors = [anchor for anchor in panel.anchor_widgets()
                       if anchor is not None]
            if any(_widget_within(widget, anchor) for anchor in anchors):
                continue
            panel.hide()
            self._hide_skill_card()

    def _release_panel_click(self, event):
        """输入框销毁时摘掉整窗 ``<Button-1>`` 监听，不留指向死控件的绑定。"""
        if event.widget is not self:
            return
        top = getattr(self, '_panel_click_top', None)
        funcid = getattr(self, '_panel_click_id', None)
        try:
            if top is not None and funcid:
                top.unbind('<Button-1>', funcid)
        except Exception:
            app_logging.swallowed()

    # ── 技能行内容（清单、默认勾选、说明、点名插入） ──────────────────
    @staticmethod
    def _skill_name(item):
        """技能规范名：``Skill`` 对象取 ``.name``、字典取 ``name``、字符串原样——
        不取 ``str(item)`` 的 ``Skill(name @ stage)`` repr，也不映射别名。"""
        if isinstance(item, dict):
            return str(item.get('name') or '')
        name = getattr(item, 'name', None)
        if name is not None:
            return str(name)
        return str(item or '')

    @staticmethod
    def _skill_display(item):
        """列表行只显示技能包原始 ``name``（REQ-S01-91），不拼 displayName。"""
        return _MenuFlow._skill_name(item) or '（未命名技能）'

    def _skill_stage(self, item):
        """技能归属阶段 id（``stage_id`` 归一）：显式 ``stage`` 字段优先，
        缺失按名回查注册表；判不出返回 ``''``。"""
        stage = item.get('stage') if isinstance(item, dict) else getattr(item, 'stage', None)
        if not stage:
            name = self._skill_name(item)
            if name:
                try:
                    import skill_registry
                    found = skill_registry.default_registry().getById(name)
                    stage = getattr(found, 'stage', None) if found is not None else None
                except Exception:
                    app_logging.swallowed()
        if not stage:
            return ''
        try:
            import skill_registry
            return skill_registry.stage_id(stage)
        except Exception:
            return str(stage)

    def _skill_defaultable(self, item):
        """可设为本阶段默认：项目已开 且 归属阶段==当前阶段（R3040：
        跨阶段与判不出阶段的行不给会永远写不进的死勾选框）。"""
        if self.project is None:
            return False
        own = self._skill_stage(item)
        if not own:
            return False
        try:
            import skill_registry
            return own == skill_registry.stage_id(self.stage)
        except Exception:
            return own == self.stage

    def _skill_list_items(self):
        """当前阶段技能在前、其余在后；去重、限量。"""
        try:
            import orchestrator.skill_registry as skill_registry
            registry = skill_registry.default_registry(project=self.project)
            current = list(registry.getByStage(self.stage))
            seen = {self._skill_name(item) for item in current if self._skill_name(item)}
            others = [item for item in registry.getAll()
                      if self._skill_name(item) and self._skill_name(item) not in seen]
            return (current + others)[:20]
        except Exception:
            app_logging.swallowed()
            return list(self.skill_items())[:20]

    def _default_skills(self):
        """当前阶段在三虎默认里的 skill 名单（stage_config 条目的 skills 字段）。"""
        try:
            import orchestrator.stage_config as stage_config
            project = self.project
            if project is None:
                return []
            entry = stage_config.get(project, self.stage) or {}
            return list(entry.get('skills') or [])
        except Exception:
            app_logging.swallowed()
            return []

    def _skill_description(self, item):
        """悬停说明：字典取 ``description``；``Skill`` 对象直接读属性（``str(item)``
        是 ``Skill(name @ stage)`` repr，不能拿去 ``getById`` 查——R2971 修正）。"""
        if isinstance(item, dict):
            return str(item.get('description') or '')
        desc = getattr(item, 'description', None)
        if desc is not None:
            return str(desc)
        try:
            import orchestrator.skill_registry as skill_registry
            registry = skill_registry.default_registry(project=self.project)
            found = registry.getById(_MenuFlow._skill_name(item))
            if found is not None:
                return str(getattr(found, 'description', '') or '')
        except Exception:
            app_logging.swallowed()
        return ''

    def _pick_skill(self, item):
        """点击技能：在光标处插入 ``/技能名 `` 并聚焦（REQ-S01-107 草稿不丢：
        原整框 set_text 会把已写的字全冲掉）；插入收成一次可撤销动作。"""
        name = self._skill_name(item)
        self._hide_panels()
        if not name:
            return
        self._atomic_edit(
            lambda: self.input.insert('insert', '/' + name + ' '))
        try:
            self.input.focus_set()
        except Exception:
            app_logging.swallowed()

"""共享输入框右下角的模型选择器（R2964 定版）：无外框文字钮＋上方卡片浮层。

按钮显示「当前模型名 ▾」，点击在输入框上方弹出 ``ui_popup.Flyout`` 卡片：
模型行（当前项打勾、推理能力项带「推理·<档位>」徽标）、推理等级四档；
点外部、Esc 或选中模型即关。上一版 ``ttk.Menubutton``＋
``tk.Menu`` 在输入框贴底时被系统翻转方向、盖住按钮本体，且存在误触尾项
直接打开模型管理的反馈（R2964 用户实测四条修复点），故改自绘浮层。
模型管理入口在共享输入框「＋」下拉（REQ-S01-91），本浮层不再保留尾项。

模型的唯一写入口仍是 ``stage_config.put``；选项仍来自 ``grouped_model_choices``
（模型池＋页面生产模型）。REQ-S01-82：条目只显示模型名称（不带供应商前缀）；
「推理等级」档位写进阶段配置的 ``reasoning`` 字段。
"""
import tkinter as tk
from tkinter import ttk

import infra.model_pool as model_pool
import infra.model_router as model_router
import orchestrator.stage_config as stage_config
from responsive_ui import ScrollForm
from ui.skill_panel_support import (
    desktop_project, grouped_model_choices, pet_of, pool_records, register_live,
                                 stage_for, unregister_live)
from ui_popup import Flyout, monitor_bounds
from ui_tokens import COLORS, FONTS, SPACING
from ui_widgets import SecondaryButton, setup_styles

LEVEL_MENU = '推理等级'
# 触发钮文案截断：模型名过长时不把输入行撑破（保守按字符数截，CJK 视觉更宽）。
MODEL_LABEL_MAX_CHARS = 24
# 浮层模型区最多露出的行数；超出走滚轮。
POPUP_MAX_MODEL_ROWS = 5


def _clip_label(text):
    text = str(text or '')
    return text if len(text) <= MODEL_LABEL_MAX_CHARS else text[:MODEL_LABEL_MAX_CHARS - 1] + '…'


class StageModelPicker(ttk.Frame):
    """模型选择器：无外框按钮＋上弹卡片；无项目时只读展示「自动」。"""

    def __init__(self, master, desktop, stage):
        ttk.Frame.__init__(self, master)
        setup_styles(self)
        self.desktop = desktop
        self.stage = stage_for(stage)
        self.groups = {}
        self.model = tk.StringVar(value='')
        self._display = tk.StringVar(value='')
        self.model.trace_add('write', lambda *_a: self._sync_display())
        self._picked = ''
        self._by_display = {}          # 模型显示名 → 稳定模型 id（同名取先出现的一条）
        self._items = []               # [(model_id, 显示名)]
        self._capable = set()          # 带 reasoning 能力标签的模型 id
        self._level = tk.StringVar(value='auto')
        self._popup = None             # 打开中的 Flyout
        self._popup_win = None         # 浮层所属主窗（解绑点外部监听用）
        self._popup_binds = []         # 主窗上的点外部／Esc 绑定 (event, seqid)
        # R2964：Menubutton 换无外框按钮——文案经 _display 带「▾」，model 变量仍是纯模型名。
        # 语义组件 SecondaryButton＋自定义无框样式（按钮边界门禁要求走 ui_widgets 组件）。
        self.models = SecondaryButton(self, textvariable=self._display,
                                      style='Tokens.Composer.Model.TButton',
                                      command=self.toggle_popup, takefocus=0)
        self.models.pack(side='left')
        register_live(self)
        self.bind('<Destroy>', self._on_destroy, add='+')
        self.refresh_models()

    # ── 数据 ────────────────────────────────────────────────────────────────
    def project(self):
        return desktop_project(self.desktop)

    def _entry(self):
        """当前阶段的已保存配置；读不到就是默认的一份。"""
        project = self.project()
        if not project:
            return {'model': model_router.AUTO, stage_config.REASONING: 'auto'}
        try:
            return stage_config.get(project, self.stage)
        except Exception:
            return {'model': model_router.AUTO, stage_config.REASONING: 'auto'}

    def saved_model(self):
        return str(self._entry().get('model') or model_router.AUTO).strip()

    def saved_reasoning(self):
        return stage_config.clean_reasoning(self._entry().get(stage_config.REASONING))

    def model_id(self):
        """当前文案 → 稳定模型 id；空或「自动」返回自动。"""
        display = str(self.model.get() or '').strip()
        if not display or display == model_pool.AUTO_LABEL:
            return model_router.AUTO
        return self._by_display.get(display) or model_router.AUTO

    def refresh_models(self):
        """模型池或项目变了：重读选项，并把已保存的那一档摆回去。"""
        self.groups = grouped_model_choices(self.desktop, self.stage)
        records = pool_records(self.desktop)
        self._items = []
        self._by_display = {}
        self._capable = set()
        for options in self.groups.values():
            for model_id, label in options:
                self._by_display.setdefault(label, model_id)
                self._items.append((model_id, label))
                if 'reasoning' in model_pool.capabilities_of(
                        (records.get(model_id) or {}).get('capabilities')):
                    self._capable.add(model_id)
        self._level.set(self.saved_reasoning())
        self.set_model(self.saved_model())
        self._close_popup()
        return self.groups

    def set_model(self, model):
        """按模型 id 同步选择器；认不出的值显示为「自动」，不改写已保存的配置。"""
        wanted = str(model or model_router.AUTO)
        for model_id, label in self._items:
            if model_id == wanted:
                self.model.set(label)
                self._picked = label
                return wanted
        if wanted != model_router.AUTO:
            # 手写的本地模型 id 还没登记到模型池：照原样显示，不丢配置。
            self._by_display.setdefault(wanted, wanted)
            self._items.append((wanted, wanted))
            self.model.set(wanted)
            self._picked = wanted
            return wanted
        self.model.set(model_pool.AUTO_LABEL)
        self._picked = model_pool.AUTO_LABEL
        return model_router.AUTO

    def set_model_label(self, label):
        """按显示名同步选择器（点击模型目录条时用）；找不到匹配就不改动当前选择。"""
        wanted = str(label or '').strip()
        if not wanted:
            return None
        for options in self.groups.values():
            for model_id, item_label in options:
                if item_label == wanted:
                    self.model.set(item_label)
                    self._picked = item_label
                    return model_id
        return None

    def labels(self):
        """浮层里的模型项显示名。"""
        return [label for _model_id, label in self._items]

    # ── 浮层内容（数据视图，测试与渲染共用） ────────────────────────────────
    def _popup_spec(self):
        """浮层行规格：模型行 → 推理等级区（管理入口在共享输入框「＋」下拉）。"""
        level = self.saved_reasoning()
        level_label = stage_config.REASONING_LABELS[level]
        current = str(self.model.get() or '')
        rows = []
        for model_id, label in self._items:
            rows.append({'kind': 'model', 'id': model_id, 'label': label,
                         'badge': ('推理·' + level_label) if model_id in self._capable else '',
                         'current': label == current})
        rows.append({'kind': 'separator'})
        rows.append({'kind': 'reasoning', 'label': LEVEL_MENU,
                     'levels': [(value, stage_config.REASONING_LABELS[value], value == level)
                                for value in stage_config.REASONING_LEVELS]})
        return rows

    # ── 浮层开合与定位 ──────────────────────────────────────────────────────
    def _sync_display(self):
        try:
            text = str(self.model.get() or '').strip()
            self._display.set(_clip_label(text) + ' ▾' if text else '')
        except tk.TclError:
            pass

    def toggle_popup(self):
        if self._popup_open():
            self._close_popup()
        else:
            self._open_popup()

    def _popup_open(self):
        top = self._popup
        return top is not None and top.winfo_exists()

    def _open_popup(self):
        self._close_popup()
        win = self.winfo_toplevel()
        top = Flyout(win)
        self._popup = top
        self._popup_win = win
        self._fill_popup(top.body)
        self._place_popup(top)
        # 点外部／Esc 关：监听挂主窗绑定（bindtags 让窗内控件点击都经过），浮层内点击到不了。
        self._popup_binds = [
            ('<Button-1>', win.bind('<Button-1>', self._popup_outside, add='+')),
            ('<Escape>', win.bind('<Escape>', self._popup_escape, add='+')),
        ]
        top.bind('<Destroy>', self._popup_destroyed, add='+')

    def _place_popup(self, top):
        """锚定按钮正上方、右缘对齐；上方放不下退回按钮下方，按显示器钳位。"""
        top.update_idletasks()
        width = max(top.winfo_reqwidth(), self.models.winfo_width())
        height = top.winfo_reqheight()
        anchor_x = self.models.winfo_rootx() + self.models.winfo_width()
        anchor_top = self.models.winfo_rooty()
        anchor_bottom = anchor_top + self.models.winfo_height()
        win = self._popup_win if self._popup_win is not None else self.winfo_toplevel()
        left, stop, right, sbottom = monitor_bounds(win, anchor_x, anchor_top)
        width = min(width, right - left - 2 * SPACING['xs'])
        x = anchor_x - width
        y = anchor_top - height - SPACING['xs']
        if y < stop + SPACING['xs']:
            y = anchor_bottom + SPACING['xs']
        x = min(max(x, left + SPACING['xs']),
                max(left + SPACING['xs'], right - SPACING['xs'] - width))
        y = min(max(y, stop + SPACING['xs']),
                max(stop + SPACING['xs'], sbottom - SPACING['xs'] - height))
        top.geometry('%dx%d+%d+%d' % (width, height, int(x), int(y)))

    def _fill_popup(self, body):
        """按 ``_popup_spec`` 重建浮层内容：模型行进滚动区，推理区与尾行钉在下方。"""
        for child in body.winfo_children():
            child.destroy()
        spec = self._popup_spec()
        models = [row for row in spec if row['kind'] == 'model']
        pinned_spec = [row for row in spec if row['kind'] != 'model']

        holder = tk.Frame(body, bg=COLORS['background_primary'])
        holder.pack(fill='x')
        scroll = ScrollForm(holder, bg=COLORS['background_primary'], scrollbar=True)
        first_row = [None]
        row_widgets = []
        if models:
            for row_spec in models:
                row = self._model_row(scroll.form, row_spec)
                row.pack(fill='x')
                row_widgets.append(row)
                if first_row[0] is None:
                    first_row[0] = row
        else:
            row_widgets.append(self._text_row(
                scroll.form, '暂无可用模型', fg=COLORS['text_muted'],
                command=lambda: None))
        scroll.form.update_idletasks()
        # ScrollForm 的画布不把内容需求宽度传给外层：模型行最宽者决定浮层宽度，
        # 否则长模型名会被画布宽度裁掉（R2964 预览反馈）。
        need_w = max((w.winfo_reqwidth() for w in row_widgets), default=0)
        row_h = (first_row[0].winfo_reqheight() if first_row[0] is not None
                 else SPACING['xl'])
        content_h = scroll.form.winfo_reqheight()
        view_h = min(content_h, row_h * POPUP_MAX_MODEL_ROWS + SPACING['lg'])
        holder.configure(height=view_h)
        # 画布需求宽度不含窗内 form：把最宽模型行的需求宽度直接喂给画布，
        # 否则长模型名会被画布默认宽度裁掉（R2964 预览反馈）。不拿 Tk 画布的默认宽度兜底：
        # 模型名短时它会把卡片撑宽，右侧留出一大块空白。
        scroll.canvas.configure(width=need_w)
        scroll.bind_wheel()

        pinned = tk.Frame(body, bg=COLORS['background_primary'])
        pinned.pack(fill='x')
        for row_spec in pinned_spec:
            kind = row_spec['kind']
            if kind == 'separator':
                tk.Frame(pinned, bg=COLORS['border_default'], height=1).pack(
                    fill='x', padx=SPACING['xs'], pady=SPACING['xs'])
            elif kind == 'reasoning':
                self._reasoning_block(pinned, row_spec)

    # ── 行构造 ──────────────────────────────────────────────────────────────
    @staticmethod
    def _descendants(widget):
        for child in widget.winfo_children():
            yield child
            yield from StageModelPicker._descendants(child)

    def _bind_row_events(self, row, command):
        """行内所有标签都接悬停底色与点击（bindtags 不含父件，逐个绑）。"""
        widgets = [row] + list(self._descendants(row))

        def paint(color):
            for w in widgets:
                try:
                    w.configure(bg=color)
                except tk.TclError:
                    pass

        def hover_on(_e):
            paint(COLORS['surface_hover'])

        def hover_off(_e):
            paint(COLORS['background_primary'])

        def pick(_e):
            command()
            return 'break'

        for w in widgets:
            w.bind('<Enter>', hover_on)
            w.bind('<Leave>', hover_off)
            w.bind('<Button-1>', pick)

    def _model_row(self, parent, spec):
        row = tk.Frame(parent, bg=COLORS['background_primary'])
        # ✓ 常渲染、非当前项用底色藏起：列宽恒定且不写数字 width（token 棘轮门禁）。
        tk.Label(row, text='✓', anchor='w',
                 bg=COLORS['background_primary'],
                 fg=COLORS['primary'] if spec['current'] else COLORS['background_primary'],
                 font=FONTS['hint'], pady=SPACING['xs']).pack(side='left')
        # R3060：模型名不再 expand，徽标紧跟其后——「模型名 推理·档位」视觉上一体，
        # 卡片宽度由最宽行自然决定，不再把左右两端拉开。
        tk.Label(row, text=spec['label'], anchor='w',
                 bg=COLORS['background_primary'], fg=COLORS['text_primary'],
                 font=FONTS['hint'], padx=SPACING['sm'],
                 pady=SPACING['xs']).pack(side='left')
        if spec['badge']:
            # tk 控件的 padx 不收元组（只有 pack/grid 收）：用标量 xs，右侧外边距交给行内自然排布。
            tk.Label(row, text=spec['badge'], anchor='w',
                     bg=COLORS['background_primary'], fg=COLORS['text_muted'],
                     font=FONTS['hint'], padx=SPACING['xs'],
                     pady=SPACING['xs']).pack(side='left')
        self._bind_row_events(row, lambda mid=spec['id']: self._choose_model(mid))
        return row

    def _reasoning_block(self, parent, spec):
        block = tk.Frame(parent, bg=COLORS['background_primary'])
        tk.Label(block, text=spec['label'], anchor='w',
                 bg=COLORS['background_primary'], fg=COLORS['text_muted'],
                 font=FONTS['hint'], padx=SPACING['sm'], pady=SPACING['xs']
                 ).pack(side='left')
        chips = tk.Frame(block, bg=COLORS['background_primary'])
        chips.pack(side='right', padx=(SPACING['sm'], SPACING['xs']))
        for value, label, current in spec['levels']:
            chip = tk.Label(chips, text=label, cursor='hand2',
                            bg=COLORS['primary_subtle'] if current else COLORS['background_primary'],
                            fg=COLORS['primary'] if current else COLORS['text_secondary'],
                            font=FONTS['hint'], padx=SPACING['sm'], pady=SPACING['xs'])
            chip.pack(side='left', padx=(SPACING['xs'], SPACING['none']))
            chip.bind('<Button-1>', lambda _e, level=value: self.choose_reasoning(level))
            chip.bind('<Enter>', lambda _e, c=chip, cur=current: c.configure(
                bg=COLORS['surface_hover'] if not cur else COLORS['primary_subtle']))
            chip.bind('<Leave>', lambda _e, c=chip, cur=current: c.configure(
                bg=COLORS['primary_subtle'] if cur else COLORS['background_primary']))
        block.pack(fill='x')
        return block

    def _text_row(self, parent, text, *, fg, command):
        row = tk.Frame(parent, bg=COLORS['background_primary'])
        tk.Label(row, text=text, anchor='w', bg=COLORS['background_primary'],
                 fg=fg, font=FONTS['hint'], padx=SPACING['sm'], pady=SPACING['xs']
                 ).pack(fill='x')
        self._bind_row_events(row, command)
        row.pack(fill='x')
        return row

    # ── 浮层外部事件 ────────────────────────────────────────────────────────
    def _popup_outside(self, event):
        """主窗内点外部即关；点在触发钮上放行给按钮自己切换。"""
        if not self._popup_open():
            return None
        try:
            if event.widget is self.models or event.widget is self:
                return None
        except tk.TclError:
            pass
        self._close_popup()
        return None

    def _popup_escape(self, _event=None):
        if self._popup_open():
            self._close_popup()
            return 'break'
        return None

    def _popup_destroyed(self, event=None):
        if event is not None and event.widget is not self._popup:
            return
        self._popup = None
        self._popup_win = None
        self._unbind_popup()

    def _unbind_popup(self):
        pairs = self._popup_binds
        self._popup_binds = []
        win = self._popup_win
        if not pairs or win is None:
            return
        for event_name, seq in pairs:
            if seq:
                try:
                    win.unbind(event_name, seq)
                except tk.TclError:
                    pass

    def _close_popup(self):
        self._unbind_popup()
        self._popup_win = None
        top, self._popup = self._popup, None
        if top is not None:
            try:
                if top.winfo_exists():
                    top.destroy()
            except tk.TclError:
                pass

    def _on_destroy(self, event=None):
        if event is not None and event.widget is not self:
            return
        self._close_popup()
        unregister_live(self)

    # ── 交互 ────────────────────────────────────────────────────────────────
    def _choose_model(self, model_id):
        self.choose_model(model_id)
        self._close_popup()

    def choose_model(self, model_id=None):
        if model_id is not None:
            self.set_model(model_id)
            return self.save()
        self._picked = self.model.get()
        return self.save()

    def choose_reasoning(self, level):
        """写本阶段的推理等级；界面档位立即跟随（不写模型与 SKILL）。"""
        level = stage_config.clean_reasoning(level)
        self._level.set(level)
        project = self.project()
        if not project:
            return None
        entry = stage_config.put(project, self.stage, reasoning=level)
        if self._popup_open():
            self._fill_popup(self._popup.body)
            self._place_popup(self._popup)
        return entry

    def save(self):
        """只写模型这一项，SKILL 勾选与推理等级保持原样。"""
        project = self.project()
        if not project:
            return None
        entry = stage_config.put(project, self.stage, model=self.model_id())
        if self.stage == 'script':
            refresh = getattr(self.desktop, 'refresh_script_chat_for_selected_model', None)
            if callable(refresh):
                refresh()
        return entry

    def open_model_manager(self):
        """模型管理唯一入口（共享输入框「＋」下拉调用）；模型池只有模型管理的一扇门。"""
        pet = pet_of(self.desktop)
        if pet is None:
            return ''
        import ui.pet_models_ui as pet_models_ui
        try:
            return pet_models_ui.open_manager(pet)
        except Exception:
            return ''

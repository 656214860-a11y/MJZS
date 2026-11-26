# -*- coding: utf-8 -*-
"""模型管理页重构组件（L4 UI）：双行模型状态卡片列表、DSH 风格路线卡、折叠区与远端模型选择器。

严格遵守项目 UI 契约：
- 零内联 hex，零原始 ``font=``/``fg=``/``foreground=`` 标签参数，样式全部取自 ``ui_theme``；
- 按钮走 ``PrimaryButton``/``SecondaryButton``，非密钥表单项用 ``EditablePresetBox``（5+ 主流可编辑下拉），
  搜索/备注短输入用 ``CompactLineInput``，密钥用 ``PasswordInput(mask='*', show='*')``；
- 滚动复用 ``responsive_ui.ScrollForm``，不直接使用裸 ``ttk.Treeview``。
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from account_inputs import PasswordInput
import infra.model_pool as model_pool
import infra.model_routes as model_routes
from responsive_ui import ScrollForm
from ui_tokens import (BUTTON_GAP_TIGHT, CHAR_WIDTH, COLORS, COMBOBOX_PADDING,
                       INPUT_PADDING_X, SPACING, TEXT_DESC, TEXT_ROWS)
from ui_widgets import (BaseDialog, DataTable, HintLabel, LineInput,
                        PrimaryButton, SecondaryButton, SelectBox)

COMPACT_PREFIX = 'Compact.'
COMPACT_COMBOBOX_STYLE = COMPACT_PREFIX + 'Tokens.Combobox.TCombobox'
COMPACT_COMBOBOX_PAD_Y = SPACING['xs'] - SPACING['xs'] // 4


class CompactLineInput(LineInput):
    NORMAL_STYLE = COMPACT_PREFIX + LineInput.NORMAL_STYLE
    PLACEHOLDER_STYLE = COMPACT_PREFIX + LineInput.PLACEHOLDER_STYLE
    ERROR_STYLE = COMPACT_PREFIX + LineInput.ERROR_STYLE

    def __init__(self, master=None, *, on_change=None, **kwargs):
        self._on_change = on_change
        self._mute_change = False
        super().__init__(master, **kwargs)

    def insert(self, index, string):
        res = super().insert(index, string)
        if callable(self._on_change) and not self._mute_change and not self._placeholder_active:
            self._on_change()
        return res

    def delete(self, first, last=None):
        res = super().delete(first, last)
        if callable(self._on_change) and not self._mute_change and not self._placeholder_active:
            self._on_change()
        return res


class EditablePresetBox(SelectBox):
    """可编辑紧凑下拉框（5+ 主流预设），支持 on_change 回调与静音回填。"""

    def __init__(self, master=None, *, values=(), on_change=None, width=None, **kwargs):
        self._on_change = on_change
        self._mute_change = False
        kwargs.setdefault('state', 'normal')
        kwargs.setdefault('style', COMPACT_COMBOBOX_STYLE)
        super().__init__(master, values=values, width=width, **kwargs)
        if callable(on_change):
            self.bind('<<ComboboxSelected>>', lambda _e: self._notify_change(), add='+')

    def _notify_change(self):
        if callable(self._on_change) and not self._mute_change:
            self._on_change()

    def insert(self, index, string):
        res = super().insert(index, string)
        self._notify_change()
        return res

    def delete(self, first, last=None):
        res = super().delete(first, last)
        self._notify_change()
        return res

    def set(self, value):
        res = super().set(value)
        self._notify_change()
        return res


def install_compact_form_styles(widget):
    """派生样式只改 padding，其余颜色、边框与状态映射沿用父样式。"""
    style = ttk.Style(widget)
    for name in (CompactLineInput.NORMAL_STYLE, CompactLineInput.PLACEHOLDER_STYLE, CompactLineInput.ERROR_STYLE):
        style.configure(name, padding=(INPUT_PADDING_X, SPACING['none']))
    style.configure(COMPACT_COMBOBOX_STYLE, padding=(COMBOBOX_PADDING[0], COMPACT_COMBOBOX_PAD_Y))


STATE_STYLE_SUFFIX = {
    'ok': 'Ok',
    'idle': 'Idle',
    'warn': 'Warn',
    'missing': 'Warn',
    'error': 'Err',
    'disabled': 'Muted',
}
STATE_DOT = {
    'ok': '●',
    'idle': '●',
    'warn': '●',
    'missing': '●',
    'error': '●',
    'disabled': '○',
}


def set_input_value(entry, text):
    """向 CompactLineInput 或 EditablePresetBox 安全写入值，回填期间静音 on_change。"""
    if not hasattr(entry, 'delete'):
        entry.set(str(text or ''))
        return
    prev_mute = getattr(entry, '_mute_change', False)
    entry._mute_change = True
    try:
        entry.delete(0, 'end')
        val = str(text or '')
        if val:
            entry.insert(0, val)
        elif hasattr(entry, '_restore_placeholder'):
            entry._restore_placeholder()
    finally:
        entry._mute_change = prev_mute


def status_style_name(state, *, selected=False, header=False):
    """把四态状态键映射到 ``ui_theme`` 已登记的语义标签样式名。"""
    suffix = STATE_STYLE_SUFFIX.get(state, 'Idle')
    if header:
        return f'ModelRouteStatus{suffix}.TLabel'
    if selected:
        return f'ModelStatus{suffix}Selected.TLabel'
    return f'ModelStatus{suffix}.TLabel'


def status_prefix(state, text):
    """拼接语义圆点与简洁状态文字。"""
    dot = STATE_DOT.get(state, '●')
    body = str(text or '').strip()
    return f'{dot} {body}' if body else dot


class CollapsibleSection(ttk.Frame):
    """默认可折叠分区（用于「高级参数」与路线级高级项）。"""

    def __init__(self, master, title, *, open_by_default=False, action_text='',
                 action_command=None, card_bg=False):
        super().__init__(master, style='Card.TFrame' if card_bg else 'TFrame')
        self._base_title = title
        self._open = bool(open_by_default)
        self._summary = ''
        header_style = 'Card.TFrame' if card_bg else 'TFrame'
        self.header = ttk.Frame(self, style=header_style)
        self.header.pack(fill='x')
        self.toggle_button = SecondaryButton(
            self.header, text='', width=0, style='Tokens.Text.TButton', command=self.toggle)
        self.toggle_button.pack(side='left')
        self.action_button = None
        if action_text and callable(action_command):
            self.action_button = SecondaryButton(
                self.header, text=action_text, width=0, style='Tokens.Text.TButton',
                command=action_command)
            self.action_button.pack(side='right')
        self.body = ttk.Frame(self, style=header_style,
                              padding=(SPACING['sm'], SPACING['xs'], SPACING['none'], SPACING['xs']))
        self._refresh_header()
        if self._open:
            self.body.pack(fill='x')

    def is_open(self):
        return self._open

    def set_summary(self, summary):
        self._summary = str(summary or '').strip()
        self._refresh_header()

    def _refresh_header(self):
        arrow = '▾' if self._open else '▸'
        tail = f'（{self._summary}）' if (self._summary and not self._open) else ''
        self.toggle_button.configure(text=f'{arrow} {self._base_title}{tail}')

    def toggle(self):
        self.set_open(not self._open)

    def set_open(self, opened):
        flag = bool(opened)
        if flag == self._open:
            return
        self._open = flag
        if self._open:
            self.body.pack(fill='x')
        else:
            self.body.pack_forget()
        self._refresh_header()


class ModelCardList(ttk.Frame):
    """左侧可滚动双行模型状态卡片列表，支持选中高亮与单项徽标就地刷新。"""

    def __init__(self, master, *, on_select=None, empty_text='暂无模型配置'):
        super().__init__(master)
        self._on_select = on_select
        self._empty_text = empty_text
        self._selected = ''
        self._order = []
        self._cards = {}
        self._scroll = ScrollForm(self, bg=COLORS['background_primary'])
        self._empty_label = HintLabel(self._scroll.form, text=empty_text)

    @property
    def scroll_form(self):
        return self._scroll

    def item_ids(self):
        return tuple(self._order)

    def selected_id(self):
        return self._selected

    def card_widgets(self):
        return dict(self._cards)

    def render(self, items, *, selected=''):
        """按 ``[(model_id, title, badge_dict), ...]`` 重建双行卡片列表。"""
        for child in self._scroll.form.winfo_children():
            if child is not self._empty_label:
                child.destroy()
        self._cards.clear()
        self._order = []
        self._selected = str(selected or '')
        if not items:
            self._empty_label.configure(text=self._empty_text)
            self._empty_label.pack(fill='x', padx=SPACING['sm'], pady=SPACING['lg'])
            self._scroll.fit()
            return
        self._empty_label.pack_forget()
        for model_id, title, badge in items:
            self._order.append(model_id)
            card = self._build_card(model_id, title, badge, is_selected=(model_id == self._selected))
            card.pack(fill='x', padx=(SPACING['none'], SPACING['xs']), pady=(SPACING['none'], SPACING['xs']))
            self._cards[model_id] = card
        self._scroll.bind_wheel()
        self._scroll.fit()

    def _build_card(self, model_id, title, badge, *, is_selected=False):
        frame_style = 'ModelListCardSelected.TFrame' if is_selected else 'ModelListCard.TFrame'
        title_style = 'ModelCardTitleSelected.TLabel' if is_selected else 'ModelCardTitle.TLabel'
        meta_style = 'ModelCardMetaSelected.TLabel' if is_selected else 'ModelCardMeta.TLabel'
        state = badge.get('state') or 'idle'
        badge_style = status_style_name(state, selected=is_selected)
        card = ttk.Frame(self._scroll.form, style=frame_style,
                         padding=(SPACING['sm'], SPACING['sm']))
        card._model_id = model_id
        card._badge = dict(badge)
        row1 = ttk.Frame(card, style='ModelListCardSelected.TFrame' if is_selected else 'Card.TFrame')
        row1.configure(borderwidth=0, relief='flat')
        row1.pack(fill='x')
        title_lbl = ttk.Label(row1, text=title or model_id, style=title_style)
        title_lbl.pack(side='left', fill='x', expand=True)
        status_lbl = ttk.Label(row1, text=status_prefix(state, badge.get('short') or ''),
                               style=badge_style)
        status_lbl.pack(side='right', padx=(SPACING['xs'], SPACING['none']))
        meta_lbl = ttk.Label(card, text=badge.get('meta') or '', style=meta_style)
        meta_lbl.pack(anchor='w', pady=(SPACING['xs'], SPACING['none']))
        card._parts = (row1, title_lbl, status_lbl, meta_lbl)
        self._bind_click(card, model_id)
        return card

    def _bind_click(self, card, model_id):
        def choose(_event=None):
            if callable(self._on_select):
                self._on_select(model_id)
            else:
                self.set_selected(model_id)
        for widget in (card, *card._parts):
            widget.bind('<Button-1>', choose, add='+')

    def set_selected(self, model_id):
        """仅刷新选中高亮样式，不重建卡片。"""
        target = str(model_id or '')
        self._selected = target
        for mid, card in self._cards.items():
            picked = mid == target
            state = card._badge.get('state') or 'idle'
            row1, title_lbl, status_lbl, meta_lbl = card._parts
            card.configure(style='ModelListCardSelected.TFrame' if picked else 'ModelListCard.TFrame')
            row1.configure(style='ModelListCardSelected.TFrame' if picked else 'Card.TFrame')
            title_lbl.configure(style='ModelCardTitleSelected.TLabel' if picked else 'ModelCardTitle.TLabel')
            meta_lbl.configure(style='ModelCardMetaSelected.TLabel' if picked else 'ModelCardMeta.TLabel')
            status_lbl.configure(style=status_style_name(state, selected=picked))

    def update_badge(self, model_id, badge):
        """就地更新单张卡片的四态徽标与副标题，无需整列重绘。"""
        card = self._cards.get(model_id)
        if card is None:
            return
        card._badge = dict(badge)
        picked = model_id == self._selected
        state = badge.get('state') or 'idle'
        _row1, _title_lbl, status_lbl, meta_lbl = card._parts
        status_lbl.configure(text=status_prefix(state, badge.get('short') or ''),
                             style=status_style_name(state, selected=picked))
        meta_lbl.configure(text=badge.get('meta') or '')


class RouteCard(ttk.Frame):
    """单条 API 路线卡片：首选默认展开、备用默认折叠单行摘要条，右侧顺手可点「测试」。"""

    def __init__(self, master, *, index, route, total, expanded, callbacks):
        super().__init__(master, style='ModelRouteCard.TFrame')
        self.index = index
        self.total = total
        self.callbacks = dict(callbacks or {})
        self.route_id = str(route.get('id') or f'r{index + 1}')
        self._expanded = bool(expanded)
        self._details_open = False
        self._loading = True
        self._enabled = bool(route.get('enabled', True))
        self.provider_var = tk.StringVar(value=model_routes.match_preset(
            route.get('provider', ''), route.get('base_url', '')))
        self.wire_var = tk.StringVar(value=model_pool.WIRE_LABELS.get(
            route.get('wire_api'), model_pool.WIRE_LABELS[model_pool.DEFAULT_WIRE]))
        self.key_state_var = tk.StringVar(value='未存本机密钥')
        self.status_line_var = tk.StringVar(value='● 未测试')
        self.detail_text_var = tk.StringVar(value='')
        self._build_header()
        self._build_body()
        self._fill_initial(route)
        self._bind_events()
        self._loading = False
        self._sync_expand_ui()
        self._sync_header_title()

    def _build_header(self):
        self.header = ttk.Frame(self, style='ModelRouteHeader.TFrame',
                                padding=(SPACING['sm'], SPACING['xs']))
        self.header.pack(fill='x')
        self.title_label = ttk.Label(self.header, text='', style='ModelRouteTitle.TLabel')
        self.title_label.pack(side='left')
        self.header_status = ttk.Label(self.header, text='', style='ModelRouteStatusIdle.TLabel')
        self.header_status.pack(side='left', padx=(SPACING['sm'], SPACING['none']))
        actions = ttk.Frame(self.header, style='ModelRouteHeader.TFrame')
        actions.pack(side='right')
        self.test_button = SecondaryButton(
            actions, text='测试', width=0, command=lambda: self._fire('on_test', self))
        self.test_button.pack(side='left')
        self.promote_button = None
        if self.index > 0:
            self.promote_button = SecondaryButton(
                actions, text='设为首选', width=0, style='Tokens.Text.TButton',
                command=lambda: self._fire('on_promote', self))
            self.promote_button.pack(side='left', padx=(BUTTON_GAP_TIGHT, SPACING['none']))
        self.toggle_btn = SecondaryButton(
            actions, text='收起 ▴' if self._expanded else '编辑 ▾', width=0,
            style='Tokens.Text.TButton', command=self.toggle_expanded)
        self.toggle_btn.pack(side='left', padx=(BUTTON_GAP_TIGHT, SPACING['none']))
        self.enable_button = None
        self.remove_button = None
        if self.total > 1:
            self.enable_button = SecondaryButton(
                actions, text='停用' if self._enabled else '启用', width=0,
                style='Tokens.Text.TButton', command=self._toggle_enabled)
            self.enable_button.pack(side='left', padx=(BUTTON_GAP_TIGHT, SPACING['none']))
            self.remove_button = SecondaryButton(
                actions, text='删', width=0, style='Tokens.Text.TButton',
                command=lambda: self._fire('on_remove', self))
            self.remove_button.pack(side='left', padx=(BUTTON_GAP_TIGHT, SPACING['none']))

    def _build_body(self):
        from ui.ui_popup import measure_text_width
        from ui_tokens import FONTS, FORM_LABEL_WIDTH
        self.body = ttk.Frame(self, style='Card.TFrame', padding=(SPACING['md'], SPACING['sm']))
        label_min = max(
            measure_text_width(FONTS['body'], ['0']) * FORM_LABEL_WIDTH,
            measure_text_width(FONTS['body'], ('服务商预设', '模型名称', '应用安装路径', '命令行程序路径')),
        ) + SPACING['md']
        self.body.columnconfigure(0, minsize=label_min)
        self.body.columnconfigure(1, weight=1)
        row = 0
        ttk.Label(self.body, text='服务商预设', style='ModelField.TLabel').grid(
            row=row, column=0, sticky='w', pady=(SPACING['none'], SPACING['xs']))
        top_row = ttk.Frame(self.body, style='Card.TFrame')
        top_row.grid(row=row, column=1, sticky='ew', pady=(SPACING['none'], SPACING['xs']))
        top_row.columnconfigure(2, weight=1)
        self.provider_box = SelectBox(
            top_row, textvariable=self.provider_var, state='normal',
            values=self._provider_values(), style=COMPACT_COMBOBOX_STYLE, fit=True)
        self.provider_box.grid(row=0, column=0, sticky='w')
        ttk.Label(top_row, text='路线备注', style='ModelFieldMuted.TLabel').grid(
            row=0, column=1, sticky='e', padx=(SPACING['md'], SPACING['xs']))
        self.name_entry = CompactLineInput(top_row, placeholder='如：官方直连 / 中转站A')
        self.name_entry.grid(row=0, column=2, sticky='ew')
        row += 1
        ttk.Label(self.body, text='API 地址', style='ModelField.TLabel').grid(
            row=row, column=0, sticky='w', pady=(SPACING['none'], SPACING['xs']))
        self.base_url_entry = EditablePresetBox(self.body, values=self._base_url_values())
        self.base_url_entry.grid(row=row, column=1, sticky='ew', pady=(SPACING['none'], SPACING['xs']))
        row += 1
        ttk.Label(self.body, text='模型 ID', style='ModelField.TLabel').grid(
            row=row, column=0, sticky='w', pady=(SPACING['none'], SPACING['xs']))
        model_row = ttk.Frame(self.body, style='Card.TFrame')
        model_row.grid(row=row, column=1, sticky='ew', pady=(SPACING['none'], SPACING['xs']))
        model_row.columnconfigure(0, weight=1)
        self.model_entry = EditablePresetBox(model_row, values=self._model_values())
        self.model_entry.grid(row=0, column=0, sticky='ew')
        self.fetch_button = SecondaryButton(
            model_row, text='获取模型…', width=0, command=lambda: self._fire('on_fetch_models', self))
        self.fetch_button.grid(row=0, column=1, padx=(BUTTON_GAP_TIGHT, SPACING['none']))
        row += 1
        ttk.Label(self.body, text='API Key', style='ModelField.TLabel').grid(
            row=row, column=0, sticky='w', pady=(SPACING['none'], SPACING['xs']))
        key_row = ttk.Frame(self.body, style='Card.TFrame')
        key_row.grid(row=row, column=1, sticky='ew', pady=(SPACING['none'], SPACING['xs']))
        key_row.columnconfigure(0, weight=1)
        self.key_entry = PasswordInput(key_row, width=CHAR_WIDTH['3xl'], mask='*', show='*')
        self.key_entry.grid(row=0, column=0, sticky='ew')
        self.key_state_label = ttk.Label(key_row, textvariable=self.key_state_var,
                                         style='ModelFieldMuted.TLabel')
        self.key_state_label.grid(row=0, column=1, sticky='w', padx=(SPACING['sm'], SPACING['none']))
        self.clear_key_button = SecondaryButton(
            key_row, text='清除', width=0, style='Tokens.Text.TButton',
            command=lambda: self._fire('on_clear_key', self))
        self.clear_key_button.grid(row=0, column=2, padx=(BUTTON_GAP_TIGHT, SPACING['none']))
        row += 1
        status_row = ttk.Frame(self.body, style='Card.TFrame')
        status_row.grid(row=row, column=0, columnspan=2, sticky='ew', pady=(SPACING['xs'], SPACING['none']))
        self.status_label = ttk.Label(status_row, textvariable=self.status_line_var,
                                      style='ModelStatusIdle.TLabel')
        self.status_label.pack(side='left', fill='x', expand=True)
        self.detail_toggle = SecondaryButton(
            status_row, text='详情 ▾', width=0, style='Tokens.Text.TButton',
            command=self.toggle_details)
        self.detail_toggle.pack(side='right')
        row += 1
        self.detail_frame = ttk.Frame(self.body, style='Card.TFrame',
                                      padding=(SPACING['sm'], SPACING['xs']))
        self.detail_frame_row = row
        self.detail_label = ttk.Label(self.detail_frame, textvariable=self.detail_text_var,
                                      style='ModelFieldMuted.TLabel',
                                      wraplength=TEXT_DESC['wraplength'])
        self.detail_label.pack(anchor='w', fill='x')
        detail_bar = ttk.Frame(self.detail_frame, style='Card.TFrame')
        detail_bar.pack(fill='x', pady=(SPACING['xs'], SPACING['none']))
        self.verify_button = SecondaryButton(
            detail_bar, text='小样本完整验证', width=0,
            command=lambda: self._fire('on_verify', self))
        self.verify_button.pack(side='left')
        ttk.Label(detail_bar, text='发送一次短对话以确认正文与完整能力（可能产生极少量用量）',
                  style='ModelFieldMuted.TLabel').pack(side='left', padx=(SPACING['sm'], SPACING['none']))
        row += 1
        self.route_adv = CollapsibleSection(self.body, '协议与环境变量（默认已自动匹配）',
                                            open_by_default=False, card_bg=True)
        self.route_adv.grid(row=row, column=0, columnspan=2, sticky='ew', pady=(SPACING['xs'], SPACING['none']))
        adv = self.route_adv.body
        adv.columnconfigure(1, weight=1)
        ttk.Label(adv, text='接口协议', style='ModelField.TLabel').grid(
            row=0, column=0, sticky='w', pady=(SPACING['none'], SPACING['xs']))
        self.wire_box = SelectBox(
            adv, textvariable=self.wire_var, style=COMPACT_COMBOBOX_STYLE,
            values=[label for _v, label in model_pool.WIRE_APIS], fit=True)
        self.wire_box.grid(row=0, column=1, sticky='w', pady=(SPACING['none'], SPACING['xs']))
        ttk.Label(adv, text='密钥环境变量', style='ModelField.TLabel').grid(
            row=1, column=0, sticky='w', pady=(SPACING['none'], SPACING['xs']))
        self.key_env_entry = EditablePresetBox(adv, values=self._key_env_values())
        self.key_env_entry.grid(row=1, column=1, sticky='ew', pady=(SPACING['none'], SPACING['xs']))
        ttk.Label(adv, text='请求路径', style='ModelField.TLabel').grid(row=2, column=0, sticky='w')
        self.path_entry = CompactLineInput(adv, placeholder='/chat/completions')
        self.path_entry.grid(row=2, column=1, sticky='ew')

    def _fill_initial(self, route):
        set_input_value(self.name_entry, route.get('name') or '')
        set_input_value(self.base_url_entry, route.get('base_url') or '')
        set_input_value(self.model_entry, route.get('model') or '')
        set_input_value(self.key_env_entry, route.get('key_env') or '')
        set_input_value(self.path_entry, route.get('path') or model_routes.DEFAULT_PATH)

    def _provider_values(self):
        extra = self.callbacks.get('extra_providers') or ()
        presets = model_routes.preset_labels()
        seen = {item.casefold() for item in presets}
        tail = [item for item in extra if item and item.casefold() not in seen]
        return [*presets, *tail]

    def _base_url_values(self):
        custom = self.callbacks.get('base_url_presets')
        if custom:
            return tuple(custom)
        return tuple(row[2] for row in model_routes.PROVIDER_PRESETS if row[2])

    def _model_values(self):
        return tuple(self.callbacks.get('model_presets') or (
            'deepseek-chat', 'gpt-4o', 'claude-sonnet-4-5', 'qwen-max', 'gemini-2.5-pro'))

    def _key_env_values(self):
        custom = self.callbacks.get('key_env_presets')
        if custom:
            return tuple(custom)
        return tuple(row[4] for row in model_routes.PROVIDER_PRESETS if row[4])

    def set_model_presets(self, values):
        self.callbacks['model_presets'] = tuple(values or ())
        self.model_entry.set_values(self._model_values(), refit=False)

    def _bind_events(self):
        self.provider_box.bind('<<ComboboxSelected>>', self._on_preset_selected, add='+')
        self.wire_box.bind('<<ComboboxSelected>>', self._mark_changed, add='+')
        for entry in (self.name_entry, self.base_url_entry, self.model_entry,
                      self.key_entry, self.key_env_entry, self.path_entry):
            entry.bind('<KeyRelease>', self._mark_changed, add='+')
        for box in (self.base_url_entry, self.model_entry, self.key_env_entry):
            box.bind('<<ComboboxSelected>>', self._mark_changed, add='+')
        self.name_entry.bind('<KeyRelease>', lambda _e: self._sync_header_title(), add='+')
        self.model_entry.bind('<KeyRelease>', lambda _e: self._fire('on_model_edited', self), add='+')
        self.model_entry.bind('<<ComboboxSelected>>', lambda _e: self._fire('on_model_edited', self), add='+')
        self.key_entry.bind('<Return>', lambda _e: self._fire('on_key_commit', self), add='+')

    def _fire(self, name, *args):
        fn = self.callbacks.get(name)
        return fn(*args) if callable(fn) else None

    def _mark_changed(self, _event=None):
        if not self._loading:
            self._fire('on_dirty')

    def _on_preset_selected(self, _event=None):
        preset = model_routes.preset_by_label(self.provider_var.get())
        if preset:
            if preset['base_url']:
                set_input_value(self.base_url_entry, preset['base_url'])
            wire_label = model_pool.WIRE_LABELS.get(
                preset['wire_api'], model_pool.WIRE_LABELS[model_pool.DEFAULT_WIRE])
            self.wire_var.set(wire_label)
            if not self.name_entry.get().strip() and preset['id'] != 'custom':
                set_input_value(self.name_entry, preset['label'])
        self._sync_header_title()
        self._mark_changed()

    def _toggle_enabled(self):
        self._enabled = not self._enabled
        if self.enable_button is not None:
            self.enable_button.configure(text='停用' if self._enabled else '启用')
        self._sync_header_title()
        self._mark_changed()
        self._fire('on_enabled_changed', self)

    def toggle_expanded(self):
        self._expanded = not self._expanded
        self._sync_expand_ui()
        self._fire('on_layout_changed')

    def is_expanded(self):
        return self._expanded

    def _sync_expand_ui(self):
        if self._expanded:
            self.body.pack(fill='x')
            self.toggle_btn.configure(text='收起 ▴')
        else:
            self.body.pack_forget()
            self.toggle_btn.configure(text='编辑 ▾')

    def toggle_details(self):
        self._details_open = not self._details_open
        if self._details_open:
            self.detail_frame.grid(row=self.detail_frame_row, column=0, columnspan=2,
                                   sticky='ew', pady=(SPACING['xs'], SPACING['xs']))
            self.detail_toggle.configure(text='详情 ▴')
        else:
            self.detail_frame.grid_forget()
            self.detail_toggle.configure(text='详情 ▾')
        self._fire('on_layout_changed')

    def _sync_header_title(self):
        custom_name = self.name_entry.get().strip() or self.provider_var.get().strip() or '自定义中转'
        prefix = '★ 首选路线' if self.index == 0 else f'#{self.index + 1} 备用路线'
        tag = '（已停用）' if not self._enabled else ''
        self.title_label.configure(text=f'{prefix} · {custom_name}{tag}')

    def set_key_state(self, local_key=''):
        if local_key:
            self.key_state_var.set('本机已存：' + model_pool.redacted(local_key))
            self.clear_key_button.grid()
        else:
            self.key_state_var.set('未存本机密钥')
            self.clear_key_button.grid_remove()

    def set_badge(self, badge, *, breakdown_text=''):
        state = (badge or {}).get('state') or 'idle'
        label = (badge or {}).get('label') or '未测试'
        short = (badge or {}).get('short') or label
        self.header_status.configure(text=status_prefix(state, short),
                                     style=status_style_name(state, header=True))
        self.status_line_var.set(status_prefix(state, label))
        self.status_label.configure(style=status_style_name(state))
        if breakdown_text:
            self.detail_text_var.set(breakdown_text)
        elif not self.detail_text_var.get():
            self.detail_text_var.set((badge or {}).get('detail') or '点击右上角「测试」可查看五维诊断详情。')

    def set_testing(self, busy):
        self.test_button.configure(text='测试中…' if busy else '测试')
        self.test_button.state(['disabled'] if busy else ['!disabled'])

    def set_fetching(self, busy):
        self.fetch_button.configure(text='拉取中…' if busy else '获取模型…')
        self.fetch_button.state(['disabled'] if busy else ['!disabled'])

    def typed_key(self):
        return self.key_entry.get().strip()

    def clear_typed_key(self):
        self.key_entry.delete(0, 'end')

    def to_dict(self):
        return {
            'id': self.route_id,
            'name': self.name_entry.get().strip(),
            'provider': self.provider_var.get().strip(),
            'base_url': self.base_url_entry.get().strip(),
            'path': self.path_entry.get().strip() or model_routes.DEFAULT_PATH,
            'wire_api': model_pool.id_of_label(self.wire_var.get(), model_pool.WIRE_APIS),
            'model': self.model_entry.get().strip(),
            'key_env': self.key_env_entry.get().strip(),
            'enabled': self._enabled,
        }


def open_remote_model_picker(parent, models, on_pick):
    """弹出轻量可搜索的远端模型 ID 选择窗（对齐 DSH「获取可用模型」体验，复用 DataTable）。"""
    win = BaseDialog(parent, '选择远端模型', modal=False, chrome=False)
    win.title('选择远端模型')
    win.geometry('420x400')
    win.minsize(340, 280)
    win.transient(parent)
    body = ttk.Frame(win, padding=SPACING['md'])
    body.pack(fill='both', expand=True)
    search = CompactLineInput(body, placeholder='输入关键词筛选模型 ID…')
    search.pack(fill='x', pady=(SPACING['none'], SPACING['sm']))
    table = DataTable(body, columns=(('model', '远端模型 ID', 360),), show='headings',
                      height=TEXT_ROWS['2xl'], empty_text='无匹配的远端模型')
    table.pack(fill='both', expand=True)
    tree = table.tree

    def refresh(_event=None):
        kw = search.get().strip().casefold()
        tree.delete(*tree.get_children())
        for item in models:
            if not kw or kw in item.casefold():
                tree.insert('', 'end', iid=item, values=(item,))
        table.refresh_empty_state()

    def confirm(_event=None):
        sel = tree.selection()
        if not sel:
            return
        picked = str(sel[0])
        win.destroy()
        if callable(on_pick):
            on_pick(picked)

    search.bind('<KeyRelease>', refresh)
    tree.bind('<Double-Button-1>', confirm)
    tree.bind('<Return>', confirm)
    win.bind('<Escape>', lambda _e: win.destroy())
    bar = ttk.Frame(body)
    bar.pack(fill='x', pady=(SPACING['sm'], SPACING['none']))
    PrimaryButton(bar, text='选用', command=confirm).pack(side='right')
    SecondaryButton(bar, text='取消', command=win.destroy).pack(
        side='right', padx=(SPACING['none'], SPACING['sm']))
    refresh()
    search.focus_set()
    return win

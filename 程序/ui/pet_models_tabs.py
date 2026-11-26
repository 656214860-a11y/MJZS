# -*- coding: utf-8 -*-
"""模型管理窗口的调用方式分段、5+ 主流预设表、卡片过滤、内嵌接缝、多路线管理与脏守卫。

按调用方式（API／Desktop／CLI／语音识别）分段：前三种采用左右主从卡片与多路线配置，
「语音识别」原地展示语音识别与词典面板；独立弹窗与设置窗右侧内嵌共用同一实现
（REQ-UI-MODEL-PAGE-2 + UX-SETTINGS-MODELS）。
"""
from tkinter import ttk
import tkinter as tk
from ui.pet_models_cards import (COMPACT_COMBOBOX_PAD_Y, COMPACT_COMBOBOX_STYLE,
                                 COMPACT_PREFIX, CompactLineInput, EditablePresetBox,
                                 RouteCard, install_compact_form_styles,
                                 open_remote_model_picker, set_input_value)
from ui.ui_dialogs import FileDialog
from ui_widgets import SecondaryButton
from ui_tokens import FONTS, FORM_LABEL_WIDTH, SPACING
import infra.model_pool as model_pool
import infra.model_routes as model_routes

SPEECH_MODE = '语音识别'
MODES = ('API', 'Desktop', 'CLI', SPEECH_MODE)
MODALITY_FILTERS = ('全部', '文本', '图片', '语音', '视频')
FORM_FIELDS = (('label', '显示名'), ('model', '模型 ID'), ('base_url', 'API 根地址'),
               ('key_env', '密钥环境变量'))
FORM_DEFAULT_PROVIDER = model_pool.PROVIDER_LABELS['custom']
DEFAULT_CONTEXT_LENGTH = 262144
NEW_MODEL_DEFAULTS = {'context_length': DEFAULT_CONTEXT_LENGTH,
                      'max_output': 8192,
                      'temperature': 0.7,
                      'timeout': 120,
                      'retries': 2}

# UX-SETTINGS-MODELS：每个非密钥单行字段默认提供 5+ 项主流预设（API 地址派生自 model_routes 单一真源）。
PROVIDER_PRESETS = ('DeepSeek', 'OpenAI', 'Anthropic', '通义千问', 'Google Gemini')
API_MODEL_PRESETS = {
    '文本': ('deepseek-chat', 'gpt-4o', 'claude-sonnet-4-5', 'qwen-max', 'gemini-2.5-pro'),
    '图片': ('gpt-image-1', 'flux-pro-1.1', 'wanx2.1-t2i-turbo', 'jimeng-3.0', 'imagen-3.0'),
    '语音': ('cosyvoice-v2', 'gpt-4o-mini-tts', 'eleven_multilingual_v2', 'fish-speech-1.5', 'qwen-tts'),
    '视频': ('kling-v2', 'wan2.1-t2v-turbo', 'jimeng-video-3.0', 'veo-3', 'sora-2'),
}
LOCAL_MODEL_PRESETS = {
    'Desktop': ('chatgpt-desktop', 'claude-desktop', 'opencode-desktop', 'gemini-desktop', 'deepseek-desktop'),
    'CLI': ('codex-cli', 'claude-code', 'qwen-code', 'opencode-cli', 'deepseek-harness'),
}
API_LABEL_PRESETS = {
    '文本': ('DeepSeek 对话', 'GPT-4o', 'Claude Sonnet', '通义千问 Max', 'Gemini 2.5 Pro'),
    '图片': ('GPT Image 1', 'FLUX Pro 1.1', '通义万相 2.1 Turbo', '即梦 3.0', 'Imagen 3.0'),
    '语音': ('CosyVoice v2', 'GPT-4o Mini TTS', 'ElevenLabs Multilingual v2', 'Fish Speech 1.5', 'Qwen TTS'),
    '视频': ('可灵 Kling v2', '通义万相 2.1 视频', '即梦视频 3.0', 'Google Veo 3', 'OpenAI Sora 2'),
}
LOCAL_LABEL_PRESETS = {
    'Desktop': ('ChatGPT Desktop', 'Claude Desktop', 'OpenCode Desktop', 'Gemini Desktop', 'DeepSeek Desktop'),
    'CLI': ('Codex CLI', 'Claude Code CLI', 'Qwen Code CLI', 'OpenCode CLI', 'DeepSeek Harness CLI'),
}
PROGRAM_PRESETS = {
    'Desktop': (
        r'C:\Users\Public\Apps\ChatGPT\ChatGPT.exe',
        r'C:\Users\Public\Apps\Claude\Claude.exe',
        r'C:\Users\Public\Apps\OpenCode\opencode.exe',
        r'C:\Users\Public\Apps\Cursor\Cursor.exe',
        r'C:\Users\Public\Apps\DeepSeek\DeepSeek.exe',
    ),
    'CLI': ('codex.cmd', 'claude.cmd', 'qwen.cmd', 'opencode.exe', 'gemini.cmd'),
}
STATIC_FIELD_PRESETS = {
    'base_url': tuple(row[2] for row in model_routes.PROVIDER_PRESETS if row[2]),
    'key_env': tuple(dict.fromkeys(
        [*(row[4] for row in model_routes.PROVIDER_PRESETS if row[4]), 'GEMINI_API_KEY'])),
    'context_length': ('32768', '65536', '131072', '262144', '1048576'),
    'note': ('主力文本创作', '快速草稿与大纲', '复杂推理与审校', '视觉分镜与出图', '备用兜底线路'),
    'rpm': ('10', '30', '60', '120', '300'),
    'max_output': ('4096', '8192', '16384', '32768', '65536'),
    'temperature': ('0.0', '0.3', '0.7', '1.0', '1.2'),
    'timeout': ('30', '60', '120', '180', '300'),
    'retries': ('0', '1', '2', '3', '5'),
}


def provider_choices():
    """下拉不含「OpenAI 兼容接口」，含主流厂商＋「自定义」，按 casefold 去重并排序。"""
    builtins = [label for value, label in model_pool.PROVIDERS if value != model_pool.DEFAULT_PROVIDER]
    seen = {item.casefold() for item in builtins}
    merged = list(builtins)
    for preset in PROVIDER_PRESETS:
        if preset.casefold() not in seen:
            seen.add(preset.casefold())
            merged.append(preset)
    return sorted(merged, key=str.casefold)


def merge_provider_choices(builtins, records):
    saved = {model_pool.provider_name(model_id, item) for model_id, item in records.items()}
    seen = {label.casefold() for label in builtins}
    extra = [item for item in sorted((x for x in saved if x), key=str.casefold)
             if item.casefold() not in seen and not seen.add(item.casefold())]
    return sorted([*builtins, *extra], key=str.casefold), extra


def model_presets(mode, modality_label='文本'):
    if mode in LOCAL_MODEL_PRESETS:
        return LOCAL_MODEL_PRESETS[mode]
    return API_MODEL_PRESETS.get(modality_label, API_MODEL_PRESETS['文本'])


def label_presets(mode, modality_label='文本'):
    if mode in LOCAL_LABEL_PRESETS:
        return LOCAL_LABEL_PRESETS[mode]
    return API_LABEL_PRESETS.get(modality_label, API_LABEL_PRESETS['文本'])


def program_presets(mode, extra=()):
    base = PROGRAM_PRESETS.get(mode, PROGRAM_PRESETS['Desktop'])
    seen, merged = set(), []
    for item in (*extra, *base):
        text = str(item or '').strip()
        if text and text.casefold() not in seen:
            seen.add(text.casefold())
            merged.append(text)
    return tuple(merged)


def field_presets(key, mode='API', modality_label='文本'):
    if key == 'model':
        return model_presets(mode, modality_label)
    if key == 'label':
        return label_presets(mode, modality_label)
    if key == 'program':
        return program_presets(mode)
    return STATIC_FIELD_PRESETS.get(key, ())


def prepend_dropdown_value(box, value):
    """把自动探测出的路径置前合并到下拉候选里，不改变框体固定宽度。"""
    text = str(value or '').strip()
    if not text or not hasattr(box, 'set_values'):
        return
    current = [str(item) for item in (box.cget('values') or ())]
    if any(item.casefold() == text.casefold() for item in current):
        return
    box.set_values((text, *current), refit=False)


def list_status(record, program):
    """模型列表状态文案：用得了写「可用」，用不了写缺什么。"""
    ok, why = model_pool.status(record, program)
    return '可用' if ok else why


def attach_manager_seams(manager, target):
    """把模型管理自检接缝挂到独立弹窗宿主对象上。"""
    target._pet_detect_program = manager.detect_program
    target._pet_read_form = manager.read_form
    target._pet_delete_one = manager.delete_one
    target._pet_reload = manager.load_rows
    target._pet_hint = manager.hint
    target._pet_manager_hint_label = manager.manager_hint_label
    target._pet_entries = manager.entries
    target._pet_labels = manager.labels
    target._pet_mode = manager.mode
    target._pet_modality_box = manager.modality_box
    target._pet_mode_control = manager.mode_tabs
    target._pet_mode_buttons = manager.mode_tabs.buttons
    target._pet_cards = manager.card_list
    target._pet_select_model = manager.select_model
    target._pet_route_cards = lambda: list(manager.route_cards)
    target._pet_add_route = manager.add_route
    target._pet_advanced_section = manager.advanced_section
    target._pet_probe_all = manager.probe_all_visible
    target._pet_probe_route = manager.probe_route_card
    target._pet_save_key = manager.local_save
    target._pet_save_typed = manager.save_typed_key
    target._pet_clear_key = manager.local_clear
    target._pet_key_state = manager._primary_key_state
    target._pet_program_row = manager.program_row
    target._pet_api_controls = (manager.routes_section,)
    target._pet_cancel = manager.cancel
    target._pet_search_entry = manager.search_entry


def build_embedded_seam(manager):
    """构造设置窗内嵌「模型配置」页返回给 pet_settings_ui 的接缝字典。"""
    first = manager.route_cards[0] if manager.route_cards else None
    return {
        'manager': manager, 'hint': manager.hint, 'entries': manager.entries,
        'provider': (manager.local_provider if manager.desktop_mode() or not first else first.provider_var),
        'provider_box': (manager.local_provider_box if manager.desktop_mode() or not first else first.provider_box),
        'mode': manager.mode, 'mode_control': manager.mode_tabs,
        'mode_buttons': manager.mode_tabs.buttons, 'modality_box': manager.modality_box,
        'cards': manager.card_list, 'select_model': manager.select_model,
        'route_cards': lambda: list(manager.route_cards),
        'key_entry': (first.key_entry if first else None),
        'reload': manager.load_rows, 'save': manager.save_current,
        'is_dirty': manager.is_dirty, 'confirm_leave': manager.leave_page,
        'destroy_cleanup': manager._cleanup_resources, 'scroll': manager.right_scroll,
    }


class ModelManagerModeTabsMixin:
    """调用方式分段 + 语音识别原地切换 + 5+ 下拉刷新 + 左侧双行卡片过滤。"""

    def _on_tab_changed(self, _event=None):
        current = self.mode_tabs.current()
        if current != self.mode.get():
            self.mode.set(current)
        return True

    def _on_mode_change(self, *_args):
        current = self.mode.get()
        if current == self._last_mode:
            return
        self._last_mode = current
        if current in MODES:
            self.mode_tabs.select(current)
        self._sync_mode_view()
        if current == SPEECH_MODE:
            return
        self._refresh_field_presets()
        if not self.pending['loading']:
            self.load_rows(refresh=False)

    def _sync_mode_view(self):
        speech_active = self.mode.get() == SPEECH_MODE
        if speech_active == getattr(self, '_speech_visible', False):
            return
        self._speech_visible = speech_active
        if speech_active:
            self._ensure_speech_panel()
            self.split_container.pack_forget()
            self.speech_container.pack(fill='both', expand=True)
        else:
            self.speech_container.pack_forget()
            self.split_container.pack(fill='both', expand=True)

    def _refresh_field_presets(self, *_args):
        mode = self.mode.get()
        if mode == SPEECH_MODE:
            return
        modality_label = self.modality.get()
        for key in ('model', 'label'):
            box = self.entries.get(key)
            if box is not None and hasattr(box, 'set_values'):
                box.set_values(field_presets(key, mode, modality_label), refit=False)
        program_box = self.entries.get('program')
        if program_box is not None and hasattr(program_box, 'set_values'):
            current = program_box.get().strip()
            extra = (current,) if current else ()
            program_box.set_values(program_presets(mode, extra), refit=False)
        if mode == 'API':
            presets = model_presets('API', modality_label)
            for card in self.route_cards:
                card.set_model_presets(presets)

    def _matches_filters(self, model_id, item):
        mode = self.mode.get()
        if model_pool.call_mode(item, model_id) != mode:
            return False
        if mode == 'API':
            wanted_mod = self.modality_filter.current() if hasattr(self, 'modality_filter') else '全部'
            if wanted_mod != '全部':
                mod_label = model_pool.MODALITY_LABELS.get(item.get('modality'), '文本')
                if mod_label != wanted_mod:
                    return False
        kw = self.search_entry.get().strip().casefold() if hasattr(self, 'search_entry') else ''
        if not kw:
            return True
        hay = ' '.join((
            str(model_id or ''), str(item.get('label') or ''), str(item.get('model') or ''),
            model_pool.provider_name(model_id, item),
            ' '.join(str(r.get('name') or '') + ' ' + str(r.get('provider') or '')
                     for r in model_routes.routes_of(item, model_id=model_id)),
        )).casefold()
        return kw in hay

    def _render_mode_rows(self, records):
        if self.mode.get() == SPEECH_MODE:
            return
        probe_map = getattr(self, '_probe_cache', None)
        if probe_map is None:
            probe_map = self._probe_cache = model_routes.all_probe_status(program=self.program)
        filtered = []
        for model_id, item in records.items():
            if not self._matches_filters(model_id, item):
                continue
            vendor = model_pool.provider_name(model_id, item)
            title = str(item.get('label') or item.get('model') or model_id)
            badge = model_routes.model_badge(model_id, item, program=self.program, probe_map=probe_map)
            filtered.append((vendor.casefold(), title.casefold(), model_id, title, badge))
        filtered.sort(key=lambda row: (row[0], row[1], row[2]))
        cards = [(mid, title, badge) for _v, _t, mid, title, badge in filtered]
        self.card_list.render(cards, selected=self.state['id'])


class ModelManagerFormGuardMixin:
    """DES《05》§15.3：模型管理与内嵌语音页的统一「未保存改动」守卫。"""

    def _bind_dirty_marks(self):
        for entry in self.static_entries.values():
            entry.bind('<KeyRelease>', self._mark_dirty, add='+')
            if entry.winfo_class() == 'TCombobox':
                entry.bind('<<ComboboxSelected>>', self._mark_dirty, add='+')
        for box in (self.local_provider_box, self.modality_box):
            box.bind('<<ComboboxSelected>>', self._mark_dirty, add='+')

    def _mark_dirty(self, *_args):
        if not self.pending.get('loading'):
            self._dirty = True
            if callable(self._on_dirty):
                self._on_dirty()

    def _speech_dirty(self):
        return bool(self._speech_panel is not None and self._speech_panel['is_dirty']())

    def is_dirty(self):
        return bool(self._dirty or self._speech_dirty())

    def _active_dirty(self):
        return self._speech_dirty() if self.mode.get() == SPEECH_MODE else bool(self._dirty)

    def _confirm_discard(self, action, *, active_only=False):
        dirty = self._active_dirty() if active_only else self.is_dirty()
        if not dirty:
            return True
        return bool(self.pet.confirm_start('放弃未保存的改动',
                                           '有未保存的改动，%s后不保留。继续吗？' % action))

    def leave_page(self, action='切换页面'):
        if not self._confirm_discard(action):
            return False
        self._dirty = False
        if self._speech_panel is not None and self._speech_panel['is_dirty']():
            self._speech_panel['reload']()
        return True

    def select_model(self, model_id):
        target = str(model_id or '')
        if not target:
            return None
        if target != str(self.state['id']) and not self._confirm_discard('切换编辑对象', active_only=True):
            self.card_list.set_selected(self.state['id'])
            return None
        records = getattr(self, '_records_cache', None)
        if records is None:
            records = self._records_cache = self.pet.agent_model_records()
        item = records.get(target)
        if not isinstance(item, dict):
            return None
        self.card_list.set_selected(target)
        self.fill(target, item)
        self.hint.set('正在编辑「%s」；修改后点右上角「%s」。' % (
            item.get('label') or target, '保存当前' if self._embedded else '保存'))
        return item

    def _on_tab_changed(self, _event=None):
        current = self.mode_tabs.current()
        previous = self.mode.get()
        if current != previous:
            if not self._confirm_discard('切换调用方式', active_only=True):
                if previous in MODES:
                    self.mode_tabs.select(previous)
                return False
            if previous == SPEECH_MODE and self._speech_panel is not None and self._speech_panel['is_dirty']():
                self._speech_panel['reload']()
            else:
                self._dirty = False
        super()._on_tab_changed(_event)
        return True

    def new_one(self, _confirmed=False):
        if not _confirmed and not self._confirm_discard('新建模型', active_only=True):
            return None
        self._load_new_draft()
        return self.state

    def save_current(self):
        if self.mode.get() == SPEECH_MODE:
            return self._ensure_speech_panel()['save']()
        return self.save_one()

    def cancel(self, *_args):
        if not self._confirm_discard('关闭窗口'):
            return None
        self._cleanup_resources()
        self.win.destroy()
        return True

    def save_and_close(self):
        if self.save_current():
            self._cleanup_resources()
            self.win.destroy()


MODE_SEGMENT_STYLE = 'RailIcon.TButton'
MODE_SEGMENT_SELECTED_STYLE = 'Selected.RailIcon.TButton'


class ModeSegmentedControl(ttk.Frame):
    """调用方式／类型分段切换：小型胶囊按钮，鼠标、方向键、空格与回车都能切。"""

    def __init__(self, master, modes, command=None):
        super().__init__(master)
        self.modes = tuple(modes)
        self._command = command
        self._current = self.modes[0]
        self.buttons = {}
        for index, mode in enumerate(self.modes):
            button = SecondaryButton(self, text=mode, width=0, style=MODE_SEGMENT_STYLE,
                                     command=lambda value=mode: self.select(value, user=True))
            button.pack(side='left', padx=(SPACING['none'] if index == 0 else SPACING['xs'], SPACING['none']))
            button.bind('<Left>', lambda event, i=index: self._move(i - 1))
            button.bind('<Right>', lambda event, i=index: self._move(i + 1))
            button.bind('<Home>', lambda event: self._move(0))
            button.bind('<End>', lambda event: self._move(len(self.modes) - 1))
            button.bind('<Return>', lambda event, target=button: self._press(target))
            button.bind('<space>', lambda event, target=button: self._press(target))
            self.buttons[mode] = button
        self._sync_styles()

    def current(self):
        return self._current

    def select(self, mode, user=False):
        if mode not in self.buttons:
            return False
        if mode == self._current:
            self._sync_styles()
            return True
        previous = self._current
        self._current = mode
        self._sync_styles()
        accepted = True
        if user and self._command is not None:
            accepted = self._command()
        if accepted is False:
            self._current = previous
            self._sync_styles()
        return accepted

    def _sync_styles(self):
        for mode, button in self.buttons.items():
            button.configure(style=MODE_SEGMENT_SELECTED_STYLE if mode == self._current else MODE_SEGMENT_STYLE)

    def _move(self, index):
        mode = self.modes[index % len(self.modes)]
        self.buttons[mode].focus_set()
        if self.select(mode, user=True) is False:
            self.buttons[self._current].focus_set()
        return 'break'

    def _press(self, button):
        button.invoke()
        return 'break'


def form_column_width(labels):
    """表单标签列宽：令牌字符宽给下限，再按实际标签量出像素，避免中文标签被裁。"""
    from ui.ui_popup import measure_text_width
    gap = SPACING['md']
    floor = measure_text_width(FONTS['body'], ['0']) * FORM_LABEL_WIDTH
    return max(floor, measure_text_width(FONTS['body'], labels)) + gap


class ModelManagerRoutesMixin:
    """单模型多条 API 路线的渲染、增删改序与独立 DPAPI 密钥存取。"""

    def _render_routes(self, routes, *, expand_indices=None):
        for card in self.route_cards:
            card.destroy()
        self.route_cards = []
        items = list(routes or []) or [model_routes.normalize_route({'id': 'r1'}, index=0)]
        expanded = set(expand_indices if expand_indices is not None else {0})
        parent_item = self._partial_parent_record()
        probe_map = (self._probe_cache if self._probe_cache is not None
                     else model_routes.all_probe_status(program=self.program))
        callbacks = {
            'extra_providers': self._extra_providers,
            'model_presets': model_presets('API', self.modality.get()),
            'base_url_presets': STATIC_FIELD_PRESETS['base_url'],
            'key_env_presets': STATIC_FIELD_PRESETS['key_env'],
            'on_dirty': self._mark_dirty,
            'on_test': self.probe_route_card,
            'on_verify': self.verify_route_card,
            'on_fetch_models': self.fetch_models_for_card,
            'on_promote': self.promote_route,
            'on_remove': self.remove_route,
            'on_clear_key': self.clear_route_card_key,
            'on_key_commit': lambda c: self.save_route_card_key(c),
            'on_model_edited': self._on_route_model_edited,
            'on_enabled_changed': self._on_route_enabled_changed,
            'on_layout_changed': lambda: self.right_scroll.fit(),
        }
        total = len(items)
        for idx, route in enumerate(items):
            card = RouteCard(
                self.routes_container, index=idx, route=route, total=total,
                expanded=(idx in expanded), callbacks=callbacks,
            )
            card.pack(fill='x', pady=(SPACING['none'], SPACING['xs']))
            local_key = model_routes.local_route_key_of(
                parent_item, route, program=self.program, model_id=self.state['id'], index=idx)
            card.set_key_state(local_key)
            badge = model_routes.route_badge(
                parent_item, route, model_id=self.state['id'], index=idx,
                program=self.program, probe_map=probe_map)
            card.set_badge(badge, breakdown_text=self._breakdown_from_badge(parent_item, route, badge, idx))
            self.route_cards.append(card)
        self._sync_primary_hooks()
        self.right_scroll.bind_wheel()
        self.right_scroll.fit()

    def _snapshot_route_dicts(self):
        return [card.to_dict() for card in self.route_cards]

    def _expanded_indices(self):
        return {idx for idx, card in enumerate(self.route_cards) if card.is_expanded()}

    def add_route(self):
        routes = self._snapshot_route_dicts()
        used = {r['id'] for r in routes}
        seq = len(routes) + 1
        while f'r{seq}' in used:
            seq += 1
        default_model = self.entries['model'].get().strip() or (routes[0]['model'] if routes else '')
        routes.append(model_routes.normalize_route(
            {'id': f'r{seq}', 'name': f'备用路线 {seq - 1}', 'model': default_model, 'enabled': True},
            index=len(routes), used=used))
        expanded = self._expanded_indices() | {len(routes) - 1}
        self._render_routes(routes, expand_indices=expanded)
        self._mark_dirty()
        self.hint.set('已添加备用路线，填完地址和 API Key 可直接点该路线右侧「测试」。')

    def promote_route(self, card):
        routes = self._snapshot_route_dicts()
        idx = card.index
        if idx <= 0 or idx >= len(routes):
            return
        chosen = routes.pop(idx)
        routes.insert(0, chosen)
        self._render_routes(routes, expand_indices={0})
        self._mark_dirty()
        self.hint.set('已将该路线设为首选，主请求将优先走此路线；请点保存生效。')

    def remove_route(self, card):
        routes = self._snapshot_route_dicts()
        if len(routes) <= 1 or card.index >= len(routes):
            return
        routes.pop(card.index)
        self._render_routes(routes, expand_indices={0})
        self._mark_dirty()
        self.hint.set('已移除该备用路线，请点保存生效。')

    def _on_route_enabled_changed(self, card):
        route = card.to_dict()
        parent = self._partial_parent_record()
        badge = model_routes.route_badge(
            parent, route, model_id=self.state['id'], index=card.index,
            program=self.program, probe_map=self._probe_cache, override_key=card.typed_key())
        card.set_badge(badge)

    def _on_route_model_edited(self, card):
        if card.index != 0 or self.pending['loading']:
            return
        text = card.model_entry.get().strip()
        top_text = self.entries['model'].get().strip()
        if not top_text or top_text == self._auto_model_sync:
            set_input_value(self.entries['model'], text)
            self._auto_model_sync = text
            self.fill_label()

    def _on_top_model_edited(self, _event=None):
        if self.pending['loading'] or self.mode.get() == SPEECH_MODE:
            return
        self.fill_label()
        if not self.desktop_mode() and self.route_cards:
            top_text = self.entries['model'].get().strip()
            first = self.route_cards[0]
            cur_route_model = first.model_entry.get().strip()
            if not cur_route_model or cur_route_model == self._auto_model_sync:
                set_input_value(first.model_entry, top_text)
                self._auto_model_sync = top_text
        if self.desktop_mode() and self.entries['model'].get().strip():
            self._schedule_delayed_detect()

    def save_route_card_key(self, card, *, persist_pool=True):
        text = card.typed_key()
        if not text:
            return None
        parent = self.read_form()
        route = card.to_dict()
        model_key = self.state['id'] or parent.get('model') or route.get('model')
        try:
            secret_name = model_routes.save_route_key(
                parent, route, text, program=self.program, model_id=model_key, index=card.index)
        except (ValueError, OSError) as exc:
            self._report_error(exc)
            return None
        set_input_value(card.key_env_entry, secret_name)
        card.clear_typed_key()
        card.set_key_state(text)
        if persist_pool and model_key:
            updated = self.read_form()
            old_id = self.state['id']
            self.state['id'] = model_pool.model_id_of(updated, old_id)
            self.pet.save_pool(updated, old_id)
            self._dirty = False
            self.load_rows()
        self.hint.set('API Key 已加密保存到本机 DPAPI 存储（不落明文）。')
        return secret_name

    def clear_route_card_key(self, card):
        parent = self.read_form()
        route = card.to_dict()
        model_key = self.state['id'] or parent.get('model') or route.get('model')
        if not model_routes.clear_route_key(parent, route, program=self.program,
                                            model_id=model_key, index=card.index):
            self.hint.set('该路线本机本来就没存密钥。')
            return False
        card.set_key_state('')
        self.hint.set('已清除该路线的本机加密密钥。')
        return True

    def local_save(self):
        return self.save_route_card_key(self.route_cards[0], persist_pool=True) if self.route_cards else None

    def local_clear(self):
        return self.clear_route_card_key(self.route_cards[0]) if self.route_cards else False

    def save_typed_key(self, _event=None):
        if self.desktop_mode() or not self.route_cards or not self.route_cards[0].typed_key():
            return None
        return self.save_route_card_key(self.route_cards[0], persist_pool=True)


class ModelManagerActionsMixin:
    """后台异步测试、小样本验证、远端模型拉取、批量检测与本地程序定位。"""

    def _run_bg(self, life, key, worker_fn, on_done):
        prev_after = self._bg_polls.pop(key, None)
        if prev_after is not None:
            try:
                self.win.after_cancel(prev_after)
            except tk.TclError:
                pass
        ticket = life.submit(object(), label=key)
        box = self.Queue()

        def run():
            try:
                box.put((True, worker_fn()))
            except Exception as exc:
                box.put((False, exc))

        def poll():
            self._bg_polls.pop(key, None)
            if not life.accepts(ticket) or not self.win.winfo_exists():
                return
            try:
                ok, payload = box.get_nowait()
            except self.Empty:
                self._bg_polls[key] = self.win.after(40, poll)
                return
            life.finish(ticket, succeeded=ok, error='' if ok else str(payload))
            on_done(ok, payload)

        self.Thread(target=run, daemon=True).start()
        self._bg_polls[key] = self.win.after(40, poll)

    def _breakdown_from_badge(self, parent_item, route, badge, index):
        probe = (badge or {}).get('probe') or {}
        if not probe.get('checks'):
            return (badge or {}).get('detail') or '点击右上角「测试」可查看五维诊断详情。'
        flat = model_routes.route_as_record(parent_item, route, model_id=self.state['id'], index=index)
        return self._probe_breakdown(probe, flat)

    def probe_route_card(self, card):
        parent = self.read_form()
        route = card.to_dict()
        if not route.get('model') and not parent.get('model'):
            self._report_error('请先填写模型 ID 再测试。')
            return None
        typed = card.typed_key()
        model_id, idx = self.state['id'], card.index
        card.set_testing(True)
        self.hint.set('正在测试「%s」连通性…' % (route.get('name') or route.get('provider') or f'路线 {idx + 1}'))
        transport = self._transport()

        def work():
            return model_routes.probe_route(
                parent, route, model_id=model_id, index=idx, transport=transport,
                program=self.program, options={'override_key': typed, 'persist': bool(model_id and not typed)})

        def done(ok, payload):
            if not card.winfo_exists():
                return
            card.set_testing(False)
            if not ok:
                self._report_error('测试失败：' + str(payload))
                return
            res = payload
            flat = model_routes.route_as_record(parent, route, model_id=model_id, index=idx)
            badge = ({'state': 'ok', 'label': f"已测通 · {int(res.get('ms') or 0)}ms",
                      'short': f"{int(res.get('ms') or 0)}ms", 'probe': res}
                     if res.get('ok') else
                     {'state': 'error', 'label': res.get('error_short') or '连接失败',
                      'short': res.get('error_short') or '连接失败', 'probe': res})
            card.set_badge(badge, breakdown_text=self._probe_breakdown(res, flat))
            if model_id and not typed:
                self._probe_cache = model_routes.all_probe_status(program=self.program)
                self._refresh_single_left_badge(model_id)
            msg = ('连接成功，延迟 %d ms%s' % (int(res.get('ms') or 0),
                   '（新密钥测通后请点保存）' if typed else '')
                   if res.get('ok') else f"测试未通过：{badge['label']}")
            self.hint.set(msg)

        self._run_bg(self.probe_life, f'probe:{card.route_id}', work, done)
        return card

    def verify_route_card(self, card):
        parent, route = self.read_form(), card.to_dict()
        model_id, idx, typed = self.state['id'], card.index, card.typed_key()
        self.hint.set('正在运行小样本完整验证…')
        transport = self._transport()

        def work():
            return model_routes.verify_route(
                parent, route, model_id=model_id, index=idx, transport=transport,
                program=self.program, options={'override_key': typed})

        def done(ok, payload):
            if not card.winfo_exists():
                return
            if not ok:
                self._report_error('小样本验证异常：' + str(payload))
                return
            res = payload
            flat = model_routes.route_as_record(parent, route, model_id=model_id, index=idx)
            if res.get('checks'):
                card.detail_text_var.set(self._probe_breakdown(res, flat))
            verdict = '通过' if res.get('ok') else '未通过'
            tail = res.get('error') or ('正文 %s 字' % res.get('content_length'))
            self.hint.set(f'小样本完整验证{verdict} · {tail}')

        self._run_bg(self.probe_life, f'verify:{card.route_id}', work, done)

    def fetch_models_for_card(self, card):
        route, parent = card.to_dict(), self.read_form()
        api_key = card.typed_key() or model_routes.route_key_of(
            parent, route, program=self.program, model_id=self.state['id'], index=card.index)
        card.set_fetching(True)
        self.hint.set('正在从远端拉取可用模型列表…')
        transport = self._transport()

        def work():
            return model_routes.fetch_remote_models(
                route.get('base_url', ''), api_key=api_key,
                wire_api=route.get('wire_api', 'chat'), transport=transport)

        def done(ok, payload):
            if not card.winfo_exists():
                return
            card.set_fetching(False)
            if not ok:
                self._report_error('拉取失败：' + str(payload))
                return
            if not payload.get('ok'):
                self._report_error(payload.get('error') or '无法拉取模型列表')
                return
            self.hint.set('已拉取 %d 个远端模型，请选择。' % len(payload['models']))
            def pick(chosen):
                if card.winfo_exists():
                    set_input_value(card.model_entry, chosen)
                    self._on_route_model_edited(card)
                    self._mark_dirty()
            open_remote_model_picker(self.win, payload['models'], pick)

        self._run_bg(self.fetch_life, f'fetch:{card.route_id}', work, done)

    def probe_all_visible(self):
        records = self._records_cache if self._records_cache is not None else self.pet.agent_model_records()
        ids = list(self.card_list.item_ids())
        if not ids:
            self.hint.set('当前列表没有可检测的模型。')
            return
        if self.desktop_mode():
            self.load_rows(refresh=True)
            self.hint.set('已刷新 %d 个本机程序的状态。' % len(ids))
            return
        targets = [(mid, records[mid]) for mid in ids if mid in records]
        transport = self._transport()
        self.batch_button.configure(text='检测中…')
        self.batch_button.state(['disabled'])
        self.hint.set('正在后台检测 %d 个模型的 API 路线…' % len(targets))

        def work():
            ok_count = 0
            for mid, item in targets:
                for idx, route in enumerate(model_routes.routes_of(item, model_id=mid)):
                    ready, _why = model_routes.route_status(item, route, program=self.program,
                                                            model_id=mid, index=idx)
                    if not ready:
                        continue
                    res = model_routes.probe_route(
                        item, route, model_id=mid, index=idx, transport=transport,
                        program=self.program, options={'persist': True})
                    if res.get('ok'):
                        ok_count += 1
            return ok_count

        def done(ok, payload):
            if not self.win.winfo_exists():
                return
            self.batch_button.configure(text='检测全部')
            self.batch_button.state(['!disabled'])
            if not ok:
                self._report_error('批量检测异常：' + str(payload))
                return
            self._probe_cache = model_routes.all_probe_status(program=self.program)
            self.load_rows(refresh=False)
            self.hint.set('检测完成：%d 条路线已测通，左侧状态已更新。' % int(payload or 0))

        self._run_bg(self.batch_life, 'probe_all', work, done)

    def _refresh_single_left_badge(self, model_id):
        records = self._records_cache or {}
        item = records.get(model_id)
        if item:
            badge = model_routes.model_badge(model_id, item, program=self.program, probe_map=self._probe_cache)
            self.card_list.update_badge(model_id, badge)

    def probe_local_one(self):
        return self._probe_local(self.read_form())

    def fill_label(self, _event=None):
        current = self.entries['label'].get().strip()
        if current and current != self.auto_label['text']:
            return None
        guess = model_pool.suggest_label(self.entries['model'].get())
        set_input_value(self.entries['label'], guess)
        self.auto_label['text'] = guess
        return guess

    def stop_search(self):
        self.search.cancel()
        if self.search_poll['after'] is not None:
            try:
                self.win.after_cancel(self.search_poll['after'])
            except tk.TclError:
                pass
            self.search_poll['after'] = None
        self.search_busy.set_busy(False)
        try:
            if self.search_button.winfo_exists():
                self.search_button.configure(text='自动搜寻')
        except tk.TclError:
            pass

    def _cancel_pending_detect(self):
        if self.pending['after'] is not None:
            try:
                self.win.after_cancel(self.pending['after'])
            except tk.TclError:
                pass
            self.pending['after'] = None

    def _schedule_delayed_detect(self):
        self._cancel_pending_detect()
        self.pending['after'] = self.win.after(450, self.delayed_detect)

    def delayed_detect(self):
        self.pending['after'] = None
        self.detect_program()

    def browse_program(self):
        self.stop_search()
        path = FileDialog(self.win).open_file(title='选择应用可执行文件', filetypes=[('程序', '*.exe')])
        if path:
            set_input_value(self.program_entry, path)
            prepend_dropdown_value(self.program_entry, path)
            self._mark_dirty()

    def detect_program(self, _event=None, quiet=True):
        if not self.desktop_mode() or (quiet and self.program_entry.get().strip()):
            return None
        from orchestrator.workflow_settings import find_model_program
        model = self.entries['model'].get().strip()
        if not model:
            self._report_error('请先填写程序名，再自动搜寻安装路径。')
            return None
        self._cancel_pending_detect()
        self.stop_search()
        ticket = self.search.submit(object(), label='安装路径搜寻')
        call_mode, original_path = self.mode.get(), self.program_entry.get()
        results = self.Queue()
        self.hint.set('正在搜寻「%s」：检查注册表、商店安装记录和常见安装目录…' % model)
        self.search_button.configure(text='正在搜寻…')
        self.search_busy.set_busy(True, controls=(self.search_button,))

        def worker():
            try:
                results.put((find_model_program(model, call_mode), ''))
            except Exception as exc:
                results.put(('', str(exc)))

        def poll():
            self.search_poll['after'] = None
            if not self.search.accepts(ticket) or not self.win.winfo_exists():
                return
            try:
                path, error = results.get_nowait()
            except self.Empty:
                self.search_poll['after'] = self.win.after(50, poll)
                return
            self.search.finish(ticket, succeeded=bool(path), error=error)
            self.search_busy.set_busy(False)
            self.search_button.configure(text='自动搜寻')
            self._apply_search(path, error, original_path)

        self.Thread(target=worker, daemon=True).start()
        self.search_poll['after'] = self.win.after(50, poll)

    def changed_identity(self, *_args):
        if self.pending['loading']:
            return
        self.stop_search()
        self._cancel_pending_detect()
        if self.mode.get() == SPEECH_MODE:
            return
        set_input_value(self.program_entry, '')
        self.editor_title_var.set(self.entries['label'].get().strip() or ('新建 %s 模型' % self.mode.get()))
        self.hint.set('正在编辑 %s 配置。' % self.mode.get())
        self.refresh_connection_fields()
        if self.desktop_mode() and self.entries['model'].get().strip():
            self._schedule_delayed_detect()

    def _cleanup_resources(self):
        self.stop_search()
        self._cancel_pending_detect()
        for life in (self.probe_life, self.batch_life, self.fetch_life):
            life.cancel()
        for after_id in list(self._bg_polls.values()):
            try:
                self.win.after_cancel(after_id)
            except tk.TclError:
                pass
        self._bg_polls.clear()
        freezer = getattr(self, '_rows_paint_freeze', None)
        if freezer is not None:
            freezer.thaw()
        if self._speech_panel is not None:
            self._speech_panel['destroy_cleanup']()

    def _on_destroy(self, event):
        if event.widget in (self._root_frame, self.win):
            self._cleanup_resources()

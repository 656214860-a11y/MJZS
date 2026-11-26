# -*- coding: utf-8 -*-
"""模型管理窗口的调用方式分段 + 模态（功能）分类 + 表单脏检查 + 5 项主流预设表（R2399 / UX-SETTINGS-MODELS）。

按调用方式（API／Desktop／CLI／语音识别）分段：前三种按当前调用方式过滤列表并按
「功能 → Provider」分组排序，「语音识别」原地展示语音识别与词典配置。
下方全部非密钥输入框采用可编辑 SelectBox，按调用方式与模态提供 5 个市场主流预设。
"""
from tkinter import ttk
from ui_widgets import LineInput, SecondaryButton
from ui_tokens import COMBOBOX_PADDING, FONTS, FORM_LABEL_WIDTH, INPUT_PADDING_X, SPACING
import infra.model_pool as model_pool

SPEECH_MODE = '语音识别'
MODES = ('API', 'Desktop', 'CLI', SPEECH_MODE)  # 左上角分段切换顺序
FORM_FIELDS = (('label', '显示名'), ('model', '模型 ID'), ('base_url', 'API 根地址'),
               ('key_env', '密钥环境变量'))
OPTIONAL_FORM_KEYS = ('context_length', 'rpm', 'group', 'weight', 'note',
                      'max_output', 'temperature', 'timeout', 'retries')
FORM_DEFAULT_PROVIDER = model_pool.PROVIDER_LABELS['custom']  # 新建默认「自定义」
# UX-MODEL-PAGE：模型管理页「新建一条」时编辑区的预填默认（DES《05》§15.3，均标「可改」）。
# 只新增默认值，不改存量字段语义；已存记录没有这些字段时不回填（record 对缺省字段保持空串）。
DEFAULT_CONTEXT_LENGTH = 262144          # 上下文窗口 256K＝256×1024
NEW_MODEL_DEFAULTS = {'context_length': DEFAULT_CONTEXT_LENGTH,
                      'max_output': 8192,          # 最大输出 tokens（本项目设计选择）
                      'temperature': 0.7,          # 温度（本项目设计选择）
                      'timeout': 120,              # 请求超时秒（本项目设计选择）
                      'retries': 2}                # 失败重试次数（本项目设计选择）

# UX-SETTINGS-MODELS：每个非密钥表单字段默认提供 5 个市场主流选项（不编造假 URL 或假密钥）。
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
    'base_url': (
        'https://api.deepseek.com',
        'https://api.openai.com/v1',
        'https://api.anthropic.com',
        'https://dashscope.aliyuncs.com/compatible-mode/v1',
        'https://generativelanguage.googleapis.com/v1beta/openai',
    ),
    'key_env': ('DEEPSEEK_API_KEY', 'OPENAI_API_KEY', 'ANTHROPIC_API_KEY', 'DASHSCOPE_API_KEY', 'GEMINI_API_KEY'),
    'context_length': ('32768', '65536', '131072', '262144', '1048576'),
    'note': ('主力文本创作', '快速草稿与大纲', '复杂推理与审校', '视觉分镜与出图', '备用兜底线路'),
    'rpm': ('10', '30', '60', '120', '300'),
    'group': ('default', 'fast', 'reasoning', 'creative', 'fallback'),
    'weight': ('1', '2', '3', '5', '10'),
    'max_output': ('4096', '8192', '16384', '32768', '65536'),
    'temperature': ('0.0', '0.3', '0.7', '1.0', '1.2'),
    'timeout': ('30', '60', '120', '180', '300'),
    'retries': ('0', '1', '2', '3', '5'),
}


def provider_choices():
    """下拉不含「OpenAI 兼容接口」，含 5 大主流厂商＋「自定义」，按 casefold 去重并排序。"""
    builtins = [label for value, label in model_pool.PROVIDERS if value != model_pool.DEFAULT_PROVIDER]
    seen = {item.casefold() for item in builtins}
    merged = list(builtins)
    for preset in PROVIDER_PRESETS:
        if preset.casefold() not in seen:
            seen.add(preset.casefold())
            merged.append(preset)
    return sorted(merged, key=str.casefold)


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


def populate_form_entries(manager, model_id, item):
    """把一条模型记录回填到表单控件，供 _ModelManager.fill 调用以控制主文件长度。"""
    manager.state['id'] = model_id
    manager.mode.set(model_pool.call_mode(item, model_id))
    manager.key_entry.delete(0, 'end')          # 只写不读：界面里从不回显整把密钥
    for key, _label in FORM_FIELDS:
        manager.entries[key].delete(0, 'end')
        manager.entries[key].insert(0, str(item.get(key) or ''))
    for key in OPTIONAL_FORM_KEYS:
        manager.entries[key].delete(0, 'end')
        if item.get(key):
            manager.entries[key].insert(0, str(item[key]))
    for tag, var in manager.caps.items():
        var.set(tag in (item.get('capabilities') or []))
    saved_provider = str(item.get('provider') or '').strip()
    if item.get('provider_label') or (saved_provider == 'desktop' and model_pool.desktop_engine(model_id)):
        vendor = model_pool.provider_name(model_id, item)
        manager.provider.set(model_pool.PROVIDER_LABELS.get(vendor.casefold(), vendor))
    else:
        manager.provider.set(model_pool.PROVIDER_LABELS.get(
            saved_provider, saved_provider or FORM_DEFAULT_PROVIDER))
    manager.wire.set(model_pool.WIRE_LABELS.get(item.get('wire_api'), model_pool.WIRE_LABELS[model_pool.DEFAULT_WIRE]))
    manager.modality.set(model_pool.MODALITY_LABELS.get(item.get('modality'), model_pool.MODALITY_LABELS[model_pool.DEFAULT_MODALITY]))
    manager.program_entry.delete(0, 'end')
    manager.program_entry.insert(0, item.get('program') or '')
    return saved_provider


def read_form_values(manager):
    """读取当前表单为模型记录输入字典。"""
    local = manager.desktop_mode()
    value = {key: manager.entries[key].get().strip() for key, _label in FORM_FIELDS}
    value['provider'] = 'desktop' if local else model_pool.id_of_label(manager.provider.get(), model_pool.PROVIDERS)
    value['provider_label'] = manager.provider.get().strip() if local else ''
    value['call_mode'] = manager.mode.get()
    value['wire_api'] = model_pool.id_of_label(manager.wire.get(), model_pool.WIRE_APIS)
    value['capabilities'] = [tag for tag, var in manager.caps.items() if var.get()]
    for key in OPTIONAL_FORM_KEYS:
        value[key] = manager.entries[key].get().strip()
    value['program'] = manager.program_entry.get().strip()
    value['modality'] = model_pool.id_of_label(manager.modality.get(), model_pool.MODALITIES)
    return value


def merge_provider_choices(builtins, records):
    """合并内建主流厂商与模型池内已保存厂商，按 casefold 去重并排序。"""
    saved = {model_pool.provider_name(model_id, item) for model_id, item in records.items()}
    seen = {label.casefold() for label in builtins}
    extra = []
    for item in sorted((item for item in saved if item), key=str.casefold):
        if item.casefold() not in seen:
            seen.add(item.casefold())
            extra.append(item)
    return sorted([*builtins, *extra], key=str.casefold)


def attach_manager_seams(manager, target):
    """把模型管理自检接缝挂到独立弹窗宿主对象上。"""
    target._pet_detect_program = manager.detect_program
    target._pet_read_form = manager.read_form
    target._pet_provider_box = manager.provider_box
    target._pet_tree = manager.tree
    target._pet_delete_one = manager.delete_one
    target._pet_labels = manager.labels
    target._pet_key_entry = manager.key_entry
    target._pet_save_key = manager.local_save
    target._pet_save_typed = manager.save_typed_key
    target._pet_clear_key = manager.local_clear
    target._pet_key_state = manager.key_state.get
    target._pet_api_controls = manager.api_controls
    target._pet_program_row = manager.program_row
    target._pet_reload = manager.load_rows
    target._pet_hint = manager.hint
    target._pet_manager_hint_label = manager._manager_hint
    target._pet_entries = manager.entries
    target._pet_provider = manager.provider
    target._pet_mode = manager.mode
    target._pet_modality_box = manager.modality_box
    target._pet_mode_control = manager.mode_tabs
    target._pet_mode_buttons = manager.mode_tabs.buttons


def build_embedded_seam(manager):
    """构造设置窗内嵌「模型配置」页返回给 pet_settings_ui 的接缝字典。"""
    return {
        'manager': manager, 'hint': manager.hint, 'entries': manager.entries,
        'provider': manager.provider, 'provider_box': manager.provider_box,
        'mode': manager.mode, 'mode_control': manager.mode_tabs,
        'mode_buttons': manager.mode_tabs.buttons, 'modality_box': manager.modality_box,
        'tree': manager.tree, 'key_entry': manager.key_entry, 'reload': manager.load_rows,
        'save': manager.save_current, 'is_dirty': manager.is_dirty,
        'confirm_leave': manager.leave_page, 'destroy_cleanup': manager._cleanup_resources,
        'scroll': manager._embed_scroll,
    }


def list_status(record, program):
    """模型列表「状态」那一格：用得了只写「可用」（模型 ID 已有自己一列），用不了写缺什么。"""
    ok, why = model_pool.status(record, program)
    return '可用' if ok else why


class ModelManagerModeTabsMixin:
    """调用方式分段 + 模态分类 + 语音识别原地视图切换；宿主 _ModelManager 提供 UI 容器属性。"""

    def _on_tab_changed(self, _event=None):
        """分段点击：把调用方式同步过去（换段即切换 API／Desktop／CLI／语音识别）。"""
        current = self.mode_tabs.current()
        if current != self.mode.get():
            self.mode.set(current)
        return True

    def _on_mode_change(self, *_args):
        """调用方式变了：同步分段、切换模型/语音视图、刷新 5 项下拉预设并重刷列表。"""
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
        if not self.pending['loading']:   # fill 回填期间只同步分段，不重建列表
            self.load_rows(refresh=False)   # 只换过滤条件，模型池内容不因切页重新读盘

    def _sync_mode_view(self):
        """切到「语音识别」时隐藏模型区并原地显示语音面板；切回时恢复模型区。"""
        speech_active = self.mode.get() == SPEECH_MODE
        if speech_active == self._speech_visible:
            return
        self._speech_visible = speech_active
        if speech_active:
            self._ensure_speech_panel()
            self.models_container.pack_forget()
            self.model_actions_bar.pack_forget()
            self.speech_container.pack(fill='both', expand=True)
        else:
            self.speech_container.pack_forget()
            self.models_container.pack(fill='both', expand=True)
            self.model_actions_bar.pack(side='top', fill='x')

    def _refresh_field_presets(self, *_args):
        """按当前调用方式与模态刷新 model / label / program 的 5 项主流下拉候选。"""
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

    def _render_mode_rows(self, records):
        """按当前调用方式过滤并插入列表行；只显示本调用方式的模型，按「功能 → Provider」分组。"""
        current = self.mode.get()
        if current == SPEECH_MODE:
            return
        self.tree.delete(*self.tree.get_children())
        rows = sorted(((model_pool.MODALITY_LABELS.get(item.get('modality'), '文本'),
                        model_pool.provider_name(model_id, item), model_id, item)
                       for model_id, item in records.items()
                       if model_pool.call_mode(item, model_id) == current),
                      key=lambda r: (r[0], r[1].casefold(), str(r[3].get('label') or '').casefold(), r[2]),
                      reverse=self.provider_descending)
        last = None
        for modality, name, model_id, item in rows:
            # 同一功能内同一 Provider 只在分组第一行写名字，后面留空，读起来像合并单元格。
            shown, last = ('' if (modality, name) == last else name), (modality, name)
            self.tree.insert('', 'end', iid=model_id,
                             values=(modality, shown, model_pool.call_mode(item, model_id), item['model'], item['label'],
                                     model_pool.capability_text(item['capabilities']),
                                     list_status(item, self.program)))
        self.table_shell.refresh_empty_state()


class ModelManagerFormGuardMixin:
    """DES《05》§15.2：模型管理表单（含内嵌语音识别页）的「未保存改动」守卫。"""

    def _bind_dirty_marks(self):
        """未保存改动只认真实键入／下拉／勾选；fill/new_one 这类程序化回填不算。"""
        for entry in self.entries.values():
            entry.bind('<KeyRelease>', self._mark_dirty, add='+')
            entry.bind('<<ComboboxSelected>>', self._mark_dirty, add='+')
        for box in (self.provider_box, self.modality_box, self.wire_box):
            box.bind('<<ComboboxSelected>>', self._mark_dirty, add='+')

    def _mark_dirty(self, *_args):
        """真实键入／下拉／勾选才算未保存改动；程序化回填不触发这些事件。"""
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
        """有未保存改动时先确认；干净表单直接放行。"""
        dirty = self._active_dirty() if active_only else self.is_dirty()
        if not dirty:
            return True
        return bool(self.pet.confirm_start('放弃未保存的改动',
                                           '有未保存的改动，%s后不保留。继续吗？' % action))

    def leave_page(self, action='切换页面'):
        """设置窗切离「模型配置」页时确认丢弃；确认后清空脏态。"""
        if not self._confirm_discard(action):
            return False
        self._dirty = False
        if self._speech_panel is not None and self._speech_panel['is_dirty']():
            self._speech_panel['reload']()
        return True

    def _restore_selection(self):
        """确认被拒：把列表高亮拉回正在编辑的那一条（新建态则清掉高亮）。"""
        self._selecting = True
        try:
            current = self.state['id']
            if current and self.tree.exists(current):
                self.tree.selection_set(current)
            else:
                for iid in self.tree.selection():
                    self.tree.selection_remove(iid)
        finally:
            self._selecting = False

    def on_select(self, event=None):
        if self._selecting:
            return None
        picked = self.tree.selection()
        if not picked:
            return None
        if str(picked[0]) != str(self.state['id']) and not self._confirm_discard('切换编辑对象', active_only=True):
            self._restore_selection()
            return None
        records = getattr(self, '_records_cache', None)
        if records is None:
            records = self._records_cache = self.pet.agent_model_records()
        item = records.get(picked[0]) or {}
        self.fill(picked[0], item)
        self.hint.set('正在改「%s」；改完点「保存这条」。' % (item.get('label') or picked[0]))
        return item

    def _on_tab_changed(self, _event=None):
        """DES《05》§15.2：有未保存改动时切调用方式分段也要确认；拒绝则分段弹回原位。"""
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
        if not _confirmed and not self._confirm_discard('新建一条', active_only=True):
            return None
        self.pending['loading'] = True
        self.state['id'] = ''
        for key, _label in FORM_FIELDS:
            self.entries[key].delete(0, 'end')
        for key in (*OPTIONAL_FORM_KEYS, 'program'):
            self.entries[key].delete(0, 'end')
        # DES《05》§15.3：新建预填主流默认（NEW_MODEL_DEFAULTS，均可改）。
        for key, value in NEW_MODEL_DEFAULTS.items():
            self.entries[key].insert(0, str(value))
        for var in self.caps.values():
            var.set(False)
        self.key_entry.delete(0, 'end')
        self.show_key_state()
        self.provider.set(FORM_DEFAULT_PROVIDER)
        self.wire.set(model_pool.WIRE_LABELS[model_pool.DEFAULT_WIRE])
        self.modality.set(model_pool.MODALITY_LABELS[model_pool.DEFAULT_MODALITY])
        self.pending['loading'] = False
        self.auto_label['text'] = ''
        self._refresh_field_presets()
        self.changed_identity()
        self._dirty = False
        self.hint.set('新建 %s 模型：填写模型 ID；本地调用会自动搜寻对应程序。' % self.mode.get())
        return self.state

    def save_current(self):
        """底行「保存」：在「语音识别」段保存语音设置，在模型段保存当前模型。"""
        if self.mode.get() == SPEECH_MODE:
            return self._ensure_speech_panel()['save']()
        return self.save_one()

    def cancel(self, *_args):
        """「取消」／Esc／窗口 X：有未保存改动先确认，拒绝则留在页内。"""
        if not self._confirm_discard('关闭窗口'):
            return None
        self._cleanup_resources()
        self.win.destroy()
        return True

    def save_and_close(self):
        """底行「保存」：写入并关闭；失败留在页内（原因已由 save_one/语音面板写进提示）。"""
        if self.save_current():
            self._cleanup_resources()
            self.win.destroy()

    def desktop_mode(self):
        return self.mode.get() in ('Desktop', 'CLI')

    def match_wire(self, event=None):
        """换了 Provider，「协议」栏自动摆到它默认的那一档（只挂选中，不挂失焦）。"""
        if self.desktop_mode():
            return None
        value = model_pool.wire_for_provider(
            model_pool.id_of_label(self.provider.get(), model_pool.PROVIDERS))
        self.wire.set(model_pool.WIRE_LABELS.get(value, model_pool.WIRE_LABELS[model_pool.DEFAULT_WIRE]))

    def flip_provider_order(self):
        """点 Provider 列头：分组顺序正反翻转（同组内仍按显示名、模型 ID 排）。"""
        self.provider_descending = not self.provider_descending
        self.load_rows(refresh=False)

    def show_key_state(self, value=None):
        """本机加密那份现在什么情况：只报前 4 位 ＋ ****，别把整把钥匙摆到界面上。"""
        item = value if isinstance(value, dict) else self.read_form()
        local = model_pool.local_key_of(item, self.program, self.state['id'])
        self.key_state.set(('本机已存：%s（不落明文）' % model_pool.redacted(local)) if local
                           else '未存本机密钥')
        return local

    def local_clear(self):
        """删掉本机加密那份密钥。"""
        if not model_pool.clear_local_key(self.read_form(), self.program, self.state['id']):
            self.hint.set('本机本来就没存这一条。')
            return False
        self.show_key_state()
        self.hint.set('已删掉本机加密的那份密钥。')
        return True

    def fill(self, model_id, item):
        self.stop_search()
        self.pending['loading'] = True
        if self.pending['after'] is not None:
            self.win.after_cancel(self.pending['after'])
            self.pending['after'] = None
        saved_provider = populate_form_entries(self, model_id, item)
        self.pending['loading'] = False
        self.auto_label['text'] = self.entries['label'].get().strip()
        self._refresh_field_presets()
        self.refresh_connection_fields()
        if saved_provider != 'desktop':
            self.show_key_state(item)
        self._dirty = False

    def read_form(self):
        return read_form_values(self)


MODE_SEGMENT_STYLE = 'RailIcon.TButton'
MODE_SEGMENT_SELECTED_STYLE = 'Selected.RailIcon.TButton'


class ModeSegmentedControl(ttk.Frame):
    """调用方式分段切换：小型胶囊按钮，鼠标、方向键、空格与回车都能切。"""

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
        """选中一段；用户触发时先走宿主的脏表单守卫，被拒绝就回到原段。"""
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


# 模型管理表单用紧凑输入框：纵向内边距归零，行高约为常规输入框一半，空出高度给模型列表。
COMPACT_PREFIX = 'Compact.'
COMPACT_COMBOBOX_STYLE = COMPACT_PREFIX + 'Tokens.Combobox.TCombobox'
# 下拉框纵向内边距：零内边距时框高约 19px，上下各 3px 后约 25px，高出三分之一。
COMPACT_COMBOBOX_PAD_Y = SPACING['xs'] - SPACING['xs'] // 4


class CompactLineInput(LineInput):
    NORMAL_STYLE = COMPACT_PREFIX + LineInput.NORMAL_STYLE
    PLACEHOLDER_STYLE = COMPACT_PREFIX + LineInput.PLACEHOLDER_STYLE
    ERROR_STYLE = COMPACT_PREFIX + LineInput.ERROR_STYLE


def install_compact_form_styles(widget):
    """派生样式只改 padding，其余颜色、边框与状态映射沿用父样式。"""
    style = ttk.Style(widget)
    for name in (CompactLineInput.NORMAL_STYLE, CompactLineInput.PLACEHOLDER_STYLE, CompactLineInput.ERROR_STYLE):
        style.configure(name, padding=(INPUT_PADDING_X, SPACING['none']))
    style.configure(COMPACT_COMBOBOX_STYLE, padding=(COMBOBOX_PADDING[0], COMPACT_COMBOBOX_PAD_Y))

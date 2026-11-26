# -*- coding: utf-8 -*-
import inspect
import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk
import infra.model_pool as model_pool
import infra.model_routes as model_routes
from ui.pet_models_tabs import (FORM_DEFAULT_PROVIDER, FORM_FIELDS, MODES, MODALITY_FILTERS,
                                NEW_MODEL_DEFAULTS, SPEECH_MODE, MODE_SEGMENT_STYLE,
                                MODE_SEGMENT_SELECTED_STYLE, ModeSegmentedControl,
                                CompactLineInput, EditablePresetBox, COMPACT_COMBOBOX_STYLE,
                                COMPACT_COMBOBOX_PAD_Y, attach_manager_seams, build_embedded_seam,
                                field_presets, form_column_width, install_compact_form_styles,
                                merge_provider_choices, prepend_dropdown_value, provider_choices,
                                ModelManagerActionsMixin, ModelManagerFormGuardMixin,
                                ModelManagerModeTabsMixin, ModelManagerRoutesMixin)
from ui.pet_models_cards import CollapsibleSection, ModelCardList, set_input_value
from responsive_ui import ScrollForm, auto_height
from ui.desktop_layout_resize import PaintFreeze
from ui_tokens import (BUTTON_GAP, BUTTON_GAP_TIGHT, CHAR_WIDTH, COLORS, COMBOBOX_PADDING, TEXT_ROWS,
                       FONTS, FORM_LABEL_WIDTH, INPUT_PADDING_X, SPACING, TEXT_DESC, TEXT_HINT, OVERLAY_RATIO)
from ui.ui_dialogs import FileDialog
from account_inputs import PasswordInput
from ui_widgets import (BusyState, NotificationDispatcher, SelectBox, BaseDialog, Card, DataTable,
                        LineInput, PrimaryButton, SecondaryButton)
TITLE = '三虎 · 设置'
SETTINGS_TITLE = '三虎模型配置'          # 第 46 期第 6 条：这一页与它的独立窗口都叫这个名字
MANAGER_BUTTON = '模型配置'              # 用户要求：原「API 统一配置」改名为「模型配置」，仍打开模型管理
MANAGER_TITLE = '模型管理'
SETTINGS_GEOMETRY = '700x430'
SETTINGS_MIN = (620, 430)
def report_error(hint, message):
    """可恢复错误只写非模态提示（`NotificationDispatcher.error` 默认 modal=False）。

    模型检测、保存失败等失败不应弹模态框锁住整扇窗；破坏性删除仍走宿主确认。
    """
    return NotificationDispatcher(hint).error(str(message))


def model_options(records, with_auto=True):
    """模型设置页展示候选；桌面 Agent 状态只在此按需查询一次。"""
    import orchestrator.workflow_settings as workflow_settings
    return model_pool.options(records, with_auto=with_auto,
                              labeler=workflow_settings.desktop_model_label)
# REQ-UI-MODEL-PAGE-2：左右主从分栏＋右栏独立滚动，独立弹窗 1180×820，内嵌模式自适应设置窗右栏。
MANAGER_GEOMETRY = '1180x820'
MANAGER_MIN = (820, 620)
LEFT_PANE_WIDTH = 320
LEFT_PANE_EMBED_WIDTH = 240
NOTE_ABOUT = '三虎用于决策、对话、路由；子模块执行模型在阶段配置里选。'
MODEL_FIELD_LOCAL, MODEL_FIELD_API = '程序名', '模型 ID'
NOTE_MANAGER = '左侧查看可用状态，右侧自上而下配置模型与多条 API 路线。'
COLUMNS = (('modality', '功能', 60), ('provider', 'Provider', 90), ('call_mode', '调用方式', 70),
           ('model', '模型 ID', 150), ('label', '显示名', 160), ('capabilities', '能力标签', 270),
           ('state', '状态', 200))
TASK_FIELD_LABELS = tuple(label for _key, label, _note in model_pool.TASK_FIELDS)
MANAGER_FORM_LABELS = ('Provider', '模型 ID', '显示名', '功能', 'API 根地址',
                       '密钥环境变量', '直接输入密钥', '协议', '能力标签',
                       '上下文长度（可选）', '每分钟请求上限（可选）', '模型组（可选）',
                       '权重（可选）', '备注（可选）', '最大输出', '温度', '超时（秒）', '重试次数',
                       '应用安装路径', '命令行程序路径')
SECRET_FIELD_WIDTH = CHAR_WIDTH['3xl']
FORM_RIGHT_LABEL_PAD = (SPACING['lg'], SPACING['xs'])


def parent_of(pet):
    return getattr(pet, 'win', None)


def main_box(parent):
    """主界面的位置与大小；量不出来（自检里窗口还没摆开）返回 None。"""
    if parent is None:
        return None
    try:
        width, height = parent.winfo_width(), parent.winfo_height()
        if width <= 1 or height <= 1:
            parent.update_idletasks()
            width, height = parent.winfo_width(), parent.winfo_height()
        if width <= 1 or height <= 1:
            return None
        return parent.winfo_rootx(), parent.winfo_rooty(), width, height
    except Exception:
        return None


def fit_to_main(win, parent, geometry, ratio=OVERLAY_RATIO, floor=MANAGER_MIN, cap=None):
    """把这扇窗摆成「主界面的固定比例、落在主界面正中、永不超出主界面」。"""
    try:
        back_w, back_h = (int(value) for value in str(geometry).split('x'))
    except (TypeError, ValueError):
        return geometry
    box = main_box(parent)
    if box is None:
        win.geometry(geometry)
        return geometry
    left, top, parent_width, parent_height = box
    cap_width = parent_width if cap is None else min(parent_width, cap[0])
    cap_height = parent_height if cap is None else min(parent_height, cap[1])
    width = min(cap_width, max(int(parent_width * ratio), min(floor[0], parent_width)))
    height = min(cap_height, max(int(parent_height * ratio), min(floor[1], parent_height)))
    x = max(0, left + (parent_width - width) // 2)
    y = max(0, top + (parent_height - height) // 2)
    win.geometry('%dx%d+%d+%d' % (width, height, x, y))
    return win.geometry()


def program_of(pet):
    return getattr(pet, 'program', model_pool.PROGRAM)


def transport_of(pet):
    return getattr(pet, 'probe_transport', None)


def window(pet, title, geometry, minsize=None):
    """一扇小窗：transient 挂在三虎的窗口上，Escape 关掉。"""
    parent = parent_of(pet)
    win = BaseDialog(parent, '', modal=False, chrome=False)
    win.title(title)
    win.geometry(geometry)
    if minsize:
        win.minsize(*minsize)
    win.transient(parent or None)
    win.bind('<Escape>', lambda event: win.destroy())
    body = Card(win)
    body.pack(fill='both', expand=True, padx=SPACING['md'], pady=SPACING['md'])
    return win, body


def heading(body, title, note, columns=3):
    """标题与说明同占一行（说明跟在标题右侧），把纵向空间留给下面的模型列表。"""
    row = ttk.Frame(body)
    row.grid(row=0, column=0, columnspan=columns, sticky='ew', pady=(SPACING['none'], SPACING['sm']))
    ttk.Label(row, text=title, font=FONTS['title']).pack(side='left')
    ttk.Label(row, text=note, style='Muted.TLabel', wraplength=TEXT_DESC['wraplength']).pack(
        side='left', anchor='s', padx=(SPACING['md'], SPACING['none']))
    return 1


def status_text(record, program):
    """一条记录现在的样子：可用／缺什么（与客户端真发请求时的判据同一份）。"""
    ok, why = model_pool.status(record, program)
    if not ok:
        return why
    return '可用 · %s' % record['model']


def probe_breakdown(result, record, program=None):
    """把「测试连接」拆开说明：连通／协议／模型标识／能力／完整任务，另附配置版本与最近完整任务。"""
    marks = {True: '通过', False: '异常'}
    lines = ['%s：%s%s' % (entry['label'], marks.get(entry['ok'], '未验证'),
                           (' · ' + entry['detail']) if entry.get('detail') else '')
             for entry in (result.get('checks') or [])]
    version = result.get('config_version')
    if version:
        lines.append('配置版本：' + version)
    latest = model_pool.health_of(record, program=program)
    if latest:
        stamp = latest.get('at') or '（未记时间）'
        tail = latest.get('error') or ('正文 %s 字' % latest.get('content_length'))
        lines.append('最近完整任务：%s · %s · %s'
                     % (stamp, '通过' if latest.get('ok') else '失败', tail))
    else:
        lines.append('最近完整任务：还没跑过（点「小样本完整验证」会发一次真实短请求）')
    return '\n'.join(lines)


def probe_line(record, pet):
    """测一条连接：发一次最小请求，结果翻成人话；再分项说清这趟证明了什么、没证明什么。"""
    program = program_of(pet)
    result = model_pool.probe(record, transport_of(pet), program)
    name = record.get('label') or record.get('model') or '这一条'
    if result.get('ok'):
        note = result.get('usage_note') or ''
        head = '%s：连接成功，延迟 %d ms' % (name, int(result.get('ms') or 0))
        head = head + ('（' + note + '）' if note else '')
    else:
        status = result.get('status')
        reason = result.get('error') or '没有响应'
        head = '%s：%s%s' % (name, ('HTTP %s · ' % status) if status else '', reason)
    return head + '\n' + probe_breakdown(result, record, program)


def verify_line(record, pet):
    """小样本验证：用户点名才发一次真实短请求，跑完把「最近完整任务结果」记下来。"""
    program = program_of(pet)
    outcome = model_pool.verify_sample(record, transport_of(pet), program)
    model_pool.record_health(record, outcome, program)
    name = record.get('label') or record.get('model') or '这一条'
    verdict = '通过' if outcome.get('ok') else '没通过'
    tail = outcome.get('error') or ('正文 %s 字' % outcome.get('content_length'))
    return '%s：完整任务%s · %s（配置版本 %s）' % (name, verdict, tail, outcome.get('config_version'))


def open_settings(pet):
    """「设置 → 模型配置」单独开一扇窗时走的这条路（规格里的「三虎设置 → 模型」页）。"""
    win, body = window(pet, SETTINGS_TITLE, SETTINGS_GEOMETRY, minsize=SETTINGS_MIN)
    page = settings_page(body, pet, close=win.destroy)
    win._pet_hint, win._pet_refresh = page['hint'], page['refresh']
    return win


def settings_page(parent, pet, close=None, with_manager=True, label_width=None, show_save=True):
    """构建独立或嵌入设置页的模型配置表单。"""
    program = program_of(pet)
    records = pet.agent_model_records()
    choices = {'default': model_options(records, with_auto=True),
               'plain': model_options(records, with_auto=False)}
    actions = ttk.Frame(parent)
    actions.pack(side='bottom', fill='x', pady=(SPACING['md'], SPACING['none']))
    body = ttk.Frame(parent)
    body.pack(fill='both', expand=True)
    body.columnconfigure(0, minsize=label_width or form_column_width(TASK_FIELD_LABELS))
    body.columnconfigure(1, weight=1)
    ttk.Label(body, text=NOTE_ABOUT, style='Muted.TLabel', wraplength=TEXT_DESC['wraplength']).grid(
        row=0, column=0, columnspan=2, sticky='w')
    manager_button = None
    if with_manager:
        manager_button = SecondaryButton(body, text=MANAGER_BUTTON, command=lambda: pet.open_model_manager())
        manager_button.grid(row=0, column=2, sticky='e')
    row = 1
    tasks = pet.agent_model_tasks()
    resolver = pet.resolve_agent_model
    try:
        parameters = inspect.signature(resolver).parameters
        resolver_shares_records = ('records' in parameters or any(
            parameter.kind is inspect.Parameter.VAR_KEYWORD for parameter in parameters.values()))
    except (TypeError, ValueError):
        resolver_shares_records = False

    def resolve_best(key):
        if resolver_shares_records:
            return resolver(key, records=records)
        return resolver(key)

    picked = {}
    states = {}
    hint = tk.StringVar(master=parent, value='改完点「保存」立刻生效，不用重启。')
    cert_var = tk.BooleanVar(master=parent, value=model_pool.require_certified(program))
    for key, label, note in model_pool.TASK_FIELDS:
        pairs = choices['default'] if key == 'default' else choices['plain']
        values = [text for _model_id, text in pairs]
        import orchestrator.workflow_settings as workflow_settings
        var = tk.StringVar(master=parent, value=model_pool.label_of(tasks.get(key) or model_pool.TASKS_DEFAULT[key],
                                                     records, labeler=workflow_settings.desktop_model_label))
        picked[key] = var
        ttk.Label(body, text=label).grid(row=row, column=0, sticky='w', pady=(SPACING['xs'], SPACING['none']))
        SelectBox(body, textvariable=var, values=values).grid(
            row=row, column=1, sticky='ew', pady=(SPACING['xs'], SPACING['none']))
        state = ttk.Label(body, text='', style='Muted.TLabel', wraplength=TEXT_HINT['wraplength'])
        state.grid(row=row, column=2, sticky='w', padx=(SPACING['md'], SPACING['none']), pady=(SPACING['xs'], SPACING['none']))
        states[key] = state
        row += 1
        ttk.Label(body, text=note, style='Muted.TLabel').grid(row=row, column=1, columnspan=2, sticky='w')
        row += 1
    ttk.Checkbutton(body, text='无人值守前要求五合一认证',
                    variable=cert_var).grid(row=row, column=1, columnspan=2, sticky='w',
                                            pady=(SPACING['xs'], SPACING['none']))
    row += 1
    ttk.Label(body, text='五项：连接/协议/模型/能力/完整任务', style='Muted.TLabel').grid(
        row=row, column=1, columnspan=2, sticky='w')
    row += 1

    def model_of(key):
        pairs = choices['default'] if key == 'default' else choices['plain']
        return model_pool.id_of_label(picked[key].get(), pairs)

    def refresh():
        for key, _label, _note in model_pool.TASK_FIELDS:
            model_id = model_of(key)
            if model_id == model_pool.AUTO:
                best = resolve_best(key)
                states[key].config(text=('自动 · %s' % best.label) if best.ok else (
                    '自动 · %s' % best.reason))
                continue
            item = records.get(model_id) or {}
            states[key].config(text=status_text(item, program) if item else '池里没有这一条')
        return states

    def probe_all():
        seen = []
        for key, _label, _note in model_pool.TASK_FIELDS:
            model_id = model_of(key)
            names = list(records) if model_id == model_pool.AUTO else [model_id]
            for name in names:
                if name in seen or name not in records:
                    continue
                seen.append(name)
        if not seen:
            report_error(hint, '池里还没有可测的模型，先去「模型管理」加一条。')
            return []
        lines = [probe_line(records[name], pet) for name in seen]
        hint.set('\n\n'.join(lines))
        refresh()
        return lines

    def probe_sample():
        """小样本验证：只在「默认模型」这一条上发一次真实短请求，跑完记下最近完整任务。"""
        model_id = model_of('default')
        if model_id == model_pool.AUTO or model_id not in records:
            report_error(hint, '先在「默认模型」里选一条具体模型，再点「小样本验证」。')
            return None
        line = verify_line(records[model_id], pet)
        hint.set(line)
        refresh()
        return line

    def save():
        chosen = {key: model_of(key) for key, _label, _note in model_pool.TASK_FIELDS}
        try:
            pet.save_agent_models(chosen)
            model_pool.set_require_certified(cert_var.get(), program)
        except (ValueError, OSError) as exc:
            report_error(hint, exc)
            return None
        refresh()
        hint.set('已保存：默认模型＝%s（下一次调用生效）。'
                 % model_pool.label_of(chosen['default'], records))
        return chosen

    def reset():
        now = pet.agent_model_tasks()
        cert_var.set(model_pool.require_certified(program))
        for key, _label, _note in model_pool.TASK_FIELDS:
            picked[key].set(model_pool.label_of(now.get(key) or model_pool.TASKS_DEFAULT[key], records))
        refresh()
        hint.set('已按盘上的设置还原。')

    refresh()
    ttk.Label(body, textvariable=hint, style='PaleGreenHint.TLabel', wraplength=TEXT_DESC['wraplength']).grid(
        row=row, column=0, columnspan=3, sticky='w', pady=(SPACING['md'], SPACING['none']))
    row += 1
    bar = ttk.Frame(actions)
    bar.pack(fill='x')
    SecondaryButton(bar, text='测试连接', command=probe_all).pack(side='left')
    SecondaryButton(bar, text='小样本验证',
                    command=probe_sample).pack(side='left', padx=(BUTTON_GAP, SPACING['none']))
    if show_save:
        PrimaryButton(bar, text='保存', command=save).pack(side='right')
    if close is not None:
        SecondaryButton(bar, text='关闭', command=close).pack(
            side='right', padx=(SPACING['none'], BUTTON_GAP))
    SecondaryButton(bar, text='重置', command=reset).pack(
        side='right', padx=(SPACING['none'], BUTTON_GAP))
    return {'hint': hint, 'refresh': refresh, 'picked': picked, 'states': states, 'records': records,
            'choice_groups': choices, 'probe_all': probe_all, 'probe_sample': probe_sample,
            'save': save, 'reset': reset,
            'manager': manager_button}


def _derive_client_profile(path, display, mode, entries, *, probe):
    '''Adapt one executable and fill the model id when only a path was given.'''
    from infra.client_profiles import adapt_executable
    adapted = adapt_executable(path, display=display, probe=probe)
    profile = adapted.get('profile') or {}
    kind = profile.get('kind')
    switched = ''
    if kind:
        wanted = 'CLI' if kind == 'cli' else 'Desktop'
        if mode.get() != wanted:
            mode.set(wanted)
            switched = wanted
        if not entries['model'].get().strip():
            set_input_value(entries['model'], profile.get('id', ''))
    return adapted, switched


def _probe_local_model(pet, value, mode, entries, program_entry, hint):
    '''Locate and adapt a local Desktop program, filling the path back into the form.'''
    from pathlib import Path
    from orchestrator.workflow_settings import find_model_program, current_store_program
    if not value.get('program') and not value.get('model'):
        report_error(hint, '先填模型 ID，或点“浏览…”选择 .exe。')
        return None
    try:
        path = (current_store_program(value['program']) if value['program'] else
                find_model_program(value['model'], mode.get()))
        if not Path(path).is_file():
            raise ValueError('应用路径不存在')
        set_input_value(program_entry, path)
        prepend_dropdown_value(program_entry, path)
        adapted, _switched = _derive_client_profile(
            path, value.get('label') or value.get('model'), mode, entries, probe=True)
        hint.set('已找到程序：%s；%s。请点「保存」。' %
                 (path, adapted.get('reason') or '已记录程序路径'))
    except (ValueError, KeyError) as exc:
        report_error(hint, '检查程序失败：' + str(exc))
    return value


def _apply_program_search(path, error, original_path, program_entry, hint):
    """自动搜寻结束后回填路径；用户在等待期间手填过就不覆盖。"""
    if program_entry.get() != original_path:
        hint.set('搜寻已结束；保留您手动填写的安装路径。')
        return
    if not path:
        report_error(hint, '未自动找到安装路径：%s' % error)
        return
    set_input_value(program_entry, path)
    prepend_dropdown_value(program_entry, path)
    hint.set('已自动找到安装路径：%s；确认后点「保存」。' % path)


def open_manager(pet):
    """模型管理…：模型池＋多路线 API 配置的独立窗口入口（DSH 主从重构版）。"""
    return _ModelManager(pet, embedded=False).build()


def manager_page(parent, pet, *, win=None, on_dirty=None):
    """设置窗内嵌「模型配置」页：复用 DSH 主从多路线视图，不弹出独立窗口。"""
    return _ModelManager(pet, host=parent, win=win, on_dirty=on_dirty, embedded=True).build_embedded()


class _ModelManager(ModelManagerFormGuardMixin, ModelManagerModeTabsMixin,
                    ModelManagerRoutesMixin, ModelManagerActionsMixin):
    """模型管理视图（独立弹窗与设置窗内嵌共用，REQ-UI-MODEL-PAGE-2 + UX-SETTINGS-MODELS）。"""

    def __init__(self, pet, *, host=None, win=None, on_dirty=None, embedded=False):
        self.pet = pet
        self._host = host
        self._external_win = win
        self._on_dirty = on_dirty
        self._embedded = bool(embedded)
        self._dirty = False
        self._records_cache = None
        self._probe_cache = None
        self._rows_paint_freeze = None
        self._extra_providers = []
        self._bg_polls = {}
        self._auto_model_sync = ''
        self._speech_panel = None
        self._embedded_seam = None
        self._root_frame = None
        self.speech_save_button = None
        self.route_cards = []

    def build(self):
        self.program = program_of(self.pet)
        self.win, container = window(self.pet, MANAGER_TITLE, MANAGER_GEOMETRY, minsize=MANAGER_MIN)
        fit_to_main(self.win, parent_of(self.pet), MANAGER_GEOMETRY)
        self._build_workspace(container)
        self._expose_hooks()
        return self.win

    def build_embedded(self):
        self.program = program_of(self.pet)
        self.win = self._external_win or self._host.winfo_toplevel()
        self._build_workspace(self._host)
        self._embedded_seam = build_embedded_seam(self)
        self._sync_primary_hooks()
        return self._embedded_seam

    def _build_workspace(self, container):
        self._root_frame = container
        install_compact_form_styles(container)
        self._init_runtime_helpers()
        self._build_top_bar(container)
        content = ttk.Frame(container)
        content.pack(fill='both', expand=True)
        self.split_container = ttk.Frame(content)
        self.split_container.pack(fill='both', expand=True)
        self.speech_container = ttk.Frame(content)
        self._build_left_pane(self.split_container)
        ttk.Separator(self.split_container, orient='vertical').pack(side='left', fill='y', padx=SPACING['sm'])
        self._build_right_pane(self.split_container)
        self._wire_events()
        self.load_rows()
        self._load_new_draft()

    def _init_runtime_helpers(self):
        from orchestrator.desktop_automation_service import BackgroundTaskLifecycle
        from queue import Empty, Queue
        from threading import Thread
        self.Queue, self.Empty, self.Thread = Queue, Empty, Thread
        self.search = BackgroundTaskLifecycle()
        self.probe_life = BackgroundTaskLifecycle()
        self.batch_life = BackgroundTaskLifecycle()
        self.fetch_life = BackgroundTaskLifecycle()
        self.search_poll = {'after': None}
        self.pending = {'after': None, 'loading': False}
        self.state = {'id': ''}
        self.auto_label = {'text': ''}
        self.mode = tk.StringVar(master=self.win, value='API')
        self.local_provider = tk.StringVar(master=self.win, value=FORM_DEFAULT_PROVIDER)
        self.modality = tk.StringVar(master=self.win, value=model_pool.MODALITY_LABELS[model_pool.DEFAULT_MODALITY])
        self.hint = tk.StringVar(master=self.win, value='在左侧选择模型编辑，或直接新建模型并点击路线右侧「测试」。')
        self.editor_title_var = tk.StringVar(master=self.win, value='新建 API 模型')
        self.entries = {}
        self.static_entries = {}
        self.labels = {}
        self.caps = {}

    def _build_top_bar(self, card):
        top = ttk.Frame(card)
        top.pack(fill='x', pady=(SPACING['none'], SPACING['sm']))
        if not self._embedded:
            title_box = ttk.Frame(top)
            title_box.pack(side='left')
            heading(title_box, MANAGER_TITLE, NOTE_MANAGER, columns=1)
        self.mode_tabs = ModeSegmentedControl(top, MODES, command=self._on_tab_changed)
        from ui.model_connections import open_client_accounts, open_flow
        SecondaryButton(top, text='Google Flow…', command=lambda: open_flow(self)).pack(side='right')
        self.account_button = SecondaryButton(top, text='客户端账号…',
            command=lambda: open_client_accounts(self, self.read_form()))
        self.account_button.pack(side='right')
        self.mode_tabs.pack(side='left', padx=(SPACING['none'] if self._embedded else SPACING['md'], SPACING['none']))

    def _build_left_pane(self, split):
        left_w = LEFT_PANE_EMBED_WIDTH if self._embedded else LEFT_PANE_WIDTH
        left = ttk.Frame(split, width=left_w)
        left.pack(side='left', fill='y')
        left.pack_propagate(False)
        bar = ttk.Frame(left)
        bar.pack(fill='x', pady=(SPACING['none'], SPACING['xs']))
        SecondaryButton(bar, text='+ 新建模型', width=0, command=self.new_one).pack(side='left')
        self.batch_button = SecondaryButton(
            bar, text='检测全部', width=0, command=self.probe_all_visible)
        self.batch_button.pack(side='right')
        self.search_entry = CompactLineInput(left, placeholder='搜索模型名、ID 或服务商…')
        self.search_entry.pack(fill='x', pady=(SPACING['none'], SPACING['xs']))
        self.search_entry.bind('<KeyRelease>', lambda _e: self.load_rows(refresh=False), add='+')
        self.modality_filter_bar = ttk.Frame(left)
        self.modality_filter_bar.pack(fill='x', pady=(SPACING['none'], SPACING['xs']))
        self.modality_filter = ModeSegmentedControl(
            self.modality_filter_bar, MODALITY_FILTERS,
            command=lambda: (self.load_rows(refresh=False), True)[1])
        self.modality_filter.pack(side='left')
        self.card_list = ModelCardList(left, on_select=self.select_model, empty_text='暂无匹配的模型配置')
        self.card_list.pack(fill='both', expand=True)

    def _build_right_pane(self, split):
        right = ttk.Frame(split)
        right.pack(side='left', fill='both', expand=True)
        header = ttk.Frame(right)
        header.pack(fill='x', pady=(SPACING['none'], SPACING['xs']))
        ttk.Label(header, textvariable=self.editor_title_var,
                  style='ModelSection.TLabel').pack(side='left')
        if self._embedded:
            self.save_button = SecondaryButton(header, text='保存当前', width=0, command=self.save_one)
        else:
            self.save_button = PrimaryButton(header, text='保存', command=self.save_one)
        self.save_button.pack(side='right')
        self.delete_button = SecondaryButton(header, text='删除', command=self.delete_one)
        self.delete_button.pack(side='right', padx=(SPACING['none'], BUTTON_GAP))
        self.manager_hint_label = ttk.Label(
            right, textvariable=self.hint, style='PaleGreenHint.TLabel',
            wraplength=TEXT_DESC['wraplength'])
        self.manager_hint_label.pack(fill='x', pady=(SPACING['none'], SPACING['xs']))
        self.search_busy = BusyState(self.hint)
        scroll_wrap = ttk.Frame(right)
        scroll_wrap.pack(fill='both', expand=True)
        self.right_scroll = ScrollForm(scroll_wrap, bg=COLORS['background_primary'])
        self.form_host = self.right_scroll.form
        self._build_basic_card()
        self._build_routes_section()
        self._build_advanced_section()

    def _build_basic_card(self):
        box = ttk.Frame(self.form_host, style='ModelRouteCard.TFrame',
                        padding=(SPACING['md'], SPACING['sm']))
        box.pack(fill='x', pady=(SPACING['none'], SPACING['sm']))
        box.columnconfigure(0, minsize=form_column_width(('服务商预设', '模型名称', '应用安装路径', '命令行程序路径')))
        box.columnconfigure(1, weight=1)
        self.basic_form = box
        self.labels['label'] = ttk.Label(box, text='模型名称', style='ModelField.TLabel')
        self.labels['label'].grid(row=0, column=0, sticky='w', pady=(SPACING['none'], SPACING['xs']))
        label_entry = EditablePresetBox(box, values=field_presets('label', 'API', self.modality.get()))
        label_entry.grid(row=0, column=1, sticky='ew', pady=(SPACING['none'], SPACING['xs']))
        self._register_static_entry('label', label_entry)
        self.labels['model'] = ttk.Label(box, text=MODEL_FIELD_API, style='ModelField.TLabel')
        self.labels['model'].grid(row=1, column=0, sticky='w', pady=(SPACING['none'], SPACING['xs']))
        model_entry = EditablePresetBox(
            box, values=field_presets('model', 'API', self.modality.get()),
            on_change=self._on_top_model_edited)
        model_entry.grid(row=1, column=1, sticky='ew', pady=(SPACING['none'], SPACING['xs']))
        self._register_static_entry('model', model_entry)
        self.modality_label = ttk.Label(box, text='模型类型', style='ModelField.TLabel')
        self.modality_label.grid(row=2, column=0, sticky='w')
        self.modality_box = SelectBox(
            box, textvariable=self.modality, style=COMPACT_COMBOBOX_STYLE,
            values=[label for _v, label in model_pool.MODALITIES], width=CHAR_WIDTH['md'])
        self.modality_box.grid(row=2, column=1, sticky='w')
        self.local_provider_label = ttk.Label(box, text='服务商 / 品牌', style='ModelField.TLabel')
        self.local_provider_label.grid(row=3, column=0, sticky='w', pady=(SPACING['none'], SPACING['xs']))
        self.local_provider_box = SelectBox(
            box, textvariable=self.local_provider, state='normal',
            values=provider_choices(), style=COMPACT_COMBOBOX_STYLE, fit=True)
        self.local_provider_box.grid(row=3, column=1, sticky='w', pady=(SPACING['none'], SPACING['xs']))
        self.program_label = ttk.Label(box, text='应用安装路径', style='ModelField.TLabel')
        self.program_label.grid(row=4, column=0, sticky='w')
        self.program_row = ttk.Frame(box, style='Card.TFrame')
        self.program_row.grid(row=4, column=1, sticky='ew')
        self.program_row.columnconfigure(0, weight=1)
        self.program_entry = EditablePresetBox(self.program_row, values=field_presets('program', 'Desktop'))
        self.program_entry.grid(row=0, column=0, sticky='ew')
        self._register_static_entry('program', self.program_entry)
        self.search_button = SecondaryButton(
            self.program_row, text='自动搜寻', width=0,
            command=lambda: self.detect_program(quiet=False))
        self.search_button.grid(row=0, column=1, padx=(BUTTON_GAP_TIGHT, SPACING['none']))
        SecondaryButton(self.program_row, text='浏览…', width=0, command=self.browse_program).grid(
            row=0, column=2, padx=(BUTTON_GAP_TIGHT, SPACING['none']))
        self.local_probe_button = SecondaryButton(
            self.program_row, text='检查程序', width=0, command=self.probe_local_one)
        self.local_probe_button.grid(row=0, column=3, padx=(BUTTON_GAP_TIGHT, SPACING['none']))

    def _build_routes_section(self):
        self.routes_section = ttk.Frame(self.form_host)
        self.routes_section.pack(fill='x', pady=(SPACING['none'], SPACING['sm']))
        bar = ttk.Frame(self.routes_section)
        bar.pack(fill='x', pady=(SPACING['none'], SPACING['xs']))
        ttk.Label(bar, text='API 路线（按顺序自动故障转移）', style='ModelSection.TLabel').pack(side='left')
        SecondaryButton(bar, text='+ 添加备用路线', width=0, command=self.add_route).pack(side='right')
        self.routes_container = ttk.Frame(self.routes_section)
        self.routes_container.pack(fill='x')

    def _build_advanced_section(self):
        self.advanced_section = CollapsibleSection(
            self.form_host, '高级参数', open_by_default=False,
            action_text='恢复默认', action_command=self.restore_defaults, card_bg=False)
        self.advanced_section.pack(fill='x', pady=(SPACING['none'], SPACING['md']))
        self.advanced_section.set_summary('默认：256K / 8192 / 温度 0.7')
        panel = ttk.Frame(self.advanced_section.body, style='ModelRouteCard.TFrame',
                          padding=(SPACING['md'], SPACING['sm']))
        panel.pack(fill='x')
        panel.columnconfigure(1, weight=1)
        panel.columnconfigure(3, weight=1)
        self.api_adv_widgets = []
        pairs = (
            (0, ('context_length', '上下文长度', CHAR_WIDTH['xl']), ('max_output', '最大输出', CHAR_WIDTH['xl'])),
            (1, ('temperature', '温度', CHAR_WIDTH['md']), ('timeout', '超时（秒）', CHAR_WIDTH['md'])),
            (2, ('retries', '重试次数', CHAR_WIDTH['md']), ('rpm', '每分钟上限（RPM）', CHAR_WIDTH['xl'])),
        )
        for row_idx, left_spec, right_spec in pairs:
            for col_offset, (key, title, width) in ((0, left_spec), (2, right_spec)):
                lbl = ttk.Label(panel, text=title, style='ModelField.TLabel')
                lbl.grid(row=row_idx, column=col_offset, sticky='w' if col_offset == 0 else 'e',
                         padx=(SPACING['none'] if col_offset == 0 else SPACING['md'], SPACING['xs']),
                         pady=(SPACING['none'], SPACING['xs']))
                entry = EditablePresetBox(panel, values=field_presets(key), width=width)
                entry.grid(row=row_idx, column=col_offset + 1, sticky='w',
                           pady=(SPACING['none'], SPACING['xs']))
                self._register_static_entry(key, entry)
                self.labels[key] = lbl
                self.api_adv_widgets.extend((lbl, entry))
        ttk.Label(panel, text='能力标签', style='ModelField.TLabel').grid(
            row=3, column=0, sticky='nw', pady=(SPACING['xs'], SPACING['xs']))
        cap_row = ttk.Frame(panel, style='Card.TFrame')
        cap_row.grid(row=3, column=1, columnspan=3, sticky='w', pady=(SPACING['xs'], SPACING['xs']))
        for idx, tag in enumerate(model_pool.CAPABILITY_TAGS):
            var = tk.BooleanVar(master=self.win, value=False)
            self.caps[tag] = var
            ttk.Checkbutton(
                cap_row, text=model_pool.CAPABILITY_LABELS[tag], variable=var,
                style='Card.TCheckbutton', command=self._mark_dirty,
            ).grid(row=idx // 4, column=idx % 4, sticky='w', padx=(SPACING['none'], SPACING['sm']))
        self.labels['note'] = ttk.Label(panel, text='备注（可选）', style='ModelField.TLabel')
        self.labels['note'].grid(row=4, column=0, sticky='w', pady=(SPACING['xs'], SPACING['none']))
        note_entry = EditablePresetBox(panel, values=field_presets('note'))
        note_entry.grid(row=4, column=1, columnspan=3, sticky='ew', pady=(SPACING['xs'], SPACING['none']))
        self._register_static_entry('note', note_entry)

    def _register_static_entry(self, key, widget):
        self.entries[key] = widget
        self.static_entries[key] = widget

    def _wire_events(self):
        self._root_frame.bind('<Destroy>', self._on_destroy, add='+')
        if not self._embedded:
            self.win.bind('<Escape>', lambda _e: self.cancel())
            self.win.protocol('WM_DELETE_WINDOW', self.cancel)
        self.entries['model'].bind('<KeyRelease>', self._on_top_model_edited, add='+')
        self.entries['model'].bind('<FocusOut>', self.detect_program, add='+')
        self.local_provider_box.bind('<<ComboboxSelected>>', lambda _e: self.detect_program(), add='+')
        self.modality_box.bind('<<ComboboxSelected>>', self._refresh_field_presets, add='+')
        self.modality.trace_add('write', self._refresh_field_presets)
        self._last_mode = self.mode.get()
        self.mode.trace_add('write', self._on_mode_change)
        self.mode.trace_add('write', self.changed_identity)
        self._bind_dirty_marks()

    def _ensure_speech_panel(self):
        if self._speech_panel is None:
            import ui.speech_settings_ui as speech_settings_ui
            if not self._embedded:
                bar = ttk.Frame(self.speech_container)
                bar.pack(side='bottom', fill='x', pady=(SPACING['xs'], SPACING['none']))
                PrimaryButton(bar, text='保存', command=self.save_and_close).pack(side='right')
            host = ttk.Frame(self.speech_container)
            host.pack(fill='both', expand=True)
            self._speech_panel = speech_settings_ui.speech_settings_panel(
                host, self.pet, host_win=self.win,
                on_dirty=self._on_dirty, embedded=True, combobox_style=COMPACT_COMBOBOX_STYLE)
        return self._speech_panel

    def _expose_hooks(self):
        attach_manager_seams(self, self.win)
        self._sync_primary_hooks()

    def _sync_primary_hooks(self):
        if self.desktop_mode() or not self.route_cards:
            provider, box, key_entry = self.local_provider, self.local_provider_box, None
        else:
            first = self.route_cards[0]
            self.entries['base_url'] = first.base_url_entry
            self.entries['key_env'] = first.key_env_entry
            provider, box, key_entry = first.provider_var, first.provider_box, first.key_entry
        if not self._embedded:
            self.win._pet_provider = provider
            self.win._pet_provider_box = box
            if key_entry is not None:
                self.win._pet_key_entry = key_entry
        if self._embedded_seam is not None:
            self._embedded_seam['provider'] = provider
            self._embedded_seam['provider_box'] = box
            if key_entry is not None:
                self._embedded_seam['key_entry'] = key_entry

    def _primary_key_state(self):
        return self.route_cards[0].key_state_var.get() if self.route_cards else ''

    def _report_error(self, message):
        return report_error(self.hint, message)

    def _transport(self):
        return transport_of(self.pet)

    def _probe_breakdown(self, result, flat):
        return probe_breakdown(result, flat, self.program)

    def _probe_local(self, value):
        return _probe_local_model(self.pet, value, self.mode, self.entries, self.program_entry, self.hint)

    def _apply_search(self, path, error, original_path):
        return _apply_program_search(path, error, original_path, self.program_entry, self.hint)

    def desktop_mode(self):
        return self.mode.get() in ('Desktop', 'CLI')

    def refresh_connection_fields(self, *_args):
        if self.mode.get() == SPEECH_MODE:
            return
        local = self.desktop_mode()
        if local:
            self.modality_filter_bar.pack_forget()
            self.modality_label.grid_remove()
            self.modality_box.grid_remove()
            self.local_provider_label.grid()
            self.local_provider_box.grid()
            self.program_label.grid()
            self.program_row.grid()
            self.routes_section.pack_forget()
            for w in self.api_adv_widgets:
                w.grid_remove()
        else:
            self.modality_filter_bar.pack(fill='x', pady=(SPACING['none'], SPACING['xs']),
                                          before=self.card_list)
            self.modality_label.grid()
            self.modality_box.grid()
            self.local_provider_label.grid_remove()
            self.local_provider_box.grid_remove()
            self.program_label.grid_remove()
            self.program_row.grid_remove()
            self.routes_section.pack(fill='x', pady=(SPACING['none'], SPACING['sm']),
                                     before=self.advanced_section)
            for w in self.api_adv_widgets:
                w.grid()
        self.program_label.configure(text='命令行程序路径' if self.mode.get() == 'CLI' else '应用安装路径')
        self.labels['model'].configure(text=MODEL_FIELD_LOCAL if local else MODEL_FIELD_API)
        self._sync_primary_hooks()
        self._refresh_adv_summary()
        self.right_scroll.fit()

    def _refresh_adv_summary(self):
        ctx = self.entries['context_length'].get().strip() or '默认'
        out = self.entries['max_output'].get().strip() or '默认'
        temp = self.entries['temperature'].get().strip() or '默认'
        if self.desktop_mode():
            self.advanced_section.set_summary('能力标签与备注')
        else:
            self.advanced_section.set_summary(f'上下文 {ctx} / 输出 {out} / 温度 {temp}')

    def restore_defaults(self):
        for key, value in NEW_MODEL_DEFAULTS.items():
            set_input_value(self.entries[key], str(value))
        set_input_value(self.entries['rpm'], '')
        self._refresh_adv_summary()
        self._mark_dirty()
        self.hint.set('已恢复主流默认参数（上下文 256K、最大输出 8192、温度 0.7、超时 120s、重试 2）。')

    def _load_new_draft(self):
        self.stop_search()
        self.pending['loading'] = True
        self.state['id'] = ''
        self._auto_model_sync = ''
        self.auto_label['text'] = ''
        self.card_list.set_selected('')
        for key, entry in self.static_entries.items():
            set_input_value(entry, '')
        for key, value in NEW_MODEL_DEFAULTS.items():
            set_input_value(self.entries[key], str(value))
        for var in self.caps.values():
            var.set(False)
        self.local_provider.set(FORM_DEFAULT_PROVIDER)
        self.modality.set(model_pool.MODALITY_LABELS[model_pool.DEFAULT_MODALITY])
        self._render_routes([model_routes.normalize_route({'id': 'r1'}, index=0)], expand_indices={0})
        self.pending['loading'] = False
        self._refresh_field_presets()
        self.editor_title_var.set('新建 %s 模型' % self.mode.get())
        self.refresh_connection_fields()
        self._dirty = False
        self.hint.set('新建 %s 模型：从上往下填写核心信息，配置完可直接点右侧「测试」。' % self.mode.get())

    def fill(self, model_id, item):
        self.stop_search()
        self.pending['loading'] = True
        self._cancel_pending_detect()
        self.state['id'] = model_id
        self.mode.set(model_pool.call_mode(item, model_id))
        set_input_value(self.entries['label'], item.get('label') or '')
        set_input_value(self.entries['model'], item.get('model') or model_id or '')
        self._auto_model_sync = self.entries['model'].get().strip()
        self.auto_label['text'] = self.entries['label'].get().strip()
        for key in ('context_length', 'rpm', 'note', 'max_output', 'temperature', 'timeout', 'retries'):
            set_input_value(self.entries[key], str(item[key]) if item.get(key) else '')
        for tag, var in self.caps.items():
            var.set(tag in (item.get('capabilities') or []))
        self.modality.set(model_pool.MODALITY_LABELS.get(
            item.get('modality'), model_pool.MODALITY_LABELS[model_pool.DEFAULT_MODALITY]))
        vendor = model_pool.provider_name(model_id, item)
        self.local_provider.set(model_pool.PROVIDER_LABELS.get(vendor.casefold(), vendor))
        set_input_value(self.program_entry, item.get('program') or '')
        routes = model_routes.routes_of(item, model_id=model_id)
        self._render_routes(routes, expand_indices={0})
        self.pending['loading'] = False
        self._refresh_field_presets()
        self.editor_title_var.set(item.get('label') or model_id)
        self.refresh_connection_fields()
        self._dirty = False

    def _partial_parent_record(self):
        return {
            'label': self.entries['label'].get().strip(),
            'model': self.entries['model'].get().strip() or self.state['id'],
            'capabilities': [tag for tag, var in self.caps.items() if var.get()],
            'context_length': self.entries['context_length'].get().strip(),
            'max_output': self.entries['max_output'].get().strip(),
            'temperature': self.entries['temperature'].get().strip(),
            'timeout': self.entries['timeout'].get().strip(),
            'retries': self.entries['retries'].get().strip(),
            'rpm': self.entries['rpm'].get().strip(),
            'note': self.entries['note'].get().strip(),
            'modality': model_pool.id_of_label(self.modality.get(), model_pool.MODALITIES),
        }

    def read_form(self):
        value = self._partial_parent_record()
        value['call_mode'] = self.mode.get()
        value['program'] = self.program_entry.get().strip()
        if self.desktop_mode():
            value['provider'] = 'desktop'
            existing = (self._records_cache or {}).get(self.state['id'], {})
            for field in ('profiles', 'flow_project', 'client_accounts'):
                if field in existing:
                    value[field] = existing[field]
            value['provider_label'] = self.local_provider.get().strip()
            value['base_url'] = ''
            value['key_env'] = ''
            value['wire_api'] = model_pool.DEFAULT_WIRE
            return value
        routes = self._snapshot_route_dicts()
        top_model = value['model']
        if not top_model and routes:
            top_model = routes[0].get('model', '')
            value['model'] = top_model
        for r in routes:
            if not r['model']:
                r['model'] = top_model
        value['routes'] = routes
        primary = model_routes.primary_route(routes) or {}
        raw_provider = primary.get('provider') or FORM_DEFAULT_PROVIDER
        value['provider'] = model_pool.id_of_label(raw_provider, model_pool.PROVIDERS)
        value['provider_label'] = ''
        value['base_url'] = primary.get('base_url', '')
        value['path'] = primary.get('path') or model_routes.DEFAULT_PATH
        value['wire_api'] = primary.get('wire_api') or model_pool.DEFAULT_WIRE
        value['key_env'] = primary.get('key_env', '')
        return value

    def load_rows(self, refresh=True):
        if self.mode.get() == SPEECH_MODE:
            return self.card_list
        builtins = provider_choices()
        if refresh or self._records_cache is None:
            self._records_cache = self.pet.agent_model_records()
            self._probe_cache = model_routes.all_probe_status(program=self.program)
        records = self._records_cache
        merged_local, extra = merge_provider_choices(builtins, records)
        self._extra_providers = extra
        freezer = self._rows_paint_freeze or PaintFreeze(self.card_list)
        self._rows_paint_freeze = freezer
        frozen = freezer.freeze()
        try:
            self.local_provider_box.set_values(merged_local, refit=True)
            for card in self.route_cards:
                card.callbacks['extra_providers'] = extra
                card.provider_box.set_values(card._provider_values(), refit=True)
            self._render_mode_rows(records)
        except Exception:
            if frozen:
                freezer.thaw()
            raise
        if frozen:
            prev_thaw = self._bg_polls.pop('thaw_rows', None)
            if prev_thaw is not None:
                try:
                    self.win.after_cancel(prev_thaw)
                except tk.TclError:
                    pass
            def thaw_rows():
                self._bg_polls.pop('thaw_rows', None)
                try:
                    if self.win.winfo_exists() and self.card_list.winfo_exists():
                        self.card_list.update_idletasks()
                except tk.TclError:
                    pass
                finally:
                    freezer.thaw()
            self._bg_polls['thaw_rows'] = self.win.after_idle(thaw_rows)
        return self.card_list

    def save_one(self):
        try:
            if self.desktop_mode() and self.program_entry.get().strip():
                self._validate_local_exe()
            if not self.desktop_mode():
                for card in self.route_cards:
                    if card.typed_key():
                        if self.save_route_card_key(card, persist_pool=False) is None:
                            return None
            form_data = self.read_form()
            old_id = self.state['id']
            self.pet.save_pool(form_data, old_id)
            self.state['id'] = model_pool.model_id_of(form_data, old_id)
        except (ValueError, OSError) as exc:
            report_error(self.hint, exc)
            return None
        self._dirty = False
        self.editor_title_var.set(form_data.get('label') or self.state['id'])
        self.load_rows(refresh=True)
        self.card_list.set_selected(self.state['id'])
        self._refresh_adv_summary()
        self.hint.set('已保存「%s」；所有路线与切换菜单立即生效。' % (form_data.get('label') or self.state['id']))
        return form_data

    def _validate_local_exe(self):
        from pathlib import Path
        from orchestrator.workflow_settings import GUI_CLAUDE_CLI_HINT, gui_claude_program
        path = Path(self.program_entry.get().strip()).expanduser()
        if not path.is_absolute() or path.suffix.lower() != '.exe' or not path.is_file():
            raise ValueError('请选择存在的应用 .exe 安装路径')
        if self.mode.get() == 'CLI' and gui_claude_program(str(path)):
            raise ValueError(GUI_CLAUDE_CLI_HINT)
        _adapted, switched = _derive_client_profile(
            str(path), self.entries['label'].get().strip(), self.mode, self.entries, probe=False)
        if switched:
            self.hint.set('PE 头显示这是%s程序，已切换调用方式。' % ('命令行' if switched == 'CLI' else '桌面'))

    def delete_one(self):
        model_id = self.state['id'] or self.card_list.selected_id()
        if not model_id:
            report_error(self.hint, '请先在左侧选择一条模型。')
            return None
        item = self.pet.agent_model_records().get(model_id) or {}
        name = item.get('label') or model_id
        presets = '、'.join('%s「%s」' % pair for pair in self.pet.pool_model_presets(model_id))
        notice = '\n\n这些 SKILL 预设用的是它，删除后改为「自动」：' + presets if presets else ''
        stages = '、'.join(self.pet.pool_model_stages(model_id))
        notice += ('\n\n当前项目这些阶段选的是它，删除后改为「自动」：' + stages) if stages else ''
        if not self.pet.confirm_start('删除模型', '把「%s」从模型池里删掉？（.env 里的密钥不动）' % name + notice):
            return None
        self.pet.delete_pool_model(model_id)
        if model_id in self.pet.agent_model_records():
            report_error(self.hint, '未能删除「%s」，请重试。' % name)
            return None
        self.state['id'] = ''
        self._dirty = False
        self.load_rows(refresh=True)
        self._load_new_draft()
        self.hint.set('已删除「%s」。' % name)
        return model_id


def open_speech_settings(pet, parent=None):
    import ui.speech_settings_ui as speech_settings_ui
    return speech_settings_ui.open_speech_settings(pet, parent)

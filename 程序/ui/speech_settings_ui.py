"""模型管理 › 语音识别分类与独立设置弹窗（REQ-S01-71 / UX-SETTINGS-MODELS）。

L4 只管表单；校验与写入在 L2 ``speech_api.save_settings``，由这里注入 ``agent.core.save`` 作发布器。
``backend`` 默认 ``offline``（本地 FunASR 子进程，逐句出字）；``cloud`` 为阿里云实时流式。
提供可嵌入模型管理分页的 ``speech_settings_panel``，并保留 ``open_speech_settings`` 弹窗壳兼容既有调用。
"""
import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk

import domain.speech_api as speech_api
import domain.voice_ai as voice_ai
from agent.core import save as save_json
from responsive_ui import ScrollForm
from ui_tokens import BUTTON_GAP, DIALOG_CONTENT_PADDING, DIALOG_MIN_HEIGHT, FONTS, SPACING, TEXT_DESC, TEXT_ROWS
from ui_widgets import BaseDialog, Card, PrimaryButton, SecondaryButton, SelectBox, TextArea

SPEECH_TITLE = '语音识别设置'
SPEECH_NOTE = ('麦克风听写用的识别后端：离线（默认）在本机逐句出字、不上传音频，首次使用自动下载'
               '约 500MB 模型；云端走实时流式、需要百炼密钥。保存后下次开麦生效。')
SPEECH_FIELDS = (
    ('backend', '识别后端', ('offline', 'cloud')),
    ('base_url', '云端服务地址（wss://）', (
        'wss://dashscope.aliyuncs.com/api-ws/v1/realtime',
        'wss://dashscope-intl.aliyuncs.com/api-ws/v1/realtime',
        'ws://127.0.0.1:10095',
        'wss://api.openai.com/v1/realtime',
        'wss://openspeech.bytedance.com/api/v3/sauc/bigmodel',
    )),
    ('model', '云端模型', (
        'qwen3-asr-flash-realtime',
        'paraformer-realtime-v2',
        'whisper-large-v3',
        'funasr-paraformer-zh',
        'sensevoice-small',
    )),
    ('key_env', '云端密钥名', (
        'DASHSCOPE_API_KEY',
        'OPENAI_API_KEY',
        'VOLC_ASR_API_KEY',
        'TENCENT_ASR_KEY',
        'AZURE_SPEECH_KEY',
    )),
    ('language', '识别语言', ('zh', 'en', 'ja', 'ko', 'yue')),
    ('silence_ms', '云端断句停顿（毫秒）', ('300', '400', '600', '800', '1200')),
    ('max_seconds', '单次开麦上限（秒）', ('60', '180', '300', '600', '1800')),
    ('timeout', '连接与收尾超时（秒）', ('10', '15', '30', '60', '120')),
    ('offline.python', '离线环境解释器（空=自动）', (
        '',
        'data/voice_asr_venv/Scripts/python.exe',
        'python',
        r'C:\Python311\python.exe',
        r'C:\Python312\python.exe',
    )),
    ('offline.cache_dir', '离线模型缓存目录（空=默认）', (
        '',
        'data/voice_models',
        '~/.cache/modelscope/hub',
        '~/.cache/huggingface/hub',
        'D:/AIModels/asr',
    )),
    ('offline.threads', '离线识别线程数（空=默认）', ('2', '4', '6', '8', '12')),
    ('offline.vad_trailing_ms', '离线断句静音（毫秒）', ('300', '500', '800', '1000', '1500')),
)

HOTWORD_PRESETS = (
    '漫剧,分镜,景别,运镜,角色卡',
    '特写,中景,全景,推镜头,拉镜头',
    '男主,女主,反派,旁白,独白',
    '剧本结构,连续性,白模预演,首帧',
    '配音,字幕,剪辑,转场,成片',
)

AI_PROMPT_PRESETS = (
    '整理口语并修正同音错字，保留原意和标点',
    '提炼为简洁分镜描述，保留景别、动作与情绪',
    '整理为标准中文剧本对白，去除口癖与重复词',
    '改写为清晰分点需求清单，不增删事实',
    '整理为流畅书面语并自动分段',
)

DICT_NOTE = ('热词：引擎支持时提高领域词命中；替换词表：每行「错词=正词」，'
             '识别定稿后自动改写；AI 优化：把整段听写交给所选文本模型做'
             '纠错/润色/翻译。MCP 工具 voice_transcribe（agent/voice_mcp_server.py）'
             '供 agent 客户端离线转写音频，同样走词典。')


def _offline_package_row(card, win, row, variables, hint):
    """离线语音包（任务书 M6）：下载独立 venv＋模型，带进度、可取消、不阻塞界面；
    返回 ``(占用行号, (runner, setup_state, setup_progress, setup_button))`` 供宿主窗挂引用。"""
    from domain import offline_asr_setup
    setup_row = row
    setup_state = tk.StringVar(value='')
    setup_progress = tk.StringVar(value='')
    runner = {'obj': None}

    def _form_settings():
        """下载探测用表单上的 offline 段（未保存值优先），其余回读文件设置。"""
        settings = dict(speech_api.read_settings())
        offline = dict(settings.get('offline') or {})
        for key, variable in variables.items():
            if key.startswith('offline.'):
                offline[key.split('.', 1)[1]] = variable.get()
        settings['offline'] = offline
        return settings

    def refresh_setup_state():
        if offline_asr_setup.environment_ready(_form_settings()):
            setup_state.set('已安装')
        elif offline_asr_setup.venv_python(offline_asr_setup.VENV_DIR).is_file():
            setup_state.set('环境已建，模型未下载完')
        else:
            setup_state.set('未安装')

    def _apply_setup_event(event):
        kind = event.get('type')
        if kind == 'progress':
            setup_progress.set(event.get('message') or '')
            return
        setup_progress.set('')
        runner['obj'] = None
        setup_button.configure(text='下载离线语音包…')
        refresh_setup_state()
        if kind == 'done':
            hint.set(event.get('message') or '离线语音包安装完成')
        elif kind == 'cancelled':
            hint.set(event.get('message') or '已取消下载；已下载部分保留，下次继续')
        else:
            hint.set(event.get('message') or '离线语音包安装失败')

    def toggle_download():
        current = runner['obj']
        if current is not None and current.running:
            current.cancel()
            setup_progress.set('正在取消…')
            return

        def on_event(event):
            try:
                win.after(0, lambda e=event: _apply_setup_event(e))
            except tk.TclError:
                pass                         # 弹窗已关：下载线程后台跑完即可

        current = offline_asr_setup.OfflineSetupRunner(_form_settings(), on_event)
        if current.start():
            runner['obj'] = current
            setup_button.configure(text='取消下载')
            setup_progress.set('正在准备…')
        else:
            hint.set('离线语音包下载已在进行中')

    ttk.Label(card, text='离线语音包').grid(row=setup_row, column=0, sticky='w', pady=SPACING['xs'])
    setup_box = ttk.Frame(card)
    setup_box.grid(row=setup_row, column=1, sticky='ew', pady=SPACING['xs'])
    setup_button = SecondaryButton(setup_box, text='下载离线语音包…', command=toggle_download)
    setup_button.pack(side='left')
    ttk.Label(setup_box, textvariable=setup_state, style='Muted.TLabel').pack(
        side='left', padx=(SPACING['sm'], SPACING['none']))
    ttk.Label(card, textvariable=setup_progress, style='Muted.TLabel',
              wraplength=TEXT_DESC['wraplength']).grid(
        row=setup_row + 1, column=0, columnspan=2, sticky='w')
    refresh_setup_state()

    return setup_row, (runner, setup_state, setup_progress, setup_button)


def _scrolling_form(parent, *, use_card=True):
    """动作区先占底部，长表单只压缩视口。"""
    pad_x = SPACING['md'] if use_card else SPACING['none']
    pad_y = SPACING['md'] if use_card else SPACING['xs']
    bar = ttk.Frame(parent)
    bar.pack(side='bottom', fill='x', padx=pad_x,
             pady=(SPACING['xs'] if not use_card else SPACING['none'], pad_y))
    holder = ttk.Frame(parent)
    holder.pack(fill='both', expand=True, padx=pad_x, pady=(pad_y, SPACING['none'] if not use_card else pad_y))
    scroll = ScrollForm(holder)
    card = Card(scroll.form) if use_card else ttk.Frame(scroll.form)
    card.pack(fill='both', expand=True)
    return scroll, card, bar


def _bind_focus_scroll(host_win, scroll, card):
    """焦点落到表单不可见字段时自动滚入视口，并递归绑定滚轮。"""
    def focus_in(event):
        if not card.winfo_exists() or not card.winfo_ismapped():
            return
        widget = event.widget
        if not str(widget).startswith(str(card) + '.'):
            return
        top = widget.winfo_rooty() - scroll.form.winfo_rooty()
        bottom = top + widget.winfo_height()
        view_top = scroll.canvas.canvasy(0)
        view_height = scroll.canvas.winfo_height()
        if top < view_top or bottom > view_top + view_height:
            target = top if top < view_top else bottom - view_height
            scroll.canvas.yview_moveto(target / max(1, scroll.form.winfo_height()))

    host_win.bind('<FocusIn>', focus_in, add='+')
    scroll.bind_wheel()


def _fit_scroll_form(win, scroll, card, bar):
    """按真实内容确定独立弹窗视口；焦点到不可见字段时自动滚入视口。"""
    _bind_focus_scroll(win, scroll, card)
    win.update_idletasks()
    # Canvas 不传播窗内 form 的请求尺寸；显式传入并为标题栏／任务栏留余量。
    margin = 2 * SPACING['2xl']
    action_height = bar.winfo_reqheight() + 3 * SPACING['md']
    scroll.canvas.configure(
        width=scroll.form.winfo_reqwidth(),
        height=min(scroll.form.winfo_reqheight(),
                   win.winfo_screenheight() - margin - action_height))
    win.update_idletasks()
    win.geometry('%dx%d' % (min(win.winfo_reqwidth(), win.winfo_screenwidth() - margin),
                            win.winfo_reqheight()))


def _build_speech_fields(card, variables, hint, key_state, combobox_style=None):
    """绘制语音识别主表单区（全部单行框为可编辑 SelectBox）；返回 (下一起始行, 控件表)。"""
    card.columnconfigure(1, weight=1)
    ttk.Label(card, text=SPEECH_TITLE, font=FONTS['title']).grid(row=0, column=0, columnspan=2, sticky='w')
    ttk.Label(card, text=SPEECH_NOTE, style='Muted.TLabel', wraplength=TEXT_DESC['wraplength']).grid(
        row=1, column=0, columnspan=2, sticky='w', pady=(SPACING['none'], SPACING['sm']))
    start = 2
    measure = tkfont.Font(font=FONTS['body']).measure
    card.columnconfigure(0, minsize=max(measure(label) for _key, label, _values in SPEECH_FIELDS) + SPACING['md'])
    style_kw = {'style': combobox_style} if combobox_style else {}
    field_widgets = {}
    for row, (key, label, values) in enumerate(SPEECH_FIELDS, start=start):
        ttk.Label(card, text=label).grid(row=row, column=0, sticky='w', pady=SPACING['xs'])
        variables[key] = tk.StringVar()
        field = SelectBox(card, textvariable=variables[key], values=values, state='normal', **style_kw)
        field.grid(row=row, column=1, sticky='ew', pady=SPACING['xs'])
        field_widgets[key] = field
    row = start + len(SPEECH_FIELDS)
    ttk.Label(card, textvariable=key_state, style='Muted.TLabel').grid(row=row, column=1, sticky='w')
    ttk.Label(card, textvariable=hint, style='PaleGreenHint.TLabel', wraplength=TEXT_DESC['wraplength']).grid(
        row=row + 1, column=0, columnspan=2, sticky='w', pady=(SPACING['sm'], SPACING['none']))
    return row + 2, field_widgets


def _build_dictionary_section(card, dict_row, combobox_style=None):
    """绘制语音词典与 AI 优化区（单行项为带 5 项主流预设的 SelectBox，替换词表保持 TextArea）。"""
    ttk.Label(card, text='语音词典与 AI 优化（可选）', font=FONTS['body_bold']).grid(
        row=dict_row, column=0, columnspan=2, sticky='w', pady=(SPACING['md'], SPACING['xs']))
    ttk.Label(card, text=DICT_NOTE, style='Muted.TLabel', wraplength=TEXT_DESC['wraplength']).grid(
        row=dict_row + 1, column=0, columnspan=2, sticky='w', pady=(SPACING['none'], SPACING['sm']))
    style_kw = {'style': combobox_style} if combobox_style else {}
    dict_fields = (
        ('hotword', '热词（逗号分隔）', HOTWORD_PRESETS),
        ('ai_enabled', 'AI 优化', ('关', '开')),
        ('ai_template', 'AI 模板', tuple(voice_ai.TEMPLATES)),
        ('ai_prompt', 'AI 自定义提示词（模板选 custom 时用）', AI_PROMPT_PRESETS),
    )
    dict_vars, dict_widgets = {}, {}
    hotword_row = dict_row + 2
    for offset, (key, label, values) in enumerate(dict_fields):
        row = hotword_row + offset
        ttk.Label(card, text=label).grid(row=row, column=0, sticky='w', pady=SPACING['xs'])
        dict_vars[key] = tk.StringVar()
        widget = SelectBox(card, textvariable=dict_vars[key], values=values, state='normal', **style_kw)
        widget.grid(row=row, column=1, sticky='ew', pady=SPACING['xs'])
        dict_widgets[key] = widget
    row = hotword_row + len(dict_fields)
    ttk.Label(card, text='替换词表（每行 错词=正词）').grid(row=row, column=0, sticky='nw', pady=SPACING['xs'])
    replace_area = TextArea(card, height=TEXT_ROWS['sm'], wrap='none')
    replace_area.grid(row=row, column=1, sticky='ew', pady=SPACING['xs'])
    dict_widgets['replace'] = replace_area
    return dict_vars, dict_widgets, replace_area


def _speech_field_value(settings, key):
    if key.startswith('offline.'):
        return str((settings.get('offline') or {}).get(key.split('.', 1)[1], ''))
    return str(settings[key])


def _collect_speech_values(variables):
    values, offline = {}, {}
    for key, variable in variables.items():
        if key.startswith('offline.'):
            offline[key.split('.', 1)[1]] = variable.get()
        else:
            values[key] = variable.get()
    values['offline'] = offline
    return values


def _read_dictionary_values(dict_vars, replace_area):
    """词典控件 → normalize_dictionary 输入；替换词表逐行「错词=正词」。"""
    replace = {}
    for index, line in enumerate(replace_area.get('1.0', 'end-1c').splitlines(), 1):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if '=' not in line:
            raise ValueError('替换词表第 %d 行缺「=」：每行写成 错词=正词' % index)
        wrong, right = line.split('=', 1)
        replace[wrong.strip()] = right.strip()
    return {'hotword': dict_vars['hotword'].get(),
            'replace': replace,
            'ai': {'enabled': dict_vars['ai_enabled'].get() == '开',
                   'template': dict_vars['ai_template'].get(),
                   'prompt': dict_vars['ai_prompt'].get()}}


def _bind_dirty_events(field_widgets, dict_widgets, on_dirty):
    if not callable(on_dirty):
        return
    notify = lambda _event=None: on_dirty()
    for widget in (*field_widgets.values(), *dict_widgets.values()):
        widget.bind('<KeyRelease>', notify, add='+')
        if widget.winfo_class() == 'TCombobox':
            widget.bind('<<ComboboxSelected>>', notify, add='+')


def speech_settings_panel(parent, pet, host_win=None, on_dirty=None, embedded=True, combobox_style=None):
    """构建可嵌入或弹窗承载的语音识别面板，返回保存、脏检查、重置与资源清理句柄。"""
    win = host_win or parent.winfo_toplevel()
    scroll, card, bar = _scrolling_form(parent, use_card=not embedded)
    variables, hint, key_state = {}, tk.StringVar(value=''), tk.StringVar(value='')

    def show_key_state(*_args):
        settings = {**speech_api.DEFAULTS, 'key_env': variables['key_env'].get().strip()}
        configured = bool(settings['key_env']) and bool(speech_api.api_key(settings))
        key_state.set('密钥已配置' if configured else '没找到这个密钥：请在模型管理里为它保存密钥')

    next_row, field_widgets = _build_speech_fields(card, variables, hint, key_state, combobox_style)
    setup_row, setup_refs = _offline_package_row(card, win, next_row, variables, hint)
    dict_vars, dict_widgets, replace_area = _build_dictionary_section(card, setup_row + 2, combobox_style)
    saved_snapshot = {'data': None}

    def snapshot():
        return (tuple((k, v.get()) for k, v in variables.items()),
                tuple((k, v.get()) for k, v in dict_vars.items()),
                replace_area.get('1.0', 'end-1c'))

    def fill_dictionary(dictionary):
        dictionary = dictionary or {}
        dict_vars['hotword'].set(','.join(dictionary.get('hotword') or ()))
        replace = dictionary.get('replace') or {}
        replace_area.delete('1.0', 'end')
        replace_area.insert('1.0', '\n'.join('%s=%s' % (wrong, right) for wrong, right in replace.items()))
        ai = dictionary.get('ai') or {}
        dict_vars['ai_enabled'].set('开' if ai.get('enabled') else '关')
        dict_vars['ai_template'].set(str(ai.get('template') or 'fix'))
        dict_vars['ai_prompt'].set(str(ai.get('prompt') or ''))

    def fill(settings):
        for key, variable in variables.items():
            variable.set(_speech_field_value(settings, key))
        show_key_state()

    def reload_all():
        fill(speech_api.read_settings())
        fill_dictionary(speech_api.read_dictionary())
        saved_snapshot['data'] = snapshot()

    def save():
        try:
            dictionary = speech_api.normalize_dictionary(_read_dictionary_values(dict_vars, replace_area))
            speech_api.save_settings(_collect_speech_values(variables), publish=save_json)
            speech_api.save_dictionary(dictionary, publish=save_json)
        except (ValueError, OSError) as error:
            hint.set('没有保存：%s' % error)
            return False
        saved_snapshot['data'] = snapshot()
        hint.set('已保存语音识别设置，下次开麦生效。')
        return True

    def reset_defaults():
        fill(speech_api.DEFAULTS)
        fill_dictionary({'hotword': [], 'replace': {}, 'ai': dict(speech_api.DICT_DEFAULTS['ai'])})
        hint.set('已填回默认值，点「保存」生效。')
        if callable(on_dirty):
            on_dirty()

    def is_dirty():
        return saved_snapshot['data'] is not None and snapshot() != saved_snapshot['data']

    def destroy_cleanup(_event=None):
        current = setup_refs[0]['obj']
        if current is not None and getattr(current, 'running', False):
            current.cancel()

    reload_all()
    variables['key_env'].trace_add('write', show_key_state)
    _bind_dirty_events(field_widgets, dict_widgets, on_dirty)
    SecondaryButton(bar, text='恢复默认', command=reset_defaults).pack(side='left')
    parent.bind('<Destroy>', lambda event: destroy_cleanup() if event.widget is parent else None, add='+')
    if embedded:
        _bind_focus_scroll(win, scroll, card)
    return {
        'frame': parent, 'scroll': scroll, 'card': card, 'bar': bar,
        'vars': variables, 'field_widgets': field_widgets,
        'dict_vars': dict_vars, 'dict_widgets': dict_widgets, 'dict_fill': fill_dictionary,
        'hint': hint, 'key_state': key_state, 'setup': setup_refs,
        'save': save, 'reset_defaults': reset_defaults, 'reload': reload_all,
        'is_dirty': is_dirty, 'destroy_cleanup': destroy_cleanup,
    }


def open_speech_settings(pet, parent=None):
    """独立语音识别设置弹窗壳：兼容直接调用，表单复用 ``speech_settings_panel``。"""
    win = BaseDialog(parent, '', modal=False, chrome=False)
    win.title(SPEECH_TITLE)
    win.minsize(TEXT_DESC['wraplength'] + 2 * DIALOG_CONTENT_PADDING, DIALOG_MIN_HEIGHT)
    win.transient(parent or None)
    win.bind('<Escape>', lambda event: win.destroy())
    panel = speech_settings_panel(win, pet, host_win=win, embedded=False)

    def save_and_close():
        if panel['save']():
            win.destroy()
            return True
        return False

    bar = panel['bar']
    PrimaryButton(bar, text='保存', command=save_and_close).pack(side='right')
    SecondaryButton(bar, text='取消', command=win.destroy).pack(side='right', padx=(SPACING['none'], BUTTON_GAP))
    win._pet_speech_vars = panel['vars']
    win._pet_speech_save = save_and_close
    win._pet_speech_reset = panel['reset_defaults']
    win._pet_speech_dict_vars = panel['dict_vars']
    win._pet_speech_dict_fill = panel['dict_fill']
    win._pet_speech_hint = panel['hint']
    win._pet_speech_key_state = panel['key_state']
    win._pet_speech_setup = panel['setup']
    win._pet_speech_scroll = panel['scroll']
    win._pet_speech_actions = bar
    _fit_scroll_form(win, panel['scroll'], panel['card'], bar)
    return win

"""模型管理 › 「语音识别…」弹窗（REQ-S01-71）：语音输入的后端与识别服务设置。

L4 只管表单；校验与写入在 L2 ``speech_api.save_settings``，由这里注入 ``agent.core.save`` 作发布器。
``backend`` 默认 ``offline``（本地 FunASR 子进程，逐句出字）；``cloud`` 为阿里云实时流式。
"""
import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk

import domain.speech_api as speech_api
import domain.voice_ai as voice_ai
from agent.core import save as save_json
from responsive_ui import ScrollForm
from ui_tokens import BUTTON_GAP, DIALOG_CONTENT_PADDING, DIALOG_MIN_HEIGHT, FONTS, SPACING, TEXT_DESC, TEXT_ROWS
from ui_widgets import (BaseDialog, Card, LineInput, PrimaryButton, SecondaryButton,
                        SelectBox, TextArea)

SPEECH_TITLE = '语音识别设置'
SPEECH_NOTE = ('麦克风听写用的识别后端：离线（默认）在本机逐句出字、不上传音频，首次使用自动下载'
               '约 500MB 模型；云端走实时流式、需要百炼密钥。保存后下次开麦生效。')
SPEECH_FIELDS = (('backend', '识别后端', ('offline', 'cloud')),
                 ('base_url', '云端服务地址（wss://）', ()), ('model', '云端模型', ('qwen3-asr-flash-realtime',)),
                 ('key_env', '云端密钥名', ()), ('language', '识别语言', ('zh', 'en', 'ja', 'ko', 'yue')),
                 ('silence_ms', '云端断句停顿（毫秒）', ()), ('max_seconds', '单次开麦上限（秒）', ()),
                 ('timeout', '连接与收尾超时（秒）', ()),
                 ('offline.python', '离线环境解释器（空=自动）', ()),
                 ('offline.cache_dir', '离线模型缓存目录（空=默认）', ()),
                 ('offline.threads', '离线识别线程数（空=默认）', ()),
                 ('offline.vad_trailing_ms', '离线断句静音（毫秒）', ()))


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


def _scrolling_form(win):
    """长表单独立滚动，底部动作始终可达。"""
    actions = ttk.Frame(win)
    actions.pack(side='bottom', fill='x', padx=SPACING['md'], pady=SPACING['md'])
    view = ScrollForm(win)
    card = Card(view.form)
    card.pack(fill='both', expand=True, padx=SPACING['md'], pady=SPACING['md'])
    return actions, card, view


def open_speech_settings(pet, parent=None):
    """``parent`` 是模型管理窗；外壳与模型管理的小窗同款：非模态、Escape 关闭、内容放进 Card。

    只给宽度下限、不写死尺寸：长表单可滚动，保存动作固定在底部可见。
    """
    win = BaseDialog(parent, '', modal=False, chrome=False)
    win.title(SPEECH_TITLE)
    win.minsize(TEXT_DESC['wraplength'] + 2 * DIALOG_CONTENT_PADDING, DIALOG_MIN_HEIGHT)
    win.transient(parent or None)
    win.bind('<Escape>', lambda event: win.destroy())
    actions, card, view = _scrolling_form(win)
    card.columnconfigure(1, weight=1)
    ttk.Label(card, text=SPEECH_TITLE, font=FONTS['title']).grid(row=0, column=0, columnspan=2, sticky='w')
    ttk.Label(card, text=SPEECH_NOTE, style='Muted.TLabel', wraplength=TEXT_DESC['wraplength']).grid(
        row=1, column=0, columnspan=2, sticky='w', pady=(SPACING['none'], SPACING['sm']))
    start = 2
    measure = tkfont.Font(font=FONTS['body']).measure
    card.columnconfigure(0, minsize=max(measure(label) for _key, label, _values in SPEECH_FIELDS) + SPACING['md'])
    variables, hint, key_state = {}, tk.StringVar(value=''), tk.StringVar(value='')

    def show_key_state(*_args):
        settings = {**speech_api.DEFAULTS, 'key_env': variables['key_env'].get().strip()}
        configured = bool(settings['key_env']) and bool(speech_api.api_key(settings))
        key_state.set('密钥已配置' if configured else '没找到这个密钥：请在模型管理里为它保存密钥')

    for row, (key, label, values) in enumerate(SPEECH_FIELDS, start=start):
        ttk.Label(card, text=label).grid(row=row, column=0, sticky='w', pady=SPACING['xs'])
        variables[key] = tk.StringVar()
        field = (SelectBox(card, textvariable=variables[key], values=values, state='normal') if values
                 else LineInput(card, textvariable=variables[key]))
        field.grid(row=row, column=1, sticky='ew', pady=SPACING['xs'])
    row = start + len(SPEECH_FIELDS)
    ttk.Label(card, textvariable=key_state, style='Muted.TLabel').grid(row=row, column=1, sticky='w')
    ttk.Label(card, textvariable=hint, style='PaleGreenHint.TLabel', wraplength=TEXT_DESC['wraplength']).grid(
        row=row + 1, column=0, columnspan=2, sticky='w', pady=(SPACING['sm'], SPACING['none']))
    setup_row, setup_refs = _offline_package_row(card, win, row + 2, variables, hint)

    # ── 语音词典与 AI 优化（可选，存 data/语音词典.json）──
    dict_row = setup_row + 2
    ttk.Label(card, text='语音词典与 AI 优化（可选）', font=FONTS['body_bold']).grid(
        row=dict_row, column=0, columnspan=2, sticky='w', pady=(SPACING['md'], SPACING['xs']))
    ttk.Label(card, text=('热词：引擎支持时提高领域词命中；替换词表：每行「错词=正词」，'
                          '识别定稿后自动改写；AI 优化：把整段听写交给所选文本模型做'
                          '纠错/润色/翻译。MCP 工具 voice_transcribe（agent/voice_mcp_server.py）'
                          '供 agent 客户端离线转写音频，同样走词典。'),
              style='Muted.TLabel', wraplength=TEXT_DESC['wraplength']).grid(
        row=dict_row + 1, column=0, columnspan=2, sticky='w', pady=(SPACING['none'], SPACING['sm']))
    dict_vars = {}
    dict_widgets = {}
    dict_fields = (('hotword', '热词（逗号分隔）'),
                   ('ai_enabled', 'AI 优化'), ('ai_template', 'AI 模板'),
                   ('ai_prompt', 'AI 自定义提示词（模板选 custom 时用）'))
    hotword_row = dict_row + 2
    for offset, (key, label) in enumerate(dict_fields):
        r = hotword_row + offset
        ttk.Label(card, text=label).grid(row=r, column=0, sticky='w', pady=SPACING['xs'])
        dict_vars[key] = tk.StringVar()
        if key == 'ai_enabled':
            widget = SelectBox(card, textvariable=dict_vars[key], values=('关', '开'), state='normal')
        elif key == 'ai_template':
            widget = SelectBox(card, textvariable=dict_vars[key],
                               values=tuple(voice_ai.TEMPLATES), state='normal')
        else:
            widget = LineInput(card, textvariable=dict_vars[key])
        widget.grid(row=r, column=1, sticky='ew', pady=SPACING['xs'])
        dict_widgets[key] = widget
    r = hotword_row + len(dict_fields)
    ttk.Label(card, text='替换词表（每行 错词=正词）').grid(row=r, column=0, sticky='nw', pady=SPACING['xs'])
    replace_area = TextArea(card, height=TEXT_ROWS['sm'], wrap='none')
    replace_area.grid(row=r, column=1, sticky='ew', pady=SPACING['xs'])
    dict_widgets['replace'] = replace_area

    def field_value(settings, key):
        if key.startswith('offline.'):
            return str((settings.get('offline') or {}).get(key.split('.', 1)[1], ''))
        return str(settings[key])

    def fill_dictionary(dictionary):
        dictionary = dictionary or {}
        dict_vars['hotword'].set(','.join(dictionary.get('hotword') or ()))
        replace = dictionary.get('replace') or {}
        replace_area.delete('1.0', 'end')
        replace_area.insert('1.0', '\n'.join('%s=%s' % (wrong, right)
                                             for wrong, right in replace.items()))
        ai = dictionary.get('ai') or {}
        dict_vars['ai_enabled'].set('开' if ai.get('enabled') else '关')
        dict_vars['ai_template'].set(str(ai.get('template') or 'fix'))
        dict_vars['ai_prompt'].set(str(ai.get('prompt') or ''))

    def _dictionary_values():
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

    def fill(settings):
        for key, variable in variables.items():
            variable.set(field_value(settings, key))
        show_key_state()

    def save():
        values, offline = {}, {}
        for key, variable in variables.items():
            if key.startswith('offline.'):
                offline[key.split('.', 1)[1]] = variable.get()
            else:
                values[key] = variable.get()
        values['offline'] = offline
        try:
            dictionary = speech_api.normalize_dictionary(_dictionary_values())
            speech_api.save_settings(values, publish=save_json)
            speech_api.save_dictionary(dictionary, publish=save_json)
        except (ValueError, OSError) as error:
            hint.set('没有保存：%s' % error)
            return False
        win.destroy()
        return True

    def reset():
        fill(speech_api.DEFAULTS)
        fill_dictionary({'hotword': [], 'replace': {},
                         'ai': dict(speech_api.DICT_DEFAULTS['ai'])})
        hint.set('已填回默认值，点「保存」生效。')

    fill(speech_api.read_settings())
    fill_dictionary(speech_api.read_dictionary())
    variables['key_env'].trace_add('write', show_key_state)
    view.bind_wheel()
    bar = actions
    SecondaryButton(bar, text='恢复默认', command=reset).pack(side='left')
    PrimaryButton(bar, text='保存', command=save).pack(side='right')
    SecondaryButton(bar, text='取消', command=win.destroy).pack(side='right', padx=(SPACING['none'], BUTTON_GAP))
    win._pet_speech_vars, win._pet_speech_save, win._pet_speech_reset = variables, save, reset
    win._pet_speech_dict_vars, win._pet_speech_dict_fill = dict_vars, fill_dictionary
    win._pet_speech_hint, win._pet_speech_key_state = hint, key_state
    win._pet_speech_setup = setup_refs
    return win

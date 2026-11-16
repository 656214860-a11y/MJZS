"""模型管理 › 「语音识别…」弹窗（REQ-S01-71）：语音输入的后端与识别服务设置。

L4 只管表单；校验与写入在 L2 ``speech_api.save_settings``，由这里注入 ``agent.core.save`` 作发布器。
``backend`` 默认 ``offline``（本地 FunASR 子进程，逐句出字）；``cloud`` 为阿里云实时流式。
"""
import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk

import domain.speech_api as speech_api
from agent.core import save as save_json
from ui_tokens import BUTTON_GAP, DIALOG_CONTENT_PADDING, DIALOG_MIN_HEIGHT, FONTS, SPACING, TEXT_DESC
from ui_widgets import BaseDialog, Card, LineInput, PrimaryButton, SecondaryButton, SelectBox

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


def open_speech_settings(pet, parent=None):
    """``parent`` 是模型管理窗；外壳与模型管理的小窗同款：非模态、Escape 关闭、内容放进 Card。

    只给宽度下限、不写死尺寸：高度随内容（高 DPI、保存失败时多出的提示行）撑开。
    """
    win = BaseDialog(parent, '', modal=False, chrome=False)
    win.title(SPEECH_TITLE)
    win.minsize(TEXT_DESC['wraplength'] + 2 * DIALOG_CONTENT_PADDING, DIALOG_MIN_HEIGHT)
    win.transient(parent or None)
    win.bind('<Escape>', lambda event: win.destroy())
    card = Card(win)
    card.pack(fill='both', expand=True, padx=SPACING['md'], pady=SPACING['md'])
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

    def field_value(settings, key):
        if key.startswith('offline.'):
            return str((settings.get('offline') or {}).get(key.split('.', 1)[1], ''))
        return str(settings[key])

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
            speech_api.save_settings(values, publish=save_json)
        except (ValueError, OSError) as error:
            hint.set('没有保存：%s' % error)
            return False
        win.destroy()
        return True

    def reset():
        fill(speech_api.DEFAULTS)
        hint.set('已填回默认值，点「保存」生效。')

    fill(speech_api.read_settings())
    variables['key_env'].trace_add('write', show_key_state)
    bar = ttk.Frame(card)
    bar.grid(row=row + 2, column=0, columnspan=2, sticky='ew', pady=(SPACING['md'], SPACING['none']))
    SecondaryButton(bar, text='恢复默认', command=reset).pack(side='left')
    PrimaryButton(bar, text='保存', command=save).pack(side='right')
    SecondaryButton(bar, text='取消', command=win.destroy).pack(side='right', padx=(SPACING['none'], BUTTON_GAP))
    win._pet_speech_vars, win._pet_speech_save, win._pet_speech_reset = variables, save, reset
    win._pet_speech_hint, win._pet_speech_key_state = hint, key_state
    return win

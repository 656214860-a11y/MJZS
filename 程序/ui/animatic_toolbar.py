# -*- coding: utf-8 -*-
"""S04 分镜预演页顶紧凑工具条（REQ-S04-114/116，DES-S04-39）。

严格固定 5 个顶级交互控件：主按钮（生成／重新合成）、草图引擎下拉、
「声音 ▾」菜单钮、「在剪映中打开」、「预演设置」。全部使用统一组件，零弹窗。
"""
from pathlib import Path
from tkinter import StringVar, ttk

import stage_execution_service
from ui.animatic_prefs_bar import (
    SKETCH_ENGINE_OPTIONS, _key_for_label, _label_for_key, _persist_prefs,
)
from ui.animatic_view_state import (
    _open_in_jianying, _quiet, _refresh_files_panel, _safe_call,
)
from ui_tokens import SPACING
from ui_widgets import ContextMenu, PrimaryButton, SecondaryButton, SelectBox

_DEFAULT_ENGINE = 'text_card'
_AUDIO_FILETYPES = [('音频', '*.mp3 *.wav *.m4a *.aac *.flac *.ogg')]


def _set_status(page, message):
    status = getattr(page, 'status', None)
    setter = getattr(status, 'set', None)
    if callable(setter):
        setter(message)


def _tts_enabled(page):
    settings = getattr(page, 'settings', None) or {}
    return bool(settings.get('animatic_use_tts', True))


def apply_audio_action(page, state, action, *, track=None, enabled=None):
    """默认「声音 ▾」动作落盘实现：显式按轨导入、回收站移除与逐镜 TTS 开关。"""
    project = state.get('project')
    if action == 'toggle_tts':
        target = (not _tts_enabled(page)) if enabled is None else bool(enabled)
        ok = _persist_prefs(page, {'animatic_use_tts': target})
        if ok:
            _set_status(page, '已开启逐镜临时 TTS' if target else '已关闭逐镜临时 TTS（静音出片）')
        return ok
    if action == 'import' and track in ('track', 'music'):
        dialog = getattr(page, 'file_dialog', None)
        opener = getattr(dialog, 'open_files', None)
        if not callable(opener) or project is None:
            return False
        title = '导入整轨配音' if track == 'track' else '导入背景音乐'
        paths = opener(parent=getattr(page, 'win', None), title=title, filetypes=_AUDIO_FILETYPES)
        if not paths:
            return False
        outcome = _safe_call(
            page, lambda: stage_execution_service.import_animatic_audio(
                project, Path(paths[0]), track=track))
        if getattr(outcome, 'ok', False):
            _set_status(page, '已导入' + ('整轨配音' if track == 'track' else '背景音乐'))
            _refresh_files_panel(page)
            return True
        if outcome is not None:
            _set_status(page, str(getattr(outcome, 'reason', '导入音频失败')))
        return False
    if action == 'remove' and track in ('track', 'music'):
        if project is None:
            return False
        removed = _safe_call(
            page, lambda: stage_execution_service.remove_animatic_audio(project, track))
        if removed is None:
            return False
        label = '整轨配音' if track == 'track' else '背景音乐'
        if removed:
            _set_status(page, '已将%s移入回收站（共 %d 个文件）' % (label, len(removed)))
            _refresh_files_panel(page)
        else:
            _set_status(page, '当前没有已导入的' + label)
        return bool(removed)
    return False


def build_audio_menu(page, state, on_audio_action):
    """构建「声音 ▾」ContextMenu：5 项动作＋1 条分隔线，显式传递 track 与开关值。"""
    tts_on = _tts_enabled(page)
    tts_label = '逐镜临时 TTS（当前：开启）' if tts_on else '逐镜临时 TTS（当前：关闭）'
    menu = ContextMenu(getattr(page, 'win', None))
    menu.command('导入整轨配音…', lambda: on_audio_action('import', track='track'))
    menu.command('导入背景音乐…', lambda: on_audio_action('import', track='music'))
    menu.separator()
    menu.command(tts_label, lambda: on_audio_action('toggle_tts', enabled=not tts_on))
    menu.command('移除整轨配音', lambda: on_audio_action('remove', track='track'))
    menu.command('移除背景音乐', lambda: on_audio_action('remove', track='music'))
    return menu


def _default_open_jianying(page, state):
    if state.get('video') is None:
        _set_status(page, '请先生成分镜预演，再在剪映中打开')
        return
    _open_in_jianying(page, state)


def _current_engine_label(page):
    settings = getattr(page, 'settings', None) or {}
    return _label_for_key(
        SKETCH_ENGINE_OPTIONS, settings.get('animatic_sketch_backend'), _DEFAULT_ENGINE)


def _generate_label(state):
    return '重新合成' if state.get('video') is not None else '生成分镜预演'


def build_toolbar(parent, page, state, *, callbacks=None, **handlers):
    """构建 S04 页顶 1 行 5 入口工具条，返回句柄字典供无重建刷新。"""
    hooks = dict(callbacks or {})
    hooks.update(handlers)
    on_generate = hooks.get('on_generate')
    on_engine_change = hooks.get('on_engine_change')
    on_audio_action = hooks.get('on_audio_action')
    on_open_jianying = hooks.get('on_open_jianying')
    on_toggle_prefs = hooks.get('on_toggle_prefs')

    bar = ttk.Frame(parent)
    bar.pack(fill='x', pady=(SPACING['none'], SPACING['sm']))

    gen_btn = PrimaryButton(
        bar, text=_generate_label(state), width=0,
        command=lambda: on_generate() if callable(on_generate) else None)
    gen_btn.pack(side='left', padx=(SPACING['none'], SPACING['sm']))

    engine_var = StringVar(value=_current_engine_label(page))
    engine_box = SelectBox(
        bar, values=[label for _key, label in SKETCH_ENGINE_OPTIONS],
        textvariable=engine_var)
    engine_box.pack(side='left', padx=(SPACING['none'], SPACING['sm']))

    def select_engine(raw_value=None):
        chosen = engine_var.get() if raw_value is None else raw_value
        key = _key_for_label(SKETCH_ENGINE_OPTIONS, chosen, _DEFAULT_ENGINE)
        engine_var.set(_label_for_key(SKETCH_ENGINE_OPTIONS, key, _DEFAULT_ENGINE))
        _persist_prefs(page, {'animatic_sketch_backend': key})
        if callable(on_engine_change):
            on_engine_change(key)
        return key

    engine_box.bind('<<ComboboxSelected>>', lambda _event: select_engine())

    def handle_audio(action, **kwargs):
        if callable(on_audio_action):
            return on_audio_action(action, **kwargs)
        return apply_audio_action(page, state, action, **kwargs)

    audio_btn = SecondaryButton(bar, text='声音 ▾', width=0)

    def open_audio_menu():
        menu = build_audio_menu(page, state, handle_audio)
        x = _quiet(audio_btn.winfo_rootx, 0)
        y = _quiet(audio_btn.winfo_rooty, 0) + _quiet(audio_btn.winfo_height, 0)
        return menu.popup_at(x, y)

    audio_btn.configure(command=open_audio_menu)
    audio_btn.pack(side='left', padx=(SPACING['none'], SPACING['sm']))

    jianying_btn = SecondaryButton(
        bar, text='在剪映中打开', width=0,
        command=lambda: (on_open_jianying() if callable(on_open_jianying)
                         else _default_open_jianying(page, state)))
    jianying_btn.pack(side='left', padx=(SPACING['none'], SPACING['sm']))

    prefs_btn = SecondaryButton(
        bar, text='预演设置', width=0,
        command=lambda: on_toggle_prefs() if callable(on_toggle_prefs) else None)
    prefs_btn.pack(side='left')

    return {
        'frame': bar,
        'controls': (gen_btn, engine_box, audio_btn, jianying_btn, prefs_btn),
        'generate_btn': gen_btn,
        'engine_box': engine_box,
        'engine_var': engine_var,
        'audio_btn': audio_btn,
        'jianying_btn': jianying_btn,
        'prefs_btn': prefs_btn,
        'open_audio_menu': open_audio_menu,
        'select_engine': select_engine,
    }


def refresh_toolbar(handles, page, state):
    """无重建刷新主按钮文案与当前草图引擎。"""
    if not isinstance(handles, dict):
        return
    frame = handles.get('frame')
    if frame is None or not _quiet(frame.winfo_exists, False):
        return
    gen_btn = handles.get('generate_btn')
    if gen_btn is not None and _quiet(gen_btn.winfo_exists, False):
        gen_btn.configure(text=_generate_label(state))
    engine_var = handles.get('engine_var')
    if engine_var is not None:
        engine_var.set(_current_engine_label(page))

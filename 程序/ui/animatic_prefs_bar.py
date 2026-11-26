# -*- coding: utf-8 -*-
"""S04 预演页内偏好条（REQ-S04-110，DES-S04-34）。

零弹窗页内展开，配置草图引擎、已配 Google Flow 图片模型、本地参考图模型名、
2D 运镜与信息烧录开关、默认播放方式；只读模型池 gflow-* 条目，不触碰模型配置页。
"""
from tkinter import BooleanVar, StringVar, ttk

import infra.model_pool as model_pool
import stage_execution_service
from ui_tokens import SPACING
from ui_widgets import LineInput, SecondaryButton, SelectBox

GFLOW_EMPTY_OPTION = '（请先在模型管理添加 Google Flow）'

SKETCH_ENGINE_OPTIONS = (
    ('text_card', '文字分镜卡（零成本）'),
    ('gflow_cli', 'Google Flow（免费）'),
    ('comfy_local', '本地 ComfyUI'),
)

PLAYER_MODE_OPTIONS = (
    ('external', '本地默认播放器'),
    ('jianying', '剪映专业版'),
    ('inline', '页内试播'),
)


def gflow_model_ids(records=None):
    """从只读模型池提取 gflow-* 且 modality=='image' 的有序 ID 列表。"""
    if records is None:
        try:
            records = model_pool.pool() or {}
        except Exception:
            records = {}
    if not isinstance(records, dict):
        return []
    found = []
    for key, row in records.items():
        if not isinstance(key, str) or not key.startswith('gflow-'):
            continue
        if not isinstance(row, dict):
            continue
        if str(row.get('modality') or '').strip().lower() != 'image':
            continue
        found.append(key)
    return sorted(found)


def _label_for_key(options, key, default_key):
    mapping = dict(options)
    return mapping.get(str(key or '').strip(), mapping[default_key])


def _key_for_label(options, label, default_key):
    target = str(label or '').strip()
    for key, text in options:
        if target in (text, key):
            return key
    return default_key


def _set_status(page, message):
    status = getattr(page, 'status', None)
    setter = getattr(status, 'set', None)
    if callable(setter):
        setter(message)


def _persist_prefs(page, patch):
    """写入 desktop_settings.json（走 L3 发布器）；假宿主无 settings_file 时更新内存设置。"""
    current = dict(getattr(page, 'settings', None) or {})
    settings_file = getattr(page, 'settings_file', None)
    if settings_file:
        result = stage_execution_service.publish_desktop_preferences(
            settings_file, current, patch)
        if not getattr(result, 'ok', False):
            _set_status(page, str(getattr(result, 'reason', '保存预演设置失败')))
            return False
        merged = dict(getattr(result, 'data', None) or {**current, **patch})
    else:
        merged = {**current, **patch}
    existing = getattr(page, 'settings', None)
    if isinstance(existing, dict):
        existing.update(merged)
    else:
        page.settings = merged
    _set_status(page, '已保存预演设置')
    return True


def open_prefs_bar(page, state, *, container, on_saved=None):
    """在 container 内联渲染 6 项 S04 预演偏好；回车/保存落盘并收起，Esc/关闭收起。"""
    if container is None:
        return None
    for child in container.winfo_children():
        child.destroy()
    settings = dict(getattr(page, 'settings', None) or {})
    panel = ttk.Frame(container)
    panel.pack(fill='x', pady=(SPACING['xs'], SPACING['none']))

    row1 = ttk.Frame(panel)
    row1.pack(fill='x', pady=(SPACING['none'], SPACING['xs']))
    ttk.Label(row1, text='草图引擎').pack(side='left', padx=(SPACING['none'], SPACING['xs']))
    engine_var = StringVar(value=_label_for_key(
        SKETCH_ENGINE_OPTIONS, settings.get('animatic_sketch_backend'), 'text_card'))
    engine_box = SelectBox(
        row1, values=[label for _key, label in SKETCH_ENGINE_OPTIONS],
        textvariable=engine_var)
    engine_box.pack(side='left', padx=(SPACING['none'], SPACING['sm']))

    ttk.Label(row1, text='Google Flow 模型').pack(side='left', padx=(SPACING['none'], SPACING['xs']))
    ids = gflow_model_ids()
    gflow_values = tuple(ids) if ids else (GFLOW_EMPTY_OPTION,)
    current_gflow = str(settings.get('animatic_gflow_model') or '').strip()
    initial_gflow = current_gflow if current_gflow in ids else gflow_values[0]
    gflow_var = StringVar(value=initial_gflow)
    gflow_box = SelectBox(row1, values=gflow_values, textvariable=gflow_var)
    gflow_box.pack(side='left', padx=(SPACING['none'], SPACING['sm']))

    ttk.Label(row1, text='参考图模型名').pack(side='left', padx=(SPACING['none'], SPACING['xs']))
    ref_entry = LineInput(row1)
    ref_entry.pack(side='left', fill='x', expand=True)
    initial_ref = str(settings.get('animatic_reference_model') or '')
    if initial_ref:
        ref_entry.insert(0, initial_ref)

    row2 = ttk.Frame(panel)
    row2.pack(fill='x')
    ttk.Label(row2, text='默认播放').pack(side='left', padx=(SPACING['none'], SPACING['xs']))
    player_var = StringVar(value=_label_for_key(
        PLAYER_MODE_OPTIONS, settings.get('animatic_player_mode'), 'external'))
    player_box = SelectBox(
        row2, values=[label for _key, label in PLAYER_MODE_OPTIONS],
        textvariable=player_var)
    player_box.pack(side='left', padx=(SPACING['none'], SPACING['sm']))

    motion_var = BooleanVar(value=bool(settings.get('animatic_ken_burns', True)))
    ttk.Checkbutton(row2, text='启用 2D 运镜', variable=motion_var).pack(
        side='left', padx=(SPACING['none'], SPACING['sm']))
    overlay_var = BooleanVar(value=bool(settings.get('animatic_burn_overlay', True)))
    ttk.Checkbutton(row2, text='烧录镜号与字幕', variable=overlay_var).pack(
        side='left', padx=(SPACING['none'], SPACING['sm']))
    tts_var = BooleanVar(value=bool(settings.get('animatic_use_tts', True)))
    ttk.Checkbutton(row2, text='逐镜临时 TTS', variable=tts_var).pack(
        side='left', padx=(SPACING['none'], SPACING['sm']))

    def close(_event=None):
        state['edit_commit'] = None
        state['edit_cancel'] = None
        state['prefs_bar'] = None
        for child in container.winfo_children():
            child.destroy()

    def save(_event=None):
        chosen_gflow = gflow_var.get().strip()
        patch = {
            'animatic_sketch_backend': _key_for_label(
                SKETCH_ENGINE_OPTIONS, engine_var.get(), 'text_card'),
            'animatic_gflow_model': '' if chosen_gflow == GFLOW_EMPTY_OPTION else chosen_gflow,
            'animatic_reference_model': ref_entry.get().strip(),
            'animatic_ken_burns': bool(motion_var.get()),
            'animatic_burn_overlay': bool(overlay_var.get()),
            'animatic_use_tts': bool(tts_var.get()),
            'animatic_player_mode': _key_for_label(
                PLAYER_MODE_OPTIONS, player_var.get(), 'external'),
        }
        if not _persist_prefs(page, patch):
            return False
        close()
        if callable(on_saved):
            on_saved(patch)
        return True

    SecondaryButton(row2, text='关闭', command=close).pack(
        side='right', padx=(SPACING['xs'], SPACING['none']))
    SecondaryButton(row2, text='保存', command=save).pack(side='right')

    state['edit_commit'] = save
    state['edit_cancel'] = close
    state['prefs_bar'] = panel
    for widget in (panel, ref_entry, engine_box, gflow_box, player_box):
        widget.bind('<Escape>', close)
    ref_entry.bind('<Return>', save)
    ref_entry.focus_set()
    return panel


def _open_inline_edit(page, state, label, initial, apply):
    """页内单行编辑条：回车提交、Esc 取消；``apply`` 返回 False 时保留不收起。"""
    box = state.get('edit_box')
    if box is None:
        return
    for child in box.winfo_children():
        child.destroy()
    ttk.Label(box, text=label).pack(side='left', padx=(SPACING['none'], SPACING['sm']))
    entry = LineInput(box)
    entry.pack(side='left', fill='x', expand=True)
    if initial:
        entry.insert(0, initial)

    def close(_event=None):
        state['edit_commit'] = None
        state['edit_cancel'] = None
        for child in box.winfo_children():
            child.destroy()

    def commit(_event=None):
        if apply(entry.get()) is not False:
            close()

    state['edit_commit'] = commit
    state['edit_cancel'] = close
    entry.bind('<Return>', commit)
    entry.bind('<Escape>', close)
    entry.focus_set()

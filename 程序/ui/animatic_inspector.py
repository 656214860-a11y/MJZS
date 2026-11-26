# -*- coding: utf-8 -*-
"""S04 分镜预演右栏镜头检查器与管理面板（REQ-S04-115/116，DES-S04-39）。

展示当前选中镜头的大图预览、版本号切换、元信息、带来源徽章的命中参考图、
直达入口（「导入参考图…」「打开草图目录」）、单镜快捷操作与三态审核按钮。
"""
from tkinter import StringVar, ttk

from ui import asset_thumbs
from ui.animatic_view_state import _image_versions, _quiet, _shot_image
from ui_tokens import SPACING, WRAPLENGTH
from ui_widgets import HintLabel, SecondaryButton, SelectBox

REVIEW_LABELS = (
    ('pending', '待审'),
    ('approved', '通过'),
    ('needs_revision', '需修改'),
)
_REVIEW_MAP = dict(REVIEW_LABELS)
_NO_VERSION_OPTION = '无版本'
_DEFAULT_PREVIEW_SIZE = SPACING['2xl'] * 6


def review_label(status):
    """把审核状态键映射为中文标签；缺失或非法值归为待审。"""
    return _REVIEW_MAP.get(str(status or '').strip(), '待审')


def _normalized_review(row):
    raw = str((row or {}).get('review_status') or '').strip()
    return raw if raw in _REVIEW_MAP else 'pending'


def _format_meta_text(row, shot_meta):
    meta = shot_meta if isinstance(shot_meta, dict) else {}
    parts = []
    scene = str(meta.get('scene_id') or meta.get('scene') or '').strip()
    if scene:
        parts.append('场次：' + scene)
    parts.append('镜号：' + str(row.get('id') or ''))
    size = str(meta.get('shot_size') or meta.get('scale') or '').strip()
    if size:
        parts.append('景别：' + size)
    motion = str(meta.get('camera_movement') or meta.get('camera')
                 or meta.get('movement') or '').strip()
    if motion:
        parts.append('运镜：' + motion)
    parts.append('时长：%s 秒' % (row.get('seconds') or 0))
    chars = [str(item).strip() for item in (meta.get('characters') or ()) if str(item).strip()]
    if chars:
        parts.append('角色：' + '、'.join(chars))
    loc = str(meta.get('location') or '').strip()
    if loc:
        parts.append('场景：' + loc)
    note = str(row.get('note') or '').strip()
    if note:
        parts.append('批注：' + note)
    return '  |  '.join(parts)


def _preview_size(state):
    metrics = state.get('layout_metrics') if isinstance(state, dict) else None
    size = int((metrics or {}).get('cover_size') or _DEFAULT_PREVIEW_SIZE)
    return max(SPACING['2xl'] * 3, size)


def _render_preview(handles, state, row):
    label = handles['preview_label']
    shot_id = row.get('id')
    version = int(row.get('image_version') or 0)
    image_path = _shot_image(state, shot_id, version) if state.get('project') else None
    image = (asset_thumbs.thumbnail(label, image_path, size=_preview_size(state))
             if image_path is not None else None)
    if image is not None:
        label._inspector_thumb = image
        label.configure(image=image, text='')
    else:
        label._inspector_thumb = None
        label.configure(image='', text='%s 尚未生成草图；可点击「重做」或「换图」' % shot_id)


def _render_versions(handles, state, row):
    shot_id = row.get('id')
    versions = list(_image_versions(state, shot_id)) if state.get('project') else []
    handles['updating_version'] = True
    try:
        box = handles['version_box']
        var = handles['version_var']
        if versions:
            labels = tuple('v%d' % num for num in versions)
            box.set_values(labels)
            current = int(row.get('image_version') or 0)
            var.set('v%d' % current if current in versions else labels[-1])
            box.configure(state='readonly')
        else:
            box.set_values((_NO_VERSION_OPTION,))
            var.set(_NO_VERSION_OPTION)
            box.configure(state='disabled')
    finally:
        handles['updating_version'] = False


def _render_refs(handles, ref_badges):
    box = handles['refs_box']
    for child in box.winfo_children():
        child.destroy()
    labels = []
    items = list(ref_badges or ())
    if not items:
        empty = HintLabel(box, text='暂无命中参考图（可导入参考图或复用 S05 资产）')
        empty.pack(anchor='w')
        labels.append(empty)
    else:
        for badge in items[:8]:
            source = str(badge.get('source') or '未分类')
            name = str(badge.get('label') or '').strip()
            text = '[%s] %s' % (source, name) if name else '[%s]' % source
            item_label = HintLabel(box, text=text)
            item_label.pack(side='left', padx=(SPACING['none'], SPACING['sm']))
            labels.append(item_label)
    handles['ref_labels'] = labels


def _sync_review_buttons(handles, status):
    for key, btn in handles['review_buttons'].items():
        if _quiet(btn.winfo_exists, False):
            style = 'Tokens.Primary.TButton' if key == status else 'Tokens.Secondary.TButton'
            btn.configure(style=style)


def build_inspector(parent, page, state, callbacks):
    """构建右栏当前镜头管理与大图预览区，返回句柄字典供 render_inspector 复用。"""
    hooks = dict(callbacks or {})
    card = ttk.Frame(parent, style='Card.TFrame', padding=SPACING['sm'])
    card.pack(fill='both', expand=True)

    handles = {
        'frame': card,
        'current_shot_id': None,
        'current_row': None,
        'updating_version': False,
        'ref_labels': [],
        'review_buttons': {},
        'action_buttons': {},
    }

    def fire(name, *args):
        cb = hooks.get(name)
        if callable(cb):
            cb(*args)

    header = ttk.Frame(card)
    header.pack(fill='x', pady=(SPACING['none'], SPACING['xs']))
    title_label = ttk.Label(header, text='当前镜头', style='Tokens.Title.TLabel')
    title_label.pack(side='left')
    handles['title_label'] = title_label

    version_var = StringVar(value=_NO_VERSION_OPTION)
    version_box = SelectBox(header, values=(_NO_VERSION_OPTION,), textvariable=version_var)
    version_box.pack(side='right')
    ttk.Label(header, text='版本').pack(side='right', padx=(SPACING['none'], SPACING['xs']))
    handles['version_var'] = version_var
    handles['version_box'] = version_box

    def on_version_selected(_event=None):
        if handles['updating_version']:
            return
        sid = handles.get('current_shot_id')
        raw = str(version_var.get() or '').strip().lower()
        if sid and raw.startswith('v') and raw[1:].isdigit():
            fire('on_version', sid, int(raw[1:]))

    version_box.bind('<<ComboboxSelected>>', on_version_selected)

    preview_frame = ttk.Frame(card)
    preview_frame.pack(fill='both', expand=True, pady=(SPACING['none'], SPACING['xs']))
    preview_label = ttk.Label(preview_frame, text='请从时间线选择镜头', anchor='center')
    preview_label.pack(fill='both', expand=True)
    handles['preview_label'] = preview_label

    meta_label = ttk.Label(card, text='', wraplength=WRAPLENGTH['sm'], justify='left')
    meta_label.pack(fill='x', anchor='w', pady=(SPACING['none'], SPACING['xs']))
    handles['meta_label'] = meta_label

    ref_head = ttk.Frame(card)
    ref_head.pack(fill='x', pady=(SPACING['none'], SPACING['xs']))
    ttk.Label(ref_head, text='命中参考图').pack(side='left')
    open_dir_btn = SecondaryButton(
        ref_head, text='打开草图目录', width=0,
        command=lambda: (fire('on_open_shot_dir', handles['current_shot_id'])
                         if handles.get('current_shot_id') else None))
    open_dir_btn.pack(side='right')
    import_ref_btn = SecondaryButton(
        ref_head, text='导入参考图…', width=0,
        command=lambda: fire('on_import_ref'))
    import_ref_btn.pack(side='right', padx=(SPACING['none'], SPACING['xs']))
    handles['action_buttons']['import_ref'] = import_ref_btn
    handles['action_buttons']['open_dir'] = open_dir_btn

    refs_box = ttk.Frame(card)
    refs_box.pack(fill='x', pady=(SPACING['none'], SPACING['xs']))
    handles['refs_box'] = refs_box

    actions_row = ttk.Frame(card)
    actions_row.pack(fill='x', pady=(SPACING['none'], SPACING['xs']))
    specs = (
        ('duration', '改时长', lambda: fire('on_duration', handles['current_row'])),
        ('redo', '重做', lambda: fire('on_redo', handles['current_shot_id'])),
        ('replace', '换图', lambda: fire('on_replace', handles['current_shot_id'])),
        ('audition', '试听对白', lambda: fire('on_audition', handles['current_row'])),
        ('note', '批注', lambda: fire('on_note', handles['current_row'])),
    )
    for key, text, handler in specs:
        btn = SecondaryButton(
            actions_row, text=text, width=0,
            command=lambda fn=handler: fn() if handles.get('current_row') is not None else None)
        btn.pack(side='left', padx=(SPACING['none'], SPACING['xs']))
        handles['action_buttons'][key] = btn

    review_row = ttk.Frame(card)
    review_row.pack(fill='x')
    ttk.Label(review_row, text='审核').pack(side='left', padx=(SPACING['none'], SPACING['xs']))
    for status_key, text in REVIEW_LABELS:
        btn = SecondaryButton(
            review_row, text=text, width=0,
            command=lambda st=status_key: (
                fire('on_review', handles['current_shot_id'], st)
                if handles.get('current_shot_id') else None))
        btn.pack(side='left', padx=(SPACING['none'], SPACING['xs']))
        handles['review_buttons'][status_key] = btn

    return handles


def render_inspector(handles, page, state, row, shot_meta, ref_badges):
    """刷新右栏当前选中镜头的大图、版本、元信息、命中参考图徽章与审核态。"""
    if not isinstance(handles, dict):
        return
    frame = handles.get('frame')
    if frame is None or not _quiet(frame.winfo_exists, False):
        return
    if not isinstance(row, dict) or not row.get('id'):
        handles['current_shot_id'] = None
        handles['current_row'] = None
        handles['title_label'].configure(text='当前镜头（未选中）')
        handles['preview_label'].configure(image='', text='请从下方时间线选择一个镜头')
        handles['meta_label'].configure(text='')
        _render_refs(handles, ())
        _sync_review_buttons(handles, '')
        return
    shot_id = str(row['id'])
    status = _normalized_review(row)
    handles['current_shot_id'] = shot_id
    handles['current_row'] = row
    handles['title_label'].configure(text='%s · %s' % (shot_id, review_label(status)))
    _render_versions(handles, state, row)
    _render_preview(handles, state, row)
    handles['meta_label'].configure(text=_format_meta_text(row, shot_meta))
    _render_refs(handles, ref_badges)
    _sync_review_buttons(handles, status)

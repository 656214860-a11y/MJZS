# -*- coding: utf-8 -*-
"""S04 分镜预演工作台：页顶工具条＋左右分栏管理预览＋筛选时间线（REQ-S04-95…116）。

页顶 5 入口紧凑工具条；宽屏左右分栏（左：空态 3 步引导／整片动态预览；右：当前选中
镜头大图、元信息、带来源徽章的命中参考图与单镜快捷／审核操作），窄屏 <1200px 自动
上下堆叠；下方带场次与状态筛选的分页时间线（20 镜/页）；保留全部右键与底栏发送键，
有可播放版本后才出现三项确认与「锁定」。业务一律走 L3 网关，零弹窗。
"""
import tkinter as tk
from pathlib import Path
from tkinter import BooleanVar, StringVar, ttk

import stage_execution_service
import ui.desktop_files_panel_filters as files_panel_filters
from contract.pet_bus import stage_step
from contract.stage_path_service import shared_reference_dir
from domain import animatic_audio
from domain.animatic_references import CATEGORIES
from infra import file_index
from infra.pet_state import PAGE_OF
from ui import asset_thumbs
from ui.animatic_inspector import build_inspector, render_inspector
from ui.animatic_player import fit_video_preview
from ui.animatic_prefs_bar import _open_inline_edit, open_prefs_bar
from ui.animatic_toolbar import apply_audio_action, build_toolbar, refresh_toolbar
from ui.animatic_view_state import (
    EMPTY_GUIDE_STEPS, PLAYER_CAPTIONS, SCENE_ALL_LABEL, TIMELINE_STATUS_FILTERS,
    _TIMELINE_CELL_HEIGHT, _TIMELINE_THUMB_SIZE, _after_sketch,
    _apply_sketch, _audio_mode, _audition_dialogue, _board_names,
    _confirmed, _dispatch_generate, _dispatch_lock, _dispatch_redo_revisions,
    _dispatch_redo_shot, _image_versions, _import_references_dialog, _is_alive,
    _load_board, _locked, _manifest, _music_text, _open_in_jianying,
    _open_shot_dir, _open_video, _playable_video, _quiet, _reclassify,
    _register_panel, _register_send_key_impl, _rename_reference, _reply_note,
    _safe_call, _shot_image, _timeline_width, _update_summary, _version_tag,
    animatic_layout_metrics, filtered_timeline_shots, format_status_summary,
    load_timeline_for_show, parse_animatic_command, player_mode_of,
    scene_filter_options, schedule_debounced_layout, shot_cell_caption,
    shot_dialogue_seconds, shot_page_for_id, shot_prompt_text,
    timeline_page_slice,
)
from ui_tokens import COLORS, SPACING, WRAPLENGTH
from ui_widgets import (ContextMenu, DescriptionBlock, HintLabel,
                        PrimaryButton, SecondaryButton, SelectBox)

_CHECK_LABELS = (('rhythm', '已确认节奏'), ('duration', '已确认时长'),
                 ('dialogue_sync', '已确认对白同步'))
_TIMELINE_GUTTER_WIDTH = 56
_STATUS_LABEL_BY_KEY = dict(TIMELINE_STATUS_FILTERS)
_STATUS_KEY_BY_LABEL = {label: key for key, label in TIMELINE_STATUS_FILTERS}


# ── 布局：引导 / 页顶工具条 / 左右分栏工作区 / 筛选条 / 时间线 / 确认条 ─────────

def _guide(page, frame):
    """无已采用分镜的引导页：一段说明＋一颗跳回 S03 的主按钮。"""
    DescriptionBlock(
        frame, text='请先在初步分镜完成并采用分镜，再回来生成分镜预演。').pack(
        anchor='w', pady=SPACING['xs'])
    PrimaryButton(frame, text='去' + stage_step('storyboard'),
                  command=lambda: page.go(PAGE_OF['storyboard'])).pack(
        anchor='w', pady=SPACING['sm'])


def _build_confirm_bar(page, state):
    """有可播放版本才出现的确认条；先占在页底，保证小窗口里看得见。"""
    if state['video'] is None:
        return
    frame = state['frame']
    host = getattr(page, 'stage_area', None)
    bar = ttk.Frame(host if host is not None else frame)
    padding = (SPACING['sm'], SPACING['none'])
    if host is None:
        bar.pack(side='bottom', fill='x', pady=padding)
    else:
        # 桌面画布里的高页面可以滚动，确认栏固定在画布与共用输入框之间。
        def show_bar(_event=None):
            bar.pack(side='bottom', before=page.canvas, fill='x', pady=padding)
        frame.bind('<Map>', show_bar, add='+')
        frame.bind('<Unmap>', lambda _event: bar.pack_forget(), add='+')
        frame.bind('<Destroy>', lambda _event: bar.destroy(), add='+')
        if frame.winfo_ismapped():
            show_bar()
    SecondaryButton(bar, text='锁定',
                    command=lambda: _lock(page, state)).pack(side='right')
    for key, label in _CHECK_LABELS:
        var = BooleanVar(value=bool(state.get('confirmed')))
        ttk.Checkbutton(bar, text=label, variable=var).pack(
            side='left', padx=(SPACING['none'], SPACING['sm']))
        state['checks'][key] = var
    state['confirm_bar'] = bar


def _build_toolbar(page, state):
    def on_audio(action, **kwargs):
        if apply_audio_action(page, state, action, **kwargs):
            _render_timeline(page, state)
            _update_summary(page, state)

    def on_jianying():
        if state.get('video') is None:
            page.status.set('请先生成分镜预演，再在剪映中打开')
            return
        _open_in_jianying(page, state)

    state['toolbar'] = build_toolbar(
        state['frame'], page, state,
        on_generate=lambda: run_command(
            page, state, '重新合成' if state.get('video') is not None else ''),
        on_engine_change=lambda _key: _update_summary(page, state),
        on_audio_action=on_audio,
        on_open_jianying=on_jianying,
        on_toggle_prefs=lambda: _open_prefs(page, state),
    )


def _layout_metrics(page, state):
    metrics = state.get('layout_metrics')
    if metrics is None:
        metrics = animatic_layout_metrics(getattr(page, 'win', None))
        state['layout_metrics'] = metrics
    return metrics


def _layout_workbench(page, state):
    """REQ-S04-116：宽屏 >=1200px 左右分栏，窄屏 <1200px 自动上下堆叠防裁切。"""
    wb = state.get('workbench_box')
    left = state.get('player_box')
    right = state.get('inspector_box')
    if not (wb and left and right and _quiet(wb.winfo_exists, False)):
        return
    split = bool(_layout_metrics(page, state).get('split'))
    if split:
        wb.columnconfigure(0, weight=1, uniform='wb')
        wb.columnconfigure(1, weight=1, uniform='wb')
        left.grid(row=0, column=0, sticky='nsew',
                  padx=(SPACING['none'], SPACING['sm']), pady=SPACING['none'])
        right.grid(row=0, column=1, sticky='nsew',
                   padx=SPACING['none'], pady=SPACING['none'])
    else:
        wb.columnconfigure(0, weight=1, uniform='')
        wb.columnconfigure(1, weight=0, uniform='')
        left.grid(row=0, column=0, sticky='nsew',
                  padx=SPACING['none'], pady=(SPACING['none'], SPACING['sm']))
        right.grid(row=1, column=0, sticky='nsew',
                   padx=SPACING['none'], pady=SPACING['none'])


def _inspector_callbacks(page, state):
    def on_import_ref():
        if _import_references_dialog(page, state):
            _render_inspector(page, state)

    return {
        'on_version': lambda sid, ver: _apply_shot_update(page, state, sid, image_version=ver),
        'on_duration': lambda row: _open_inline_edit(
            page, state, '时长（2–15 秒）', str(row.get('seconds') or ''),
            lambda value, sid=row['id']: _apply_seconds(page, state, sid, value)),
        'on_redo': lambda sid: _redo_shot(page, state, sid),
        'on_replace': lambda sid: _replace_shot_image(page, state, sid),
        'on_audition': lambda row: _audition_dialogue(page, state, row),
        'on_note': lambda row: _open_inline_edit(
            page, state, '批注', str(row.get('note') or ''),
            lambda value, sid=row['id']: _apply_shot_update(page, state, sid, note=value)),
        'on_review': lambda sid, st: _apply_shot_update(page, state, sid, review_status=st),
        'on_import_ref': on_import_ref,
        'on_open_shot_dir': lambda sid: _open_shot_dir(page, state, sid),
    }


def _build_workbench(page, state):
    wb = ttk.Frame(state['frame'])
    wb.pack(fill='both', expand=True, pady=(SPACING['none'], SPACING['sm']))
    left = ttk.Frame(wb)
    right = ttk.Frame(wb)
    state['workbench_box'] = wb
    state['player_box'] = left
    state['inspector_box'] = right
    left.bind('<Button-3>', lambda event: video_context_menu(page, state).popup(event))
    state['inspector'] = build_inspector(right, page, state, _inspector_callbacks(page, state))
    _layout_workbench(page, state)
    _render_player(page, state)
    _render_inspector(page, state)


def _bind_video_menu_recursive(widget, page, state):
    handler = lambda event: video_context_menu(page, state).popup(event)
    widget.bind('<Button-3>', handler)
    for child in widget.winfo_children():
        _bind_video_menu_recursive(child, page, state)


def _render_player(page, state):
    """REQ-S04-106/116：有版本渲染外置优先轻量封面／按需内播；无版本显示 3 步空态引导。"""
    box = state.get('player_box')
    if box is None or not _quiet(box.winfo_exists, False):
        return
    metrics = _layout_metrics(page, state)
    for child in box.winfo_children():
        child.destroy()
    state['video_view'] = None
    state['player_cover'] = None
    if state['video'] is not None:
        if state.get('inline_player'):
            from ui.animatic_player import VideoPreview
            view = VideoPreview(box, state['video'], page.status,
                                lambda event: video_context_menu(page, state).popup(event))
            view._animatic_default_height = _quiet(lambda: int(float(view.cget('height') or 0)), 0)
            fit_video_preview(view, state, metrics)
            view.pack(fill='both', expand=True)
            state['video_view'] = view
            return
        cover_height = metrics.get('player_height') or SPACING['2xl'] * 6
        cover_box = ttk.Frame(box, height=cover_height, style='Card.TFrame', takefocus=True)
        cover_box.pack_propagate(False)
        cover_box.pack(fill='both', expand=True)
        caption = PLAYER_CAPTIONS.get(player_mode_of(page), PLAYER_CAPTIONS['external'])
        cover = ttk.Label(cover_box, text=caption, compound='top', anchor='center')
        image = asset_thumbs.media_thumbnail(cover_box, state['video'], size=metrics['cover_size'])
        if image is not None:
            cover._animatic_thumb = image
            cover.configure(image=image)
        cover.pack(fill='both', expand=True)
        state['player_cover'] = cover_box
        for target in (cover_box, cover):
            target.bind('<Button-1>', lambda _event: _activate_player(page, state))
            target.bind('<Button-3>', lambda event: video_context_menu(page, state).popup(event))
        cover_box.bind('<space>', lambda _event: _activate_player(page, state))
        cover_box.bind('<Return>', lambda _event: _activate_player(page, state))
        return
    guide = ttk.Frame(box, style='Card.TFrame', padding=SPACING['sm'])
    guide.pack(fill='both', expand=True)
    ttk.Label(guide, text='分镜预演 · 三步快速出片', style='Tokens.Title.TLabel').pack(
        anchor='w', pady=(SPACING['none'], SPACING['xs']))
    for step in EMPTY_GUIDE_STEPS:
        ttk.Label(guide, text=step, wraplength=WRAPLENGTH['sm'], justify='left').pack(
            anchor='w', pady=(SPACING['none'], SPACING['xs']))
    _bind_video_menu_recursive(guide, page, state)


def _render_inspector(page, state):
    """REQ-S04-116：刷新右栏选中镜头大图与元信息，有视频后也不被封面锁死。"""
    handles = state.get('inspector')
    if handles is None:
        return
    rows = [row for row in (state.get('timeline') or {}).get('shots') or []
            if isinstance(row, dict)]
    selected = state.get('selected_shot')
    row = next((item for item in rows if item.get('id') == selected), None)
    if row is None and rows:
        row = rows[0]
        state['selected_shot'] = row.get('id')
    meta = (state.get('board') or {}).get(str(row.get('id')), {}) if row else {}
    badges = (_quiet(lambda: stage_execution_service.shot_ref_details(
        state['project'], meta), ()) if row else ())
    render_inspector(handles, page, state, row, meta, badges)
    preview = handles.get('preview_label')
    if row and preview is not None and str(_quiet(lambda: preview.cget('image'), '')):
        preview.configure(text='%s 当前镜头草图' % row['id'], compound='top')


def _sync_filter_options(state):
    controls = state.get('filter_controls')
    if not controls:
        return
    options = scene_filter_options(state.get('board'))
    controls['scene_box'].set_values(options)
    current = state.get('filter_scene') or SCENE_ALL_LABEL
    if current not in options:
        state['filter_scene'] = ''
        current = SCENE_ALL_LABEL
    controls['scene_var'].set(current)
    controls['status_var'].set(_STATUS_LABEL_BY_KEY.get(state.get('filter_status', 'all'), '全部'))


def _build_filter_bar(page, state):
    bar = ttk.Frame(state['frame'])
    bar.pack(fill='x', pady=(SPACING['none'], SPACING['xs']))
    scene_var = StringVar(value=SCENE_ALL_LABEL)
    scene_box = SelectBox(bar, values=scene_filter_options(state.get('board')),
                          textvariable=scene_var)
    scene_box.pack(side='left', padx=(SPACING['none'], SPACING['sm']))
    status_var = StringVar(value='全部')
    status_box = SelectBox(bar, values=[label for _k, label in TIMELINE_STATUS_FILTERS],
                           textvariable=status_var)
    status_box.pack(side='left', padx=(SPACING['none'], SPACING['sm']))
    redo_btn = SecondaryButton(
        bar, text='重做全部需修改', width=0,
        command=lambda: _redo_revision_shots(page, state))
    redo_btn.pack(side='right')
    scene_box.bind('<<ComboboxSelected>>', lambda _e: set_timeline_filter(
        page, state, scene='' if scene_var.get() == SCENE_ALL_LABEL else scene_var.get()))
    status_box.bind('<<ComboboxSelected>>', lambda _e: set_timeline_filter(
        page, state, status=_STATUS_KEY_BY_LABEL.get(status_var.get(), 'all')))
    state['filter_bar'] = bar
    state['filter_controls'] = {
        'scene_box': scene_box, 'scene_var': scene_var,
        'status_box': status_box, 'status_var': status_var,
        'redo_revisions_btn': redo_btn,
    }


def set_timeline_filter(page, state, *, scene=None, status=None):
    """REQ-S04-115/116：切换场次／状态筛选并从第 1 页重绘时间线与右栏检查器。"""
    if scene is not None:
        state['filter_scene'] = '' if scene in ('', SCENE_ALL_LABEL) else str(scene).strip()
    if status is not None:
        key = _STATUS_KEY_BY_LABEL.get(str(status).strip(), str(status).strip() or 'all')
        state['filter_status'] = key
    state['timeline_page'] = 1
    _sync_filter_options(state)
    _render_timeline(page, state)
    _render_inspector(page, state)


def _build_tracks(page, state):
    box = ttk.Frame(state['frame'])
    box.pack(fill='x', pady=(SPACING['none'], SPACING['sm']))
    state['timeline_box'] = box
    _render_timeline(page, state)


def _build_editor(page, state):
    box = ttk.Frame(state['frame'])
    box.pack(fill='x', pady=(SPACING['none'], SPACING['xs']))
    state['edit_box'] = box


def _build_info(page, state):
    label = DescriptionBlock(
        state['frame'], text='镜头格右键可重做、换图、改时长、切版本、看提示词、写批注。')
    label.pack(fill='x', anchor='w')
    state['info_label'] = label


def _sync_layout_metrics(page, state):
    if not _is_alive(page, state):
        return
    metrics = animatic_layout_metrics(getattr(page, 'win', None))
    if metrics == state.get('layout_metrics'):
        return
    state['layout_metrics'] = metrics
    _layout_workbench(page, state)
    view = state.get('video_view')
    if state.get('video') is not None and view is not None and _quiet(view.winfo_exists, False):
        fit_video_preview(view, state, metrics)
    else:
        _render_player(page, state)
    _render_inspector(page, state)
    focused_shot = _quiet(state['frame'].focus_get) in state.get('shot_widgets', {}).values()
    _render_timeline(page, state)
    target = state['shot_widgets'].get(state.get('selected_shot'))
    if focused_shot and target is not None:
        target.focus_set()
    refit = getattr(page, 'fit_content', None)
    if callable(refit):
        refit()


def _watch_layout_metrics(page, state):
    state['frame'].bind(
        '<Configure>',
        lambda _event: schedule_debounced_layout(
            state, lambda: _sync_layout_metrics(page, state)),
        add='+')


def _track_gutter(parent, text=''):
    gutter = ttk.Frame(parent, width=_TIMELINE_GUTTER_WIDTH)
    gutter.pack_propagate(False)
    gutter.pack(side='left', padx=(SPACING['none'], SPACING['sm']))
    if text:
        ttk.Label(gutter, text=text).pack(side='left')
    return gutter


def set_timeline_page(page, state, page_number):
    """REQ-S04-108：切换时间线页码并重绘当前页（每页最多 20 镜）。"""
    state['timeline_page'] = int(page_number)
    _render_timeline(page, state)


def _render_timeline(page, state):
    """重画分页横向时间线：仅渲染筛选后当前页 ≤20 镜（镜头格＋对白轨＋音乐轨）。"""
    box = state['timeline_box']
    metrics = _layout_metrics(page, state)
    for child in box.winfo_children():
        child.destroy()
    shots = filtered_timeline_shots(state)
    if shots and not any(row.get('id') == state.get('selected_shot') for row in shots):
        state['selected_shot'] = shots[0].get('id')
    page_shots, clamped_page, total_pages = timeline_page_slice(
        shots, state.get('timeline_page', 1))
    state['timeline_page'] = clamped_page
    state['timeline_total_pages'] = total_pages
    state['pager_bar'] = None
    if total_pages > 1:
        pager = ttk.Frame(box)
        pager.pack(fill='x', pady=(SPACING['none'], SPACING['xs']))
        prev_btn = SecondaryButton(
            pager, text='上一页',
            command=lambda: set_timeline_page(page, state, clamped_page - 1))
        if clamped_page <= 1:
            prev_btn.configure(state='disabled')
        prev_btn.pack(side='left', padx=(SPACING['none'], SPACING['sm']))
        ttk.Label(pager, text='第 %d/%d 页（共 %d 镜）' % (
            clamped_page, total_pages, len(shots))).pack(side='left')
        next_btn = SecondaryButton(
            pager, text='下一页',
            command=lambda: set_timeline_page(page, state, clamped_page + 1))
        if clamped_page >= total_pages:
            next_btn.configure(state='disabled')
        next_btn.pack(side='left', padx=(SPACING['sm'], SPACING['none']))
        state['pager_bar'] = pager
    state['shot_widgets'] = {}
    if not shots:
        HintLabel(box, text='当前筛选条件下无匹配镜头').pack(anchor='w', pady=SPACING['xs'])
        return
    canvas = tk.Canvas(box, highlightthickness=0, bg=COLORS['background_primary'])
    scrollbar = ttk.Scrollbar(box, orient='horizontal', command=canvas.xview)
    canvas.configure(xscrollcommand=scrollbar.set)
    inner = ttk.Frame(canvas)
    canvas.create_window((0, 0), window=inner, anchor='nw')

    def sync_scroll_region(_event=None):
        canvas.configure(scrollregion=canvas.bbox('all'),
                         height=max(1, inner.winfo_reqheight()))

    inner.bind('<Configure>', sync_scroll_region)
    canvas.bind('<Shift-MouseWheel>', lambda event:
                (canvas.xview_scroll(-1 if event.delta > 0 else 1, 'units'), 'break')[-1])
    canvas.pack(fill='x')
    scrollbar.pack(fill='x')
    state['timeline_canvas'] = canvas
    shots_bar = ttk.Frame(inner)
    shots_bar.pack(fill='x')
    _track_gutter(shots_bar)
    for row in page_shots:
        _shot_cell(page, state, shots_bar, row, metrics)
    dialogue = ttk.Frame(inner)
    dialogue.pack(fill='x')
    _track_gutter(dialogue, '对白轨')
    for row in page_shots:
        _dialogue_cell(state, dialogue, row)
    music = ttk.Frame(inner)
    music.pack(fill='x')
    _track_gutter(music, '音乐轨')
    ttk.Label(music, text=_music_text(state)).pack(side='left')
    sync_scroll_region()


def _paint_shot_selection(state):
    selected = state.get('selected_shot')
    for sid, widget in (state.get('shot_widgets') or {}).items():
        if not _quiet(widget.winfo_exists, False):
            continue
        style = 'SelectedShot.TFrame' if sid == selected else 'Card.TFrame'
        widget.configure(style=style)


def _select_shot(page, state, shot_id, *, focus=False):
    """选中时间线镜头格：跨页自动切页，右栏检查器实时刷新大图与元信息。"""
    rows = filtered_timeline_shots(state)
    if not any(row.get('id') == shot_id for row in rows):
        all_rows = [item for item in (state.get('timeline') or {}).get('shots') or []
                    if isinstance(item, dict)]
        if not any(row.get('id') == shot_id for row in all_rows):
            return False
        rows = all_rows
    state['selected_shot'] = shot_id
    widget = (state.get('shot_widgets') or {}).get(shot_id)
    if widget is None or not _quiet(widget.winfo_exists, False):
        state['timeline_page'] = shot_page_for_id(rows, shot_id)
        _render_timeline(page, state)
        widget = (state.get('shot_widgets') or {}).get(shot_id)
    else:
        _paint_shot_selection(state)
    _render_inspector(page, state)
    if focus and widget is not None:
        _quiet(widget.focus_set)
    return True


def _select_neighbor_shot(page, state, shot_id, offset):
    rows = filtered_timeline_shots(state)
    ids = [row.get('id') for row in rows]
    if shot_id not in ids:
        return False
    index = min(len(ids) - 1, max(0, ids.index(shot_id) + int(offset)))
    return _select_shot(page, state, ids[index], focus=True)


def _popup_shot_menu(page, state, row, widget):
    menu = shot_context_menu(page, state, row)
    x = widget.winfo_rootx()
    y = widget.winfo_rooty() + widget.winfo_height()
    return menu.popup_at(x, y)


def _shot_cell(page, state, bar, row, metrics):
    """时间线镜头格：宽度随秒数、缩略图、审核角标、点击与键盘选中。"""
    seconds = float(row.get('seconds') or 0)
    width = _timeline_width(seconds)
    selected = row.get('id') == state.get('selected_shot')
    cell = ttk.Frame(bar, width=width, height=metrics['cell_height'],
                     style='SelectedShot.TFrame' if selected else 'Card.TFrame')
    cell.pack_propagate(False)
    cell.pack(side='left', padx=(SPACING['none'], SPACING['sm']))
    shot_id = row.get('id')
    state.setdefault('shot_widgets', {})[shot_id] = cell
    image_path = _shot_image(state, shot_id, int(row.get('image_version') or 0))
    image = (asset_thumbs.thumbnail(cell, image_path, size=metrics['thumb_size'])
             if image_path is not None else None)
    if image is not None:
        thumb = ttk.Label(cell, image=image)
        thumb._animatic_thumb = image
    else:
        thumb = ttk.Label(cell, text='未生成')
    thumb.pack(pady=(SPACING['xs'], SPACING['none']))
    label = ttk.Label(cell, text=shot_cell_caption(row))
    label.pack()

    def popup_current(event=None, widget=cell, shot=row):
        return shot_context_menu(page, state, shot).popup(event) if event is not None \
            else _popup_shot_menu(page, state, shot, widget)

    def key(event, shot=row):
        sid = shot.get('id')
        if event.keysym in ('Return', 'space'):
            _select_shot(page, state, sid, focus=True)
            return 'break'
        if event.keysym == 'Left':
            _select_neighbor_shot(page, state, sid, -1)
            return 'break'
        if event.keysym == 'Right':
            _select_neighbor_shot(page, state, sid, 1)
            return 'break'
        return None

    for widget in (cell, thumb, label):
        widget.bind('<Button-1>', lambda _event, sid=shot_id:
                    _select_shot(page, state, sid, focus=True))
        widget.bind('<Button-3>', popup_current)
        widget.bind('<KeyPress>', key)
        widget.bind('<Shift-F10>', lambda event, shot=row, widget=cell:
                    (_popup_shot_menu(page, state, shot, widget), 'break')[-1])
        widget.bind('<App>', lambda event, shot=row, widget=cell:
                    (_popup_shot_menu(page, state, shot, widget), 'break')[-1])
        _quiet(lambda w=widget: w.configure(takefocus=True))


def _dialogue_cell(state, bar, row):
    """对白轨单元与上方镜头格同宽，保持逐镜对齐；超长只标记不截断。"""
    sid = row.get('id')
    cell = ttk.Frame(bar, width=_timeline_width(row.get('seconds')))
    cell.pack_propagate(False)
    cell.pack(side='left', padx=(SPACING['none'], SPACING['sm']))
    clip = row.get('dialogue_audio')
    if not clip:
        ttk.Label(cell, text='%s 无对白' % sid).pack(side='left')
        return
    duration = shot_dialogue_seconds(state['project'], row, probe=asset_thumbs.media_info)
    ttk.Label(cell, text='%s 对白 %.1f 秒' % (sid, duration)).pack(side='left')
    if duration > float(row.get('seconds') or 0) + animatic_audio.OVERLONG_TOLERANCE_SECONDS:
        HintLabel(cell, text='对白超长').pack(side='left')


# ── 动作：刷新、生成、单镜／批量重做、锁定、外置播放 ───────────────────────────

def _refresh(page, state):
    """网关落盘之后刷新页面事实：页面失效即静默；版本变化时重建本页。"""
    if not _is_alive(page, state):
        return
    fresh = _safe_call(
        page, lambda: stage_execution_service.load_or_sync_animatic_timeline(state['project']))
    if isinstance(fresh, dict):
        state['timeline'] = fresh
    previous = state.get('video')
    state['video'] = _playable_video(state['project'])
    state['manifest'] = _manifest(state['project'])
    state['version_tag'] = _version_tag(state['video'], state['manifest'])
    state['confirmed'] = _confirmed(state['manifest'])
    for var in state['checks'].values():
        var.set(bool(state['confirmed']))
    if state['video'] != previous and callable(getattr(page, 'show', None)):
        page.show(state.get('page_index'))
        return
    if state['video'] != previous:
        state['inline_player'] = False
    refresh_toolbar(state.get('toolbar'), page, state)
    _sync_filter_options(state)
    _render_timeline(page, state)
    if state.get('video') is None:
        _render_player(page, state)
    _render_inspector(page, state)
    _update_summary(page, state)


def _redo_shot(page, state, shot_id):
    return _dispatch_redo_shot(page, state, shot_id, lambda: _refresh(page, state))


def _redo_revision_shots(page, state):
    return _dispatch_redo_revisions(page, state, lambda: _refresh(page, state))


def _replace_shot_image(page, state, shot_id):
    dialog = getattr(page, 'file_dialog', None)
    opener = getattr(dialog, 'open_files', None)
    if not callable(opener):
        return
    paths = opener(parent=getattr(page, 'win', None), title='选择替换图片',
                   filetypes=[('图片', '*.png *.jpg *.jpeg *.webp')])
    if not paths:
        return
    result = _safe_call(
        page, lambda: stage_execution_service.replace_animatic_shot_image(
            state['project'], shot_id, Path(paths[0])))
    if result is not None:
        if isinstance(result, dict):
            state['timeline'] = result
        _render_timeline(page, state)
        _render_inspector(page, state)
        _update_summary(page, state)


def _apply_shot_update(page, state, shot_id, **fields):
    result = _safe_call(
        page, lambda: stage_execution_service.update_animatic_shot(
            state['project'], shot_id, **fields))
    if result is None:
        return False
    if isinstance(result, dict):
        state['timeline'] = result
    _render_timeline(page, state)
    _render_inspector(page, state)
    _update_summary(page, state)
    return True


def _apply_seconds(page, state, shot_id, value):
    try:
        seconds = int(str(value).strip())
    except (TypeError, ValueError):
        page.status.set('请输入 2 至 15 的整数秒')
        return False
    return _apply_shot_update(page, state, shot_id, seconds=seconds)


def _show_shot_info(page, state, row):
    board_row = (state.get('board') or {}).get(str(row.get('id'))) or {}
    prompt = shot_prompt_text(board_row)
    refs = row.get('references') or []
    if not refs:
        refs = _safe_call(page, lambda: stage_execution_service.refs_for_animatic_shot(
            state['project'], board_row)) or []
    names = '、'.join(Path(str(path)).name for path in refs) or '无'
    state['info_label'].configure(text='提示词：%s，参考图：%s' % (prompt, names))


def _lock(page, state):
    _dispatch_lock(page, state)


def _start_inline_preview(page, state, *, auto_play=True):
    """REQ-S04-106：按需挂载 VideoPreview 页内试播，不加高频进度条轮询。"""
    if state.get('video') is None:
        return None
    state['inline_player'] = True
    _render_player(page, state)
    view = state.get('video_view')
    if auto_play and view is not None:
        view.toggle()
    return view


def _activate_player(page, state):
    mode = player_mode_of(page)
    if mode == 'jianying':
        _open_in_jianying(page, state)
    elif mode == 'inline':
        _start_inline_preview(page, state)
    else:
        state['open_video']()


def _open_prefs(page, state):
    def saved(_patch):
        refresh_toolbar(state.get('toolbar'), page, state)
        if state.get('video') is not None and not state.get('inline_player'):
            _render_player(page, state)

    return open_prefs_bar(page, state, container=state.get('edit_box'), on_saved=saved)


def run_command(page, state, text):
    """发送键统一入口：『重做 SHxxx』单镜重做，其余整片合成。"""
    command = parse_animatic_command(text)
    if command['action'] == 'redo_shot':
        shot_id = command['shot_id']
        shots = (state.get('timeline') or {}).get('shots') or []
        if not any(str(row.get('id')) == shot_id for row in shots):
            message = '时间线没有此镜头：%s' % shot_id
            page.status.set(message)
            _reply_note(page, 'error', message, expand=True)
            return False
        return _redo_shot(page, state, shot_id)
    return _dispatch_generate(page, state, text, lambda: _refresh(page, state))


# ── 右键菜单与文件面板挂钩 ───────────────────────────────────────────────────

def shot_context_menu(page, state, row):
    """REQ-S04-97/107：镜头格右键七项动作，全部本地处理无弹窗。"""
    shot_id = row.get('id')
    menu = ContextMenu(page.win)
    menu.command('重做这一镜', lambda: _redo_shot(page, state, shot_id))
    menu.command('用导入的图替换', lambda: _replace_shot_image(page, state, shot_id))
    menu.command('改时长', lambda: _open_inline_edit(
        page, state, '时长（2–15 秒）', str(row.get('seconds') or ''),
        lambda value: _apply_seconds(page, state, shot_id, value)))
    versions = menu.submenu()
    for number in _image_versions(state, shot_id):
        versions.command('v%d' % number, lambda version=number:
                         _apply_shot_update(page, state, shot_id, image_version=version))
    menu.cascade('切换图版本', versions)
    menu.command('查看提示词与所用参考图', lambda: _show_shot_info(page, state, row))
    menu.command('写批注', lambda: _open_inline_edit(
        page, state, '批注', str(row.get('note') or ''),
        lambda value: _apply_shot_update(page, state, shot_id, note=value)))
    menu.command('试听本镜对白', lambda: _audition_dialogue(page, state, row))
    return menu


def video_context_menu(page, state):
    """REQ-S04-106/110：播放区右键优先外置播放，常驻草图与预演设置入口。"""
    menu = ContextMenu(page.win)
    if state.get('video') is not None:
        menu.command('用本地播放器打开', lambda: state['open_video']())
        menu.command('在剪映中打开', lambda: _open_in_jianying(page, state))
        menu.command('页内试播', lambda: _start_inline_preview(page, state))
        menu.command('重新合成新版本', lambda: run_command(page, state, '重新合成'))
    else:
        menu.command('生成分镜预演', lambda: run_command(page, state, ''))
    menu.command('本地生成参考草图', lambda: _open_inline_edit(
        page, state, '草图描述', '', lambda value: _apply_sketch(page, state, value)))
    menu.command('预演设置…', lambda: _open_prefs(page, state))
    return menu


def _reference_menu_hook(page, state):
    """DES-S04-25：参考图右键挂钩；草图常驻，改分类只认共享参考图目录里的图片。"""
    def hook(menu, ref):
        path = Path(ref)
        try:
            inside = path.resolve().is_relative_to(
                shared_reference_dir(state['project']).resolve())
        except (OSError, ValueError):
            inside = False
        if inside and path.suffix.lower() in file_index.IMAGE_SUFFIXES:
            submenu = menu.submenu()
            for category in CATEGORIES:
                submenu.command(category, lambda pick=category:
                                _reclassify(page, state, path, pick))
            menu.cascade('修改参考图分类', submenu)
            menu.command('修改参考图对应名', lambda: _open_inline_edit(
                page, state, '对应名（角色／场景名）', path.stem,
                lambda value: _rename_reference(page, state, path, value)))
        menu.command('本地生成参考草图', lambda: _open_inline_edit(
            page, state, '草图描述', '', lambda value: _apply_sketch(page, state, value)))
    return hook


def _import_files(page, state, paths):
    """DES-S04-25：图片进参考库、音频进临时声音，其余回落阶段默认导入。"""
    images, audios, rest = [], [], []
    for raw in paths or ():
        path = Path(raw)
        suffix = path.suffix.lower()
        if suffix in file_index.IMAGE_SUFFIXES:
            images.append(path)
        elif suffix in file_index.AUDIO_SUFFIXES:
            audios.append(path)
        else:
            rest.append(path)
    result = {'imported': [], 'skipped': [], 'rejected': []}
    if images:
        characters, locations = _board_names(state.get('board'))
        imported = _safe_call(
            page, lambda: stage_execution_service.import_animatic_reference_library(
                state['project'], images, characters=characters, locations=locations))
        result['imported'].extend(imported or ())
    for audio in audios:
        outcome = _safe_call(
            page, lambda: stage_execution_service.import_animatic_audio(
                state['project'], audio))
        if getattr(outcome, 'ok', False):
            result['imported'].append(outcome.data)
        elif outcome is not None:
            result['rejected'].append((audio.name, str(getattr(outcome, 'reason', '导入失败'))))
    if rest:
        fallback = _safe_call(page, lambda: files_panel_filters.import_into_stage(
            state['project'], 'animatic', rest)) or {}
        for key in ('imported', 'skipped', 'rejected'):
            result[key].extend(fallback.get(key) or ())
    if result['imported']:
        first = next((item for item in result['imported'] if isinstance(item, (str, Path))), None)
        if first is not None:
            name = Path(str(first)).name
            _reply_note(page, 'artifact', '已导入 %d 个文件，例如：%s' % (
                len(result['imported']), name), path=str(first), title=name)
    if result['rejected']:
        detail = '；'.join('%s：%s' % (name, reason)
                          for name, reason in result['rejected'][:3])
        _reply_note(page, 'error', '有 %d 个文件未导入：%s' % (
            len(result['rejected']), detail), expand=True)
    _render_inspector(page, state)
    _update_summary(page, state)
    return result


def _select_board(page, state, path):
    """面板点选分镜 JSON 时切换时间线来源；非 .json 一律不理。"""
    target = Path(path)
    if target.suffix.lower() != '.json':
        return
    fresh = _safe_call(
        page, lambda: stage_execution_service.load_or_sync_animatic_timeline(
            state['project'], target))
    if isinstance(fresh, dict):
        state['timeline'] = fresh
        state['source'] = str(fresh.get('source') or '')
        state['board'] = _load_board(state['project'], state['source'])
        state['video'] = _playable_video(state['project'])
        state['inline_player'] = False
        state['timeline_page'] = 1
        state['filter_scene'] = ''
        state['filter_status'] = 'all'
        state['manifest'] = _manifest(state['project'])
        state['version_tag'] = _version_tag(state['video'], state['manifest'])
        state['confirmed'] = _confirmed(state['manifest'])
        for var in state['checks'].values():
            var.set(bool(state['confirmed']))
        refresh_toolbar(state.get('toolbar'), page, state)
        _sync_filter_options(state)
        _render_timeline(page, state)
        _render_player(page, state)
        _render_inspector(page, state)
        _update_summary(page, state)


def _register_send_key(page, state):
    """底栏发送键：空＝生成；自由文本＝本地指令；斜杠命令交还原发送链。"""
    _register_send_key_impl(page, state, lambda text: run_command(page, state, text))


# ── 建页 ────────────────────────────────────────────────────────────────────

def _new_state(page, frame, project, timeline):
    video = _playable_video(project)
    manifest = _manifest(project)
    state = {'page': page, 'frame': frame, 'project': project,
             'page_index': getattr(page, 'page_index', None),
             'source': str(timeline.get('source') or ''),
             'timeline': timeline, 'board': {}, 'video': video,
             'inline_player': False, 'player_cover': None, 'video_view': None,
             'toolbar': None, 'workbench_box': None, 'inspector_box': None,
             'inspector': None, 'filter_bar': None, 'filter_controls': None,
             'filter_scene': '', 'filter_status': 'all',
             'manifest': manifest,
             'version_tag': _version_tag(video, manifest),
             'confirmed': _confirmed(manifest),
             'checks': {}, 'confirm_bar': None,
             'edit_box': None, 'edit_commit': None, 'edit_cancel': None,
             'prefs_bar': None, 'layout_metrics': None, 'resize_job': None,
             'timeline_box': None, 'pager_bar': None,
             'timeline_page': 1, 'timeline_total_pages': 1,
             'info_label': None, 'shot_widgets': {},
             'selected_shot': ((timeline.get('shots') or [{}])[0].get('id')
                               if timeline.get('shots') else None),
             'select_fn': None, 'import_fn': None, 'menu_fn': None}
    state['board'] = _load_board(project, state['source'])
    state['open_video'] = lambda: _open_video(page, state)
    state['activate_player'] = lambda: _activate_player(page, state)
    state['select_fn'] = lambda path: _select_board(page, state, path)
    state['import_fn'] = lambda paths: _import_files(page, state, paths)
    state['menu_fn'] = _reference_menu_hook(page, state)
    return state


def show(page):
    """建 S04 分镜预演工作台；返回页面外框（``_animatic_state`` 携带全部事实）。"""
    frame = ttk.Frame(page.content)
    frame.pack(fill='both', expand=True)
    project = getattr(page, 'root', None)
    timeline = None
    if project is not None:
        timeline = load_timeline_for_show(
            page, lambda: stage_execution_service.load_or_sync_animatic_timeline(project))
    if not isinstance(timeline, dict):
        _guide(page, frame)
        frame._animatic_state = {'project': project, 'timeline': None}
        return frame
    state = _new_state(page, frame, project, timeline)
    _build_confirm_bar(page, state)
    _build_toolbar(page, state)
    _build_workbench(page, state)
    _build_filter_bar(page, state)
    _build_tracks(page, state)
    _build_editor(page, state)
    _build_info(page, state)
    _watch_layout_metrics(page, state)
    _register_panel(page, state)
    _register_send_key(page, state)
    _update_summary(page, state)
    frame._animatic_state = state
    return frame


def build_animatic_page(page):
    """页面构建入口别名：与 ``show`` 同一条建页链。"""
    return show(page)

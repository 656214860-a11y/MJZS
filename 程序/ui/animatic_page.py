# -*- coding: utf-8 -*-
"""S04 分镜预演页：少按钮三段式布局（REQ-S04-95…99，DES-S04-25）。

上方播放区（无版本显示当前镜缩略图，有版本点击画面原位播放/暂停）；
中间时间线（各镜一格＋对白轨「对白超长」高亮＋音乐轨）；右侧沿用阶段
文件面板（按后缀自动归位的导入分流、点选分镜、参考图右键）；底部共享
输入框发送键（空＝生成预演，「只重做 SHxxx」＝单镜重做）；状态栏摘要；
有可播放版本后才出现三项确认与「锁定」。业务一律走 L3
``stage_execution_service`` 网关，页面只注入回调，不新增弹窗。
"""
import tkinter as tk
from pathlib import Path
from tkinter import BooleanVar, ttk

import stage_execution_service
import ui.desktop_files_panel_filters as files_panel_filters
from contract.pet_bus import stage_step
from contract.stage_path_service import shared_reference_dir
from domain import animatic_audio
from domain.animatic_references import CATEGORIES, UNCATEGORIZED
from infra import file_index
from infra.pet_state import PAGE_OF
from ui.animatic_prefs_bar import _open_inline_edit, open_prefs_bar
from ui.animatic_view_state import (
    PLAYER_CAPTIONS, _TASK_FAILED, _TIMELINE_CELL_HEIGHT, _TIMELINE_THUMB_SIZE,
    _animatic_settings, _audio_mode, _audition_dialogue, _board_names,
    _confirmed, _image_versions, _is_alive, _load_board, _manifest,
    _music_text, _open_in_jianying, _open_video, _playable_video, _quiet,
    _refresh_files_panel, _register_panel, _release_panel, _reply_note,
    _run_async, _safe_call, _shot_image, _task_payload, _timeline_width,
    _version_tag, animatic_layout_metrics, cancel_debounced_layout,
    format_status_summary, load_timeline_for_show, parse_animatic_command,
    player_mode_of, schedule_debounced_layout, shot_dialogue_seconds,
    shot_page_for_id, shot_prompt_text, timeline_page_slice,
)
from ui import asset_thumbs
from ui.animatic_player import fit_video_preview
from ui_tokens import COLORS, SPACING
from ui_widgets import (ContextMenu, DescriptionBlock, HintLabel,
                        PrimaryButton, SecondaryButton)

_CHECK_LABELS = (('rhythm', '已确认节奏'), ('duration', '已确认时长'),
                 ('dialogue_sync', '已确认对白同步'))
_TIMELINE_GUTTER_WIDTH = 56


# ── 布局：播放区 / 时间线 / 内联编辑条 / 信息条 / 确认锁定条 ──────────────────

def _guide(page, frame):
    """无已采用分镜的引导页：一段说明＋一颗跳回 S03 的主按钮。"""
    DescriptionBlock(
        frame, text='请先在初步分镜完成并采用分镜，再回来生成分镜预演。').pack(
        anchor='w', pady=SPACING['xs'])
    PrimaryButton(frame, text='去' + stage_step('storyboard'),
                  command=lambda: page.go(PAGE_OF['storyboard'])).pack(
        anchor='w', pady=SPACING['sm'])


def _build_confirm_bar(page, state):
    """有可播放版本才出现的确认条；先占位在页底，保证小窗口里看得见。"""
    if state['video'] is None:
        return
    bar = ttk.Frame(state['frame'])
    bar.pack(fill='x', pady=(SPACING['sm'], SPACING['none']))
    SecondaryButton(bar, text='锁定',
                    command=lambda: _lock(page, state)).pack(side='right')
    for key, label in _CHECK_LABELS:
        var = BooleanVar(value=bool(state.get('confirmed')))
        ttk.Checkbutton(bar, text=label, variable=var).pack(
            side='left', padx=(SPACING['none'], SPACING['sm']))
        state['checks'][key] = var
    state['confirm_bar'] = bar


def _build_player(page, state):
    box = ttk.Frame(state['frame'])
    box.pack(fill='x', pady=(SPACING['none'], SPACING['sm']))
    state['player_box'] = box
    box.bind('<Button-3>', lambda event: video_context_menu(page, state).popup(event))
    _render_player(page, state)


def _layout_metrics(page, state):
    metrics = state.get('layout_metrics')
    if metrics is None:
        metrics = animatic_layout_metrics(getattr(page, 'win', None))
        state['layout_metrics'] = metrics
    return metrics


def _render_player(page, state):
    """REQ-S04-106：有版本默认渲染轻量封面（外置优先），选「页内试播」才挂载 VideoPreview。"""
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
    rows = [row for row in (state['timeline'].get('shots') or [])
            if isinstance(row, dict)]
    selected = state.get('selected_shot')
    row = next((item for item in rows if item.get('id') == selected), None)
    if row is None and rows:
        row = rows[0]
    image_path = (_shot_image(state, row.get('id'),
                              int(row.get('image_version') or 0)) if row else None)
    image = (asset_thumbs.thumbnail(box, image_path, size=metrics['cover_size'])
             if image_path is not None else None)
    if image is not None:
        view = ttk.Label(box, image=image)
        view._animatic_thumb = image
        view.pack(anchor='w')
        ttk.Label(box, text='%s 当前镜头草图' % row.get('id')).pack(anchor='w')
    else:
        text = ('%s 尚未生成草图；底栏发送键直接合成' % row.get('id') if row
                else '尚未生成分镜预演；底栏发送键直接合成')
        ttk.Label(box, text=text).pack(anchor='w')
    for widget in box.winfo_children():
        widget.bind('<Button-3>',
                    lambda event: video_context_menu(page, state).popup(event))


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
    view = state.get('video_view')
    if state.get('video') is not None and view is not None and _quiet(view.winfo_exists, False):
        fit_video_preview(view, state, metrics)
    else:
        _render_player(page, state)
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
    """重画分页横向时间线：仅渲染当前页 ≤20 镜（镜头格＋对白轨＋音乐轨）。"""
    box = state['timeline_box']
    metrics = _layout_metrics(page, state)
    for child in box.winfo_children():
        child.destroy()
    shots = [row for row in (state.get('timeline') or {}).get('shots') or []
             if isinstance(row, dict)]
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
    """选中时间线镜头格：跨页时自动切页，无视频时播放区同步显示这一镜的大图。"""
    rows = [item for item in (state.get('timeline') or {}).get('shots') or []
            if isinstance(item, dict)]
    if not any(row.get('id') == shot_id for row in rows):
        return False
    state['selected_shot'] = shot_id
    widget = (state.get('shot_widgets') or {}).get(shot_id)
    if widget is None or not _quiet(widget.winfo_exists, False):
        state['timeline_page'] = shot_page_for_id(rows, shot_id)
        _render_timeline(page, state)
        widget = (state.get('shot_widgets') or {}).get(shot_id)
    else:
        _paint_shot_selection(state)
    if state.get('video') is None:
        _render_player(page, state)
    if focus and widget is not None:
        _quiet(widget.focus_set)
    return True


def _select_neighbor_shot(page, state, shot_id, offset):
    rows = [item for item in (state.get('timeline') or {}).get('shots') or []
            if isinstance(item, dict)]
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
    """时间线镜头格：宽度随秒数、缩略图、点击选中，键盘可左右移动与开菜单。"""
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
    label = ttk.Label(cell, text='%s · %s 秒' % (shot_id, row.get('seconds')))
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


# ── 动作：发送键指令、单镜操作、锁定、外部播放 ────────────────────────────────

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
        page.show(state.get('page_index'))  # 版本变化要换确认条：真宿主整页重建
        return
    if state['video'] != previous:
        state['inline_player'] = False
    _render_timeline(page, state)
    if state.get('video') is None:
        _render_player(page, state)
    _update_summary(page, state)


def _update_summary(page, state):
    library = _quiet(lambda: stage_execution_service.animatic_reference_library(
        state['project']), {})
    formal = _quiet(lambda: stage_execution_service.formal_animatic_assets(
        state['project']), {})
    formal_count = sum(len(v) for v in formal.values()) if isinstance(formal, dict) else 0
    segment = format_status_summary(
        state['timeline'], library if isinstance(library, dict) else {},
        _audio_mode(state), state.get('version_tag'), state.get('confirmed'),
        formal_count=formal_count)
    setter = getattr(page, 'set_status_segment', None)
    if callable(setter):
        setter('animatic_note', segment, tooltip=segment)


def _after_generate(page, state, outcome):
    if not _is_alive(page, state):
        return
    result = _task_payload(page, outcome, '合成分镜预演')
    if result is _TASK_FAILED:
        return
    if result:
        name = Path(str(result)).name
        _reply_note(page, 'artifact', '分镜预演已生成：%s' % name,
                    path=str(result), title=name)
    _refresh(page, state)


def _after_redo(page, state, shot_id, outcome):
    if not _is_alive(page, state):
        return
    result = _task_payload(page, outcome, '重做 %s' % shot_id)
    if result is _TASK_FAILED:
        return
    if result:
        rows = result.get('shots') if isinstance(result, dict) else []
        row = next((item for item in rows or []
                    if isinstance(item, dict) and item.get('id') == shot_id), {})
        version = row.get('image_version')
        _reply_note(page, 'progress', '%s 已重做完成%s' % (
            shot_id, '，当前图版本 v%s' % version if version else ''))
    _refresh(page, state)


def _redo_shot(page, state, shot_id):
    _reply_note(page, 'user', '重做这一镜：%s' % shot_id)
    accepted = _run_async(
        page,
        lambda: stage_execution_service.regenerate_animatic_shot(
            state['project'], shot_id, settings=_animatic_settings(page)),
        lambda result: _after_redo(page, state, shot_id, result),
        label='正在重做 %s' % shot_id)
    if accepted:
        _reply_note(page, 'progress', '正在重做 %s…' % shot_id, expand=True)
    return accepted


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
        if state.get('video') is None:
            _render_player(page, state)
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
    if state.get('video') is None:
        _render_player(page, state)
    _update_summary(page, state)
    return True


def _apply_seconds(page, state, shot_id, value):
    try:
        seconds = int(str(value).strip())
    except (TypeError, ValueError):
        page.status.set('请输入 2 至 15 的整数秒')
        return False
    return _apply_shot_update(page, state, shot_id, seconds=seconds)


def _apply_sketch(page, state, value):
    prompt = str(value or '').strip()
    if not prompt:
        return False
    settings = getattr(page, 'settings', None) or {}
    model = str(settings.get('animatic_reference_model') or '').strip()
    if not model:
        message = '请先在设置里配置参考图模型名'
        page.status.set(message)
        _reply_note(page, 'error', message, expand=True)
        return False
    url = settings.get('comfy_url')
    _reply_note(page, 'user', '本地生成参考草图：%s' % prompt)
    accepted = _run_async(
        page,
        lambda: stage_execution_service.generate_animatic_reference(
            state['project'], prompt, model, {'url': url} if url else {}),
        lambda result: _after_sketch(page, state, result), label='正在生成参考草图…')
    if accepted:
        _reply_note(page, 'progress', '正在生成参考草图…', expand=True)
    return accepted


def _after_sketch(page, state, outcome):
    if not _is_alive(page, state):
        return
    result = _task_payload(page, outcome, '生成参考草图')
    if result is _TASK_FAILED:
        return
    ok = getattr(result, 'ok', result is not None)
    if ok:
        page.status.set('已生成共享参考草图')
        data = getattr(result, 'data', result)
        if isinstance(data, (str, Path)):
            paths = (data,)
        else:
            paths = tuple(data or ()) if isinstance(data, (list, tuple)) else ()
        if paths:
            name = Path(str(paths[0])).name
            _reply_note(page, 'artifact', '共享参考草图已生成：%s' % name,
                        path=str(paths[0]), title=name)
        else:
            _reply_note(page, 'reply', '共享参考草图已生成')
    else:
        message = str(getattr(result, 'reason', '参考草图生成失败'))
        page.status.set(message)
        _reply_note(page, 'error', message, expand=True)
    _update_summary(page, state)


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
    """三项未勾全只写状态栏、不调后端；全勾才走 L3 锁定事务。"""
    if not all(var.get() for var in state['checks'].values()):
        message = '请先勾选三项确认再锁定'
        page.status.set(message)
        _reply_note(page, 'error', message, expand=True)
        return
    _reply_note(page, 'user', '锁定分镜预演')
    accepted = _run_async(
        page,
        lambda: stage_execution_service.lock_animatic(
            state['project'], rhythm=True, duration=True, dialogue_sync=True),
        lambda outcome: _lock_finished(page, state, outcome), label='正在锁定分镜预演…')
    if accepted:
        _reply_note(page, 'progress', '正在回写分镜时长并锁定预演…', expand=True)


def _lock_finished(page, state, outcome):
    if not _is_alive(page, state):
        return
    if _task_payload(page, outcome, '锁定分镜预演') is not _TASK_FAILED:
        _locked(page, state)


def _locked(page, state):
    if not _is_alive(page, state):
        return
    page.status.set('分镜预演已锁定，可以进入资产管理')
    _reply_note(page, 'reply', '分镜预演已锁定；分镜时长已回写，可以进入资产管理')
    report = getattr(page, 'pet_report', None)
    if getattr(page, 'root', None) == state['project'] and callable(report):
        report('animatic', '节奏、时长与对白同步均已确认')
    state['confirmed'] = True
    _update_summary(page, state)


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
    spoken = str(text or '').strip()
    _reply_note(page, 'user', spoken or '生成分镜预演')
    source = Path(state['project']) / state['source'] if state.get('source') else None
    accepted = _run_async(
        page,
        lambda: stage_execution_service.run_animatic_timeline(
            state['project'], source=source, settings=_animatic_settings(page)),
        lambda result: _after_generate(page, state, result), label='正在合成分镜预演…')
    if accepted:
        _reply_note(page, 'progress', '正在合成分镜预演…', expand=True)
    return accepted


# ── 右键菜单：镜头格七项＋播放区外置优先＋参考图挂钩 ──────────────────────────

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


def _reclassify(page, state, path, category):
    result = _safe_call(page, lambda: stage_execution_service.reclassify_animatic_reference(
        state['project'], path, category))
    if result is not None:
        page.status.set('参考图已改分类：%s' % category)
        _refresh_files_panel(page)


def _rename_reference(page, state, path, value):
    """修改参考图对应名：保留原扩展名，留在原分类，用文件名参与角色／场景匹配。"""
    path = Path(path)
    category = path.parent.name if path.parent.name in CATEGORIES else UNCATEGORIZED
    name = str(value or '').strip()
    if name and not Path(name).suffix:
        name += path.suffix.lower()
    result = _safe_call(page, lambda: stage_execution_service.reclassify_animatic_reference(
        state['project'], path, category, new_name=name))
    if result is not None:
        try:
            display = Path(result).name
        except (TypeError, ValueError):
            display = name
        page.status.set('参考图已改名：%s' % display)
        _refresh_files_panel(page)


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


# ── 文件面板挂钩：导入分类、点选分镜、登记与销毁释放 ───────────────────────────

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
        state['manifest'] = _manifest(state['project'])
        state['version_tag'] = _version_tag(state['video'], state['manifest'])
        state['confirmed'] = _confirmed(state['manifest'])
        for var in state['checks'].values():
            var.set(bool(state['confirmed']))
        _render_timeline(page, state)
        _render_player(page, state)
        _update_summary(page, state)


def _register_send_key(page, state):
    """底栏发送键：空＝生成；自由文本＝本地指令；斜杠命令交还原发送链。"""
    shared = getattr(page, 'shared_input', None)
    register = getattr(shared, 'set_stage_action', None)
    action, wrapped, previous = None, None, None
    if callable(register):
        def action():
            return run_command(page, state, shared.text())
        register('animatic', action)
        previous = getattr(shared, 'on_send', None)

        def wrapped(value, parsed):
            ours = getattr(shared, 'stage', 'animatic') == 'animatic'
            if str(value or '').strip().startswith('/') or not ours:
                return previous(value, parsed) if callable(previous) else True
            accepted = run_command(page, state, value)
            if accepted:
                shared.end_request()
            return accepted

        shared.on_send = wrapped

    def release(event=None):
        if event is not None and event.widget is not state['frame']:
            return
        cancel_debounced_layout(state)
        if wrapped is not None and getattr(shared, 'on_send', None) is wrapped:
            shared.on_send = previous
        if callable(register) and getattr(
                shared, 'stage_action', lambda _s: None)('animatic') is action:
            register('animatic', None)
        setter = getattr(page, 'set_status_segment', None)
        if callable(setter):
            setter('animatic_note', '')
        _release_panel(page, state)

    state['frame'].bind('<Destroy>', release, add='+')


# ── 建页 ────────────────────────────────────────────────────────────────────

def _new_state(page, frame, project, timeline):
    video = _playable_video(project)
    manifest = _manifest(project)
    state = {'page': page, 'frame': frame, 'project': project,
             'page_index': getattr(page, 'page_index', None),
             'source': str(timeline.get('source') or ''),
             'timeline': timeline, 'board': {}, 'video': video,
             'inline_player': False, 'player_cover': None, 'video_view': None,
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
    """建 S04 分镜预演页；返回页面外框（``_animatic_state`` 携带全部事实）。"""
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
    _build_player(page, state)
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

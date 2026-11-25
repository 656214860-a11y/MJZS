# -*- coding: utf-8 -*-
"""S04 分镜预演页：少按钮三段式布局（REQ-S04-95…99，DES-S04-25）。

上方播放区（无版本显示当前镜缩略图，有版本显示封面＋点击外部播放）；
中间时间线（各镜一格＋对白轨「对白超长」高亮＋音乐轨）；右侧沿用阶段
文件面板（按后缀自动归位的导入分流、点选分镜、参考图右键）；底部共享
输入框发送键（空＝生成预演，「只重做 SHxxx」＝单镜重做）；状态栏摘要；
有可播放版本后才出现三项确认与「锁定」。业务一律走 L3
``stage_execution_service`` 网关，页面只注入回调，不新增弹窗。
"""
import re
from pathlib import Path
from tkinter import BooleanVar, ttk

import infra.file_cache as file_cache
import stage_execution_service
import ui.desktop_files_panel_filters as files_panel_filters
from contract.pet_bus import stage_step
from contract.stage_path_service import shared_reference_dir, write_dir
from domain import animatic_audio
from domain.animatic_references import CATEGORIES
from domain.animatic_service import CONFIRMATIONS, MANIFEST
from infra import file_index
from infra.pet_state import PAGE_OF
from ui import asset_thumbs
from ui_tokens import SPACING
from ui_widgets import (ContextMenu, DescriptionBlock, HintLabel, LineInput,
                        PrimaryButton, SecondaryButton)

_REDO = re.compile(r'重做[^0-9a-zA-Z]{0,8}sh?\s*(\d+)', re.IGNORECASE)
_VERSION_NAME = re.compile(r'^v(\d+)\.', re.IGNORECASE)
_CHECK_LABELS = (('rhythm', '已确认节奏'), ('duration', '已确认时长'),
                 ('dialogue_sync', '已确认对白同步'))


# ── REQ-S04-96/98：指令解析与状态栏摘要（无 Tk 的纯函数）─────────────────────

def parse_animatic_command(text):
    """底栏文本解析：含「重做」与镜头号 → 单镜重做，其余 → 整片生成。"""
    match = _REDO.search(str(text or ''))
    if match is None:
        return {'action': 'generate'}
    return {'action': 'redo_shot', 'shot_id': 'SH%03d' % int(match.group(1))}


def format_status_summary(timeline, library, audio_mode, version_tag, confirmed):
    """状态栏摘要：镜头数／参考图数／声音来源／版本与确认状态。"""
    shots = len((timeline or {}).get('shots') or [])
    refs = sum(len(value) for value in (library or {}).values())
    if version_tag:
        tail = '%s %s' % (version_tag, '已锁定' if confirmed else '未确认')
    else:
        tail = '未生成'
    return '分镜 %d 镜 / 参考图 %d 张 / 声音：%s / %s' % (
        shots, refs, audio_mode or '静音', tail)


# ── 小工具：安静执行与统一异常收口 ──────────────────────────────────────────

def _quiet(work, fallback=None):
    """读侧探测失败一律吞掉（页面照样能画），``fallback`` 为兜底值。"""
    try:
        return work()
    except Exception:
        return fallback


def _safe_call(page, work):
    """写侧动作统一收口：异常写状态栏，返回结果或 None。"""
    try:
        return work()
    except Exception as exc:
        page.status.set(str(exc))
        return None


def _run_async(page, work, done=None, label=None):
    """统一经宿主 ``async_`` 后台执行；worker 占用拒绝重入。返回是否已受理。"""
    if getattr(page, 'worker', None):
        page.status.set('请等待当前任务完成')
        return False
    runner = getattr(page, 'async_', None)
    if callable(runner):
        runner(work, done, label=label)
        return True
    result = _safe_call(page, work)
    if callable(done):
        done(result)
    return True


def _animatic_settings(page):
    """页面设置浅拷贝：comfy_url 映射为网关约定的 url，其余键原样透传。"""
    settings = dict(getattr(page, 'settings', None) or {})
    if 'comfy_url' in settings and 'url' not in settings:
        settings['url'] = settings['comfy_url']
    return settings


def _is_alive(page, state):
    """页面框还在且仍是当前页码才允许写界面——切页后迟到的回调一律静默。"""
    frame = state.get('frame')
    if frame is None or not _quiet(frame.winfo_exists, False):
        return False
    index = state.get('page_index')
    return index is None or getattr(page, 'page_index', None) == index


# ── 页面状态：分镜板、版本、清单、镜头图版本 ─────────────────────────────────

def _load_board(project, source):
    """把已采用分镜读成 ``{镜头 id: 行}``，供「查看提示词与所用参考图」用。"""
    data = _quiet(lambda: file_cache.read_json(Path(project) / source), {}) if source else {}
    rows = data.get('shots') if isinstance(data, dict) else []
    return {str(row.get('id')): row for row in rows or [] if isinstance(row, dict)}


def _playable_video(project):
    return _quiet(lambda: stage_execution_service.animatic_video(project))


def _manifest(project):
    data = _quiet(lambda: file_cache.read_json(write_dir(project, 'animatic') / MANIFEST))
    return data if isinstance(data, dict) else None


def _version_tag(video, manifest):
    if video is not None:
        return Path(video).stem
    raw = (manifest or {}).get('video')
    return Path(raw).stem if raw else None


def _confirmed(manifest):
    flags = (manifest or {}).get('confirmed') or {}
    return bool(flags) and all(bool(flags.get(key)) for key in CONFIRMATIONS)


def _shot_dir(state, shot_id):
    return write_dir(state['project'], 'animatic') / '镜头' / str(shot_id)


def _image_versions(state, shot_id):
    folder = _shot_dir(state, shot_id)
    if not folder.is_dir():
        return ()
    found = []
    for path in sorted(folder.iterdir()):
        match = _VERSION_NAME.match(path.name) if path.is_file() else None
        if match:
            found.append(int(match.group(1)))
    return found


def _shot_image(state, shot_id, version):
    """当前选用版本的图；未登记版本时退回目录里第一张 ``v<N>.*``。"""
    folder = _shot_dir(state, shot_id)
    if not folder.is_dir():
        return None
    prefix = ('v%d.' % int(version)).lower() if version else ''
    fallback = None
    for path in sorted(folder.iterdir()):
        if not path.is_file() or not _VERSION_NAME.match(path.name):
            continue
        if prefix and path.name.lower().startswith(prefix):
            return path
        if fallback is None:
            fallback = path
    return fallback


def _board_names(board):
    """分镜表里去重的角色与场景名，供参考图导入自动归类。"""
    characters, locations = [], []
    for row in (board or {}).values():
        if not isinstance(row, dict):
            continue
        for name in row.get('characters') or ():
            if name and name not in characters:
                characters.append(name)
        location = row.get('location')
        if location and location not in locations:
            locations.append(location)
    return characters, locations


def _audio_mode(state):
    shots = (state.get('timeline') or {}).get('shots') or []
    root = write_dir(state['project'], 'animatic')
    track = root / animatic_audio.SUBDIRS['track']
    if track.is_dir() and any(track.iterdir()):
        return '整轨'
    if any(isinstance(row, dict) and row.get('dialogue_audio') for row in shots):
        return '逐镜 TTS'
    if (state.get('manifest') or {}).get('audio'):
        return '整轨'
    return '静音'


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
    bar.pack(side='bottom', fill='x', pady=(SPACING['sm'], SPACING['none']))
    for key, label in _CHECK_LABELS:
        var = BooleanVar(value=bool(state.get('confirmed')))
        ttk.Checkbutton(bar, text=label, variable=var).pack(
            side='left', padx=(SPACING['none'], SPACING['sm']))
        state['checks'][key] = var
    SecondaryButton(bar, text='锁定',
                    command=lambda: _lock(page, state)).pack(side='left')
    state['confirm_bar'] = bar


def _build_player(page, state):
    box = ttk.Frame(state['frame'])
    box.pack(fill='x', pady=(SPACING['none'], SPACING['sm']))
    state['player_box'] = box
    box.bind('<Button-3>', lambda event: video_context_menu(page, state).popup(event))
    if state['video'] is not None:
        cover = asset_thumbs.media_thumbnail(box, state['video'], size=160)
        if cover is not None:
            view = ttk.Label(box, image=cover)
            view._animatic_thumb = cover
        else:
            view = ttk.Label(box, text='分镜预演已生成，点击播放')
        view.pack(anchor='w')
        hint = ttk.Label(box, text='点击画面或右键用外部播放器打开')
        hint.pack(anchor='w')
        for widget in (view, hint):
            widget.bind('<Button-1>', lambda _event: state['open_video']())
            widget.bind('<Button-3>',
                        lambda event: video_context_menu(page, state).popup(event))
        state['video_view'] = view
        return
    rows = state['timeline'].get('shots') or []
    row = rows[0] if rows else None
    image_path = (_shot_image(state, row.get('id'),
                              int(row.get('image_version') or 0)) if row else None)
    image = (asset_thumbs.thumbnail(box, image_path, size=160)
             if image_path is not None else None)
    if image is not None:
        view = ttk.Label(box, image=image)
        view._animatic_thumb = image
        view.pack(anchor='w')
    else:
        ttk.Label(box, text='尚未生成分镜预演；底栏发送键直接合成').pack(anchor='w')
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


def _render_timeline(page, state):
    """重画时间线：镜头格（宽随时长）＋对白轨（超长标记）＋音乐轨。"""
    box = state['timeline_box']
    for child in box.winfo_children():
        child.destroy()
    shots = [row for row in (state.get('timeline') or {}).get('shots') or []
             if isinstance(row, dict)]
    shots_bar = ttk.Frame(box)
    shots_bar.pack(fill='x')
    for row in shots:
        _shot_cell(page, state, shots_bar, row)
    dialogue = ttk.Frame(box)
    dialogue.pack(fill='x')
    ttk.Label(dialogue, text='对白轨').pack(
        side='left', padx=(SPACING['none'], SPACING['sm']))
    for row in shots:
        _dialogue_cell(state, dialogue, row)
    music = ttk.Frame(box)
    music.pack(fill='x')
    ttk.Label(music, text='音乐轨').pack(
        side='left', padx=(SPACING['none'], SPACING['sm']))
    ttk.Label(music, text=_music_text(state)).pack(side='left')


def _shot_cell(page, state, bar, row):
    cell = ttk.Frame(bar)
    seconds = float(row.get('seconds') or 0)
    width = max(64, int(16 * seconds))
    cell.pack(side='left', padx=(SPACING['none'], SPACING['sm']))
    label = ttk.Label(cell, text='%s · %s 秒' % (row.get('id'), row.get('seconds')),
                      width=max(8, width // 16))
    label.pack()
    for widget in (cell, label):
        widget.bind('<Button-3>', lambda event, shot=row:
                    shot_context_menu(page, state, shot).popup(event))


def _dialogue_cell(state, bar, row):
    sid = row.get('id')
    clip = row.get('dialogue_audio')
    if not clip:
        ttk.Label(bar, text='%s 无对白' % sid).pack(
            side='left', padx=(SPACING['none'], SPACING['sm']))
        return
    info = asset_thumbs.media_info(Path(state['project']) / clip)
    duration = float((info or {}).get('duration') or 0)
    ttk.Label(bar, text='%s 对白 %.1f 秒' % (sid, duration)).pack(side='left')
    if duration > float(row.get('seconds') or 0) + animatic_audio.OVERLONG_TOLERANCE_SECONDS:
        HintLabel(bar, text='对白超长').pack(side='left')


def _music_text(state):
    folder = write_dir(state['project'], 'animatic') / animatic_audio.SUBDIRS['music']
    if folder.is_dir() and any(folder.iterdir()):
        return '已导入'
    return '未导入'


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
    _render_timeline(page, state)
    _update_summary(page, state)


def _update_summary(page, state):
    library = _quiet(lambda: stage_execution_service.animatic_reference_library(
        state['project']), {})
    segment = format_status_summary(
        state['timeline'], library if isinstance(library, dict) else {},
        _audio_mode(state), state.get('version_tag'), state.get('confirmed'))
    setter = getattr(page, 'set_status_segment', None)
    if callable(setter):
        setter('animatic_note', segment, tooltip=segment)


def _redo_shot(page, state, shot_id):
    return _run_async(
        page,
        lambda: stage_execution_service.regenerate_animatic_shot(
            state['project'], shot_id, settings=_animatic_settings(page)),
        lambda _result: _refresh(page, state), label='正在重做 %s' % shot_id)


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
        page.status.set('请先在设置里配置参考图模型名')
        return False
    url = settings.get('comfy_url')
    return _run_async(
        page,
        lambda: stage_execution_service.generate_animatic_reference(
            state['project'], prompt, model, {'url': url} if url else {}),
        lambda result: _after_sketch(page, state, result), label='正在生成参考草图…')


def _after_sketch(page, state, result):
    if not _is_alive(page, state):
        return
    ok = getattr(result, 'ok', result is not None)
    if ok:
        page.status.set('已生成共享参考草图')
    else:
        page.status.set(str(getattr(result, 'reason', '参考草图生成失败')))
    _update_summary(page, state)


def _show_shot_info(page, state, row):
    board_row = (state.get('board') or {}).get(str(row.get('id'))) or {}
    prompt = str(board_row.get('video_prompt') or '').strip() or '（分镜未写提示词）'
    refs = row.get('references') or []
    if not refs:
        refs = _safe_call(page, lambda: stage_execution_service.refs_for_animatic_shot(
            state['project'], board_row)) or []
    names = '、'.join(Path(str(path)).name for path in refs) or '无'
    state['info_label'].configure(text='提示词：%s，参考图：%s' % (prompt, names))


def _lock(page, state):
    """三项未勾全只写状态栏、不调后端；全勾才走 L3 锁定事务。"""
    if not all(var.get() for var in state['checks'].values()):
        page.status.set('请先勾选三项确认再锁定')
        return
    _run_async(
        page,
        lambda: stage_execution_service.lock_animatic(
            state['project'], rhythm=True, duration=True, dialogue_sync=True),
        lambda _result: _locked(page, state), label='正在锁定分镜预演…')


def _locked(page, state):
    if not _is_alive(page, state):
        return
    page.status.set('分镜预演已锁定，可以进入资产管理')
    report = getattr(page, 'pet_report', None)
    if getattr(page, 'root', None) == state['project'] and callable(report):
        report('animatic', '节奏、时长与对白同步均已确认')
    state['confirmed'] = True
    _update_summary(page, state)


def _open_video(page, state):
    """外部播放经注入的 media_page_services.open_path，不直接碰系统出口。"""
    services = getattr(page, 'media_page_services', None)
    opener = getattr(services, 'open_path', None)
    if state.get('video') is None or not callable(opener):
        return
    _safe_call(page, lambda: opener(state['video']))


def run_command(page, state, text):
    """发送键统一入口：『重做 SHxxx』单镜重做，其余整片合成。"""
    command = parse_animatic_command(text)
    if command['action'] == 'redo_shot':
        shot_id = command['shot_id']
        shots = (state.get('timeline') or {}).get('shots') or []
        if not any(str(row.get('id')) == shot_id for row in shots):
            page.status.set('时间线没有此镜头：%s' % shot_id)
            return False
        return _redo_shot(page, state, shot_id)
    source = Path(state['project']) / state['source'] if state.get('source') else None
    return _run_async(
        page,
        lambda: stage_execution_service.run_animatic_timeline(
            state['project'], source=source, settings=_animatic_settings(page)),
        lambda _result: _refresh(page, state), label='正在合成分镜预演…')


# ── 右键菜单：镜头格六项＋播放区一项＋参考图挂钩 ──────────────────────────────

def shot_context_menu(page, state, row):
    """REQ-S04-97：镜头格右键六项动作，全部本地处理无弹窗。"""
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
    return menu


def video_context_menu(page, state):
    """播放区右键：草图入口常驻（REQ-S04-99）；按有无版本给播放或生成项。"""
    menu = ContextMenu(page.win)
    if state.get('video') is not None:
        menu.command('用外部播放器打开', lambda: state['open_video']())
        menu.command('重新合成新版本', lambda: run_command(page, state, '重新合成'))
    else:
        menu.command('生成分镜预演', lambda: run_command(page, state, ''))
    menu.command('本地生成参考草图', lambda: _open_inline_edit(
        page, state, '草图描述', '', lambda value: _apply_sketch(page, state, value)))
    return menu


def _reclassify(page, state, path, category):
    result = _safe_call(page, lambda: stage_execution_service.reclassify_animatic_reference(
        state['project'], path, category))
    if result is not None:
        page.status.set('参考图已改分类：%s' % category)


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
        state['manifest'] = _manifest(state['project'])
        state['version_tag'] = _version_tag(state['video'], state['manifest'])
        state['confirmed'] = _confirmed(state['manifest'])
        for var in state['checks'].values():
            var.set(bool(state['confirmed']))
        _render_timeline(page, state)
        _update_summary(page, state)


def _registered_hook(panel, kind, key, ours):
    """当前登记是不是本页挂上去的——换页／重建时只释放自己的，不动别页的。"""
    box = getattr(panel, '_' + kind + '_handlers', None)
    if box is None:
        box = getattr(panel, kind + 's', None)
    entry = (box or {}).get(key)
    if entry is None:
        return False
    current = entry[1] if isinstance(entry, tuple) else entry
    return current is ours


def _release_panel(page, state):
    panel = getattr(page, 'files_panel', None)
    if panel is None:
        return
    index = state.get('page_index')
    if _registered_select(panel, index, state.get('select_fn')):
        setter = getattr(panel, 'set_select_handler', None)
        if callable(setter):
            setter(index, None)
    for kind, key in (('import', 'import_fn'), ('menu', 'menu_fn')):
        if _registered_hook(panel, kind, 'animatic', state.get(key)):
            setter = getattr(panel, 'set_' + kind + '_handler', None)
            if callable(setter):
                setter('animatic', None)


def _registered_select(panel, index, ours):
    box = getattr(panel, '_select_handlers', None)
    if box is None:
        box = getattr(panel, 'select', None)
    entry = (box or {}).get(index)
    return bool(entry and entry[0] is ours)


def _register_panel(page, state):
    panel = getattr(page, 'files_panel', None)
    if panel is None:
        return
    select = getattr(panel, 'set_select_handler', None)
    if callable(select):
        select(getattr(page, 'page_index', None), state['select_fn'],
               default=state.get('source') or None)
    importer = getattr(panel, 'set_import_handler', None)
    if callable(importer):
        importer('animatic', state['import_fn'])
    menus = getattr(panel, 'set_menu_handler', None)
    if callable(menus):
        menus('animatic', state['menu_fn'])


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

    def release(_event=None):
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
             'manifest': manifest,
             'version_tag': _version_tag(video, manifest),
             'confirmed': _confirmed(manifest),
             'checks': {}, 'confirm_bar': None,
             'edit_box': None, 'edit_commit': None, 'edit_cancel': None,
             'timeline_box': None, 'info_label': None,
             'select_fn': None, 'import_fn': None, 'menu_fn': None}
    state['board'] = _load_board(project, state['source'])
    state['open_video'] = lambda: _open_video(page, state)
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
        timeline = _quiet(
            lambda: stage_execution_service.load_or_sync_animatic_timeline(project))
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
    _register_panel(page, state)
    _register_send_key(page, state)
    _update_summary(page, state)
    frame._animatic_state = state
    return frame


def build_animatic_page(page):
    """页面构建入口别名：与 ``show`` 同一条建页链。"""
    return show(page)

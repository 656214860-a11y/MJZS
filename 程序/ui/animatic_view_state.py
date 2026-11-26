"""分镜预演界面使用的指令解析、摘要、镜头图版本、时间线度量与宿主回调小助手。"""
import math
import re
from pathlib import Path

import contract.error_codes as error_codes
import infra.app_logging as app_logging
import infra.file_cache as file_cache
import stage_execution_service
from contract.platform_tools import ExecutionStopped
from contract.stage_path_service import write_dir
from domain import animatic_audio
from domain.animatic_service import CONFIRMATIONS, MANIFEST
from ui_tokens import DESKTOP_LAYOUT, SPACING

_REDO = re.compile(r'重做[^0-9a-zA-Z]{0,8}sh?\s*(\d+)', re.IGNORECASE)


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


def _expand_reply(page):
    area = getattr(page, 'reply_area', None)
    if area is None or not callable(getattr(area, 'set_expanded', None)):
        return
    current = getattr(area, 'stage', None)
    if isinstance(current, str) and current != 'animatic':
        return
    try:
        area.set_expanded(True)
    except Exception:
        app_logging.swallowed()


def _reply_note(page, kind, text, *, expand=False, **fields):
    """向共用过程与回话区写本阶段记录；兼容无回话区或旧三参测试桩。"""
    note = getattr(page, 'reply_note', None)
    expanded = False
    if callable(note):
        kwargs = dict(fields)
        if expand:
            kwargs['expand'] = True
        attempts = [kwargs]
        if fields:
            attempts.append(dict(fields))
        attempts.append({})
        for extra in attempts:
            try:
                note(kind, 'animatic', text, **extra)
                expanded = bool(extra.get('expand'))
                break
            except TypeError:
                continue
            except Exception:
                app_logging.swallowed()
                break
    if expand and not expanded:
        _expand_reply(page)


def _run_async(page, work, done=None, label=None):
    """统一经宿主 ``async_`` 后台执行；业务异常包成结果，失败不进全局弹窗。"""
    if getattr(page, 'worker', None):
        page.status.set('请等待当前任务完成')
        return False

    def guarded():
        try:
            return True, work()
        except ExecutionStopped:
            raise
        except Exception as exc:
            try:
                import infra.diagnostic_capture as diagnostic_capture
                diagnostic_capture.record_degradation(
                    exc, page='animatic', project=str(getattr(page, 'root', '') or ''))
            except Exception:
                app_logging.swallowed()
            return False, error_codes.user_text(exc)

    runner = getattr(page, 'async_', None)
    if callable(runner):
        runner(guarded, done, label=label)
        return True
    result = _safe_call(page, guarded)
    if callable(done):
        done(result)
    return True


_TASK_FAILED = object()


def _task_payload(page, outcome, action):
    """解开 ``_run_async`` 的成败信封；失败只写状态栏与回话区。"""
    if not (isinstance(outcome, tuple) and len(outcome) == 2):
        return outcome
    ok, payload = outcome
    if ok:
        return payload
    message = '%s失败：%s' % (action, payload)
    page.status.set(message)
    _reply_note(page, 'error', message, expand=True)
    return _TASK_FAILED


_VERSION_NAME = re.compile(r'^v(\d+)\.', re.IGNORECASE)


_TIMELINE_WIDTH_PER_SECOND = 16


_TIMELINE_MIN_CELL_WIDTH = 64
_TIMELINE_CELL_HEIGHT = 86
_TIMELINE_THUMB_SIZE = 48

_TIMELINE_COMPACT_CELL_HEIGHT = SPACING['2xl'] * 2
_TIMELINE_COMPACT_THUMB_SIZE = SPACING['2xl']
_PLAYER_COMPACT_HEIGHT = SPACING['2xl'] * 4
_PLAYER_COMPACT_COVER_SIZE = SPACING['2xl'] * 3
_PLAYER_REGULAR_COVER_SIZE = 160


def animatic_viewport_compact(win):
    width = _quiet(win.winfo_width, 0) if win is not None else 0
    height = _quiet(win.winfo_height, 0) if win is not None else 0
    if width < DESKTOP_LAYOUT['min_width'] or height <= 1:
        return False
    return height < DESKTOP_LAYOUT['compact_below']


def animatic_layout_metrics(win):
    compact = animatic_viewport_compact(win)
    return {
        'compact': compact,
        'player_height': _PLAYER_COMPACT_HEIGHT if compact else None,
        'cover_size': (_PLAYER_COMPACT_COVER_SIZE if compact
                       else _PLAYER_REGULAR_COVER_SIZE),
        'cell_height': (_TIMELINE_COMPACT_CELL_HEIGHT if compact
                        else _TIMELINE_CELL_HEIGHT),
        'thumb_size': (_TIMELINE_COMPACT_THUMB_SIZE if compact
                       else _TIMELINE_THUMB_SIZE),
    }


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


def _timeline_width(seconds):
    return max(_TIMELINE_MIN_CELL_WIDTH,
               int(_TIMELINE_WIDTH_PER_SECOND * float(seconds or 0)))


_PROMPT_FIELDS = ('image_prompt', 'prompt', 'video_prompt', 'description')
_UNADOPTED_MARKS = ('请先采用分镜', '未采用分镜', '尚无已采用分镜')
_STATUS_ERROR_MAX = 45


def shot_prompt_text(board_row):
    """与 animatic_service 同口径：依次读 image_prompt/prompt/video_prompt/description。"""
    row = board_row if isinstance(board_row, dict) else {}
    for key in _PROMPT_FIELDS:
        text = str(row.get(key) or '').strip()
        if text:
            return text
    return '（分镜未写提示词）'


def _timeline_load_error_text(exc):
    """把时间线载入异常压成 <=45 字的中文状态栏提示；未采用分镜返回空串。"""
    raw = str(exc or '').strip()
    if isinstance(exc, ValueError) and any(mark in raw for mark in _UNADOPTED_MARKS):
        return ''
    if isinstance(exc, UnicodeDecodeError) or exc.__class__.__name__ == 'JSONDecodeError':
        detail = '分镜文件格式损坏，请检查后重试'
    else:
        detail = error_codes.user_text(exc)
    text = detail if detail.startswith('载入') else ('载入预演时间线失败：' + detail)
    if len(text) > _STATUS_ERROR_MAX:
        return text[:_STATUS_ERROR_MAX - 1] + '…'
    return text


def load_timeline_for_show(page, loader):
    """建页载入时间线：未采用分镜安静进引导页，其余异常写入 <=45 字中文报错。"""
    try:
        return loader()
    except Exception as exc:
        message = _timeline_load_error_text(exc)
        if message:
            setter = getattr(getattr(page, 'status', None), 'set', None)
            if callable(setter):
                _quiet(lambda: setter(message))
        return None


def _refresh_files_panel(page):
    """参考图改类／改名／生图后刷新右侧文件面板（存在时）。"""
    refresh = getattr(getattr(page, 'files_panel', None), 'fill_script_list', None)
    if callable(refresh):
        _quiet(refresh)


TIMELINE_PAGE_SIZE = 20
CONFIGURE_DEBOUNCE_MS = 150
PLAYER_MODES = ('external', 'jianying', 'inline')
PLAYER_CAPTIONS = {
    'external': '点击用本地播放器打开（右键切换剪映/页内试播）',
    'jianying': '点击在剪映中打开（右键切换本地/页内试播）',
    'inline': '点击页内试播（右键切换本地播放器/剪映）',
}


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


def _version_tag(video, manifest):
    if video is not None:
        return Path(video).stem
    raw = (manifest or {}).get('video')
    return Path(raw).stem if raw else None


def player_mode_of(page):
    """读取并归一化默认播放方式，默认 external（优先本地默认播放器）。"""
    raw = str((getattr(page, 'settings', None) or {}).get('animatic_player_mode') or '').strip()
    return raw if raw in PLAYER_MODES else 'external'


def timeline_page_slice(shots, page_number, page_size=TIMELINE_PAGE_SIZE):
    """REQ-S04-108：按每页 page_size 镜切分时间线，返回 (page_shots, clamped_page, total_pages)。"""
    items = list(shots or ())
    size = max(1, int(page_size or TIMELINE_PAGE_SIZE))
    total_pages = max(1, (len(items) + size - 1) // size)
    try:
        wanted = int(page_number)
    except (TypeError, ValueError):
        wanted = 1
    clamped = max(1, min(total_pages, wanted))
    start = (clamped - 1) * size
    return items[start:start + size], clamped, total_pages


def shot_page_for_id(shots, shot_id, page_size=TIMELINE_PAGE_SIZE):
    """返回指定镜头 ID 所在的 1-based 页码；找不到时返回第 1 页。"""
    size = max(1, int(page_size or TIMELINE_PAGE_SIZE))
    for index, row in enumerate(shots or ()):
        if isinstance(row, dict) and row.get('id') == shot_id:
            return (index // size) + 1
    return 1


def shot_dialogue_seconds(project, row, probe=None):
    """REQ-S04-105/112：优先读时间线落盘的 dialogue_seconds，缺省再兜底 probe。"""
    if not isinstance(row, dict):
        return 0.0
    recorded = row.get('dialogue_seconds')
    if recorded is not None and not isinstance(recorded, bool):
        try:
            value = float(recorded)
            if math.isfinite(value) and value >= 0:
                return value
        except (TypeError, ValueError):
            pass
    clip = row.get('dialogue_audio')
    if not clip or not callable(probe) or not project:
        return 0.0
    target = Path(clip)
    if not target.is_absolute():
        target = Path(project) / target
    info = _quiet(lambda: probe(target))
    raw = info.get('duration') if isinstance(info, dict) else info
    if raw is None or isinstance(raw, bool):
        return 0.0
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return 0.0
    return value if math.isfinite(value) and value > 0 else 0.0


def cancel_debounced_layout(state):
    """取消挂起的 <Configure> 防抖定时器，避免销毁后迟到重绘。"""
    job = state.get('resize_job')
    state['resize_job'] = None
    frame = state.get('frame')
    if job is not None and frame is not None:
        _quiet(lambda: frame.after_cancel(job))


def schedule_debounced_layout(state, callback, *, delay_ms=CONFIGURE_DEBOUNCE_MS):
    """REQ-S04-108：<Configure> 150ms 防抖调度；连续触发合并为 1 次重绘。"""
    frame = state.get('frame')
    if frame is None or not _quiet(frame.winfo_exists, False):
        cancel_debounced_layout(state)
        return None
    cancel_debounced_layout(state)

    def run():
        state['resize_job'] = None
        if not _quiet(frame.winfo_exists, False):
            return
        callback()

    job = _quiet(lambda: frame.after(int(delay_ms), run))
    state['resize_job'] = job
    return job


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


def _confirmed(manifest):
    flags = (manifest or {}).get('confirmed') or {}
    return bool(flags) and all(bool(flags.get(key)) for key in CONFIRMATIONS)


def _music_text(state):
    folder = write_dir(state['project'], 'animatic') / animatic_audio.SUBDIRS['music']
    if folder.is_dir() and any(folder.iterdir()):
        return '已导入'
    return '未导入'


def _open_video(page, state):
    """外部播放经注入的 media_page_services.open_path，不直接碰系统出口。"""
    services = getattr(page, 'media_page_services', None)
    opener = getattr(services, 'open_path', None)
    if state.get('video') is None or not callable(opener):
        return
    _safe_call(page, lambda: opener(state['video']))


def _open_in_jianying(page, state):
    """REQ-S04-106：复用 launch_editor 打开剪映并定位预演视频目录；未安装则只开目录并提示。"""
    video = state.get('video')
    folder = Path(video).parent if video is not None else None
    services = getattr(page, 'media_page_services', None)
    opener = getattr(services, 'open_path', None)
    launcher = getattr(page, 'launch_editor', None)
    launched = False
    if callable(launcher):
        try:
            launcher()
            launched = True
        except Exception:
            launched = False
    if folder is not None and callable(opener):
        _safe_call(page, lambda: opener(folder))
    if not launched:
        page.status.set('未检测到剪映，已打开预演视频目录')


def _audition_dialogue(page, state, row):
    """REQ-S04-107：非阻塞试听本镜对白音频；无对白时写状态栏不报错。"""
    clip = row.get('dialogue_audio') if isinstance(row, dict) else None
    if not clip:
        page.status.set('该镜头暂无对白音频')
        return False
    target = Path(clip)
    if not target.is_absolute():
        target = Path(state['project']) / target
    services = getattr(page, 'media_page_services', None)
    opener = getattr(services, 'open_path', None)
    if not callable(opener):
        return False
    _safe_call(page, lambda: opener(target))
    return True


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


def _registered_select(panel, index, ours):
    box = getattr(panel, '_select_handlers', None)
    if box is None:
        box = getattr(panel, 'select', None)
    entry = (box or {}).get(index)
    return bool(entry and entry[0] is ours)


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

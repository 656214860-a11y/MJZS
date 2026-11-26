"""分镜预演界面使用的指令解析、摘要、镜头图版本、时间线度量与宿主回调小助手。"""
import re

import contract.error_codes as error_codes
import infra.app_logging as app_logging
from contract.platform_tools import ExecutionStopped
from contract.stage_path_service import write_dir
from domain import animatic_audio
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

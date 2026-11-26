"""REQ-S04-80…85/90：分镜预演时间线纯模型——构建、重建、改时长／版本／批注、版本命名与回写计划。

纯 L2：零同层 import、不写盘；timeline.json 的读取走 ``file_cache.read_json``、写入走
L3 发布器；版本登记经 ``contract.artifact_schema.stamp('animatic_timeline', ...)``。
时间线不改 S03 原稿；镜头顺序固定跟随已采用分镜，预演里不能调整。
"""
from copy import deepcopy
from pathlib import Path
import re

import contract.artifact_schema as artifact_schema

TIMELINE_FILE = 'timeline.json'
MIN_DURATION = 2
MAX_DURATION = 15
_DEFAULT_SECONDS = 4
_VERSION_PATTERN = re.compile(r'^v(\d+)\.[^.]+$', re.IGNORECASE)
_VIDEO_PATTERN = re.compile(r'^animatic_v(\d+)\.mp4$', re.IGNORECASE)

# REQ-S04-85/105/115 重建时同 ID 保留的时间线字段与单镜审核状态。
REVIEW_STATES = ('pending', 'approved', 'needs_revision')
_CARRIED = ('seconds', 'image_version', 'source', 'references',
            'dialogue_audio', 'dialogue_seconds', 'note', 'review_status')


def _shot_rows(storyboard):
    rows = storyboard.get('shots') if isinstance(storyboard, dict) else None
    if not isinstance(rows, list):
        raise ValueError('分镜缺少镜头数组')
    out = [row for row in rows if isinstance(row, dict) and str(row.get('id') or '').strip()]
    if not out:
        raise ValueError('分镜没有可用镜头')
    return out


def _default_seconds(shot):
    value = shot.get('duration')
    if type(value) is int:
        return min(MAX_DURATION, max(MIN_DURATION, value))
    if type(value) is float and float(value).is_integer():
        return min(MAX_DURATION, max(MIN_DURATION, int(value)))
    return _DEFAULT_SECONDS


def _new_row(shot):
    return {'id': str(shot['id']), 'seconds': _default_seconds(shot), 'image_version': 0,
            'source': 'generated', 'references': [], 'dialogue_audio': None,
            'dialogue_seconds': None, 'note': '', 'review_status': 'pending'}


def review_status_of(row):
    """REQ-S04-115：单镜审核状态归一化；旧项目缺失或非法值统一归为 pending。"""
    value = row.get('review_status') if isinstance(row, dict) else None
    return value if value in REVIEW_STATES else 'pending'


def build(storyboard, source_rel, source_sha, *, previous=None):
    """初建或按 REQ-S04-85 重建时间线，返回 ``(timeline, rebuilt)``。

    同一路径的旧时间线：同 ID 保留时长调整、图版本、来源、参考图、对白音频、批注与审核状态；
    新增镜头取默认值，已删镜头从时间线移除（盘上版本图文件由 L3 保留不删）。
    """
    previous = previous if isinstance(previous, dict) else None
    carried = {}
    if previous is not None and previous.get('source') == source_rel:
        for row in previous.get('shots') or []:
            if isinstance(row, dict) and row.get('id'):
                carried[str(row['id'])] = row
    shots = []
    for shot in _shot_rows(storyboard):
        old = carried.get(str(shot['id']))
        entry = _new_row(shot)
        if old is not None:
            for key in _CARRIED:
                if key in old:
                    entry[key] = deepcopy(old[key])
            entry['review_status'] = review_status_of(entry)
        shots.append(entry)
    timeline = artifact_schema.stamp('animatic_timeline', {
        'kind': 'animatic_timeline', 'source': str(source_rel),
        'source_sha256': str(source_sha), 'shots': shots})
    return timeline, previous is not None


def _row(timeline, shot_id):
    for row in timeline.get('shots') or []:
        if isinstance(row, dict) and row.get('id') == shot_id:
            return row
    raise ValueError('时间线没有此镜头：' + str(shot_id))


def set_duration(timeline, shot_id, seconds):
    """改单镜时长：仅 2–15 的整数秒（REQ-S04-81），返回新副本。"""
    if type(seconds) is not int or not MIN_DURATION <= seconds <= MAX_DURATION:
        raise ValueError('镜头时长必须是 2 至 15 的整数秒')
    out = deepcopy(timeline)
    _row(out, shot_id)['seconds'] = seconds
    return out


def set_version(timeline, shot_id, version, *, source=None):
    """切换当前选用的图版本（REQ-S04-82），可顺带记录来源，返回新副本。"""
    if type(version) is not int or version < 1:
        raise ValueError('图版本必须是正整数')
    out = deepcopy(timeline)
    row = _row(out, shot_id)
    row['image_version'] = version
    if source is not None:
        row['source'] = str(source)
    return out


def set_note(timeline, shot_id, note):
    """写单镜批注，返回新副本。"""
    out = deepcopy(timeline)
    _row(out, shot_id)['note'] = str(note or '')
    return out


def set_review_status(timeline, shot_id, status):
    """REQ-S04-115：设置单镜审核状态，非 REVIEW_STATES 抛 ValueError，返回新副本。"""
    if status not in REVIEW_STATES:
        raise ValueError('审核状态无效：' + str(status))
    out = deepcopy(timeline)
    _row(out, shot_id)['review_status'] = status
    return out


def needs_revision_ids(timeline):
    """REQ-S04-115：按时间线顺序返回全部标记为 needs_revision 的镜头编号。"""
    return tuple(
        str(row['id'])
        for row in (timeline.get('shots') or () if isinstance(timeline, dict) else ())
        if isinstance(row, dict) and row.get('id')
        and review_status_of(row) == 'needs_revision'
    )


def _board_shot_map(board):
    if isinstance(board, dict):
        shots = board.get('shots')
        if isinstance(shots, list):
            return {str(item['id']): item for item in shots
                    if isinstance(item, dict) and item.get('id')}
        return {str(key): value for key, value in board.items() if isinstance(value, dict)}
    if isinstance(board, (list, tuple)):
        return {str(item['id']): item for item in board
                if isinstance(item, dict) and item.get('id')}
    return {}


def _is_overlong(row):
    dialogue = row.get('dialogue_seconds')
    if not isinstance(dialogue, (int, float)) or isinstance(dialogue, bool):
        return False
    return float(dialogue) > float(row.get('seconds') or 0) + 0.1


def filter_shots(timeline, board, *, scene='', status=''):
    """REQ-S04-115：按场次与状态筛选时间线镜头（保序返回行列表）。"""
    rows = [row for row in (timeline.get('shots') or () if isinstance(timeline, dict) else ())
            if isinstance(row, dict)]
    scene_key = str(scene or '').strip()
    status_key = str(status or '').strip()
    board_map = _board_shot_map(board) if scene_key else {}
    matched = []
    for row in rows:
        if scene_key:
            meta = board_map.get(str(row.get('id') or ''), {})
            candidates = {
                str(meta.get(field) or '').strip()
                for field in ('scene_id', 'scene', 'location')
                if str(meta.get(field) or '').strip()
            }
            if scene_key not in candidates:
                continue
        if status_key in ('', 'all'):
            matched.append(row)
        elif status_key == 'needs_revision':
            if review_status_of(row) == 'needs_revision':
                matched.append(row)
        elif status_key == 'overlong':
            if _is_overlong(row):
                matched.append(row)
        elif status_key == 'missing_image':
            if int(row.get('image_version') or 0) <= 0:
                matched.append(row)
        elif status_key in REVIEW_STATES:
            if review_status_of(row) == status_key:
                matched.append(row)
    return matched


def next_version(existing_files):
    """扫描 ``v<N>.*`` 返回最大 N+1；无版本文件返回 1（REQ-S04-82 递增不覆盖）。"""
    top = 0
    for name in existing_files or ():
        match = _VERSION_PATTERN.match(Path(name).name)
        if match:
            top = max(top, int(match.group(1)))
    return top + 1


def next_video_name(existing_files):
    """返回下一个 ``版本/animatic_v<NNN>.mp4``（三位序号递增，REQ-S04-84）。"""
    top = 0
    for name in existing_files or ():
        match = _VIDEO_PATTERN.match(Path(name).name)
        if match:
            top = max(top, int(match.group(1)))
    return '版本/animatic_v%03d.mp4' % (top + 1)


def writeback_plan(storyboard, timeline):
    """REQ-S04-90：产出 ``(回写后的分镜深拷贝, changed)``，只改时长字段不写盘。

    各镜 ``duration`` 换成时间线 ``seconds``；顶层 ``duration`` 等于各镜之和。
    ``trim_out`` 大于新时长时夹紧到新时长；``trim_in`` 越界归零；``edit_duration``
    同步为 ``trim_out - trim_in``（REQ-S03-13）。提示词、对白与镜头顺序一律不动。
    """
    seconds = {str(row['id']): row.get('seconds') for row in timeline.get('shots') or []
               if isinstance(row, dict)}
    out = deepcopy(storyboard)
    changed = False
    for row in out.get('shots') or []:
        if not isinstance(row, dict):
            continue
        new = seconds.get(str(row.get('id')))
        if new is None or row.get('duration') == new:
            continue
        row['duration'] = new
        if row.get('trim_out') is not None and new < row['trim_out']:
            row['trim_out'] = new
            if row.get('trim_in', 0) >= new:
                row['trim_in'] = 0
            row['edit_duration'] = row['trim_out'] - row.get('trim_in', 0)
        changed = True
    total = sum(row['duration'] for row in out.get('shots') or []
                if isinstance(row, dict) and type(row.get('duration')) is int)
    if out.get('duration') != total:
        out['duration'] = total
        changed = True
    return out, changed

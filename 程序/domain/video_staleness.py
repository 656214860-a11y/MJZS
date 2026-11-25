"""视频版本输入指纹与只读过期判定。

目标不是预测“结果一定不同”，而是回答：这条已生成视频提交时所依赖的镜头内容、
首帧与参考资产，和当前要提交的内容是否仍是同一份。判定只读现算；不写回状态，
也不自动重做。
"""
from collections import OrderedDict
from pathlib import Path
import threading

from agent.core import file_hash, fingerprint, read
from contract.storyboard_paths import media_root
from domain.keyframe_evidence import picture_shot_payload

INPUT_SIGNATURE_FIELD = 'input_signature'
STATUS_GENERATING = 'generating'
STATUS_MISSING = 'missing'
STATUS_REVISE = 'revise'
STATUS_LEGACY_UNKNOWN = 'legacy_unknown'
STATUS_STALE = 'stale'
STATUS_CURRENT = 'current'

_VIDEO_OPTION_FIELDS = ('generate_audio', 'upload_white_model')
_HASH_CACHE = OrderedDict()
_HASH_LOCK = threading.Lock()


def _shot_payload(shot):
    """镜头侧语义输入；默认开关归一化，资产选择以实际解析出的参考图清单表达。"""
    payload = picture_shot_payload(shot if isinstance(shot, dict) else {})
    for key in _VIDEO_OPTION_FIELDS:
        default = True if key == 'generate_audio' else False
        payload[key] = bool((shot or {}).get(key, default))
    return payload


def _hash_file(path):
    try:
        path = Path(path).resolve()
    except (OSError, TypeError, ValueError):
        return None
    try:
        stat = path.stat()
    except OSError:
        return None
    if not path.is_file():
        return None
    key = (str(path), stat.st_mtime_ns, stat.st_size)
    with _HASH_LOCK:
        cached = _HASH_CACHE.get(key)
        if cached is not None:
            _HASH_CACHE.move_to_end(key)
            return cached
    try:
        digest = file_hash(path)
        after = path.stat()
    except OSError:
        return None
    if (after.st_mtime_ns, after.st_size) != (stat.st_mtime_ns, stat.st_size):
        return None
    with _HASH_LOCK:
        _HASH_CACHE[key] = digest
        while len(_HASH_CACHE) > 256:
            _HASH_CACHE.popitem(last=False)
    return digest


def _frame_sha256(source, shot):
    name = str((shot or {}).get('frame') or '')
    if not name or (shot or {}).get('frame_deleted'):
        return None
    try:
        media = media_root(source).resolve()
        path = (media / name).resolve()
    except (OSError, TypeError, ValueError):
        return None
    if not path.is_relative_to(media):
        return None
    return _hash_file(path)


def _declared_references(source, shot):
    """当前镜头声明的全部资产；清单缺失时保留未解析编号，不把旧视频误判成未过期。"""
    try:
        from agent import shot_assets
        rows = shot_assets.asset_rows(source)
        refs = shot_assets.assets(source, shot)
    except Exception:
        from domain.asset_context import references
        rows = {}
        refs = [{'id': value, 'name': value, 'path': None, 'ready': False}
                for _kind, value in references(shot)]
    return rows, refs


def _selected_references(source, shot, backend):
    _rows, refs = _declared_references(source, shot)
    if backend == 'comfy':
        selected = list((shot or {}).get('local_asset_ids') or [])
        selected = set(selected)
        return [row for row in refs if row.get('id') in selected]
    if not (shot or {}).get('upload_assets', True):
        return []
    selected = (shot or {}).get('upload_asset_ids')
    if selected is None:
        return refs
    selected = set(selected)
    return [row for row in refs if row.get('id') in selected]


def _reference_evidence(rows):
    result = []
    for row in rows or []:
        sha256 = row.get('sha256') or _hash_file(row.get('path'))
        result.append({'id': str(row.get('id') or ''),
                       'sha256': sha256})
    return result


def input_evidence(source, shot, backend='cloud', reference_rows=None, frame_sha256=None):
    """当前/提交时视频生成输入的可比对事实；只含会影响生成结果的内容。"""
    refs = (_selected_references(source, shot, backend)
            if reference_rows is None else list(reference_rows))
    return {'backend': backend,
            'shot': _shot_payload(shot),
            'frame_sha256': frame_sha256 or _frame_sha256(source, shot),
            'references': _reference_evidence(refs)}


def input_signature(source, shot, backend='cloud', reference_rows=None, frame_sha256=None):
    """按同一证据口径生成稳定指纹。内容不变则指纹不变，路径或展示性字段移动不影响。"""
    return fingerprint(input_evidence(source, shot, backend, reference_rows, frame_sha256))


def version_signature(version):
    return str((version or {}).get(INPUT_SIGNATURE_FIELD) or '')


def version_is_stale(source, shot, version):
    """已生成版本是否与当前内容不符。

    历史无签名记录无法可靠比对，返回 False；展示层须另按 ``legacy_unknown`` 明示
    “无法判定”，绝不静默当成最新。
    """
    if not version_signature(version):
        return False
    backend = 'comfy' if (version or {}).get('backend') == 'comfy' else 'cloud'
    return version_signature(version) != input_signature(source, shot, backend)


def stale_shots(source, shot_ids, versions_by_shot):
    """返回 shot_ids 中最新已下载版本输入已过期的镜头编号（只读）。"""
    episode = read(source)
    shots = {str(row.get('id') or ''): row for row in episode.get('shots', [])
             if isinstance(row, dict)}
    result = []
    for sid in sorted(shot_ids):
        shot = shots.get(sid)
        if shot is None:
            continue
        downloaded = [v for v in versions_by_shot.get(sid, [])
                      if isinstance(v, dict) and v.get('state') == 'downloaded']
        if downloaded and version_is_stale(source, shot, downloaded[-1]):
            result.append(sid)
    return result


def version_file_exists(root, version):
    name = str((version or {}).get('file') or '')
    if not name:
        return False
    try:
        root = Path(root).resolve()
        path = (root / name).resolve()
    except (OSError, TypeError, ValueError):
        return False
    return path.is_relative_to(root) and path.is_file()


def version_status(source, shot, version, root=None):
    """单个已生成版本的展示状态；missing/legacy/stale/current 语义互不混用。"""
    if not isinstance(version, dict):
        return STATUS_GENERATING
    if version.get('state') != 'downloaded':
        return STATUS_GENERATING
    if root is not None and not version_file_exists(root, version):
        return STATUS_MISSING
    if version.get('review') == 'revise':
        return STATUS_REVISE
    if not version_signature(version):
        return STATUS_LEGACY_UNKNOWN
    if version_is_stale(source, shot, version):
        return STATUS_STALE
    return STATUS_CURRENT

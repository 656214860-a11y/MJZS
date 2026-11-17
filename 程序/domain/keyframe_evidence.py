"""Read-only image validation and version evidence for first-frame publication."""
from collections import OrderedDict
import hashlib
import subprocess
import json
from pathlib import Path
import threading

from contract.platform_tools import run_process, tool_path


_DECODED = OrderedDict()
_LOCK = threading.Lock()
_FRAME_FIELDS = frozenset(('frame', 'frame_deleted', 'frame_evidence'))


def _digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(',', ':')).encode()).hexdigest()


def _file_hash(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def image_facts(image):
    """Fully decode PNG once per content digest; never trust filename or mtime."""
    raw = bytes(image) if isinstance(image, (bytes, bytearray)) else None
    path = None if raw is not None else Path(image)
    size = len(raw) if raw is not None else path.stat().st_size
    if not 0 < size <= 64 * 1024 * 1024:
        raise ValueError('首帧须为非空且不超过 64MB 的 PNG 图片')
    digest = hashlib.sha256(raw).hexdigest() if raw is not None else _file_hash(path)
    with _LOCK:
        cached = _DECODED.get(digest)
        if cached is not None:
            _DECODED.move_to_end(digest)
            return dict(cached)
    import struct
    import zlib
    try:
        data = raw if raw is not None else path.read_bytes()
        if data[:8] != b'\x89PNG\r\n\x1a\n':
            raise ValueError('首帧须为 PNG 图片')
        offset, width, height = 8, 0, 0
        chunks = []
        while offset < len(data):
            length = struct.unpack('>I', data[offset:offset + 4])[0]
            kind = data[offset + 4:offset + 8]
            end = offset + 8 + length
            payload = data[offset + 8:end]
            crc = struct.unpack('>I', data[end:end + 4])[0]
            if zlib.crc32(kind + payload) & 0xffffffff != crc:
                raise ValueError('首帧 PNG 校验和错误，图片已损坏')
            if not chunks:
                if kind != b'IHDR' or length != 13:
                    raise ValueError('首帧 PNG 图片头无效')
                width, height = struct.unpack('>II', payload[:8])
                if not 0 < width * height <= 40_000_000:
                    raise ValueError('首帧尺寸无效或超过 4000 万像素')
            chunks.append(kind)
            offset = end + 4
            if kind == b'IEND':
                if length or offset != len(data):
                    raise ValueError('首帧 PNG 结尾无效')
                break
        if not chunks or chunks[-1] != b'IEND' or b'IDAT' not in chunks:
            raise ValueError('首帧 PNG 未保存完整')
        decoder = tool_path('ffmpeg')
        result = run_process([decoder, '-v', 'error', '-xerror', '-err_detect', 'explode',
                              '-f', 'image2pipe', '-c:v', 'png', '-i', 'pipe:0',
                              '-f', 'null', '-'], input=data, capture_output=True, timeout=30)
        if result.returncode:
            raise ValueError('首帧图片损坏或无法完整解码，请重新导入')
        if path is not None and _file_hash(path) != digest:
            raise ValueError('首帧在校验期间发生变化，请重试')
    except (OSError, struct.error, subprocess.TimeoutExpired) as exc:
        raise ValueError('首帧图片损坏或解码器不可用，请重新导入或检查 FFmpeg') from exc
    facts = {'sha256': digest, 'width': width, 'height': height}
    with _LOCK:
        _DECODED[digest] = facts
        while len(_DECODED) > 128:
            _DECODED.popitem(last=False)
    return dict(facts)


def source_evidence(source, episode, shot):
    """Bind creative source and referenced assets, excluding generated frame state."""
    from domain.asset_context import references
    creative = dict(episode)
    creative['shots'] = [{k: v for k, v in row.items() if k not in _FRAME_FIELDS}
                         for row in episode.get('shots', ())]
    assets = []
    if list(references(shot)):
        from agent.shot_assets import assets as resolve_assets, asset_rows
        try:
            rows = asset_rows(source)
            refs = resolve_assets(source, shot)
        except ValueError:
            rows = {}
            refs = [{'id': aid, 'path': None} for _, aid in references(shot)]
        for ref in refs:
            row = {k: v for k, v in rows.get(ref['id'], {}).items()
                   if k not in ('_registry_base', 'image')}
            assets.append({'id': ref['id'], 'metadata': _digest(row),
                           'sha256': _file_hash(ref['path']) if ref.get('path') else None})
    return {'storyboard_sha256': _digest(creative), 'shot_id': shot.get('id'),
            'prompt_sha256': _digest({k: shot.get(k) for k in
                ('frame_prompt', 'keyframe_prompt', 'first_frame_prompt', 'image_prompt')}),
            'references': assets}


def _check_dimensions(facts, expected_size=None, aspect_ratio=None):
    width, height = facts['width'], facts['height']
    if expected_size is not None and [width, height] != list(expected_size):
        raise ValueError('首帧尺寸不符合本次生成设置')
    if aspect_ratio:
        try:
            w, h = (float(x) for x in str(aspect_ratio).split(':'))
            if not (w > 0 and h > 0) or abs(width / height / (w / h) - 1) > .01:
                raise ValueError
        except (ValueError, ZeroDivisionError, OverflowError):
            raise ValueError('首帧宽高比不符合当前制作画幅：' + str(aspect_ratio)) from None


def make_evidence(source, episode, shot, image, *, expected_size=None,
                  aspect_ratio=None, frozen_source=None):
    """Prepare a receipt; caller publishes it with the frame reference atomically."""
    facts = image_facts(image)
    _check_dimensions(facts, expected_size, aspect_ratio)
    current = source_evidence(source, episode, shot)
    if frozen_source is not None and current != frozen_source:
        raise ValueError('生成期间分镜或参考资产已变化，图片保留但需重新导入确认')
    return {'version': 1, 'image': facts, 'source': current,
            'expected_size': list(expected_size) if expected_size is not None else None,
            'aspect_ratio': aspect_ratio or ''}


def frame_problem(source, episode, shot, image, *, aspect_ratio=None):
    """Return actionable review reason, never silently approve legacy/external images."""
    try:
        facts = image_facts(image)
        evidence = shot.get('frame_evidence')
        if not isinstance(evidence, dict) or evidence.get('version') != 1:
            return '首帧缺少来源校验记录，请通过导入首帧重新确认'
        if evidence.get('image') != facts:
            return '首帧已被外部替换，待重新导入复核'
        _check_dimensions(facts, evidence.get('expected_size'),
                          aspect_ratio or evidence.get('aspect_ratio'))
        record = evidence.get('source')
        references = record.get('references') if isinstance(record, dict) else None
        if not isinstance(references, list) or any(not isinstance(row, dict) for row in references):
            return '首帧来源校验记录损坏，请重新导入确认'
        if any(not row.get('sha256') for row in references):
            return '首帧引用资产缺少可核对版本，请补齐资产后重新导入确认'
        if record != source_evidence(source, episode, shot):
            return '首帧来源分镜、提示词或参考资产已变化，待重新导入复核'
        return ''
    except (ValueError, OSError, TypeError, KeyError, AttributeError, IndexError) as exc:
        return str(exc) or '首帧校验未完成，请重新导入'

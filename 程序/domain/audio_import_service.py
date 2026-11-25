"""Safe, UI-independent imports of user-selected audio into the audio stage."""
import uuid
import logging
from pathlib import Path
from contract.service_contract import SystemError, UserError, success
from agent.media import MediaValidationError


_SUFFIXES = {'.wav', '.mp3', '.m4a', '.aac'}
LOGGER = logging.getLogger('audio_import_service')


def import_audio(project, source, *, publish, stage='audio', kind='dialogue', subdir=None):
    """Copy one non-empty supported audio file into the authoritative stage directory.

    ``kind`` 标明音轨用途（对白／旁白／BGM／音效／整轨）：非对白音轨加可识别前缀，
    完成核验据此判断「导入 BGM 不能算作对白已完成」。``subdir`` 仅对
    ``stage=='animatic'`` 生效，且解析后必须仍在阶段目录内。
    """
    from contract.stage_path_service import write_dir
    from domain.tts_api import AUDIO_KINDS, AUDIO_KIND_PREFIXES
    from contract.file_naming import generate_existing
    if stage not in ('audio', 'animatic'):
        raise ValueError('不支持的音频导入阶段')
    if kind not in AUDIO_KINDS:
        raise ValueError('不支持的音频用途：' + str(kind))
    if not callable(publish):
        raise TypeError('音频导入发布必须由 L3 注入。')
    try:
        project = Path(project).resolve()
        source = Path(source).resolve()
        if not source.is_file() or not source.stat().st_size:
            return UserError('音频文件为空，请选择有效文件')
        suffix = source.suffix.lower()
        if suffix not in _SUFFIXES:
            return UserError('请选择 WAV、MP3、M4A 或 AAC 音频文件')
        folder = write_dir(project, stage)
        if stage == 'audio':
            from contract.project_stages import audio
            folder = audio(project)
        if subdir is not None and stage == 'animatic':
            target = (folder / subdir).resolve()
            if not target.is_relative_to(folder.resolve()):
                raise ValueError('音频导入目录越界')
            folder = target
        folder.mkdir(parents=True, exist_ok=True)
        destination = folder / generate_existing('audio_import', prefix=AUDIO_KIND_PREFIXES.get(kind, ''),
                                                  stem=source.stem, token=uuid.uuid4().hex[:6], suffix=suffix)
        publish(destination, source)
        from infra.file_index import record_origin
        record_origin(project, [destination], '用户上传')
    except MediaValidationError as exc:
        return UserError(str(exc))
    except OSError:
        LOGGER.exception('音频导入失败')
        return SystemError('音频导入失败，请检查源文件、文件权限和磁盘空间后重试。')
    return success(destination)


MANIFEST_NAMES = ('voice.json', 'subtitles.json', 'audio_manifest.json')
_SUBTITLE_SUFFIXES = {'.srt': 'srt', '.ass': 'ass', '.txt': 'dialogue_script', '.json': 'calibration'}


_SENTENCE_DIR = '配音分句'
_EXCLUDED_DIRS = {'历史版本', '回收站'}


def _listing(folder, project, suffixes):
    if not folder.is_dir():
        return []
    rows = []
    for path in sorted(folder.iterdir()):
        if path.is_file() and path.suffix.lower() in suffixes:
            rows.append((path, path.relative_to(project).as_posix(), path.stat().st_size))
    return rows


def _sentence_walk(folder, suffixes):
    for path in sorted(folder.iterdir()):
        if path.is_dir():
            if path.name not in _EXCLUDED_DIRS:
                yield from _sentence_walk(path, suffixes)
        elif path.is_file() and path.suffix.lower() in suffixes:
            yield path


def _sentence_listing(folder, project, suffixes):
    """递归列出 配音分句/<批次>/ 下的音频；批次名取 配音分句 下第一层目录。"""
    if not folder.is_dir():
        return []
    rows = []
    for batch in sorted(folder.iterdir()):
        if batch.is_dir() and batch.name not in _EXCLUDED_DIRS:
            rows.extend((path, path.relative_to(project).as_posix(), path.stat().st_size, batch.name)
                        for path in _sentence_walk(batch, suffixes))
    return rows


def _sha256(path):
    import hashlib
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(1 << 20), b''):
            digest.update(block)
    return digest.hexdigest()


def audio_manifests(project):
    """按磁盘上已发布的音频与字幕成果生成三份配音字幕清单载荷：{文件名: 载荷}。

    只读目录，不做哈希之外的内容解析；音轨用途沿用文件名前缀口径（认不出按对白）。
    """
    from contract.project_stages import audio, subtitles
    from domain.tts_api import audio_kind
    project = Path(project).resolve()
    tracks = [{'file': rel, 'kind': audio_kind(path.name), 'bytes': size}
              for path, rel, size in _listing(audio(project), project, _SUFFIXES)]
    tracks.extend({'file': rel, 'kind': 'dialogue', 'bytes': size, 'batch': batch}
                  for path, rel, size, batch in
                  _sentence_listing(audio(project) / _SENTENCE_DIR, project, _SUFFIXES))
    files = [{'file': rel, 'format': _SUBTITLE_SUFFIXES[path.suffix.lower()], 'bytes': size,
              'sha256': _sha256(path)}
             for path, rel, size in _listing(subtitles(project), project, set(_SUBTITLE_SUFFIXES))]
    voice = {'stage': 'audio', 'tracks': tracks}
    subtitle = {'stage': 'audio', 'files': files}
    return {'voice.json': voice, 'subtitles.json': subtitle,
            'audio_manifest.json': {'stage': 'audio', 'voice': voice, 'subtitles': subtitle,
                                    'track_count': len(tracks), 'subtitle_count': len(files)}}

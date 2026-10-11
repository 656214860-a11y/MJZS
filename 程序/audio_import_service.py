"""Safe, UI-independent imports of user-selected audio into the audio stage."""
import uuid
import logging
from pathlib import Path
from service_contract import SystemError, UserError, success
from agent.media import MediaValidationError


_SUFFIXES = {'.wav', '.mp3', '.m4a', '.aac'}
LOGGER = logging.getLogger(__name__)


def import_audio(project, source, *, publish, stage='audio'):
    """Copy one non-empty supported audio file into the authoritative stage directory."""
    from stage_path_service import write_dir
    if stage not in ('audio', 'animatic'):
        raise ValueError('不支持的音频导入阶段')
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
            from project_stages import audio
            folder = audio(project)
        folder.mkdir(parents=True, exist_ok=True)
        destination = folder / (source.stem + '_' + uuid.uuid4().hex[:6] + suffix)
        publish(destination, source)
    except MediaValidationError as exc:
        return UserError(str(exc))
    except OSError:
        LOGGER.exception('音频导入失败')
        return SystemError('音频导入失败，请检查源文件、文件权限和磁盘空间后重试。')
    return success(destination)

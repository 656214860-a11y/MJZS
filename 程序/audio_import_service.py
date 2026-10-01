"""Safe, UI-independent imports of user-selected audio into the audio stage."""
import uuid
from pathlib import Path


_SUFFIXES = {'.wav', '.mp3', '.m4a', '.aac'}


def import_audio(project, source, *, publish):
    """Copy one non-empty supported audio file into the authoritative stage directory."""
    from project_stages import audio
    project = Path(project).resolve()
    source = Path(source).resolve()
    if not source.is_file() or not source.stat().st_size:
        raise ValueError('音频文件为空，请选择有效文件')
    suffix = source.suffix.lower()
    if suffix not in _SUFFIXES:
        raise ValueError('请选择 WAV、MP3、M4A 或 AAC 音频文件')
    folder = audio(project)
    folder.mkdir(parents=True, exist_ok=True)
    destination = folder / (source.stem + '_' + uuid.uuid4().hex[:6] + suffix)
    expected_size = source.stat().st_size
    data = source.read_bytes()
    publish(destination, data,
            lambda raw: bool(raw) and len(raw) == expected_size,
            lambda _target: None)
    return destination

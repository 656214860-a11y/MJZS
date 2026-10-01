"""不依赖 Tk 的白模预演记录、目录与 Blender 发现服务。"""
import os
import shutil
from datetime import datetime
from pathlib import Path

from agent.core import save
from file_cache import read_json, remove_temporary_file
from project_naming import dated_path

_BLENDER_CACHE = []
_WORKSPACE_CACHE = {}
_BASE_CACHE = {}
_DIR_CACHE = {}

def read_record(root):
    path = root / '预演记录.json'
    if not path.is_file(): return {}
    try: result = read_json(path)
    except (OSError, UnicodeError) as exc: raise ValueError('白模记录无法读取，请保留原文件并检查') from exc
    if not isinstance(result, dict): raise ValueError('白模记录格式错误，请保留原文件并检查')
    if result.get('preview') and Path(result['preview']).suffix.lower() not in ('.mp4', '.webm', '.mov'):
        result.setdefault('project_file', result.pop('preview'))
    return result

def write_record(root, data): save(root / '预演记录.json', data)


def import_previs_media(root, sid, source):
    """受控发布用户选定的白模视频或工程，源文件始终保留。"""
    root = Path(root).resolve()
    if not sid or Path(sid).name != sid or sid in ('.', '..'):
        raise ValueError('镜头编号不正确')
    source = Path(source).resolve()
    allowed = ('.mp4', '.webm', '.mov', '.blend', '.json', '.cclayproject')
    if not source.is_file() or source.suffix.lower() not in allowed:
        raise ValueError('请选择白模视频或工程文件')
    if source.stat().st_size <= 0:
        raise ValueError('白模文件为空，原文件已保留')
    saved = read_record(root)
    root.mkdir(parents=True, exist_ok=True)
    target = dated_path(root, sid + '_白模预演', source.suffix.lower())
    temporary = target.with_suffix(target.suffix + '.importing')
    try:
        shutil.copy2(source, temporary)
        if temporary.stat().st_size != source.stat().st_size:
            raise ValueError('白模复制不完整，原文件已保留')
        temporary.replace(target)
        key = 'preview' if source.suffix.lower() in ('.mp4', '.webm', '.mov') else 'project_file'
        saved.update(shot_id=sid, updated_at=datetime.now().isoformat(timespec='seconds'))
        saved[key] = str(target)
        write_record(root, saved)
        return target
    except Exception:
        remove_temporary_file(target)
        raise
    finally:
        remove_temporary_file(temporary)


def save_previs_notes(root, sid, notes):
    """保存白模备注；UI 只提供编辑器内容。"""
    data = read_record(root)
    data.update({'shot_id': sid, 'notes': notes,
                 'updated_at': datetime.now().isoformat(timespec='seconds')})
    write_record(root, data)

def find_blender(refresh=False):
    if _BLENDER_CACHE and not refresh: return _BLENDER_CACHE[0]
    choices = [Path('E:/Blender/blender.exe'), Path('D:/Blender/blender.exe')]
    found = shutil.which('blender')
    if found: choices.insert(0, Path(found))
    base = Path(os.environ.get('ProgramFiles', 'C:/Program Files')) / 'Blender Foundation'
    if base.is_dir(): choices.extend(sorted(base.glob('*/blender.exe'), reverse=True))
    result = next((path for path in choices if path.is_file()), None)
    _BLENDER_CACHE[:] = [result]
    return result

def workspace():
    blender = find_blender(); key = str(blender) if blender else ''
    cached = _WORKSPACE_CACHE.get(key)
    if cached is None:
        cached = ((blender.parent if blender else Path('E:/Blender')) / '白模项目').resolve()
        _WORKSPACE_CACHE.clear(); _WORKSPACE_CACHE[key] = cached
    return cached

def shot_directory(project, sid, workspace_path=None):
    space = workspace_path if workspace_path is not None else workspace(); key = (str(space), Path(project).name)
    base = _BASE_CACHE.get(key)
    if base is None:
        base = (space / Path(project).name).resolve(); _BASE_CACHE.clear(); _BASE_CACHE[key] = base
    if not sid or Path(sid).name != sid or sid in ('.', '..'): raise ValueError('镜头编号不正确')
    root = base / sid
    if not root.is_relative_to(base): raise ValueError('镜头编号不正确')
    key = (base, str(sid)); cached = _DIR_CACHE.get(key)
    if cached is not None: return cached
    resolved = root.resolve()
    if resolved == root:
        if len(_DIR_CACHE) >= 1024: _DIR_CACHE.clear()
        _DIR_CACHE[key] = resolved
    return resolved

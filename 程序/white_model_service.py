"""不依赖 Tk 的白模预演记录、目录与 Blender 发现服务。"""
import os
import re
import shutil
import uuid
from datetime import datetime
from pathlib import Path

from file_cache import read_json, remove_temporary_file
from project_naming import dated_path
from project_context import ProjectContext

_BLENDER_CACHE = []
_WORKSPACE_CACHE = {}
_BASE_CACHE = {}
_DIR_CACHE = {}
_UNSAFE_SEGMENT = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def _context(value):
    """白模项目目录只能由 L3 注入的项目上下文解析。"""
    if not isinstance(value, ProjectContext):
        raise TypeError('白模项目路径需要由 L3 注入 ProjectContext。')
    return value


def _json_quiet(path):
    """读一份可缺省的 JSON：不存在或损坏都当没有，不把异常带进目录解析。"""
    try:
        return read_json(path)
    except (OSError, ValueError, UnicodeError):
        return None


def _segment(value, fallback='_'):
    """目录段只接受安全文件名；缺失或含分隔符时退回 fallback。"""
    text = _UNSAFE_SEGMENT.sub('_', str(value or '')).strip().strip('. ')
    return text[:64] if text and text not in ('.', '..') else fallback


def project_identity(root):
    """项目稳定身份：项目 config.json 里的 project_id。

    身份写在项目目录内，项目改名或整体移动后跟着走，白模目录不会串到另一处同名项目。
    没有这一项时返回 None，目录沿用旧布局（工作区／项目目录名／镜头），旧成果只读兼容；
    升级走 ``migrate_legacy_directories``。
    """
    config = _json_quiet(Path(root) / 'config.json')
    value = config.get('project_id') if isinstance(config, dict) else None
    text = str(value or '').strip()
    return text if text and text == _segment(text) else None


def _reroot(root, path):
    """绝对路径失效（项目改名／移动）时，按阶段目录名在项目内重新定位同一份分镜。"""
    from project_stages import STAGES
    names = set(STAGES.values())
    parts = Path(path).parts
    for index, part in enumerate(parts):
        if part in names:
            return Path(root).joinpath(*parts[index:])
    return None


def _episode_candidates(root, source):
    """能判定「当前是哪一集」的分镜文件，按可信度从高到低惰性给出。"""
    root = Path(root)

    def declared():
        if source is not None:
            yield Path(source)
        prefs = _json_quiet(root / 'ui_settings.json')
        if isinstance(prefs, dict):
            for key in ('frame_json', 'storyboard_file'):
                value = prefs.get(key)
                if isinstance(value, str) and value.strip():
                    path = Path(value)
                    yield path if path.is_absolute() else root / path
        config = _json_quiet(root / 'config.json')
        value = config.get('episode_file') if isinstance(config, dict) else None
        if isinstance(value, str) and value.strip():
            yield Path(value)

    for path in declared():
        yield path
        # 项目整体改名或移动后，项目配置里记的绝对路径会失效；项目内的分镜跟着项目走，
        # 所以按阶段目录名把同一份分镜重新定位一次，集号才不会退回「未分集」。
        relocated = _reroot(root, path) if path.is_absolute() else None
        if relocated is not None and relocated != path:
            yield relocated


def episode_identity(root, sid, source=None):
    """集身份：镜头编号自带的 EP 前缀最优先，其次当前分镜，最后项目配置。"""
    prefix = re.match(r'(EP\d{3,})_', str(sid))
    if prefix:
        return prefix.group(1)
    for candidate in _episode_candidates(root, source):
        data = _json_quiet(candidate)
        value = data.get('episode_id') if isinstance(data, dict) else None
        if isinstance(value, str) and value.strip():
            return _segment(value, '未分集')
    return '未分集'


def _base(context, space):
    """(项目身份, 基目录)：有身份用项目 UUID，没有身份退回旧目录名。"""
    project = _context(context).root
    key = (str(space), str(project))
    cached = _BASE_CACHE.get(key)
    if cached is None:
        identity = project_identity(project)
        cached = (identity, (space / (identity or project.name)).resolve())
        if len(_BASE_CACHE) >= 1024: _BASE_CACHE.clear()
        _BASE_CACHE[key] = cached
    return project, cached


def legacy_base(project, workspace_path=None):
    """旧布局的镜头父目录（工作区／项目目录名）；迁移源，也是旧成果所在。"""
    space = workspace_path if workspace_path is not None else workspace()
    return (space / Path(project).name).resolve()


def read_record(root):
    path = root / '预演记录.json'
    if not path.is_file(): return {}
    try: result = read_json(path)
    except (OSError, UnicodeError) as exc: raise ValueError('白模记录无法读取，请保留原文件并检查') from exc
    if not isinstance(result, dict): raise ValueError('白模记录格式错误，请保留原文件并检查')
    if result.get('preview') and Path(result['preview']).suffix.lower() not in ('.mp4', '.webm', '.mov'):
        result.setdefault('project_file', result.pop('preview'))
    return result

def write_record(root, data, *, publish):
    """发布预演记录；正式写入能力由 L3 显式注入。"""
    return publish(Path(root) / '预演记录.json', data)


def import_previs_media(root, sid, source, *, publish):
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
        write_record(root, saved, publish=publish)
        return target
    except Exception:
        remove_temporary_file(target)
        raise
    finally:
        remove_temporary_file(temporary)


def save_previs_notes(root, sid, notes, *, publish):
    """保存白模备注；UI 只提供编辑器内容。"""
    data = read_record(root)
    data.update({'shot_id': sid, 'notes': notes,
                 'updated_at': datetime.now().isoformat(timespec='seconds')})
    write_record(root, data, publish=publish)

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

def shot_directory(context, sid, workspace_path=None, source=None):
    """这一镜的白模目录：项目身份／集／镜头；没有项目身份时沿用旧布局。"""
    if not sid or Path(sid).name != sid or sid in ('.', '..'): raise ValueError('镜头编号不正确')
    space = workspace_path if workspace_path is not None else workspace()
    project, (identity, base) = _base(context, space)
    parent = base if identity is None else base / episode_identity(project, sid, source)
    root = parent / sid
    if not root.is_relative_to(base): raise ValueError('镜头编号不正确')
    key = (str(parent), str(sid)); cached = _DIR_CACHE.get(key)
    if cached is not None: return cached
    resolved = root.resolve()
    if resolved == root:
        if len(_DIR_CACHE) >= 1024: _DIR_CACHE.clear()
        _DIR_CACHE[key] = resolved
    return resolved


def _adopted_shots(root):
    """采用分镜的「镜头→集」映射与来源版本；同一镜头落在两集时拒绝猜。"""
    from storyboard_adoption_contract import adopted
    mapping, versions = {}, {}
    for path in adopted(root):
        stat = Path(path).stat()
        data = _json_quiet(path)
        if not isinstance(data, dict): continue
        episode = _segment(data.get('episode_id'), '未分集')
        version = {'storyboard': str(path), 'episode_id': episode, 'size': stat.st_size,
                   'modified_at': datetime.fromtimestamp(stat.st_mtime).isoformat(timespec='seconds')}
        for shot in data.get('shots') or []:
            sid = shot.get('id') if isinstance(shot, dict) else None
            if not sid: continue
            previous = mapping.setdefault(sid, episode)
            if previous != episode:
                raise ValueError('镜头 %s 同时出现在 %s 与 %s 两集，请先整理采用分镜再迁移' % (sid, previous, episode))
            versions[sid] = version
    return mapping, versions


def _publish_identity(project, publish, identity):
    """项目身份只写一次；已经一致就不再重复落盘，配置读不出来时宁可不写。"""
    path = Path(project) / 'config.json'
    config = _json_quiet(path)
    if config is None and path.is_file():
        raise ValueError('项目配置无法读取，未写入项目身份：' + str(path))
    if not isinstance(config, dict): config = {}
    if config.get('project_id') == identity: return
    config['project_id'] = identity
    publish(path, config)


def migrate_legacy_directories(context, *, publish, workspace_path=None):
    """把旧布局的白模镜头目录迁进「项目身份／集／镜头」：可重复、不覆盖、失败回滚。

    先算完整清单：任一旧目录找不到对应采用分镜、或新目录已存在，都先说明再处理，
    不为搬完而藏起某个镜头。搬迁中途失败把已搬目录原样搬回，旧成果保持可用；
    全部搬完才把项目身份写进项目配置并落一份含来源版本的迁移清单。已有身份时直接返回。
    """
    project = _context(context).root
    space = workspace_path if workspace_path is not None else workspace()
    identity = project_identity(project)
    if identity is not None:
        return {'project_id': identity, 'moved': [], 'skipped': [], 'manifest': None}
    identity = uuid.uuid4().hex
    base = (space / identity).resolve()
    old_base = legacy_base(project, space)
    plan, skipped, unmapped = [], [], []
    if old_base.is_dir():
        episode_of, versions = _adopted_shots(project)
        for path in sorted((item for item in old_base.iterdir() if item.is_dir()), key=lambda item: item.name):
            episode = episode_of.get(path.name)
            if episode is None:
                unmapped.append(path.name); continue
            target = base / episode / path.name
            if target.exists():
                skipped.append({'sid': path.name, 'reason': '新目录已存在，未覆盖', 'target': str(target)}); continue
            plan.append({'sid': path.name, 'episode_id': episode, 'from': str(path), 'to': str(target),
                         'source_version': versions.get(path.name, {})})
        if unmapped:
            raise ValueError('旧白模目录 %s 找不到对应采用分镜；为避免藏起旧成果，整批迁移未开始'
                             % '、'.join(sorted(unmapped)))
    manifest = (project / '工作流任务' / '白模目录迁移'
                / datetime.now().strftime('%Y%m%d_%H%M%S_%f') / '迁移清单.json')
    record = {'project_id': identity, 'generated_at': datetime.now().isoformat(timespec='seconds'),
              'items': plan, 'skipped': skipped}
    if plan or skipped:
        publish(manifest, dict(record, status='planned'))
    done = []
    try:
        for item in plan:
            Path(item['to']).parent.mkdir(parents=True, exist_ok=True)
            shutil.move(item['from'], item['to'])
            done.append(item)
        # 身份落盘和搬迁是同一步：写不进去就把已搬目录搬回，避免成果留在读不到的布局里。
        _publish_identity(project, publish, identity)
    except Exception:
        for item in reversed(done):
            try: shutil.move(item['to'], item['from'])
            except OSError: pass
        if plan or skipped:
            try: publish(manifest, dict(record, status='rolled_back', moved=[item['sid'] for item in done]))
            except OSError: pass
        raise
    _BASE_CACHE.clear(); _DIR_CACHE.clear()
    if plan or skipped:
        publish(manifest, dict(record, status='completed', moved=[item['sid'] for item in plan]))
    return {'project_id': identity, 'moved': [item['sid'] for item in plan], 'skipped': skipped,
            'manifest': str(manifest) if (plan or skipped) else None}

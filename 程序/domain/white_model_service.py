"""不依赖 Tk 的白模预演记录、目录与 Blender 发现服务。"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import uuid
from datetime import datetime
from pathlib import Path

from file_cache import probe_writable, read_json, remove_temporary_file
from contract.platform_tools import run_process
from domain.project_naming import dated_path
import contract.stage_layout as stage_layout
from contract.project_context import ProjectContext

_BLENDER_CACHE = []
_WORKSPACE_CACHE = {}
_BASE_CACHE = {}
_DIR_CACHE = {}
_SETTINGS_CACHE = {}
_VERSION_CACHE = {}
SETTINGS_NAME = 'white_model_settings.json'
SETTINGS_ENV = 'MANJU_WHITE_MODEL_SETTINGS'
WORKSPACE_ENV = 'MANJU_WHITE_MODEL_WORKSPACE'
BLENDER_ENV = 'MANJU_BLENDER_EXE'
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
    from contract.project_stages import stage_dirs
    names = set(stage_dirs())
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


SOURCE_FIELDS = ('id', 'action', 'action_description', 'action_start', 'action_end',
                 'camera', 'camera_motion', 'duration', 'seconds',
                 'first_frame', 'keyframe', 'frame', 'characters', 'assets')


def shot_digest(shot):
    """采用分镜里这一镜的调度摘要；改动作、机位、时长或首帧都会换一个摘要。"""
    if not isinstance(shot, dict):
        return ''
    payload = {}
    for key in SOURCE_FIELDS:
        if key not in shot:
            continue
        value = shot[key]
        if isinstance(value, bool):
            payload[key] = value
        elif isinstance(value, (int, float)):
            payload[key] = float(value)      # 5 与 5.0 是同一件事，别让它变成版本变化
        else:
            payload[key] = value
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True,
                                     default=str).encode('utf-8')).hexdigest()


def source_digest(source, sid):
    """按当前采用分镜算出这一镜的来源摘要；分镜缺失或镜头不在其中都返回空串。"""
    if not source or not sid:
        return ''
    try:
        episode = read_json(Path(source))
    except (OSError, ValueError):
        return ''
    shots = episode.get('shots') if isinstance(episode, dict) else None
    if not isinstance(shots, list):
        return ''
    for shot in shots:
        if isinstance(shot, dict) and str(shot.get('id')) == str(sid):
            return shot_digest(shot)
    return ''


def evidence_state(record, preview, source=None, sid=None):
    """这一份预演记录相对当前采用分镜与预演文件的状态。

    `changed`：来源分镜或预演文件已经变过，旧就绪作废（成果本身不删）。
    `ok`：来源与媒体都对得上，可以直接复用。
    `unbound`：记录里没有登记来源摘要（升级前的旧成果），无法证明当前有效。
    """
    evidence = record.get('evidence') if isinstance(record, dict) else None
    if not isinstance(evidence, dict):
        return 'unbound'
    current = source_digest(source, sid)
    stored = str(evidence.get('source_sha256') or '')
    if current and stored and current != stored:
        return 'changed'
    if current and not stored:
        return 'unbound'
    try:
        stat = Path(preview).stat()
    except OSError:
        return 'missing'
    if evidence.get('preview_bytes') is not None and int(evidence['preview_bytes']) != stat.st_size:
        return 'changed'
    if evidence.get('preview_mtime_ns') is not None and int(evidence['preview_mtime_ns']) != stat.st_mtime_ns:
        return 'changed'
    return 'ok'


def record_evidence(root, sid, source, *, publish, media=None, preview=None):
    """预演通过媒体校验后登记「来源摘要 + 媒体事实」，此后版本变化即可判过期。

    只导入工程、还没有预演视频时不登记，也不报错。
    """
    root = Path(root)
    data = read_record(root)
    value = preview or data.get('preview')
    path = Path(value) if value else None
    try:
        size = path.stat().st_size if path else 0
    except OSError:
        size = 0
    if not path or not path.is_file() or not size:
        return None
    stat = path.stat()
    data['evidence'] = {'shot_id': str(sid or data.get('shot_id') or ''),
                        'source': str(source) if source else '',
                        'source_sha256': source_digest(source, sid),
                        'preview_bytes': stat.st_size,
                        'preview_mtime_ns': stat.st_mtime_ns,
                        'media': dict(media or {}),
                        'verified_at': datetime.now().isoformat(timespec='seconds')}
    write_record(root, data, publish=publish)
    return data['evidence']


PROJECT_INDEX = 'previs.json'
_PREVIEW_SUFFIXES = ('.mp4', '.webm', '.mov')


def project_index_path(context, *, write=False):
    """项目内预演索引 `09白模预演/output/previs.json`（stage_layout 契约名）；读取时旧目录只读兼容。"""
    from contract.stage_path_service import read_file, write_dir
    root = _context(context).root
    if write:
        return write_dir(root, 'previs') / 'output' / PROJECT_INDEX
    return read_file(root, 'previs', 'output', PROJECT_INDEX)


def read_project_index(context):
    data = _json_quiet(project_index_path(context))
    shots = data.get('shots') if isinstance(data, dict) else None
    return {'schema': 1, 'shots': dict(shots) if isinstance(shots, dict) else {}}


def sync_project_copy(context, sid, source, *, publish):
    """已通过校验的预演视频在项目内留一份副本并登记 previs.json；工作区丢失后仍可凭此判就绪。

    工作区记录无可用预览或证据不是 ok 时不动，返回 None；副本失败抛 OSError 由调用方决定。
    """
    context = _context(context)
    record = read_record(shot_directory(context, sid, source=source))
    value = record.get('preview')
    path = Path(value) if value else None
    if not (path and path.is_file() and path.stat().st_size
            and path.suffix.lower() in _PREVIEW_SUFFIXES):
        return None
    if evidence_state(record, path, source, sid) != 'ok':
        return None
    from contract.stage_path_service import write_dir
    folder = write_dir(context.root, 'previs') / 'assets' / _segment(sid)
    target = folder / path.name
    if not target.is_file() or target.stat().st_size != path.stat().st_size:
        folder.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(target.suffix + '.importing')
        try:
            shutil.copy2(path, temporary)
            temporary.replace(target)
        finally:
            remove_temporary_file(temporary)
    index = read_project_index(context)
    entry = {'shot_id': str(sid), 'source': str(source) if source else '',
             'source_sha256': source_digest(source, sid),
             'preview': target.relative_to(context.root).as_posix(),
             'preview_bytes': target.stat().st_size,
             'synced_at': datetime.now().isoformat(timespec='seconds')}
    index['shots'][str(sid)] = entry
    publish(project_index_path(context, write=True), index)
    return entry


def project_copy_ready(context, sid, source=None):
    """项目内副本是否还能证明这一镜预演就绪：文件在、大小对得上、来源分镜未变。"""
    context = _context(context)
    entry = read_project_index(context)['shots'].get(str(sid))
    if not isinstance(entry, dict) or not entry.get('source_sha256'):
        return False
    root = context.root.resolve()
    try:
        target = (root / str(entry.get('preview') or '')).resolve()
        if not target.is_relative_to(root) or target.suffix.lower() not in _PREVIEW_SUFFIXES:
            return False
        if not target.is_file() or target.stat().st_size != int(entry.get('preview_bytes') or -1):
            return False
    except (OSError, ValueError):
        return False
    current = source_digest(source, sid)
    return not current or current == entry['source_sha256']


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

def user_data_dir():
    """用户级数据目录：优先 LOCALAPPDATA，退回用户主目录（与 TTS／Seedream 设置同一口径）。"""
    return Path(os.environ.get('LOCALAPPDATA') or Path.home()) / '漫剧制作助手'

def settings_path():
    """白模设置文件位置：可用 ``MANJU_WHITE_MODEL_SETTINGS`` 指到别处。"""
    override = str(os.environ.get(SETTINGS_ENV) or '').strip()
    return Path(override) if override else user_data_dir() / SETTINGS_NAME

def read_settings(refresh=False):
    """读白模设置；不存在或损坏都当没有，绝不让它挡住页面。"""
    path = settings_path(); key = str(path)
    if not refresh and key in _SETTINGS_CACHE: return _SETTINGS_CACHE[key]
    data = _json_quiet(path)
    result = data if isinstance(data, dict) else {}
    if len(_SETTINGS_CACHE) >= 256: _SETTINGS_CACHE.clear()
    _SETTINGS_CACHE[key] = result
    return result

def default_workspace():
    """默认成果目录：用户数据目录下的「白模项目」。

    旧版默认把成果建在 Blender 安装目录旁（Program Files 下标准用户往往不可写），
    这里改成用户可写目录，让「工具可执行文件」与「用户成果」分开；旧位置由
    :func:`legacy_workspaces` 只读发现，不自动写入、不删旧文件。
    """
    return (user_data_dir() / '白模项目').resolve()

def configured_workspace():
    """用户配置的成果目录：环境变量优先，其次设置文件里的 ``workspace``。"""
    value = os.environ.get(WORKSPACE_ENV)
    if not str(value or '').strip():
        value = read_settings().get('workspace')
    text = str(value or '').strip()
    return Path(text) if text else None

def workspace():
    """成果目录：配置优先，否则用户数据目录；按目录缓存，绝不指向 Blender 安装目录。"""
    target = configured_workspace() or default_workspace()
    key = str(target)
    cached = _WORKSPACE_CACHE.get(key)
    if cached is None:
        cached = target.resolve()
        _WORKSPACE_CACHE.clear(); _WORKSPACE_CACHE[key] = cached
    return cached

def blender_candidates():
    """候选 blender.exe，按优先级：配置 → PATH → 常见盘符 → 两个 Program Files。只读发现。"""
    choices = []
    settings = read_settings()
    for value in (os.environ.get(BLENDER_ENV), settings.get('blender')):
        text = str(value or '').strip()
        if text: choices.append(Path(text))
    found = shutil.which('blender')
    if found: choices.append(Path(found))
    choices.extend([Path('D:/Blender/blender.exe'), Path('E:/Blender/blender.exe')])
    base = Path(os.environ.get('ProgramFiles', 'C:/Program Files')) / 'Blender Foundation'
    if base.is_dir(): choices.extend(sorted(base.glob('*/blender.exe'), reverse=True))
    other = os.environ.get('ProgramFiles(x86)')
    if other:
        alt = Path(other) / 'Blender Foundation'
        if alt.is_dir(): choices.extend(sorted(alt.glob('*/blender.exe'), reverse=True))
    return choices

def find_blender(refresh=False):
    if _BLENDER_CACHE and not refresh: return _BLENDER_CACHE[0]
    result = next((path for path in blender_candidates() if path.is_file()), None)
    _BLENDER_CACHE[:] = [result]
    return result

def _os_hint(exc):
    """把操作系统错误翻成可执行的一句话。"""
    code = getattr(exc, 'winerror', None) or getattr(exc, 'errno', None)
    if code in (5, 13):
        return '没有写入权限（可改用用户目录，或让管理员放开该目录）'
    if isinstance(exc, FileNotFoundError) or code == 2:
        return '盘符或目录不存在（例如本机没有该盘）'
    return '系统返回：' + str(exc)

def write_check(path, *, create=True):
    """让 L1 试写一个探针文件判断目录能否落成果，返回 ``(可写, 说明)``；探针随即删除。

    ``create=False`` 时不动手建目录：目录还不存在就只看最近一个已存在父目录是否可写，
    供每次打开页面时的轻量检查使用。真正的写入在 :func:`file_cache.probe_writable`。
    """
    try:
        probe_writable(Path(path), create=create)
    except OSError as exc:
        return False, '目录不可写：' + _os_hint(exc)
    return True, ''

def blender_version(exe, *, run=None):
    """读 blender.exe 的版本号；读不出来返回空串（版本不是可用性的前提）。"""
    if not exe: return ''
    key = str(exe)
    if key in _VERSION_CACHE: return _VERSION_CACHE[key]
    text = ''
    try:
        result = run_process([key, '--version'], capture_output=True, timeout=15, run=run)
        raw = getattr(result, 'stdout', b'') or b''
        text = raw.decode('utf-8', 'replace') if isinstance(raw, (bytes, bytearray)) else str(raw)
    except (OSError, subprocess.SubprocessError, ValueError):
        text = ''
    match = re.search(r'Blender\s+([0-9][0-9.]*)', text)
    version = match.group(1) if match else ''
    if len(_VERSION_CACHE) >= 64: _VERSION_CACHE.clear()
    _VERSION_CACHE[key] = version
    return version

def legacy_workspaces(workspace_path=None):
    """旧布局成果目录（只读发现）：旧版默认把「白模项目」建在 Blender 安装目录旁。"""
    current = Path(workspace_path).resolve() if workspace_path is not None else workspace()
    found, seen = [], set()
    for exe in blender_candidates():
        if exe is None: continue
        candidate = exe.parent / '白模项目'
        key = str(candidate)
        if key in seen or candidate.resolve() == current: continue
        seen.add(key)
        if candidate.is_dir(): found.append(candidate.resolve())
    return found

def environment_summary(include_version=False):
    """一行环境摘要给页面显示：成果目录＋写权限＋Blender；默认不跑版本探测。"""
    target = workspace()
    writable, reason = write_check(target, create=False)
    exe = find_blender()
    blender = ('未检测到 Blender（可只准备脚本）' if exe is None
               else 'Blender ' + (blender_version(exe) if include_version else '已找到'))
    text = '成果目录：' + str(target) + '（' + ('可写' if writable else '不可写：' + reason) + '）；' + blender
    legacy = legacy_workspaces(target)
    if legacy: text += '　·　发现旧成果目录（只读）：' + '、'.join(str(item) for item in legacy)
    return text

def diagnose(workspace_path=None, blender=None, run=None):
    """首次配置检查：Blender 版本＋成果目录写权限＋可执行提示。只读，不写作品。"""
    exe = blender if blender is not None else find_blender()
    target = Path(workspace_path).resolve() if workspace_path is not None else workspace()
    writable, reason = write_check(target)
    version = blender_version(exe, run=run)
    issues, hints = [], []
    if exe is None:
        issues.append('未检测到 Blender')
        hints.append('请安装 Blender，或在设置里指定 blender：' + str(settings_path()))
    if not writable:
        issues.append('成果目录不可写（' + reason + '）')
        hints.append('请在设置里把 workspace 指到用户可写目录：' + str(settings_path())
                     + '（例如 ' + str(default_workspace()) + '）；不会把成果写进程序安装区。')
    legacy = legacy_workspaces(target)
    if legacy:
        hints.append('旧目录里还有白模成果，可在设置里把 workspace 指过去，或手工搬移：'
                     + '、'.join(str(item) for item in legacy))
    return {'blender': str(exe) if exe else '', 'blender_version': version,
            'workspace': str(target),
            'workspace_source': 'configured' if configured_workspace() else 'default',
            'writable': writable, 'write_issue': reason, 'legacy': [str(item) for item in legacy],
            'settings': str(settings_path()), 'issues': issues, 'hints': hints}

def diagnose_text(report=None):
    """把 :func:`diagnose` 的结果排成多行文本，给通知框显示。"""
    data = report if report is not None else diagnose()
    lines = ['成果目录：' + data['workspace'] + '（' + ('可写' if data['writable'] else '不可写') + '）',
             'Blender：' + ((data['blender'] + '（版本 ' + (data['blender_version'] or '未知') + '）')
                            if data['blender'] else '未检测到'),
             '设置文件：' + data['settings']]
    if data['legacy']: lines.append('旧成果目录（只读）：' + '、'.join(data['legacy']))
    lines.extend('· ' + hint for hint in data['hints'])
    if not data['hints']: lines.append('· 环境正常，无需处理')
    return '\n'.join(lines)

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
    from domain.storyboard_adoption_contract import adopted
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
    manifest = (stage_layout.workflow_dir(project, '白模目录迁移')
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

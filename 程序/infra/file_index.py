# -*- coding: utf-8 -*-
"""项目文件索引：目录与元数据的唯一缓存（R3093，任务书 P0 轮；Q10／Q12／Q17）。

索引是**缓存**而不是事实源：任何时刻都可以 ``rebuild()`` 从磁盘全量重建。事实仍在
磁盘上，索引用坏了大不了重扫一次——这条边界保证本模块永远不可能让用户数据受损。

- 写盘：``agent.core.save()``（原子写＋事务日志）。
- 读盘：``file_cache.read_json()``（正式 JSON 读的唯一入口）。
- 路径：一行只存**项目相对 posix**，整个项目换目录不需要改写索引。
- 扫描：只在本模块被显式调用时发生（用户点重建、发布后增量更新、后台线程首次加载），
  **绝不放进启动路径**（AGENTS 规则 33：启动零递归扫描）。
"""
from __future__ import annotations

import math
import os
import stat
import threading
import time
from contextlib import contextmanager
from pathlib import Path, PurePosixPath, PureWindowsPath

import contract.stage_layout as stage_layout
from contract import file_naming
from contract.file_index_contract import (FileRow, INDEX_VERSION, ORIGINS, ORIGIN_SYSTEM, ORIGIN_USER,
                                          STATUSES, STATUS_ARCHIVED,
                                          STATUS_DRAFT, STATUS_PUBLISHED, normalize_status)
from contract.stage_path_service import read_dirs, write_dir
from contract.pet_bus import STAGES as STAGE_ORDER

INDEX_DIR_NAME = '文件索引'
INDEX_NAME = 'index.json'
CONFIRM_DIR_NAME = '成果确认'
DELIVERY_MANIFEST = 'delivery_manifest.json'
# 兼容既有调用方的格式集合；类型判断仍由 file_naming 唯一规则产出。
IMAGE_SUFFIXES = frozenset(key for key, value in file_naming._SUFFIX_KINDS.items() if value == '资产')
AUDIO_SUFFIXES = frozenset(key for key, value in file_naming._SUFFIX_KINDS.items() if value == '音频')
VIDEO_SUFFIXES = frozenset(key for key, value in file_naming._SUFFIX_KINDS.items() if value == '视频')
# 全项目覆盖用户文件；配置、凭据、运行记录及可再生缓存永不入表。
SKIP_DIRS = frozenset({stage_layout.WORKFLOW_DIR, '__pycache__', '.git', '.cache', 'cache',
                       '配置', 'config', 'configs', 'private', 'logs', 'log', 'data',
                       '运行记录', '运行日志', '缓存', '.ssh', '.aws', '.azure', '.gnupg',
                       '.pytest_cache', '.mypy_cache', '.ruff_cache', '.venv', 'venv', 'node_modules'})
SKIP_FILES = frozenset({stage_layout.SKILL_CONFIG_NAME, 'config.json', 'projects.json', 'desktop_settings.json',
                        'credentials.json', 'credentials', '素材库.json', 'id_rsa', 'id_ed25519',
                        'token.json', 'token.txt', 'tokens.json', 'auth.json', 'env', '.netrc'})
# 停靠面板不列的功能文件后缀：这些文件仍进索引，其他调用方不受影响。
FUNCTIONAL_SUFFIXES = frozenset({'.json', '.jsonl', '.yaml', '.yml', '.toml', '.ini', '.cfg',
                                '.lock', '.bak', '.db', '.sqlite', '.pkl'})


def is_functional(relative_path):
    """按小写后缀判断是否为功能文件（停靠面板不列，索引仍收录）。"""
    return Path(str(relative_path)).suffix.lower() in FUNCTIONAL_SUFFIXES

_LOCKS = {}
_LOCKS_GUARD = threading.Lock()
_CHANGE_GUARD = threading.Lock()
_CHANGE_LISTENERS = []
_CHANGE_REVISIONS = {}


def _project_key(project):
    try:
        return os.path.normcase(str(Path(project).resolve()))
    except OSError:
        return os.path.normcase(str(project))


def subscribe_changes(callback):
    """登记索引变更监听 ``callback(project_root)``；幂等去重，供面板自动刷新。"""
    if not callable(callback):
        return callback
    with _CHANGE_GUARD:
        if callback not in _CHANGE_LISTENERS:
            _CHANGE_LISTENERS.append(callback)
    return callback


def unsubscribe_changes(callback):
    """注销索引变更监听。"""
    with _CHANGE_GUARD:
        if callback in _CHANGE_LISTENERS:
            _CHANGE_LISTENERS.remove(callback)


def change_revision(project):
    """返回该项目的单调变更计数，供候选缓存廉价判失效。"""
    with _CHANGE_GUARD:
        return _CHANGE_REVISIONS.get(_project_key(project), 0)


def _notify_changes(project):
    key = _project_key(project)
    with _CHANGE_GUARD:
        _CHANGE_REVISIONS[key] = _CHANGE_REVISIONS.get(key, 0) + 1
        listeners = tuple(_CHANGE_LISTENERS)
    resolved = Path(project)
    for callback in listeners:
        try:
            callback(resolved)
        except (OSError, RuntimeError, ValueError, TypeError):
            continue


def _excluded(relative):
    parts = PurePosixPath(relative).parts
    name = parts[-1].casefold() if parts else ''
    return (not parts or any(p.casefold() in SKIP_DIRS for p in parts[:-1])
            or name in SKIP_FILES or name.startswith('.env')
            or name.endswith(('.tmp', '.pyc', '.log', '.pem', '.key', '.p12', '.pfx'))
            or any(word in name for word in ('api_key', 'apikey', 'secret', 'credential', '密钥')))


def _safe_relative(root, value):
    """清单和缓存只接受规范相对路径，不接受绝对路径或父级跳转。"""
    if not isinstance(value, str) or not value or '\\' in value or '\x00' in value:
        raise ValueError('索引路径不是相对 posix 路径')
    path = PurePosixPath(value)
    if (path.is_absolute() or PureWindowsPath(value).drive or '..' in path.parts
            or path.as_posix() != value or value == '.' or _excluded(value)):
        raise ValueError('索引路径不允许收录')
    _relative(root, value)
    return value


@contextmanager
def _index_lock(target, root):
    """串行读改写；线程锁覆盖同进程，文件锁覆盖多个后台进程。"""
    target = Path(target).absolute()
    # resolve() can change spelling during atomic replace on Windows; choose
    # the same thread lock before doing any filesystem-dependent validation.
    key = os.path.normcase(str(target))
    with _LOCKS_GUARD:
        lock = _LOCKS.setdefault(key, threading.RLock())
    with lock:
        _relative(root, target)
        # Windows 上锁文件被其它线程持有时 resolve 可能返回非最终路径；
        # 校验与打开都在同一线程互斥区，避免把合法路径误判为越界。
        _relative(root, target.with_suffix('.lock'))
        path = Path(target).with_suffix('.lock')
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('a+b') as stream:
            stream.seek(0, os.SEEK_END)
            if stream.tell() == 0:
                stream.write(b'0')
                stream.flush()
            stream.seek(0)
            # 产品只支持 Windows，使用随附运行时的原生锁，不引入未分发的 Unix 模块。
            import msvcrt
            msvcrt.locking(stream.fileno(), msvcrt.LK_LOCK, 1)
            try:
                yield
            finally:
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)



def index_path(project):
    """索引文件位置：``<项目>/工作流任务/文件索引/index.json``（路径只经 stage_layout 产出）。"""
    return stage_layout.workflow_dir(project, INDEX_DIR_NAME, INDEX_NAME)


def _relative(project, path):
    """绝对或相对路径 → 项目相对 posix；越界抛 ``ValueError``。"""
    root = Path(project).resolve()
    target = Path(path)
    if not target.is_absolute():
        target = root / target
    resolved = target.resolve()
    if (os.name == 'nt' and len(root.drive) == 2
            and resolved.drive == '\\\\?\\' + root.drive
            and not resolved.is_relative_to(root)):
        # ntpath.realpath opens a leaf again before stripping \\?\; atomic
        # replace can fail that open and leave only the leaf prefixed. Rebase
        # only this exact spelling difference on a strictly resolved parent.
        root = Path(project).resolve(strict=True)
        parent = target.parent.resolve(strict=True)
        candidate = parent / target.name
        if (len(candidate.drive) == 2
                and resolved == Path('\\\\?\\' + str(candidate))):
            try:
                leaf = target.lstat()
            except FileNotFoundError:
                leaf = None
            # Never reinterpret a symlink/junction (including a dangling one)
            # as an ordinary leaf just because its parent is inside the root.
            if leaf is None or not (stat.S_ISLNK(leaf.st_mode) or
                    getattr(leaf, 'st_file_attributes', 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT):
                resolved = candidate
    if not resolved.is_relative_to(root):
        raise ValueError('索引只收项目内文件：' + str(path))
    return resolved.relative_to(root).as_posix()


ORIGIN_VERSION = 1
ORIGIN_NAME = '来源记录.json'


def origin_path(root):
    """独立来源事实；不是 index.json 的一部分，清缓存时必须保留。"""
    return stage_layout.workflow_dir(root, INDEX_DIR_NAME, ORIGIN_NAME)


def _read_meta(root):
    from infra.file_cache import read_json
    target = origin_path(root)
    try:
        _relative(root, target.absolute())
        data = read_json(target)
    except (OSError, ValueError):
        return {}, {}
    if not isinstance(data, dict) or data.get('schema_version') != ORIGIN_VERSION:
        return {}, {}
    origins = {}
    entries = data.get('origins')
    if isinstance(entries, dict):
        for path, origin in entries.items():
            try:
                _safe_relative(root, path)
            except (OSError, ValueError):
                continue
            if isinstance(origin, str) and origin in ORIGINS:
                origins[path] = origin
    kinds = {}
    raw_kinds = data.get('kinds')
    if isinstance(raw_kinds, dict):
        for path, kind in raw_kinds.items():
            try:
                _safe_relative(root, path)
            except (OSError, ValueError):
                continue
            if isinstance(kind, str) and kind in file_naming.KINDS:
                kinds[path] = kind
    return origins, kinds


def _read_origins(root):
    return _read_meta(root)[0]


def _read_kinds(root):
    return _read_meta(root)[1]


def _validated_meta_paths(root, paths):
    root = Path(root).resolve()
    relatives = []
    for raw in paths:
        text = str(raw)
        path = Path(raw)
        if ('\x00' in text or '..' in path.parts
                or any(':' in part for part in path.parts[1:] if path.is_absolute())):
            raise ValueError('来源路径不允许父级跳转或特殊路径')
        if not path.is_absolute():
            _safe_relative(root, text)
            if any(':' in part for part in path.parts):
                raise ValueError('来源路径不允许特殊路径')
        relative = _relative(root, path)
        _safe_relative(root, relative)
        relatives.append(relative)
    return root, relatives


def _save_meta(root, origins, kinds):
    from agent.core import save
    target = origin_path(root)
    _relative(root, target.absolute())
    payload = {'schema_version': ORIGIN_VERSION, 'origins': origins}
    if kinds:
        payload['kinds'] = kinds
    save(target, payload)


def record_origin(root, paths, origin):
    """由成功写入入口登记来源；不读缓存、不扫描、不为不存在的文件留事实。

    一批先做严格路径校验，越界或非规范路径整批拒绝。系统／模型发布保留用户上传
    事实，避免包发布／清单刷新把导入产物重标；无历史事实仍按系统生成读取。
    """
    if not isinstance(origin, str) or origin not in ORIGINS:
        raise ValueError('未知文件来源：' + str(origin))
    root, relatives = _validated_meta_paths(root, paths)
    with _index_lock(index_path(root), root):
        origins, kinds = _read_meta(root)
        changed = False
        for relative in relatives:
            try:
                info = (root / relative).stat()
            except OSError:
                continue
            if not stat.S_ISREG(info.st_mode):
                continue
            if origin != ORIGIN_USER and origins.get(relative) == ORIGIN_USER:
                continue
            if origins.get(relative) != origin:
                origins[relative] = origin
                changed = True
        if changed:
            _save_meta(root, origins, kinds)
    if changed:
        _notify_changes(root)
    return origins


def record_kind(root, paths, kind):
    """用户手动覆盖文件类型（空串／None 恢复自动判定）；持久化在来源记录并增量刷索引。"""
    from contract.infra_errors import ConfigError
    if kind not in (None, '') and (not isinstance(kind, str) or kind not in file_naming.KINDS):
        raise ConfigError('未知文件类型：' + str(kind))
    root, relatives = _validated_meta_paths(root, paths)
    with _index_lock(index_path(root), root):
        origins, kinds = _read_meta(root)
        changed = False
        for relative in relatives:
            if not kind:
                if relative in kinds:
                    kinds.pop(relative, None)
                    changed = True
            elif kinds.get(relative) != kind:
                kinds[relative] = kind
                changed = True
        if changed:
            _save_meta(root, origins, kinds)
    if changed:
        if read(root) is not None:
            update(root, relatives)
        else:
            _notify_changes(root)
    return kinds


def _apply_origins(root, data, origins=None, kinds=None):
    if origins is None or kinds is None:
        loaded_origins, loaded_kinds = _read_meta(root)
        origins = loaded_origins if origins is None else origins
        kinds = loaded_kinds if kinds is None else kinds
    files = []
    for item in data['files']:
        path = item['path']
        updated = dict(item, origin=origins.get(path, ORIGIN_SYSTEM),
                       status=normalize_status(item.get('status', STATUS_DRAFT)))
        if path in kinds:
            updated['kind'] = kinds[path]
        files.append(updated)
    return dict(data, files=files)


def _stage_match(relative_path):
    """从阶段路径权威的候选中取最长匹配，当前目录优先于旧编号冲突。"""
    path = PurePosixPath(str(relative_path))
    first = path.parts[0] if path.parts else ''
    current = stage_layout.stage_dir(first)
    if current:
        return current[1], PurePosixPath(*path.parts[1:])
    base = Path('.')
    matches = []
    for row in stage_layout.STAGES:
        for folder in read_dirs(base, row[1]):
            prefix = PurePosixPath(folder.as_posix())
            if path.is_relative_to(prefix):
                matches.append((len(prefix.parts), row[1], path.relative_to(prefix)))
    return max(matches, key=lambda item: item[0])[1:] if matches else ('', path)


def stage_of(relative_path):
    """项目相对路径 → 权威阶段 id（包含仍支持的历史目录）。"""
    return _stage_match(relative_path)[0]


_SCRIPT_REF_DIRS = frozenset(('输入', '参考', '项目设定', '项目大纲', '角色卡'))
_SCRIPT_REF_WORDS = ('项目设定', '项目大纲', '剧本大纲', '故事大纲', '分集大纲',
                     '角色卡', '人物设定', '世界观', '原始附件', '附件文本', '角色', '设定', '大纲', '创意')


_ATTACHMENT_MARKS = ('原始附件', '附件文本', '任务附件')


def _is_task_attachment(relative_path):
    """用户上传或转换出的任务附件：只认一种类型，避免按扩展名拆进「报告」和「其他」。"""
    parts = PurePosixPath(str(relative_path or '').replace('\\', '/')).parts
    if any(part == '输入' for part in parts[:-1]):
        return True
    text = '/'.join(parts)
    return any(mark in text for mark in _ATTACHMENT_MARKS)


def kind_of(relative_path):
    """项目相对路径 → 按阶段职责与扩展名推导类型标签（含「参考」类型）。"""
    posix = str(relative_path or '').replace('\\', '/')
    if _is_task_attachment(posix):
        return '参考'
    stage, within = _stage_match(posix)
    parts = within.parts
    parents = parts[:-1]
    part = parts[0] if len(parts) > 1 else 'docs'
    name = parts[-1] if parts else ''
    suffix = file_naming.kind_from_suffix(name)
    if part == 'skills':
        return '其他'
    if part == 'logs' or suffix == '日志':
        return '日志'
    if stage == 'script':
        if _SCRIPT_REF_DIRS.intersection(parents):
            return '参考'
        if '项目剧本' in parents:
            return '剧本'
        if suffix in ('资产', '音频', '视频'):
            return suffix
        if part == 'docs':
            if any(word in name for word in _SCRIPT_REF_WORDS):
                return '参考'
            return '剧本'
        return suffix
    if (posix.startswith('_shared/reference_images/')
            or any(folder in ('参考图', '参考', '输入') for folder in parents)):
        return '参考'
    if suffix in ('资产', '音频', '视频'):
        return suffix
    if stage == 'storyboard' and part == 'docs':
        return '分镜'
    if stage == 'script_structure' and part == 'docs':
        return '剧本'
    if stage == 'assets' and part == 'docs':
        return '设定'
    return suffix


def _confirmed_docs_in(root, folder):
    """读取单个 01剧本准备 目录的已确认文档与已采用自然剧本相对路径。"""
    from infra.file_cache import read_json
    found = set()
    state_file = folder / 'preparation_state.json'
    if state_file.is_file():
        try:
            _relative(root, state_file)
            data = read_json(state_file)
        except (OSError, ValueError):
            data = None
        if isinstance(data, dict):
            docs = list(data.get('documents') or ())
            rev = data.get('revision')
            if isinstance(rev, dict):
                docs.extend(rev.get('documents') or ())
            for doc in docs:
                if not isinstance(doc, dict) or doc.get('confirmed') is not True:
                    continue
                raw = doc.get('path')
                if not isinstance(raw, str):
                    continue
                try:
                    found.add(_safe_relative(root, _relative(root, folder / raw)))
                except (OSError, ValueError):
                    continue
    selection_file = folder / 'natural_script_selection.json'
    if selection_file.is_file():
        try:
            _relative(root, selection_file)
            sel = read_json(selection_file)
            raw = sel.get('path') if isinstance(sel, dict) else None
            if isinstance(raw, str) and raw.strip():
                found.add(_safe_relative(root, raw.replace('\\', '/')))
        except (OSError, ValueError):
            pass
    return found


def _preparation_confirmed_paths(root):
    """读取 01剧本准备 已确认阶段稿与已采用自然剧本，纳入「定稿」状态集合。"""
    found = set()
    for folder in read_dirs(root, 'script'):
        found.update(_confirmed_docs_in(root, folder))
    return found


def published_paths(project):
    """被「成果确认清单」、交付清单或剧本定稿/采用台账引用过的项目相对路径集合（决定 ``status``=定稿）。"""
    root = Path(project).resolve()
    found = set()
    for row in stage_layout.STAGES:
        for folder in read_dirs(root, row[1]):
            confirm = folder / CONFIRM_DIR_NAME
            if not confirm.is_dir():
                continue
            for manifest in sorted(confirm.glob('*.json')):
                found.update(_paths_in(manifest, ('outputs',), root=root))
            for name in (DELIVERY_MANIFEST,):
                listed = confirm / name
                if listed.is_file():
                    found.update(_paths_in(listed, ('files',), root=root))
    for folder in read_dirs(root, 'delivery'):
        manifest = folder / '导出成片' / DELIVERY_MANIFEST
        if manifest.is_file():
            found.update(_paths_in(manifest, ('files',), root=root))
    found.update(_preparation_confirmed_paths(root))
    return {path for path in found if path}


def _paths_in(manifest, keys, root=None):
    """只取已审核完成清单中的安全相对路径；不读取越界清单。"""
    from infra.file_cache import read_json
    try:
        _relative(root, manifest)
        data = read_json(manifest)
    except (OSError, ValueError):
        return set()
    if (not isinstance(data, dict) or data.get('status') != 'complete'
            or data.get('reviewed') is not True):
        return set()
    out = set()
    for key in keys:
        items = data.get(key)
        for item in items if isinstance(items, list) else ():
            path = item.get('path') if isinstance(item, dict) else None
            try:
                out.add(_safe_relative(root, path))
            except (OSError, ValueError):
                continue
    return out


def _row_for(project, relative_path, published, now=None, origins=None, kinds=None):
    """按磁盘现状造一行；文件已不存在则返回 ``None``。"""
    root = Path(project).resolve()
    try:
        _safe_relative(root, relative_path)
        target = root / relative_path
        info = target.stat()
    except (OSError, ValueError):
        return None
    if not stat.S_ISREG(info.st_mode):
        return None
    parsed = file_naming.parse(target.name)
    status = STATUS_DRAFT
    if str(relative_path).split('/', 1)[0] == stage_layout.ARCHIVE:
        status = STATUS_ARCHIVED
    elif relative_path in published:
        status = STATUS_PUBLISHED
    if origins is None or kinds is None:
        loaded_origins, loaded_kinds = _read_meta(root)
        origins = loaded_origins if origins is None else origins
        kinds = loaded_kinds if kinds is None else kinds
    kind = kinds.get(relative_path) or kind_of(relative_path)
    return FileRow(path=relative_path, stage=stage_of(relative_path), kind=kind,
                   origin=origins.get(relative_path, ORIGIN_SYSTEM),
                   status=status, size=info.st_size, mtime=info.st_mtime, order=parsed['order'],
                   title=parsed['title'], missing=False)


def _walk(folder):
    """只遍历根内实体目录；junction/reparse point 与文件链接均不跟随。"""
    root = Path(folder).resolve()
    def allowed(path):
        try:
            info = path.lstat()
            relative = path.relative_to(root).as_posix()
            return (not _excluded(relative) and not path.is_symlink()
                    and not (getattr(info, 'st_file_attributes', 0) & 0x400)
                    and path.resolve().is_relative_to(root))
        except (OSError, ValueError):
            return False
    for current, dirs, files in os.walk(root, followlinks=False):
        dirs[:] = [name for name in dirs if name.casefold() not in SKIP_DIRS
                   and allowed(Path(current) / name)]
        for name in files:
            path = Path(current) / name
            if allowed(path):
                yield path


def build(project, now=None):
    """全量扫描并返回索引负载（不写盘）。"""
    root = Path(project).resolve()
    published = published_paths(root)
    origins, kinds = _read_meta(root)
    rows = {}
    for path in _walk(root):
        relative = path.relative_to(root).as_posix()
        item = _row_for(root, relative, published, now=now, origins=origins, kinds=kinds)
        if item is not None:
            rows[relative] = item
    files = [item.to_dict() for item in rows.values()]
    for missing in sorted(published - set(rows)):
        files.append(FileRow(path=missing, stage=stage_of(missing),
                             kind=kinds.get(missing) or kind_of(missing),
                             origin=origins.get(missing, ORIGIN_SYSTEM),
                             status=STATUS_PUBLISHED, missing=True).to_dict())
    return {'schema_version': INDEX_VERSION, 'project': root.name,
            'generated_at': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(now or time.time())),
            'files': files}


def rebuild(project, now=None):
    """全量重建索引并原子写盘；返回写出去的负载。"""
    from agent.core import save
    with _index_lock(index_path(project), project):
        payload = build(project, now=now)
        save(index_path(project), payload)
    _notify_changes(project)
    return payload


# ── 全局素材库（R3123，任务书 P3，Q11）────────────────────────────────────
# 全局库是**用户选定目录**（默认 `我的文档\漫剧助手素材库`），不属于任何项目；
# 索引落在库自己的 `index.json`，一行只存**库相对** posix 路径，整库搬走也不用改写。
GLOBAL_INDEX_NAME = 'index.json'
# 全局库目录登记在程序配置里（不是项目内文件，也不进 data/）。
GLOBAL_CONFIG_NAME = '素材库.json'
PROGRAM_ROOT = Path(__file__).resolve().parents[1]


def global_config_path(program=None):
    """全局库配置路径：``<程序>/配置/素材库.json``。"""
    return Path(program or PROGRAM_ROOT) / '配置' / GLOBAL_CONFIG_NAME


def read_global_dir(program=None):
    """读全局素材库目录；未设置、文件缺失或内容非法时返回 ``None``。"""
    from infra.file_cache import read_json
    try:
        data = read_json(global_config_path(program))
    except (OSError, ValueError):
        return None
    value = data.get('library_dir') if isinstance(data, dict) else None
    if not isinstance(value, str) or not value.strip():
        return None
    return Path(value).expanduser()


def save_global_dir(library, program=None):
    """登记全局素材库目录（原子写）；返回写出去的配置文件路径。"""
    from agent.core import save
    raw = str(library or '').strip()
    if not raw:
        raise ValueError('全局素材库目录不能为空')
    text = str(Path(raw).expanduser())
    target = global_config_path(program)
    save(target, {'schema_version': INDEX_VERSION, 'library_dir': text})
    return target


def global_index_path(library):
    """全局素材库索引位置：``<库>/index.json``。"""
    return Path(library) / GLOBAL_INDEX_NAME


def build_global(library, now=None):
    """全量扫描全局素材库并返回索引负载（不写盘）。"""
    root = Path(library).resolve()
    origins = _read_origins(root)
    files = []
    if root.is_dir():
        for path in _walk(root):
            if path == global_index_path(root) or path == global_index_path(root).with_suffix('.lock'):
                continue
            try:
                relative = _relative(root, path)
                stat = path.stat()
            except (OSError, ValueError):
                continue
            parsed = file_naming.parse(path.name)
            files.append(FileRow(path=relative, stage='', kind=file_naming.kind_from_suffix(relative), status=STATUS_DRAFT,
                                 origin=origins.get(relative, ORIGIN_SYSTEM),
                                 size=stat.st_size, mtime=stat.st_mtime, order=parsed['order'],
                                 title=parsed['title']).to_dict())
    return {'schema_version': INDEX_VERSION, 'project': root.name,
            'generated_at': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(now or time.time())),
            'files': files}


def rebuild_global(library, now=None):
    """重建全局素材库索引并原子写盘；返回写出去的负载。"""
    from agent.core import save
    if not Path(library).is_dir():
        return build_global(library, now=now)
    with _index_lock(index_path(library), library), _index_lock(global_index_path(library), library):
        payload = build_global(library, now=now)
        save(global_index_path(library), payload)
        return payload


def _valid_payload(data, root):
    """缓存来自磁盘，必须先验证再交给宽容的 FileRow.from_dict。"""
    if (not isinstance(data, dict) or type(data.get('schema_version')) is not int
            or data.get('schema_version') != INDEX_VERSION or not isinstance(data.get('files'), list)):
        return False
    seen = set()
    for item in data['files']:
        if not isinstance(item, dict):
            return False
        try:
            path = _safe_relative(root, item.get('path'))
        except (OSError, ValueError):
            return False
        if path in seen:
            return False
        seen.add(path)
        row = FileRow.from_dict(item)
        if (not isinstance(row.stage, str) or row.stage not in ('', *STAGE_ORDER)
                or not isinstance(row.kind, str) or row.kind not in file_naming.KINDS
                or not isinstance(row.status, str) or row.status not in STATUSES
                or not isinstance(row.origin, str) or row.origin not in ORIGINS
                or type(row.size) is not int or row.size < 0 or type(row.order) is not int
                or type(row.mtime) not in (float, int) or not 0 <= row.mtime <= 1e20
                or not math.isfinite(row.mtime) or not isinstance(row.title, str) or type(row.missing) is not bool):
            return False
    return True


def _refresh(root, data, global_library=False):
    """只 stat 已有行，不发现新增文件、不递归、不哈希，也不写缓存。"""
    files = []
    origins, kinds = _read_meta(root)
    published = set() if global_library else published_paths(root)
    for raw in data['files']:
        row = FileRow.from_dict(raw)
        row.origin = origins.get(row.path, ORIGIN_SYSTEM)
        try:
            _safe_relative(root, row.path)
            info = (Path(root) / row.path).stat()
            exists = stat.S_ISREG(info.st_mode)
        except (OSError, ValueError):
            exists = False
        row.missing = not exists
        if exists:
            row.size, row.mtime = info.st_size, info.st_mtime
        row.stage = '' if global_library else stage_of(row.path)
        if global_library:
            row.kind = kinds.get(row.path) or file_naming.kind_from_suffix(row.path)
        else:
            row.kind = kinds.get(row.path) or kind_of(row.path)
            if str(row.path).split('/', 1)[0] == stage_layout.ARCHIVE:
                row.status = STATUS_ARCHIVED
            elif row.path in published:
                row.status = STATUS_PUBLISHED
            else:
                row.status = STATUS_DRAFT
        files.append(row.to_dict())
    return dict(data, files=files)


def read_global(library):
    """读取全局素材库索引；缺失／损坏／版本不符返回 ``None``。"""
    from infra.file_cache import read_json
    try:
        _relative(library, global_index_path(library).absolute())
        data = read_json(global_index_path(library))
    except (OSError, ValueError):
        return None
    return _apply_origins(library, data) if _valid_payload(data, library) else None


def global_rows(library, now=None):
    """全局库行列表（按类型、序号、路径排序）。"""
    if not Path(library).is_dir():
        return []
    data = read_global(library) or rebuild_global(library, now=now)
    data = _refresh(library, data, global_library=True)
    rows = [FileRow.from_dict(item) for item in data['files']]
    rows.sort(key=lambda row: (row.kind, row.order, row.path))
    return rows


def search_global(library, kind=None, name=None, now=None):
    """按类型与文件名关键字筛选全局素材库；条件为空表示不限。"""
    keyword = str(name or '').strip().lower()
    out = []
    for row in global_rows(library, now=now):
        if kind and row.kind != kind:
            continue
        if keyword and keyword not in row.path.lower() and keyword not in row.title.lower():
            continue
        out.append(row)
    return out


def _collect_from_folder(root, folder, ctx, seen, candidates):
    if not folder.is_dir():
        return
    published, origins, now = ctx
    try:
        for path in _walk(folder):
            try:
                relative = _relative(root, path)
            except (OSError, ValueError):
                continue
            if _excluded(relative) or relative in seen:
                continue
            seen.add(relative)
            try:
                item = _row_for(root, relative, published, now=now, origins=origins)
            except (OSError, ValueError):
                continue
            if item is not None:
                candidates.append(item)
    except (OSError, ValueError):
        return


def _collect_discover_candidates(root, stages, published, origins, now, existing):
    candidates = []
    seen = set(existing)
    ctx = (published, origins, now)
    for current_stage in stages:
        try:
            dirs = read_dirs(root, current_stage)
        except (OSError, ValueError):
            continue
        for folder in dirs:
            _collect_from_folder(root, Path(folder), ctx, seen, candidates)
    return candidates


def discover(project, stage=None, now=None):
    """增量发现磁盘上有、缓存索引里没有的文件并写回索引，返回新增行数。

    没有有效缓存索引时直接返回 0，不触发重建、不写盘。stage 给定时只遍历该阶段目录。
    """
    try:
        root = Path(project).resolve()
        data = read(project)
        if data is None:
            return 0
        existing = {str(item.get('path')) for item in data.get('files', [])
                    if isinstance(item, dict)}
        stages = [stage] if stage is not None else list(STAGE_ORDER)
        published = published_paths(root)
        origins = _read_origins(root)
        candidates = _collect_discover_candidates(root, stages, published, origins, now, existing)
        stale = _collect_removed_paths(root, data.get('files', ()), stages, published)
        if not candidates and not stale:
            return 0
        with _index_lock(index_path(root), root):
            data = read(root)
            if data is None:
                return 0
            table = {item['path']: item for item in data['files']
                     if isinstance(item, dict) and isinstance(item.get('path'), str)}
            added = 0
            for path_key in stale:
                if path_key in table:
                    table.pop(path_key, None)
                    added += 1
            for item in candidates:
                if item.path not in table:
                    table[item.path] = item.to_dict()
                    added += 1
            if added == 0:
                return 0
            data['files'] = list(table.values())
            data['schema_version'] = INDEX_VERSION
            from agent.core import save
            save(index_path(root), data)
        _notify_changes(root)
        return added
    except (OSError, ValueError):
        return 0


def _collect_removed_paths(root, items, stages, published):
    """找出阶段内已不在磁盘、且未在定稿清单登记的失效缓存行，供自动刷新清理。"""
    scope = set(stages)
    stale = []
    for item in items:
        if not isinstance(item, dict):
            continue
        rel = item.get('path')
        if not isinstance(rel, str) or rel in published or item.get('missing'):
            continue
        if stage_of(rel) not in scope:
            continue
        try:
            if not (root / rel).is_file():
                stale.append(rel)
        except OSError:
            stale.append(rel)
    return stale


def read(project):
    """读取索引；不存在、损坏或版本不符时返回 ``None``（调用方据此重建）。"""
    from infra.file_cache import read_json
    try:
        _relative(project, index_path(project).absolute())
        data = read_json(index_path(project))
    except (OSError, ValueError):
        return None
    return _apply_origins(project, data) if _valid_payload(data, project) else None


def ensure(project, now=None):
    """有可用索引就返回，否则重建。"""
    data = read(project)
    data = data if data is not None else rebuild(project, now=now)
    return _refresh(project, data)


def rows(project, now=None):
    """索引负载 → ``FileRow`` 列表（按阶段顺序、类型、序号、路径排序）。"""
    data = ensure(project, now=now)
    result = [FileRow.from_dict(item) for item in data['files']]
    result.sort(key=_sort_key)
    return result


def _sort_key(row):
    rank = STAGE_ORDER.index(row.stage) if row.stage in STAGE_ORDER else len(STAGE_ORDER)
    return (rank, '' if row.stage else 1, row.kind, row.order, row.path)


def update(project, paths=(), removed=False, now=None):
    """增量更新若干路径（发布后／改名后／删除后调用），返回最新负载。

    ``removed=True`` 表示这些路径已经从项目里消失，只做删除；否则按磁盘现状重建每一行。
    """
    from agent.core import save
    # 整批先校验，缺索引时也不能在越界输入下产生任何写入。
    relatives = [_relative(project, raw) for raw in paths]
    with _index_lock(index_path(project), project):
        data = read(project)
        if data is None:
            data = build(project, now=now)
        table = {item['path']: item for item in data['files']}
        published = published_paths(project)
        origins, kinds = _read_meta(project)
        for relative in relatives:
            if removed:
                table.pop(relative, None)
                continue
            item = _row_for(project, relative, published, now=now, origins=origins, kinds=kinds)
            if item is None:
                table.pop(relative, None)
            else:
                table[relative] = item.to_dict()
        data['files'] = list(table.values())
        data['schema_version'] = INDEX_VERSION
        save(index_path(project), data)
    _notify_changes(project)
    return data


def search(project, stage=None, kind=None, status=None, name=None, now=None):
    """按阶段／类型／状态／文件名关键字筛选；条件为空表示不限。"""
    keyword = str(name or '').strip().lower()
    wanted_status = normalize_status(status) if status else None
    out = []
    for row in rows(project, now=now):
        if stage and row.stage != stage:
            continue
        if kind and row.kind != kind:
            continue
        if wanted_status and row.status != wanted_status:
            continue
        if keyword and keyword not in row.path.lower() and keyword not in row.title.lower():
            continue
        out.append(row)
    return out


def kinds(project, now=None):
    """索引里出现过的类型，按 DES §3.1 顺序排列（侧栏下拉用）。"""
    present = {row.kind for row in rows(project, now=now)}
    return [kind for kind in file_naming.KINDS if kind in present]


def summary(project, now=None):
    """一行摘要：总文件数、缺失数、按阶段计数（状态栏／面板标题用）。"""
    data = ensure(project, now=now)
    items = [FileRow.from_dict(item) for item in data['files']]
    counts = {}
    for item in items:
        counts[item.stage] = counts.get(item.stage, 0) + 1
    return {'total': len(items), 'missing': sum(1 for item in items if item.missing),
            'by_stage': counts}

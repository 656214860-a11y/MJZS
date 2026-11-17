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

import os
import time
from pathlib import Path

import contract.stage_layout as stage_layout
from contract import file_naming
from contract.file_index_contract import (FileRow, INDEX_VERSION, STATUS_ARCHIVED, STATUS_DRAFT,
                                          STATUS_PUBLISHED)
from contract.stage_path_service import read_dirs, write_dir
from contract.pet_bus import STAGES as STAGE_ORDER

INDEX_DIR_NAME = '文件索引'
INDEX_NAME = 'index.json'
CONFIRM_DIR_NAME = '成果确认'
DELIVERY_MANIFEST = 'delivery_manifest.json'
# 不参与索引的目录：工作流任务（回收站/备份/索引自身）与字节码缓存。
SKIP_DIRS = frozenset({stage_layout.WORKFLOW_DIR, '__pycache__', '.git'})

IMAGE_SUFFIXES = frozenset({'.png', '.jpg', '.jpeg', '.webp', '.bmp', '.gif', '.tga', '.psd'})
AUDIO_SUFFIXES = frozenset({'.mp3', '.wav', '.m4a', '.aac', '.flac'})
VIDEO_SUFFIXES = frozenset({'.mp4', '.mov', '.mkv', '.avi', '.webm'})


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
    if not resolved.is_relative_to(root):
        raise ValueError('索引只收项目内文件：' + str(path))
    return resolved.relative_to(root).as_posix()


def stage_of(relative_path):
    """项目相对路径 → 阶段 id；不在阶段目录下返回 ``''``。"""
    first = str(relative_path).split('/', 1)[0]
    row = stage_layout.stage_dir(first)
    return row[1] if row else ''


def kind_of(relative_path):
    """项目相对路径 → DES §3.1 的类型标签。"""
    parts = str(relative_path).split('/')
    stage = stage_of(relative_path)
    part = parts[1] if len(parts) > 1 else ''
    suffix = Path(parts[-1]).suffix.lower()
    if part == 'skills':
        return '其他'
    if part == 'logs' or suffix == '.log':
        return '日志'
    if suffix in IMAGE_SUFFIXES:
        return '资产'
    if suffix in AUDIO_SUFFIXES:
        return '音频'
    if suffix in VIDEO_SUFFIXES:
        return '视频'
    if stage == 'storyboard' and part == 'docs':
        return '分镜'
    if stage in ('script', 'script_structure') and part == 'docs':
        name = parts[-1]
        return '设定' if any(word in name for word in ('角色', '设定', '世界观', '创意')) else '剧本'
    if stage == 'assets' and part == 'docs':
        return '设定'
    if suffix in ('.json', '.csv', '.srt', '.ass'):
        return '清单'
    if suffix in ('.md', '.txt'):
        return '报告'
    return file_naming.kind_from_suffix(parts[-1])


def published_paths(project):
    """被「成果确认清单」或交付清单引用过的项目相对路径集合（决定 ``status``）。"""
    root = Path(project).resolve()
    found = set()
    for row in stage_layout.STAGES:
        for folder in read_dirs(root, row[1]):
            confirm = folder / CONFIRM_DIR_NAME
            if not confirm.is_dir():
                continue
            for manifest in sorted(confirm.glob('*.json')):
                found.update(_paths_in(manifest, ('outputs',)))
            for name in (DELIVERY_MANIFEST,):
                listed = confirm / name
                if listed.is_file():
                    found.update(_paths_in(listed, ('files',)))
    for folder in read_dirs(root, 'delivery'):
        manifest = folder / '导出成片' / DELIVERY_MANIFEST
        if manifest.is_file():
            found.update(_paths_in(manifest, ('files',)))
    return {path for path in found if path}


def _paths_in(manifest, keys):
    """从清单里取出 ``keys`` 列表中每项的 ``path`` 字段；坏文件按空集处理。"""
    from file_cache import read_json
    try:
        data = read_json(manifest)
    except (OSError, ValueError):
        return set()
    out = set()
    for key in keys:
        items = data.get(key) if isinstance(data, dict) else None
        for item in items if isinstance(items, list) else ():
            path = item.get('path') if isinstance(item, dict) else None
            if isinstance(path, str) and path.strip():
                out.add(path.replace('\\', '/').strip('/'))
    return out


def _row_for(project, relative_path, published, now=None):
    """按磁盘现状造一行；文件已不存在则返回 ``None``。"""
    root = Path(project).resolve()
    target = root / Path(*str(relative_path).split('/'))
    try:
        stat = target.stat()
    except OSError:
        return None
    parsed = file_naming.parse(target.name)
    status = STATUS_DRAFT
    if str(relative_path).split('/', 1)[0] == stage_layout.ARCHIVE:
        status = STATUS_ARCHIVED
    elif relative_path in published:
        status = STATUS_PUBLISHED
    return FileRow(path=relative_path, stage=stage_of(relative_path), kind=kind_of(relative_path),
                   status=status, size=stat.st_size, mtime=stat.st_mtime, order=parsed['order'],
                   title=parsed['title'], missing=False)


def _walk(folder):
    """遍历一个目录，产出项目内的相对文件路径（跳过 SKIP_DIRS 与隐藏字节码）。"""
    for current, dirs, files in os.walk(folder):
        dirs[:] = [name for name in dirs if name not in SKIP_DIRS]
        for name in files:
            if name.endswith(('.tmp', '.pyc')):
                continue
            yield Path(current) / name


def build(project, now=None):
    """全量扫描并返回索引负载（不写盘）。"""
    root = Path(project).resolve()
    published = published_paths(root)
    rows = {}
    for row in stage_layout.STAGES:
        for folder in read_dirs(root, row[1]):
            if not folder.is_dir():
                continue
            for path in _walk(folder):
                try:
                    relative = _relative(root, path)
                except ValueError:
                    continue
                item = _row_for(root, relative, published, now=now)
                if item is not None:
                    rows[relative] = item
    shared = stage_layout.shared_paths(root).get('root')
    if shared is not None and Path(shared).is_dir():
        for path in _walk(shared):
            try:
                relative = _relative(root, path)
            except ValueError:
                continue
            item = _row_for(root, relative, published, now=now)
            if item is not None:
                rows[relative] = item
    archive = Path(root) / stage_layout.ARCHIVE
    if archive.is_dir():
        for path in _walk(archive):
            try:
                relative = _relative(root, path)
            except ValueError:
                continue
            item = _row_for(root, relative, published, now=now)
            if item is not None:
                rows[relative] = item
    files = [item.to_dict() for item in rows.values()]
    for missing in sorted(published - set(rows)):
        files.append(FileRow(path=missing, stage=stage_of(missing), kind=kind_of(missing),
                             status=STATUS_PUBLISHED, missing=True).to_dict())
    return {'schema_version': INDEX_VERSION, 'project': root.name,
            'generated_at': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(now or time.time())),
            'files': files}


def rebuild(project, now=None):
    """全量重建索引并原子写盘；返回写出去的负载。"""
    from agent.core import save
    payload = build(project, now=now)
    save(index_path(project), payload)
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
    from file_cache import read_json
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
    files = []
    if root.is_dir():
        for path in _walk(root):
            if path.name == GLOBAL_INDEX_NAME:
                continue
            try:
                relative = _relative(root, path)
                stat = path.stat()
            except (OSError, ValueError):
                continue
            parsed = file_naming.parse(path.name)
            files.append(FileRow(path=relative, stage='', kind=kind_of(relative), status=STATUS_DRAFT,
                                 size=stat.st_size, mtime=stat.st_mtime, order=parsed['order'],
                                 title=parsed['title']).to_dict())
    return {'schema_version': INDEX_VERSION, 'project': root.name,
            'generated_at': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(now or time.time())),
            'files': files}


def rebuild_global(library, now=None):
    """重建全局素材库索引并原子写盘；返回写出去的负载。"""
    from agent.core import save
    payload = build_global(library, now=now)
    save(global_index_path(library), payload)
    return payload


def read_global(library):
    """读取全局素材库索引；缺失／损坏／版本不符返回 ``None``。"""
    from file_cache import read_json
    try:
        data = read_json(global_index_path(library))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or data.get('schema_version') != INDEX_VERSION:
        return None
    if not isinstance(data.get('files'), list):
        return None
    return data


def global_rows(library, now=None):
    """全局库行列表（按类型、序号、路径排序）。"""
    data = read_global(library) or rebuild_global(library, now=now)
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


def read(project):
    """读取索引；不存在、损坏或版本不符时返回 ``None``（调用方据此重建）。"""
    from file_cache import read_json
    try:
        data = read_json(index_path(project))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or data.get('schema_version') != INDEX_VERSION:
        return None
    if not isinstance(data.get('files'), list):
        return None
    return data


def ensure(project, now=None):
    """有可用索引就返回，否则重建。"""
    data = read(project)
    return data if data is not None else rebuild(project, now=now)


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
    data = read(project)
    if data is None:
        return rebuild(project, now=now)
    table = {item.get('path'): item for item in data['files'] if isinstance(item, dict)}
    published = published_paths(project)
    for raw in paths:
        relative = _relative(project, raw)
        if removed:
            table.pop(relative, None)
            continue
        item = _row_for(project, relative, published, now=now)
        if item is None:
            table.pop(relative, None)
        else:
            table[relative] = item.to_dict()
    data['files'] = list(table.values())
    data['schema_version'] = INDEX_VERSION
    save(index_path(project), data)
    return data


def search(project, stage=None, kind=None, status=None, name=None, now=None):
    """按阶段／类型／状态／文件名关键字筛选；条件为空表示不限。"""
    keyword = str(name or '').strip().lower()
    out = []
    for row in rows(project, now=now):
        if stage and row.stage != stage:
            continue
        if kind and row.kind != kind:
            continue
        if status and row.status != status:
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

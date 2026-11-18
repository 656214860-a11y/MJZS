# -*- coding: utf-8 -*-
"""全局素材库与项目之间的复制动作（L1 基础设施，历史目录保留）。

双向复制保留相对目录、重名加序号且不移动源。文件通过
``agent.core.copy_file_new`` 原子排他发布；来源登记通过 ``save_text`` 保存。
失败只经 ``recycle_paths`` 回收本次新建且未被修改的副本。
"""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path, PureWindowsPath

import contract.stage_layout as stage_layout
from agent.core import copy_file_new, save_text
import infra.app_logging as app_logging
from infra import file_index, unit_of_work

SHARED_SUB = '全局素材库'
SOURCE_MANIFEST = '素材来源.json'
_source_lock = threading.RLock()


def _relative_path(value):
    """在 resolve 之前拒绝绝对、驱动器、父目录及 Windows 特殊路径。"""
    text = str(value).replace('\\', '/')
    parts = text.split('/')
    if (not text or PureWindowsPath(text).drive or text.startswith('/')
            or any(part in ('', '.', '..') or ':' in part
                   or part.endswith((' ', '.')) for part in parts)):
        raise ValueError('只能使用不含父目录的相对路径：' + str(value))
    return Path(*parts)


def _no_links(path):
    # resolve 会隐藏 junction/symlink，因此先检查原始路径及全部祖先。
    for part in (path, *path.parents):
        if part.is_symlink() or part.is_junction():
            raise ValueError('复制路径不能经过符号链接或 junction：' + str(part))


def _root(path):
    path = Path(path).absolute()
    _no_links(path)
    return path.resolve()


def _checked(path, root):
    path = Path(path)
    _no_links(path)
    # root 已规范化，relative 已排除 ../绝对路径，且所有祖先都已拒绝链接。
    # 不对正被并发创建的叶目录再 resolve（Windows 对缺失路径的解析有竞争窗口）。
    if not path.absolute().is_relative_to(root):
        raise ValueError('复制路径超出目标目录：' + str(path))
    return path


def _source(root, relative):
    source = _checked(root / relative, root)
    if not source.is_file():
        raise ValueError('只能复制所选目录内的文件：' + relative.as_posix())
    return source


def _targets(root, relative):
    """只生成候选；是否重名由 native 排他发布决定，不能先 exists 再替换。"""
    candidate = root / relative
    yield candidate
    stem, dot, suffix = candidate.name.rpartition('.')
    for index in range(2, 1000):
        name = ('%s(%d).%s' % (stem, index, suffix)) if dot else ('%s(%d)' % (candidate.name, index))
        yield candidate.with_name(name)


def _copy_file(source, root, relative):
    for target in _targets(root, relative):
        _checked(target, root)
        target.parent.mkdir(parents=True, exist_ok=True)
        _checked(target, root)
        def validate(temp):
            _checked(source, source.parent)
            _checked(temp, root)
            _checked(target, root)
            return True
        try:
            copy_file_new(target, source, validate)
        except FileExistsError:
            continue
        return target
    raise ValueError('无法生成不重名的目标：' + relative.as_posix())


def _identity(path):
    stat = path.stat(follow_symlinks=False)
    return stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns


def _rollback(root, target, identity):
    """不处理旧文件、源文件或已被用户替换/编辑的副本。"""
    _checked(target, root)
    if target.exists() and _identity(target) == identity:
        from infra.storage_maintenance import recycle_paths
        recycle_paths(root, [target], '复制失败：全局素材库回收本次新建副本')


def copy_to_project(library, relative_path, project, *, saver=None):
    """全局库 → 项目；返回实际副本 Path。saver 仅注入来源登记保存器。"""
    relative = _relative_path(relative_path)
    if relative.as_posix().casefold() == SOURCE_MANIFEST.casefold():
        raise ValueError('来源登记文件不能作为素材目标')
    library, project = _root(library), _root(project)
    source = _source(library, relative)
    root = _checked(stage_layout.shared_paths(project)['root'] / SHARED_SUB, project)
    manifest = _checked(root / SOURCE_MANIFEST, project)
    with _source_lock:
        target = _copy_file(source, root, relative)
        identity = _identity(target)
        # 来源登记与两份索引同进退；取消与进程中断也由事务 journal 恢复（R3310 轮 6）。
        # 副本本体不走事务删除：它是用户可见新文件，仍按身份核对后经回收站受控清理。
        token = unit_of_work.begin((manifest, file_index.index_path(project),
                                    file_index.origin_path(project)))
        try:
            _checked(manifest, project)
            _record_source(project, relative.as_posix(), library,
                           target.relative_to(root).as_posix(), saver=saver)
            file_index.update(project, [target])
            file_index.record_origin(project, [target], '用户上传')
            unit_of_work.commit(token)
        except BaseException:
            try:
                unit_of_work.rollback(token)
            except Exception:
                app_logging.swallowed('global_library_service.copy_to_project.rollback')
            try:
                _rollback(project, target, identity)
            except Exception:
                app_logging.swallowed('global_library_service.copy_to_project.recycle')
            raise
    return target


def copy_to_library(project, relative_path, library):
    """项目 → 全局库，保留相对结构、重名加序号；返回实际副本 Path。"""
    relative = _relative_path(relative_path)
    project, library = _root(project), _root(library)
    source = _source(project, relative)
    target = _copy_file(source, library, relative)
    identity = _identity(target)
    # 全局索引与副本登记同进退；取消与进程中断也由事务 journal 恢复（R3310 轮 6）。
    # 副本本体不走事务删除：它是用户可见新文件，仍按身份核对后经回收站受控清理。
    token = unit_of_work.begin((file_index.global_index_path(library),))
    try:
        file_index.rebuild_global(library)
        unit_of_work.commit(token)
    except BaseException:
        try:
            unit_of_work.rollback(token)
        except Exception:
            app_logging.swallowed('global_library_service.copy_to_library.rollback')
        try:
            _rollback(library, target, identity)
        except Exception:
            app_logging.swallowed('global_library_service.copy_to_library.recycle')
        raise
    return target


def _record_source(project, relative_path, library, target_path, *, saver=None):
    """登记库来源及重名后的实际副本路径，同一来源仍只保留一条登记。"""
    from infra.file_cache import read_json
    manifest = stage_layout.shared_paths(project)['root'] / SHARED_SUB / SOURCE_MANIFEST
    _checked(manifest, project)
    data = read_json(manifest) if manifest.is_file() else {}
    if not isinstance(data, dict):
        data = {}
    entries = data.get('entries') if isinstance(data.get('entries'), list) else []
    entries = [entry for entry in entries if isinstance(entry, dict) and entry.get('path') != relative_path]
    entries.append({'path': relative_path, 'library': str(library), 'target': target_path,
                    'imported_at': time.strftime('%Y-%m-%d %H:%M:%S')})
    _checked(manifest, project)
    (saver or save_text)(manifest, json.dumps({'entries': entries}, ensure_ascii=False, indent=2))

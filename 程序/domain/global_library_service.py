# -*- coding: utf-8 -*-
"""全局素材库与项目之间的复制动作（R3165，任务书 P3，Q11 收尾；L1 基础设施）。

「引用到当前项目」：把全局库里的文件复制进项目 ``_shared/全局素材库/``，并在项目侧写一份
来源登记（``素材来源.json``，记库目录与库相对路径）；不移动源文件。
「添加到全局库」：把项目里的文件复制进全局库（保留相对结构，重名加序号）；不移动源文件。

复制走 ``agent.core.save_file``（原子替换＋缓存失效＋大文件按块不进内存）；来源登记走
``agent.core.save_text``；边界由 ``file_cache`` 读保证。失败抛 OSError／ValueError，由调用方
（UI）转成用户可见文案。本模块只依赖 L0／L1，故登记 L1（与 ``storage_maintenance`` 同类文件
基础设施），不承担 L2 的发布债务与返回契约。
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import contract.stage_layout as stage_layout
from agent.core import save_text
from infra import file_index

SHARED_SUB = '全局素材库'
SOURCE_MANIFEST = '素材来源.json'


def _within(path, root):
    return Path(path).resolve().is_relative_to(Path(root).resolve())


def _copy_file(source, target):
    """复制单文件到目标：走 ``agent.core.save_file``（原子替换＋缓存失效＋大文件按块不进内存）。"""
    from agent.core import save_file
    save_file(target, source)


def copy_to_project(library, relative_path, project):
    """全局库文件 → 项目 ``_shared/全局素材库/``；登记来源后返回目标路径。"""
    library = Path(library).resolve()
    source = library / Path(*str(relative_path).split('/'))
    if not _within(source, library) or not source.is_file():
        raise ValueError('只能引用全局素材库内的文件：' + str(relative_path))
    project = Path(project).resolve()
    target = stage_layout.shared_paths(project)['root'] / SHARED_SUB / Path(*str(relative_path).split('/'))
    _copy_file(source, target)
    _record_source(project, str(relative_path), library)
    file_index.update(project, [target])
    return target


def copy_to_library(project, relative_path, library):
    """项目文件 → 全局库（保留相对结构，重名加序号）；返回目标路径。"""
    project = Path(project).resolve()
    source = project / Path(*str(relative_path).split('/'))
    if not _within(source, project) or not source.is_file():
        raise ValueError('只能添加项目内的文件：' + str(relative_path))
    library = Path(library).resolve()
    target = _available_target(library, str(relative_path))
    _copy_file(source, target)
    file_index.rebuild_global(library)
    return target


def _available_target(library, relative_path):
    """全局库内不覆盖既有文件的目标：重名时在扩展名前加 ``(2)``、``(3)``…。"""
    candidate = library / Path(*relative_path.split('/'))
    if not candidate.exists():
        return candidate
    stem, dot, suffix = candidate.name.rpartition('.')
    for index in range(2, 1000):
        name = ('%s(%d).%s' % (stem, index, suffix)) if dot else ('%s(%d)' % (candidate.name, index))
        trial = candidate.with_name(name)
        if not trial.exists():
            return trial
    raise ValueError('无法在全局库中生成不重名的目标：' + str(relative_path))


def _record_source(project, relative_path, library):
    """在项目 ``_shared/全局素材库/素材来源.json`` 追加一条来源登记。"""
    from file_cache import read_json
    manifest = stage_layout.shared_paths(project)['root'] / SHARED_SUB / SOURCE_MANIFEST
    data = read_json(manifest) if manifest.is_file() else {}
    if not isinstance(data, dict):
        data = {}
    entries = data.get('entries') if isinstance(data.get('entries'), list) else []
    entries = [entry for entry in entries if isinstance(entry, dict) and entry.get('path') != relative_path]
    entries.append({'path': relative_path, 'library': str(library),
                    'imported_at': time.strftime('%Y-%m-%d %H:%M:%S')})
    save_text(manifest, json.dumps({'entries': entries}, ensure_ascii=False, indent=2))

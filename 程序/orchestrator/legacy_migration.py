# -*- coding: utf-8 -*-
"""旧英文目录 → 当前阶段目录的存量迁移（R3125，任务书 P4，Q7=B／Q18／Q19）。

分工（任务书 §4 P4）：
- 迁移前整包备份被搬动的文件到 ``工作流任务/迁移备份/<时间戳>/``（保留原相对路径）；
- 逐项移动，冲突不覆盖，重复执行幂等（目标已存在且内容一致即跳过）；
- **E1**：把「成果确认」清单里的 ``scope.source`` 重指向新路径并按新指纹改名，
  否则已完成阶段会因指纹失配退回「未完成」；
- **E2**：把 ``assets_manifest.json`` 里的绝对路径改写为项目相对 posix；
- 产出 ``迁移报告.md``，逐项记录结果、跳过项与人工待办。

安全边界：只搬 ``stage_layout.LEGACY`` 登记过的旧目录下的文件；``_archive`` 只读不动；
本模块不删除任何未备份的内容。
"""
from __future__ import annotations

import hashlib
import json
import shutil
import time
from pathlib import Path

import contract.stage_layout as stage_layout
from contract.stage_path_service import write_dir

BACKUP_DIR_NAME = '迁移备份'
REPORT_NAME = '迁移报告.md'
CONFIRM_DIR_NAME = '成果确认'
ASSETS_MANIFEST_NAME = 'assets_manifest.json'
DOC_SUFFIXES = frozenset({'.md', '.txt', '.docx', '.rtf'})
MEDIA_SUFFIXES = frozenset({'.png', '.jpg', '.jpeg', '.webp', '.bmp', '.gif', '.tga', '.psd',
                            '.mp3', '.wav', '.m4a', '.aac', '.flac',
                            '.mp4', '.mov', '.mkv', '.avi', '.webm'})


def _digest(path):
    """流式 sha256（与 file_cache.file_digest 同口径，但只在本轮搬运里自用）。"""
    hasher = hashlib.sha256()
    with open(path, 'rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            hasher.update(block)
    return hasher.hexdigest()


def _slot(suffix):
    """按后缀决定落到阶段的哪个子目录：文档→docs，媒体→assets，其余→output。"""
    suffix = str(suffix).lower()
    if suffix in DOC_SUFFIXES:
        return 'docs'
    if suffix in MEDIA_SUFFIXES:
        return 'assets'
    return 'output'


def target_relpath(project, alias, old_relative, name):
    """旧目录里的一个文件名 → 新阶段目录下的项目相对 posix 路径。"""
    folder = stage_layout.LEGACY_STAGE_ALIASES.get(alias)
    if folder is None:
        return ''
    row = stage_layout.stage_dir(folder)
    if row is None:
        return ''
    slot = _slot(Path(name).suffix)
    return (Path(row[0]) / slot / name).as_posix()


def plan(project):
    """列出全部待迁移项：``{'source','target','action','reason'}``（纯读，不写盘）。"""
    root = Path(project).resolve()
    ops = []
    for alias, old_relative, _description in stage_layout.LEGACY:
        base = root / Path(*old_relative.split('/'))
        if not base.exists():
            continue
        for path in sorted(base.rglob('*')):
            if not path.is_file() or path.is_symlink():
                continue
            source = path.relative_to(root).as_posix()
            target = target_relpath(root, alias, old_relative, path.name)
            if not target:
                ops.append({'source': source, 'target': '', 'action': 'skip',
                            'reason': '旧阶段名没有对应的当前阶段目录'})
                continue
            destination = root / Path(*target.split('/'))
            if destination.is_file():
                same = _digest(path) == _digest(destination)
                ops.append({'source': source, 'target': target,
                            'action': 'skip' if same else 'conflict',
                            'reason': '目标已存在且内容一致' if same else '目标已存在且内容不同，未覆盖'})
                continue
            ops.append({'source': source, 'target': target, 'action': 'move', 'reason': ''})
    return ops


def _backup_path(root, stamp, relative):
    return stage_layout.workflow_dir(root, BACKUP_DIR_NAME, stamp, *relative.split('/'))


def apply(project, ops, now=None):
    """执行迁移：先备份被搬动的文件，再逐项移动；返回逐项结果的 ops 副本。"""
    root = Path(project).resolve()
    stamp = time.strftime('%Y%m%d_%H%M%S', time.localtime(now or time.time()))
    done = []
    for op in ops:
        item = dict(op)
        if item['action'] != 'move':
            done.append(item)
            continue
        source = root / Path(*item['source'].split('/'))
        target = root / Path(*item['target'].split('/'))
        backup = _backup_path(root, stamp, item['source'])
        try:
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, backup)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(source), str(target))
        except OSError as exc:
            item['action'] = 'failed'
            item['reason'] = '移动失败：' + str(exc)
            done.append(item)
            continue
        if not source.exists():
            _prune_empty(source.parent, root)
        item['action'] = 'moved'
        item['backup'] = backup.relative_to(root).as_posix()
        done.append(item)
    return done, stamp


def _prune_empty(folder, root):
    """搬空之后删除空目录；不越过项目根、不递归删除非空目录。"""
    try:
        current = Path(folder)
        while current.resolve().is_relative_to(root) and current.resolve() != root:
            if any(current.iterdir()):
                return
            current.rmdir()
            current = current.parent
    except OSError:
        return


def mapping_of(ops):
    """搬动项的原路径 → 新路径映射（E1／E2 用）。"""
    return {op['source']: op['target'] for op in ops if op.get('action') in ('move', 'moved')}


def repoint_manifests(project, moves):
    """E1：把成果确认清单的 scope.source 重指向新路径，并按新指纹改名落盘。

    不做这一步，已完成的媒体阶段会因「清单文件名＝源路径指纹」失配而退回未完成。
    """
    from agent.core import save
    from infra.file_cache import read_json
    from stage_completion_service import media_manifest_path
    root = Path(project).resolve()
    saved = []
    for row in stage_layout.STAGES:
        stage, folder_name = row[1], row[0]
        confirm = root / folder_name / CONFIRM_DIR_NAME
        if not confirm.is_dir():
            continue
        for manifest in sorted(confirm.glob('*.json')):
            try:
                data = read_json(manifest)
            except (OSError, ValueError):
                continue
            scope = data.get('scope') if isinstance(data, dict) else None
            if not isinstance(scope, dict):
                continue
            source = str(scope.get('source') or '')
            if source not in moves:
                continue
            new_scope = dict(scope, source=moves[source], source_sha256=_digest(root / Path(*moves[source].split('/'))))
            data['scope'] = new_scope
            try:
                target = media_manifest_path(root, stage, new_scope)
            except ValueError:
                # 该阶段不支持媒体成果确认清单（只有音频／后期／交付有）；跳过即可。
                continue
            save(target, data)
            if target.resolve() != manifest.resolve():
                # 物理删除只经回收权威：旧指纹清单移入项目回收站，可追溯。
                from infra.storage_maintenance import recycle_paths
                try:
                    recycle_paths(root, [manifest], '迁移：旧指纹成果确认清单')
                except (OSError, ValueError):
                    pass
            saved.append(target.relative_to(root).as_posix())
    return saved


def rewrite_absolute_manifests(project, moves):
    """E2：把清单里的绝对路径改写为项目相对 posix，并按迁移映射改指向新位置。"""
    from agent.core import save
    from infra.file_cache import read_json
    root = Path(project).resolve()
    rewritten = []
    for path in sorted(root.rglob(ASSETS_MANIFEST_NAME)):
        if stage_layout.WORKFLOW_DIR in path.parts:
            continue
        try:
            data = read_json(path)
        except (OSError, ValueError):
            continue
        changed = _rewrite_tree(data, root, moves)
        if changed:
            save(path, data)
            rewritten.append(path.relative_to(root).as_posix())
    return rewritten


def _rewrite_tree(node, root, moves):
    """递归改写 dict/list 里形如路径的字符串；返回是否有改动。"""
    changed = False
    if isinstance(node, dict):
        for key in list(node):
            value = node[key]
            if isinstance(value, str):
                new = _rewrite_one(value, root, moves)
                if new != value:
                    node[key] = new
                    changed = True
            elif isinstance(value, (dict, list)):
                changed = _rewrite_tree(value, root, moves) or changed
        return changed
    if isinstance(node, list):
        for index, value in enumerate(node):
            if isinstance(value, str):
                new = _rewrite_one(value, root, moves)
                if new != value:
                    node[index] = new
                    changed = True
            elif isinstance(value, (dict, list)):
                changed = _rewrite_tree(value, root, moves) or changed
    return changed


def _rewrite_one(text, root, moves):
    """把绝对路径收成项目相对 posix，并按迁移映射换到新位置。"""
    candidate = Path(text)
    if not candidate.is_absolute():
        return moves.get(text.replace('\\', '/'), text)
    try:
        relative = candidate.resolve().relative_to(root).as_posix()
    except (OSError, ValueError):
        return text
    return moves.get(relative, relative)


def report(project, ops, stamp):
    """写迁移报告（Markdown），返回报告路径。"""
    from agent.core import save_text
    root = Path(project).resolve()
    lines = ['# 迁移报告', '', '- 时间：' + stamp, '- 项目：' + str(root), '']
    counts = {}
    for op in ops:
        counts[op['action']] = counts.get(op['action'], 0) + 1
    lines.append('- 统计：' + '；'.join('%s %d' % (key, value) for key, value in sorted(counts.items())))
    lines.append('')
    lines.append('| 原路径 | 新路径 | 结果 | 说明 |')
    lines.append('| --- | --- | --- | --- |')
    for op in ops:
        lines.append('| %s | %s | %s | %s |' % (op['source'], op.get('target', ''), op['action'],
                                                op.get('reason', '') or op.get('backup', '')))
    lines.append('')
    target = stage_layout.workflow_dir(root, BACKUP_DIR_NAME, stamp, REPORT_NAME)
    save_text(target, '\n'.join(lines) + '\n')
    return target

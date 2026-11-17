# -*- coding: utf-8 -*-
"""Legacy migration: read-only planning, whole-batch validation and recoverable journal.

Ambiguous ownership requires explicit source->target mappings or an identical existing
canonical target. No filename/stage guessing. All destructive operations use recycle_paths.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import stat
import time
import uuid
from functools import wraps
from pathlib import Path, PureWindowsPath

import contract.stage_layout as stage_layout
from contract.stage_path_service import write_dir

BACKUP_DIR_NAME = '迁移备份'
REPORT_NAME = '迁移报告.md'
CONFIRM_DIR_NAME = '成果确认'
ASSETS_MANIFEST_NAME = 'assets_manifest.json'
DOC_SUFFIXES = frozenset({'.md', '.txt', '.docx', '.rtf'})
MEDIA_SUFFIXES = frozenset({'.png', '.jpg', '.jpeg', '.webp', '.bmp', '.gif', '.tga', '.psd',
                            '.mp3', '.wav', '.ogg', '.m4a', '.flac', '.mp4', '.mov', '.webm', '.srt', '.ass'})
PATH_KEYS = frozenset({'path', 'source', 'file', 'filepath', 'file_path', 'source_path',
    'output_path', 'target_path', 'manifest_path', 'frame_json', 'storyboard_file', 'script_json',
    'image', 'image_path', 'audio', 'audio_path', 'video', 'video_path', 'subtitle_path',
    'thumbnail', 'canonical_board', 'reference_image', 'local_path'})
PATH_LISTS = frozenset({'adopted_storyboards', 'reference_images', 'files', 'paths', 'outputs'})
EXCLUDED = frozenset({'回收站', '迁移备份', '覆盖前备份'})


class MigrationError(ValueError):
    """A batch could not be safely planned/applied/recovered."""


def _digest(path):
    hasher = hashlib.sha256()
    with open(path, 'rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            hasher.update(block)
    return hasher.hexdigest()


def _root(project):
    path = Path(os.path.abspath(project))
    _no_links(path)
    if not path.is_dir():
        raise MigrationError('项目目录不存在')
    return path


def _no_links(path):
    for item in (path, *path.parents):
        if item.exists() or item.is_symlink():
            info = item.lstat()
            if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
                raise MigrationError('拒绝 symlink/junction/reparse point: ' + str(item))


def _path(root, relative):
    text = str(relative).replace('\\', '/')
    parts = text.split('/')
    if not text or PureWindowsPath(text).drive or text.startswith('/') or any(
            part in ('', '.', '..') or ':' in part or part.rstrip(' .') != part
            or part.split('.')[0].upper() in {'CON', 'PRN', 'AUX', 'NUL',
                *(f'COM{i}' for i in range(1, 10)), *(f'LPT{i}' for i in range(1, 10))}
            for part in parts):
        raise MigrationError('非法项目相对路径: ' + text)
    path = root.joinpath(*parts)
    _no_links(path)
    if not path.resolve().is_relative_to(root):
        raise MigrationError('路径越界: ' + text)
    return path


def _files(root, folder=None):
    start = folder or root
    for base, dirs, files in os.walk(start, followlinks=False):
        here = Path(base)
        _no_links(here)
        kept = []
        for name in sorted(dirs):
            child = here / name
            _no_links(child)
            if name not in EXCLUDED:
                kept.append(name)
        dirs[:] = kept
        for name in sorted(files):
            path = here / name
            _no_links(path)
            if not path.is_file():
                raise MigrationError('不支持的文件类型: ' + str(path))
            yield path


def _directories(root):
    result = []
    for base, dirs, _files_here in os.walk(root, followlinks=False):
        dirs[:] = sorted(name for name in dirs if name not in EXCLUDED)
        for name in dirs:
            path = Path(base) / name
            _no_links(path)
            result.append(path.relative_to(root).as_posix())
    return result


def _slot(suffix):
    return 'docs' if suffix.lower() in DOC_SUFFIXES else (
        'assets' if suffix.lower() in MEDIA_SUFFIXES else 'output')


def target_relpath(project, alias, old_relative, name):
    """Preserve the complete subtree below each registered legacy root."""
    row = stage_layout.stage_dir(alias)
    if row is None or not row[1]:
        raise MigrationError('未知阶段: ' + alias)
    root = _root(project)
    source = _path(root, old_relative)
    child = _path(source, name)
    tail = child.relative_to(source)
    return (write_dir(root, row[1]) / _slot(child.suffix) / tail).relative_to(root).as_posix()


def _choose(root, source, candidates, explicit):
    if source in explicit:
        chosen = str(explicit[source]).replace('\\', '/')
        _path(root, chosen)
        if chosen not in candidates:
            raise MigrationError('明确映射不是登记目标: ' + source)
        return chosen
    if len(candidates) == 1:
        return next(iter(candidates))
    digest = _digest(_path(root, source))
    authoritative = [value for value in candidates if _path(root, value).is_file()
                     and _digest(_path(root, value)) == digest]
    if len(authoritative) == 1:
        return authoritative[0]
    raise MigrationError('重叠来源归属不明，请提供明确映射: ' + source)


def plan(project, explicit=None):
    """Plan once per physical source; any unknown/ambiguous/colliding item blocks all."""
    root, sources = _root(project), {}
    explicit = explicit or {}
    for alias, relative, _note in stage_layout.LEGACY:
        folder = _path(root, relative)
        if alias == '_archive' or not folder.exists():
            continue
        if stage_layout.stage_dir(alias) is None:
            raise MigrationError('未知阶段: ' + alias)
        if not folder.is_dir():
            raise MigrationError('旧目录不是目录: ' + relative)
        for path in _files(root, folder):
            source = path.relative_to(root).as_posix()
            target = target_relpath(root, alias, relative, path.relative_to(folder).as_posix())
            sources.setdefault(source, set()).add(target)
    unknown = set(explicit) - set(sources)
    if unknown:
        raise MigrationError('明确映射包含未知来源: ' + ', '.join(sorted(unknown)))
    ops = []
    for source, candidates in sorted(sources.items()):
        target = _choose(root, source, candidates, explicit)
        ops.append({'source': source, 'target': target, 'action': 'move', 'reason': '',
                    'sha256': _digest(_path(root, source))})
    _validate(root, ops)
    return ops


def _validate(root, ops):
    sources, targets = set(), set()
    for op in ops:
        source, target = _path(root, op['source']), _path(root, op['target'])
        source_key, target_key = str(source).casefold(), str(target).casefold()
        if source_key in sources or target_key in targets or source_key == target_key:
            raise MigrationError('批内重复来源/目标碰撞: ' + op['source'])
        sources.add(source_key)
        targets.add(target_key)
        if not source.is_file() or _digest(source) != op.get('sha256'):
            raise MigrationError('来源已变化或缺失: ' + op['source'])
        if target.exists():
            if not target.is_file() or _digest(target) != op['sha256']:
                raise MigrationError('目标冲突: ' + op['target'])
            op['action'] = 'skip'
        for parent in target.parents:
            if parent == root:
                break
            if parent.exists() and not parent.is_dir():
                raise MigrationError('目标父路径冲突: ' + str(parent))
    if sources & targets:
        raise MigrationError('来源与目标重叠')
    for target in targets:
        if any(target.startswith(other + os.sep) for other in targets if target != other):
            raise MigrationError('目标文件与目录碰撞')


def mapping_of(ops):
    return {op['source']: op['target'] for op in ops
            if op.get('action') in ('move', 'moved', 'skip')}


def _reference(value, root, moves):
    text = value.replace('\\', '/')
    candidate = Path(text)
    if candidate.is_absolute():
        _no_links(candidate)
        try:
            text = candidate.relative_to(root).as_posix()
        except ValueError:
            raise MigrationError('引用在项目外: ' + value) from None
    path = _path(root, text)
    text, seen = path.relative_to(root).as_posix(), set()
    while text in moves and moves[text] != text:
        if text in seen:
            raise MigrationError('引用映射循环: ' + text)
        seen.add(text)
        text = moves[text]
        _path(root, text)
    return text


def _affected(value, root, moves):
    text = value.replace('\\', '/')
    return any(source in text for source in moves)


def _rewrite_tree(node, root, moves, key='', hashes=None):
    """Rewrite typed path fields only; unknown affected fields fail closed."""
    if isinstance(node, list):
        return [_rewrite_tree(value, root, moves, key, hashes) for value in node]
    if isinstance(node, str):
        if key in PATH_KEYS or key in PATH_LISTS:
            return _reference(node, root, moves) if node else node
        if _affected(node, root, moves):
            raise MigrationError('未知引用字段: ' + key)
        return node
    if not isinstance(node, dict):
        return node
    for name in node:
        if _affected(name, root, moves):
            raise MigrationError('未知路径字典键: ' + name)
    result = {name: _rewrite_tree(value, root, moves, name, hashes) for name, value in node.items()}
    for name, hash_name in (('source', 'source_sha256'), ('path', 'sha256'), ('file', 'sha256')):
        if isinstance(node.get(name), str) and hash_name in node and hashes is not None:
            target = _reference(node[name], root, moves)
            if target not in hashes:
                raise MigrationError('指纹引用缺失: ' + node[name])
            original = _reference(node[name], root, {})
            old_path = _path(root, original)
            if not old_path.is_file() or node[hash_name] != _digest(old_path):
                # Migration must never repair stale evidence into a valid confirmation.
                raise MigrationError('已有指纹不匹配: ' + node[name])
            result[hash_name] = hashes[target]
    return result


def _json_bytes(data):
    return json.dumps(data, ensure_ascii=False, indent=2).replace('\n', os.linesep).encode('utf-8')


def _documents(root, inventory, *, readonly=False):
    from infra.file_cache import read_json
    docs = {}
    for relative in inventory:
        if Path(relative).suffix.lower() != '.json':
            continue
        path = _path(root, relative)
        try:
            # dry-run 必须无写副作用；解析只读快照，避免正式读取器创建事务锁。
            data = json.JSONDecoder().decode(path.read_text(encoding='utf-8-sig')) if readonly else read_json(path)
        except (OSError, ValueError, UnicodeError) as exc:
            raise MigrationError('JSON 无法解析: ' + relative) from exc
        docs[relative] = data
    return docs


def _prepare(root, ops, inventory, *, readonly=False):
    """Compute all final JSON bytes and names before creating the backup directory."""
    from stage_completion_service import media_manifest_path
    moves = mapping_of(ops)
    docs = _documents(root, inventory, readonly=readonly)
    for relative, data in docs.items():
        if CONFIRM_DIR_NAME not in Path(relative).parts:
            continue
        if not isinstance(data, dict) or not isinstance(data.get('scope'), dict):
            raise MigrationError('成果确认缺少 scope: ' + relative)
        scope = data['scope']
        if data.get('stage') not in ('audio', 'edit', 'delivery') or not scope.get('source'):
            raise MigrationError('未知成果确认类型或来源: ' + relative)
        new_scope = dict(scope, source=_reference(scope['source'], root, moves))
        target = media_manifest_path(root, data['stage'], new_scope).relative_to(root).as_posix()
        if target != relative and target in inventory:
            raise MigrationError('成果确认目标已存在: ' + target)
        if target != relative:
            moves[relative] = target
    hashes = {_reference(rel, root, moves): digest for rel, digest in inventory.items()}
    writes, changed_content = {}, set()
    for _iteration in range(len(docs) + 2):
        next_writes, next_hashes, renames = {}, dict(hashes), {}
        for relative, data in docs.items():
            updated = _rewrite_tree(data, root, moves, hashes=hashes)
            target = moves.get(relative, relative)
            scope = updated.get('scope') if isinstance(updated, dict) else None
            if isinstance(scope, dict) and isinstance(data.get('scope'), dict):
                bound = [data['scope'].get('source')] + [item.get('path') for item in
                        data.get('outputs', []) if isinstance(item, dict)]
                if any(value and _reference(value, root, {}) in changed_content for value in bound):
                    updated['reviewed'] = False
                    if updated.get('status') == 'complete':
                        updated['status'] = 'pending_review'
                if CONFIRM_DIR_NAME in Path(relative).parts:
                    stage = updated.get('stage')
                    if stage not in ('audio', 'edit', 'delivery'):
                        raise MigrationError('未知成果确认类型: ' + relative)
                    target = media_manifest_path(root, stage, scope).relative_to(root).as_posix()
                    renames[relative] = target
                if isinstance(updated.get('qc'), dict) and 'bound' in updated['qc']:
                    updated['qc']['bound'] = [item['sha256'] for item in updated.get('outputs', [])]
            if updated != data or target != relative:
                payload = _json_bytes(updated) if updated != data else _path(root, relative).read_bytes()
                if target in next_writes and next_writes[target] != payload:
                    raise MigrationError('清单重命名碰撞: ' + target)
                next_writes[target] = payload
                next_hashes[target] = hashlib.sha256(payload).hexdigest()
                if updated != data:
                    changed_content.add(relative)
        if next_writes == writes:
            break
        writes, hashes = next_writes, next_hashes
    else:
        raise MigrationError('引用指纹循环，无法稳定重写')
    for old, new in renames.items():
        if old != new:
            moves[old] = new
    deleted = set(mapping_of(ops)) | {old for old, new in renames.items() if old != new}
    for target in writes:
        _path(root, target)
        if target in inventory and target not in docs and target not in deleted:
            raise MigrationError('重写目标冲突: ' + target)
    # A renamed confirmation must not overwrite another existing confirmation, even identical.
    for old, new in renames.items():
        if old != new and new in inventory and new != old:
            raise MigrationError('成果确认目标已存在: ' + new)
    return writes, deleted, moves


def _validate_writes(root, writes):
    targets = set()
    for relative in writes:
        path = _path(root, relative)
        key = str(path).casefold()
        if key in targets:
            raise MigrationError('重写目标大小写碰撞: ' + relative)
        targets.add(key)
        if path.exists() and not path.is_file():
            raise MigrationError('重写目标不是文件: ' + relative)
        for parent in path.parents:
            if parent == root:
                break
            if parent.exists() and not parent.is_dir():
                raise MigrationError('重写目标父目录冲突: ' + relative)


def _save_journal(batch, journal):
    from agent.core import save
    save(batch / 'journal.json', journal)


def _snapshot(root):
    return {path.relative_to(root).as_posix(): _digest(path) for path in _files(root)}


def _backup(root, batch, inventory, directories):
    from agent.core import save_file
    for relative in directories:
        _path(batch / 'files', relative).mkdir(parents=True, exist_ok=True)
    for relative, digest in inventory.items():
        save_file(batch / 'files' / relative, _path(root, relative), digest=digest)


def _check_snapshot(root, inventory):
    if _snapshot(root) != inventory:
        raise MigrationError('项目在预检/备份期间发生变化，已阻止写入')


def _pending(root, *, readonly=False):
    from infra.file_cache import read_json
    base = stage_layout.workflow_dir(root, BACKUP_DIR_NAME)
    if base.exists():
        _no_links(base)
        for batch in base.iterdir():
            _no_links(batch)
            path = batch / 'journal.json'
            _no_links(path)
            if path.is_file():
                # dry-run 必须无写副作用；解析只读快照，避免正式读取器创建事务锁。
                data = json.JSONDecoder().decode(path.read_text(encoding='utf-8-sig')) if readonly else read_json(path)
                if data.get('state') not in ('committed', 'rolled_back', 'backup_failed'):
                    raise MigrationError('存在未完成事务，请先回滚: ' + batch.name)


def _publish(root, batch, journal, ops, writes, deleted):
    from agent.core import save_file, save_text
    from infra.storage_maintenance import recycle_paths
    for op in ops:
        target = _reference(op['source'], root, journal['moves'])
        if op['action'] != 'skip' and target not in writes:
            save_file(_path(root, target), batch / 'files' / op['source'], digest=op['sha256'])
        op['target'] = target
    originals = {digest: relative for relative, digest in journal['inventory'].items()}
    for relative, payload in writes.items():
        digest = hashlib.sha256(payload).hexdigest()
        if digest in originals:
            save_file(_path(root, relative), batch / 'files' / originals[digest], digest=digest)
        else:
            save_text(_path(root, relative), payload.decode('utf-8').replace('\r\n', '\n'))
    _save_journal(batch, dict(journal, state='recycling'))
    paths = [_path(root, rel) for rel in sorted(deleted) if _path(root, rel).exists()
             and rel not in journal['final']]
    if paths:
        recycle_paths(root, paths, '旧布局迁移 ' + batch.name)
    for op in ops:
        op['action'] = 'moved' if op['action'] != 'skip' else 'skip'


def _serialized(function):
    @wraps(function)
    def guarded(*args, **kwargs):
        if kwargs.get('dry_run'):
            return function(*args, **kwargs)
        from agent.publication import access
        with access():
            return function(*args, **kwargs)
    return guarded


@_serialized
def apply(project, ops, *, dry_run=False):
    """Apply migrations and references in one transaction; exceptions trigger rollback."""
    root, ops = _root(project), copy.deepcopy(ops)
    _pending(root, readonly=dry_run)
    approved = plan(root, {op['source']: op['target'] for op in ops})
    if sorted((op['source'], op['target'], op['sha256']) for op in approved) != sorted(
            (op['source'], op['target'], op.get('sha256')) for op in ops):
        raise MigrationError('计划不完整或已变化')
    _validate(root, ops)
    inventory, directories = _snapshot(root), _directories(root)
    writes, deleted, moves = _prepare(root, ops, inventory, readonly=dry_run)
    _validate_writes(root, writes)
    owners = {}
    for relative in inventory:
        target = _reference(relative, root, moves)
        if target in owners and inventory[owners[target]] != inventory[relative]:
            raise MigrationError('最终路径碰撞: ' + target)
        owners[target] = relative
    if dry_run or (not ops and not writes):
        return ops, ''
    stamp = time.strftime('%Y%m%d_%H%M%S') + '_' + uuid.uuid4().hex
    batch = stage_layout.workflow_dir(root, BACKUP_DIR_NAME, stamp)
    _no_links(batch)
    final = {_reference(op['source'], root, moves): op['sha256'] for op in ops}
    final.update({rel: hashlib.sha256(data).hexdigest() for rel, data in writes.items()})
    journal = {'schema_version': 1, 'batch': stamp, 'project': str(root), 'state': 'backing_up',
               'inventory': inventory, 'directories': directories, 'final': final,
               'deleted': sorted(deleted), 'moves': moves}
    _save_journal(batch, journal)
    try:
        _backup(root, batch, inventory, directories)
        _check_snapshot(root, inventory)
    except Exception:
        _save_journal(batch, dict(journal, state='backup_failed'))
        raise
    journal['state'] = 'prepared'
    _save_journal(batch, journal)
    try:
        _publish(root, batch, journal, ops, writes, deleted)
        for relative, digest in final.items():
            if _digest(_path(root, relative)) != digest:
                raise MigrationError('发布后指纹不匹配: ' + relative)
        report(root, ops, stamp)
        journal['state'] = 'committed'
        _save_journal(batch, journal)
    except Exception as exc:
        try:
            rollback(root, stamp)
        except Exception as recovery:
            raise MigrationError('迁移失败且回滚未完成，请保留备份并重试 --rollback %s: %s / %s'
                                 % (stamp, exc, recovery)) from recovery
        raise MigrationError('迁移失败，已回滚: ' + str(exc)) from exc
    return ops, stamp


@_serialized
def rollback(project, stamp):
    """Recover an interrupted/committed batch from its immutable complete backup."""
    from agent.core import save_file
    from infra.file_cache import read_json
    from infra.storage_maintenance import recycle_paths
    root = _root(project)
    batch = _path(root, stage_layout.workflow_dir(root, BACKUP_DIR_NAME, stamp).relative_to(root).as_posix())
    _no_links(batch / 'journal.json')
    journal = read_json(batch / 'journal.json')
    if (journal.get('batch') != stamp or journal.get('schema_version') != 1
            or journal.get('project') != str(root)):
        raise MigrationError('无效事务 journal 或项目不匹配')
    if journal.get('state') == 'rolled_back':
        return stamp
    if journal.get('state') in ('backing_up', 'backup_failed'):
        raise MigrationError('备份未完成，未修改项目，无需回滚')
    inventory, final = journal['inventory'], journal['final']
    affected = set(final) | set(journal['deleted'])
    # Validate every restore and removal before making even one recovery write.
    for relative in affected:
        path = _path(root, relative)
        old = inventory.get(relative)
        if old and _digest(_path(batch / 'files', relative)) != old:
            raise MigrationError('备份损坏: ' + relative)
        if path.exists() and (not path.is_file() or _digest(path) not in (old, final.get(relative))):
            raise MigrationError('回滚冲突，保留当前文件: ' + relative)
    journal['state'] = 'rolling_back'
    _save_journal(batch, journal)
    for relative in sorted(affected):
        if relative in inventory:
            save_file(_path(root, relative), batch / 'files' / relative, digest=inventory[relative])
    extras = [_path(root, rel) for rel in final if rel not in inventory and _path(root, rel).exists()]
    if extras:
        recycle_paths(root, extras, '撤回旧布局迁移 ' + stamp)
    journal['state'] = 'rolled_back'
    _save_journal(batch, journal)
    return stamp


def report(project, ops, stamp):
    from agent.core import save_text
    root = _root(project)
    target = _path(root, stage_layout.workflow_dir(root, BACKUP_DIR_NAME, stamp, REPORT_NAME).relative_to(root).as_posix())
    lines = ['# 迁移报告', '', '- 批次：' + stamp, '', '| 原路径 | 新路径 | 结果 |', '| --- | --- | --- |']
    lines += ['| %s | %s | %s |' % (op['source'], op['target'], op['action']) for op in ops]
    save_text(target, '\n'.join(lines) + '\n')
    return target

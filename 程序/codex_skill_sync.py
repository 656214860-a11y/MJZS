"""将注册表中的阶段单文件技能物化为 Codex 技能；不内联、不接管手工技能。"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import threading

from agent.core import read_json, save, save_text
from skill_registry import default_registry, parse, stage_from_path
from storage_maintenance import recycle_paths

_LOCK = threading.RLock()
_MARKER = '.assistant-skill-sync.json'
_OWNER = 'manju-codex-skill-sync-v1'
_NAME = re.compile(r'[a-z0-9][a-z0-9-]{0,63}\Z')


def _hash(data):
    return hashlib.sha256(data).hexdigest()


def _plain(path):
    return not path.is_symlink() and not path.is_junction()


def _metadata(directory):
    marker = directory / _MARKER
    if not _plain(directory) or not _plain(marker):
        return {}
    try:
        value = read_json(marker)
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def _render(source, text):
    meta, body = parse(text, source=str(source))
    name, description = meta.get('name'), meta.get('description')
    if not isinstance(name, str) or not _NAME.fullmatch(name):
        raise ValueError('技能 name 必须是小写英文、数字或连字符（最多 64 字符）')
    if name.lower() in {'con', 'prn', 'aux', 'nul', *('com%d' % n for n in range(10)),
                       *('lpt%d' % n for n in range(10))}:
        raise ValueError('技能 name 为系统保留名称')
    if not isinstance(description, str) or not description.strip():
        raise ValueError('技能缺少 description')
    shared = (source.parent.parent / '00全流程SKILL').resolve().as_posix() + '/'
    body = body.replace('../00全流程SKILL/', shared)
    return name, '---\nname: %s\ndescription: %s\n---\n%s' % (
        json.dumps(name, ensure_ascii=False), json.dumps(description, ensure_ascii=False), body)


def sync_codex_skills(program=None, skill_home=None):
    """同步所有已登记阶段的 .skill.md；返回 written/unchanged/recycled/conflicts/errors。

    skill_home 是目标 skills 目录。仅回收本安装拥有且内容未被修改的孤儿目录。
    扫描或读取失败时不回收；同步器与发送前检查串行，调用方应在后台执行。
    """
    report = {key: [] for key in ('written', 'unchanged', 'recycled', 'conflicts', 'errors')}
    with _LOCK:
        try:
            _sync(program, skill_home, report)
        except (OSError, ValueError, UnicodeError) as exc:
            report['errors'].append(str(exc))
    return report


def _sync(program, skill_home, report):
    registry = default_registry(program)
    root = registry.root.resolve()
    # Do not treat an unavailable installation as an empty, authoritative inventory.
    if not root.is_dir():
        raise ValueError('程序 skills 目录不可用，未同步或清理')
    destination = Path(skill_home) if skill_home is not None else Path(
        os.environ.get('CODEX_HOME') or Path.home() / '.codex') / 'skills'
    if not _plain(destination):
        raise ValueError('技能目标目录不能是符号链接或联接')
    destination = destination.resolve()
    owner_root = str(root)
    registry.scan(force=True)
    inventory = []
    seen = set()
    for skill in registry.getAll():
        source = Path(skill.path)
        if not source.name.endswith('.skill.md') or not stage_from_path(source):
            continue
        if not _plain(source) or not source.resolve().is_relative_to(root):
            report['errors'].append(source.name + '：来源不在程序技能目录内')
            continue
        try:
            raw = source.read_bytes()
            name, rendered = _render(source, raw.decode('utf-8-sig'))
            if name in seen:
                raise ValueError('技能重名')
            seen.add(name)
            inventory.append((name, source, raw, rendered))
        except (OSError, ValueError, UnicodeError) as exc:
            report['errors'].append(source.name + '：' + str(exc))
    # Registry also reports skipped unreadable and duplicate sources.
    if registry.problems():
        report['errors'].extend(registry.problems())
    destination.mkdir(parents=True, exist_ok=True)
    for name, source, raw, rendered in inventory:
        directory = destination / name
        target = directory / 'SKILL.md'
        previous = _metadata(directory)
        owned = previous.get('owner') == _OWNER and previous.get('root') == owner_root
        if (not _plain(directory) or not _plain(target)
                or (directory.exists() and not owned)):
            report['conflicts'].append(name)
            continue
        existing = target.read_bytes() if target.exists() else None
        wanted = rendered.encode('utf-8')
        matches = existing is not None and existing.replace(b'\r\n', b'\n') == wanted
        if existing is not None and not matches and _hash(existing) != previous.get('output_hash'):
            report['conflicts'].append(name)
            continue
        metadata = {'owner': _OWNER, 'root': owner_root, 'source': str(source.resolve()),
                    'source_hash': _hash(raw), 'output_hash': _hash(existing or wanted)}
        if matches and metadata == previous:
            report['unchanged'].append(name)
            continue
        save_text(target, rendered)
        metadata['output_hash'] = _hash(target.read_bytes())
        save(directory / _MARKER, metadata)
        report['written'].append(name)
    if report['errors']:
        return
    for directory in destination.iterdir():
        previous = _metadata(directory)
        if (directory.name in seen or previous.get('owner') != _OWNER
                or previous.get('root') != owner_root):
            continue
        target = directory / 'SKILL.md'
        if (not _plain(target) or not target.is_file()
                or _hash(target.read_bytes()) != previous.get('output_hash')
                or {p.name for p in directory.iterdir()} != {'SKILL.md', _MARKER}):
            report['conflicts'].append(directory.name)
            continue
        if recycle_paths(destination, [directory], '应用 Codex 技能源文件已删除'):
            report['recycled'].append(directory.name)


def start_codex_skill_sync(program=None):
    """首帧后启动独立后台维护；不占用桌面业务 worker、不访问 Tk。"""
    worker = threading.Thread(target=sync_codex_skills, kwargs={'program': program},
                              name='codex-skill-sync', daemon=True)
    worker.start()
    return worker

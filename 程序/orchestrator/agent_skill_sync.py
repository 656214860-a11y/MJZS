"""将注册表中的阶段单文件技能物化为各 Agent 客户端技能目录；不内联、不接管手工技能。

目标登记见 ``TARGETS``：codex 沿用 ``CODEX_HOME``（默认 ``~/.codex/skills``），
claude 为 ``~/.claude/skills``，agents 为业界共享 ``~/.agents/skills``
（Codex/Cursor/Gemini CLI/OpenCode/Pi 的用户级扫描目录，Claude Code 不读，
故 claude 引擎发送前只校验 claude 目标，见 ``ENGINE_TARGETS``）。
marker 增 ``target`` 字段，孤儿回收按 ``(owner, root, target)`` 三元组判定。
"""
from __future__ import annotations

import functools
import hashlib
import json
import os
from pathlib import Path
import re
import threading

import infra.executors as executors
from agent.core import read_json, save, save_text
from orchestrator.skill_registry import (default_registry, parse, stage_from_path,
                                         reference_targets, resolve_reference)
from infra.storage_maintenance import recycle_paths

_LOCK = threading.RLock()
_MARKER = '.assistant-skill-sync.json'
_OWNER = 'manju-codex-skill-sync-v1'
_NAME = re.compile(r'[a-z0-9][a-z0-9-]{0,63}\Z')

TARGETS = {
    'codex': {'label': 'Codex', 'env_home': 'CODEX_HOME', 'base': '.codex'},
    'claude': {'label': 'Claude', 'env_home': None, 'base': '.claude'},
    'agents': {'label': 'Agents', 'env_home': None, 'base': '.agents'},
}
# 各引擎发送前需要保持新鲜的导出目标：Codex 读 ~/.codex/skills 与 ~/.agents/skills，
# Claude Code 只读 ~/.claude/skills。
ENGINE_TARGETS = {'codex': ('codex', 'agents'), 'claude': ('claude',)}

_REPORT_KEYS = ('written', 'unchanged', 'recycled', 'conflicts', 'errors')


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


def _owned(previous, owner_root, target):
    # 旧版 marker 无 target 字段，只可能属于 codex 目标。
    return (previous.get('owner') == _OWNER and previous.get('root') == owner_root
            and previous.get('target', 'codex') == target)


def _render(source, text, shared_root=None):
    meta, body = parse(text, source=str(source))
    name, description = meta.get('name'), meta.get('description')
    if not isinstance(name, str) or not _NAME.fullmatch(name):
        raise ValueError('技能 name 必须是小写英文、数字或连字符（最多 64 字符）')
    if name.lower() in {'con', 'prn', 'aux', 'nul', *('com%d' % n for n in range(10)),
                       *('lpt%d' % n for n in range(10))}:
        raise ValueError('技能 name 为系统保留名称')
    if not isinstance(description, str) or not description.strip():
        raise ValueError('技能缺少 description')
    # 物化后工作目录改变：沿用注册器的三层引用解析，不依赖特定共享包。
    program = Path(shared_root).parent if shared_root else None
    def rewrite(match):
        original = match.group(0)
        entries = reference_targets(original)
        if not entries:
            return original
        entry = entries[0]
        relative = entry.get('path')
        if relative is None or relative.is_absolute():
            return original
        target = resolve_reference(source, relative, program=program)
        fragment = entry.get('fragment')
        link = target.as_posix() + ('#' + fragment if fragment else '')
        return original.replace(entry['raw'], link, 1)
    body = re.sub(r'\]\(\s*(?:<[^>]+>|[^)]+)\s*\)', rewrite, body)
    return name, '---\nname: %s\ndescription: %s\n---\n%s' % (
        json.dumps(name, ensure_ascii=False), json.dumps(description, ensure_ascii=False), body)


def _default_home(target):
    spec = TARGETS[target]
    base = os.environ.get(spec['env_home']) if spec['env_home'] else None
    root = Path(base) if base else Path.home() / spec['base']
    return root / 'skills'


def sync_agent_skills(program=None, target='codex', skill_home=None):
    """同步所有已登记阶段的 .skill.md 到指定 agent 目录；返回 written/unchanged/recycled/conflicts/errors。

    skill_home 是目标 skills 目录，缺省按 ``TARGETS`` 解析。仅回收本安装拥有且内容未被修改的孤儿目录。
    扫描或读取失败时不回收；同步器与发送前检查串行，调用方应在后台执行。
    """
    report = {key: [] for key in _REPORT_KEYS}
    with _LOCK:
        try:
            _sync(program, target, skill_home, report)
        except (OSError, ValueError, UnicodeError) as exc:
            report['errors'].append(str(exc))
    return report


def sync_all_agent_skills(program=None, homes=None, targets=None):
    """串行同步全部（或指定）目标；单目标异常不拖垮其他目标。"""
    homes = homes or {}
    reports = {}
    for target in (targets or tuple(TARGETS)):
        report = {key: [] for key in _REPORT_KEYS}
        try:
            report = sync_agent_skills(program=program, target=target,
                                       skill_home=homes.get(target))
        except Exception as exc:  # noqa: BLE001 - 单目标失败不拖垮其他目标
            import infra.app_logging as app_logging
            app_logging.swallowed('agent 技能同步 %s 失败' % target)
            report['errors'].append(str(exc))
        reports[target] = report
    return reports


def _sync(program, target, skill_home, report):
    registry = default_registry(program)
    root = registry.root.resolve()
    user_root = registry.user_root.resolve() if registry.user_root is not None else None
    # Do not treat an unavailable installation as an empty, authoritative inventory.
    if not root.is_dir():
        raise ValueError('程序 skills 目录不可用，未同步或清理')
    destination = Path(skill_home) if skill_home is not None else _default_home(target)
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
        resolved = source.resolve()
        if not _plain(source) or not (resolved.is_relative_to(root) or (
                user_root is not None and resolved.is_relative_to(user_root))):
            report['errors'].append(source.name + '：来源不在程序技能目录内')
            continue
        try:
            raw = source.read_bytes()
            name, rendered = _render(source, raw.decode('utf-8-sig'), root)
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
        target_file = directory / 'SKILL.md'
        previous = _metadata(directory)
        owned = _owned(previous, owner_root, target)
        if (not _plain(directory) or not _plain(target_file)
                or (directory.exists() and not owned)):
            report['conflicts'].append(name)
            continue
        existing = target_file.read_bytes() if target_file.exists() else None
        wanted = rendered.encode('utf-8')
        matches = existing is not None and existing.replace(b'\r\n', b'\n') == wanted
        if existing is not None and not matches and _hash(existing) != previous.get('output_hash'):
            report['conflicts'].append(name)
            continue
        metadata = {'owner': _OWNER, 'root': owner_root, 'target': target,
                    'source': str(source.resolve()),
                    'source_hash': _hash(raw), 'output_hash': _hash(existing or wanted)}
        if matches and metadata == previous:
            report['unchanged'].append(name)
            continue
        save_text(target_file, rendered)
        metadata['output_hash'] = _hash(target_file.read_bytes())
        save(directory / _MARKER, metadata)
        report['written'].append(name)
    if report['errors']:
        return
    for directory in destination.iterdir():
        previous = _metadata(directory)
        if (directory.name in seen or not _owned(previous, owner_root, target)):
            continue
        target_file = directory / 'SKILL.md'
        if (not _plain(target_file) or not target_file.is_file()
                or _hash(target_file.read_bytes()) != previous.get('output_hash')
                or {p.name for p in directory.iterdir()} != {'SKILL.md', _MARKER}):
            report['conflicts'].append(directory.name)
            continue
        if recycle_paths(destination, [directory], '应用 Agent 技能源文件已删除'):
            report['recycled'].append(directory.name)


def start_agent_skill_sync(program=None, before=None, targets=None):
    """首帧后启动独立后台维护；不占用桌面业务 worker、不访问 Tk。

    ``before`` 由上层注入（如旧版导入 SKILL 迁到 data/skills），在同一后台线程里先跑，
    保证同步看到的是迁移后的目录；它的异常不阻断同步。
    """
    def run(program=None, targets=None):
        try:
            before()
        except Exception:  # noqa: BLE001 - 维护前置步骤失败不能拖垮同步
            import infra.app_logging as app_logging
            app_logging.swallowed('Agent 技能同步前置维护失败')
        sync_all_agent_skills(program=program, targets=targets)

    worker = executors.submit('io',
                              functools.partial(run if callable(before) else _all_entry,
                                                program=program, targets=targets),
                              label='agent-skill-sync')
    return worker


def _all_entry(program=None, targets=None):
    sync_all_agent_skills(program=program, targets=targets)

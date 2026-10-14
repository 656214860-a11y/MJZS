# -*- coding: utf-8 -*-
"""总控 SKILL（原「统筹 SKILL」）：清单指纹、自动同步、体检与门禁（L4，无 Tk）。

唯一来源：``skills/00全流程SKILL/总控.json``（见 ``workflow_settings.MASTER_MANIFEST``）。

- **指纹**：总控清单、全流程包 SKILL.md、各阶段总控 SKILL 文件及其直接 Markdown 引用
  的内容摘要。只读这张固定文件表，不递归扫描目录（AGENTS 规则 33）。
- **自动同步**：项目处于总控模式且指纹变化时，逐阶段把「上次总控给的那几项」换成新清单：
  用户自己加的 SKILL 原样保留；用户已取消勾选的总控项不会被重新勾上；某阶段的旧总控项
  一个都没勾（用户已整体弃用总控建议）时，该阶段不追加新项。同步结果写入
  ``workflow.applied``，下次只在指纹再变时动作。
- **体检**：总控登记的 SKILL 不在注册表、按真实发送流程冻结失败（引用缺失／越界、
  正文为空、超上限）都列为问题，随同步结果提示用户。
- **门禁**（``gate``）：总控模式下，本阶段必填制作锁缺失或已勾选 SKILL 引用不可加载时，
  手动与自动路径一律阻断。剧本准备的简报采集仍由简报门禁负责（那一步正是在收集制作锁）。
"""
from __future__ import annotations

import hashlib
import os
import time
from pathlib import Path

import skill_registry
import stage_config
import workflow_settings

PROGRAM = Path(__file__).resolve().parent
LABEL = '总控'


def preset_for(project):
    """当前项目启用的总控预设；未启用返回 (名称空串, 空表)。"""
    workflow_settings.refresh_workflow_presets()
    name = str(stage_config.current_workflow(project).get('name') or '').strip() if project else ''
    return name, workflow_settings.WORKFLOW_PRESETS.get(name, {})


def _skill_path(registry, sid):
    item = registry.getById(sid) if registry is not None else None
    return Path(item.path) if item is not None and getattr(item, 'path', None) else None


def _reference_files(path):
    """一份 SKILL 的直接 Markdown 引用（与发送时内联的同一口径），只算路径不读正文。"""
    try:
        text = path.read_text(encoding='utf-8-sig')
    except (OSError, UnicodeError):
        return []
    out = []
    for entry in skill_registry.reference_targets(text):
        relative = entry.get('path')
        if entry.get('kind') == 'markdown' and relative is not None and not relative.is_absolute():
            out.append((path.parent / relative).resolve())
    return out


def watched_files(preset, registry=None, program=PROGRAM):
    """指纹覆盖的固定文件表：清单、全流程包入口、各阶段总控 SKILL 及其直接引用。"""
    registry = registry or skill_registry.default_registry()
    files = [workflow_settings.MASTER_MANIFEST, (Path(program) / preset.get('package', '')).resolve()]
    for stage in sorted(preset.get('stage_skills') or {}):
        for sid in preset['stage_skills'][stage]:
            path = _skill_path(registry, sid)
            if path is not None:
                files.append(path.resolve())
                files.extend(_reference_files(path))
    seen, ordered = set(), []
    for path in files:
        key = os.path.normcase(str(path))
        if key not in seen:
            seen.add(key)
            ordered.append(Path(path))
    return ordered


def fingerprint(preset, registry=None, program=PROGRAM):
    digest = hashlib.sha256()
    for path in watched_files(preset, registry, program):
        digest.update(os.path.normcase(str(path)).encode('utf-8') + b'\0')
        try:
            digest.update(path.read_bytes())
        except OSError:
            digest.update(b'<missing>')
        digest.update(b'\0')
    return digest.hexdigest()


def health(preset, registry=None, program=PROGRAM):
    """总控体检：返回问题列表（空＝通过）。"""
    registry = registry or skill_registry.default_registry()
    problems = list(workflow_settings.MASTER_MANIFEST_PROBLEMS)
    package = Path(program) / preset.get('package', '')
    if not package.is_file():
        problems.append('全流程包入口不存在：%s' % preset.get('package'))
    for stage, items in sorted((preset.get('stage_skills') or {}).items()):
        for sid in items:
            path = _skill_path(registry, sid)
            if path is None:
                problems.append('%s：总控登记的 SKILL「%s」不在注册表里' % (stage, sid))
                continue
            try:
                workflow_settings._inline_skill_report(path, strict=True)
            except (OSError, UnicodeError, ValueError) as exc:
                problems.append('%s：%s 无法按发送流程加载（%s）' % (stage, sid, exc))
    return problems


def _merge(current, old, new):
    """一个阶段的勾选合并：只替换旧总控项，保留用户自己的选择（见模块说明）。"""
    old, new = list(old or ()), list(new or ())
    following = not old or any(sid in current for sid in old)
    kept = [sid for sid in current if sid not in old or sid in new]
    if following:
        kept.extend(sid for sid in new if sid not in old and sid not in kept)
    return kept


def sync(project, registry=None, program=PROGRAM, now=None):
    """项目在总控模式下按指纹自动同步；返回 {'updated', 'stages', 'problems', 'message'}。"""
    name, preset = preset_for(project)
    if not preset:
        return {'updated': False, 'stages': [], 'problems': [], 'message': ''}
    registry = registry or skill_registry.default_registry()
    registry.scan()
    current_print = fingerprint(preset, registry, program)
    workflow = stage_config.current_workflow(project)
    applied = workflow.get('applied') if isinstance(workflow.get('applied'), dict) else {}
    if applied.get('fingerprint') == current_print and applied.get('name') == name:
        return {'updated': False, 'stages': [], 'problems': list(applied.get('problems') or ()), 'message': ''}
    # 首次登记以当前清单为基线：既有项目当初就是按同一份总控套用的。
    previous = applied.get('stage_skills') if applied.get('name') == name else None
    previous = previous if isinstance(previous, dict) else preset['stage_skills']
    changed = []
    for stage, new in preset['stage_skills'].items():
        old = previous.get(stage, [])
        if list(old) == list(new):
            continue
        current = list(stage_config.get(project, stage, registry).get('skills') or ())
        merged = _merge(current, old, new)
        if merged != current:
            stage_config.put(project, stage, skills=merged)
            changed.append(stage)
    problems = health(preset, registry, program)
    workflow = stage_config.current_workflow(project)
    workflow['applied'] = {'name': name, 'fingerprint': current_print,
                           'stage_skills': {stage: list(items) for stage, items in preset['stage_skills'].items()},
                           'problems': problems,
                           'at': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(now or time.time()))}
    stage_config.put_workflow(project, workflow)
    first = not applied
    parts = []
    if not first:
        parts.append('%s「%s」已更新' % (LABEL, name))
        if changed:
            from pet_bus import STAGE_NAMES
            parts.append('已同步 %d 个阶段：%s' % (len(changed), '、'.join(STAGE_NAMES.get(s, s) for s in changed)))
        else:
            parts.append('各阶段勾选无需调整，新内容在下次发送时生效')
    if problems:
        parts.append('体检发现 %d 个问题，相关阶段发送会被阻断：%s' % (len(problems), '；'.join(problems[:3])
                                                          + ('…' if len(problems) > 3 else '')))
    return {'updated': not first, 'stages': changed, 'problems': problems, 'message': '；'.join(parts)}


def gate(config, stage=None, check_references=True):
    """总控门禁；实现位于 workflow_settings.master_gate（低层发送入口直接调用，避免越层与循环依赖）。"""
    return workflow_settings.master_gate(config, stage, check_references)

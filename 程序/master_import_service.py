# -*- coding: utf-8 -*-
"""总控包导入：把客户本地的一套总控（清单＋全流程包）登记进内置总控清单（L4，无 Tk）。

总控清单的 ``stage_skills``／``locks`` 是受控登记，不能从外部包 frontmatter 推导
（总控宪法）；所以导入的最小单位是一个**自包含总控包目录**，里面必须有：

- 一份清单 ``总控.json``，形如 ``{version, presets: {名称: {package, stage_skills, locks}}}``；
  ``package`` 是该包内主控 ``SKILL.md`` 相对本目录的路径，``stage_skills`` 的值为注册表
  SKILL id，``locks`` 为 ``script_contract.PRODUCTION_LOCK_DEFINITIONS`` 的键。
- ``package`` 指向的主控 ``SKILL.md`` 及其相对引用（子引擎、references 等）。

导入把整个总控包目录复制到 ``skills/00全流程SKILL/<名称>/``，把 ``package`` 重写为复制后的
相对路径，再把 presets 合并进内置 ``skills/00全流程SKILL/总控.json``，最后按指纹刷新
``WORKFLOW_PRESETS``。同名旧总控先经回收服务移入程序回收站，可恢复。

流程沿用 ``skill_import_service`` 的「预检 → 暂存 → 换入 → 试冻结 → 登记」：
- 硬性拦截（不给“仍要导入”）：清单读不出、缺 presets、package 缺失、stage_skills 引用不存在的
  SKILL／锁键未登记、换入后按真实发送流程冻结失败。
- 软性问题（同名覆盖、stage_skills 引用外部包而非注册 id 等）仍交界面二次确认。
"""
from __future__ import annotations

import os
import shutil
import uuid
from pathlib import Path

import workflow_settings
from agent.core import save as save_json
from file_cache import read_json
from pet_bus import STAGES
from script_contract import PRODUCTION_LOCK_DEFINITIONS
from storage_maintenance import recycle_paths, restore_recycle_batch

STAGING_PREFIX = '.导入中-'
IGNORED_PARTS = ('.git', '__pycache__', '.DS_Store')


class ImportBlocked(ValueError):
    """导入被硬性拦截；消息可直接展示给用户。"""


def _preset_rows(manifest):
    """把清单里的 presets 规整成 {名称: {package, stage_skills, locks}}，返回 (行表, 问题)。"""
    problems = []
    data = manifest if isinstance(manifest, dict) else {}
    rows = data.get('presets')
    if not isinstance(rows, dict) or not rows:
        raise ImportBlocked('总控包清单缺少 presets')
    out = {}
    for name, row in rows.items():
        name = str(name).strip()
        if not name:
            problems.append('presets 里有空名称的条目，已跳过')
            continue
        if not isinstance(row, dict) or not str(row.get('package') or '').strip():
            raise ImportBlocked('总控「%s」缺少 package' % name)
        stages = row.get('stage_skills')
        if not isinstance(stages, dict):
            raise ImportBlocked('总控「%s」的 stage_skills 不是表' % name)
        out[name] = {
            'package': str(row['package']),
            'stage_skills': {str(stage): [str(sid) for sid in (items or ())]
                             for stage, items in stages.items()},
            'locks': [str(key) for key in (row.get('locks') or [])],
        }
    return out, problems


def plan_import(source, program=None, registry=None):
    """只读预检：读清单、核验 package／stage_skills／locks，返回导入计划。"""
    source = Path(source)
    program = Path(program or Path(__file__).resolve().parent)
    registry = registry or skill_registry.default_registry()
    try:
        data = read_json(source)
    except (OSError, UnicodeError, ValueError) as exc:
        raise ImportBlocked('读不出总控包清单（%s）' % exc) from exc
    if not isinstance(data, dict):
        raise ImportBlocked('总控包清单不是一份 JSON 对象')
    rows, problems = _preset_rows(data)

    definitions = {item['key'] for item in PRODUCTION_LOCK_DEFINITIONS}
    known_ids = {item.name for item in registry.getAll()}
    base = source.resolve().parent
    plan_rows = {}
    for name, row in rows.items():
        package = (base / row['package']).resolve()
        if not package.is_file():
            raise ImportBlocked('总控「%s」的 package 不存在：%s' % (name, row['package']))
        for stage, items in row['stage_skills'].items():
            if stage not in STAGES:
                problems.append('总控「%s」登记了未识别的阶段「%s」，导入后不会被同步' % (name, stage))
            for sid in items:
                if sid not in known_ids:
                    problems.append('总控「%s」的 SKILL「%s」不在注册表里，发送时会被门禁阻断' % (name, sid))
        unknown_locks = [key for key in row['locks'] if key not in definitions]
        if unknown_locks:
            problems.append('总控「%s」有未登记的制作锁：%s' % (name, '、'.join(unknown_locks)))
        plan_rows[name] = dict(row, package=package)

    existing = workflow_settings.refresh_workflow_presets()
    for name in plan_rows:
        if name in existing:
            problems.append('总控「%s」已存在，继续将覆盖（旧版移入程序回收站，可恢复）' % name)
    return {'source': source, 'base': base, 'rows': plan_rows, 'problems': problems}


def _batch_of(root, records):
    """由回收记录反推批次目录：recycle_path＝批次/原相对路径，去掉原路径的层数即批次。"""
    item = records[0]
    full = Path(root) / str(item['recycle_path'])
    return full.parents[len(Path(str(item['source'])).parts) - 1]


def perform_import(plan, program=None, now=None):
    """暂存 → 换入 → 试冻结 → 合并清单；任一步失败都回到导入前状态并抛出。"""
    program = Path(program or Path(__file__).resolve().parent)
    target_root = workflow_settings.MASTER_MANIFEST.parent
    target_root.mkdir(parents=True, exist_ok=True)
    staging = target_root / (STAGING_PREFIX + uuid.uuid4().hex[:8])
    staging.mkdir()
    # (回收批次, 换入的最终目录, 换入前的旧目录是否已回收) 用于失败时恢复旧版。
    replaced = []
    try:
        # 先把每个总控包的目录复制进暂存区，确认主控 SKILL.md 能按真实发送流程冻结。
        prepared = {}
        for name, row in plan['rows'].items():
            pkg_root = row['package'].parent
            # 包根：取 package 所在目录（自包含总控包可能把主控放在子目录里，整目录复制）。
            staged = staging / name
            shutil.copytree(pkg_root, staged, ignore=shutil.ignore_patterns(*IGNORED_PARTS))
            rel_package = row['package'].relative_to(pkg_root)
            entry_skill = staged / rel_package
            workflow_settings._inline_skill_report(entry_skill, strict=True)
            prepared[name] = (staged, rel_package.as_posix())

        # 换入：同名旧总控先回收，再原子换入新目录。
        final_paths = {}
        for name, (staged, rel_package) in prepared.items():
            final = target_root / name
            batch = None
            if final.exists():
                records = recycle_paths(program, [final], '导入总控包替换旧版：' + name, now=now)
                if not records:
                    raise ImportBlocked('旧总控「%s」未能移入回收站，已取消导入。' % name)
                batch = _batch_of(program, records)
                replaced.append((batch, final))
            os.replace(staged, final)
            final_paths[name] = (final, rel_package)

        # 合并清单：package 重写为复制后的相对路径，presets 合并进内置 总控.json。
        manifest = workflow_settings.MASTER_MANIFEST
        data = read_json(manifest) if manifest.is_file() else {}
        if not isinstance(data, dict):
            data = {}
        presets = dict(data.get('presets')) if isinstance(data.get('presets'), dict) else {}
        for name, (final, rel_package) in final_paths.items():
            row = dict(plan['rows'][name])
            row['package'] = 'skills/00全流程SKILL/%s/%s' % (name, rel_package)
            presets[name] = {
                'package': row['package'],
                'stage_skills': row['stage_skills'],
                'locks': row['locks'],
            }
        data['presets'] = presets
        data.setdefault('version', data.get('version', 1))
        save_json(manifest, data)
        workflow_settings.refresh_workflow_presets(force=True)
        return {'names': list(final_paths), 'manifest': manifest,
                'replaced': [final for _batch, final in replaced]}
    except Exception:
        # 换入失败时把已换入的新目录移除并恢复旧版；清单合并在换入之后才写，失败时清单未动。
        for batch, final in replaced:
            if final.exists():
                recycle_paths(program, [final], '导入总控包失败回收新版：' + final.name, now=now)
            restore_recycle_batch(program, batch)
        raise
    finally:
        if staging.exists():
            recycle_paths(program, [staging], '导入总控包暂存区收尾', now=now)

# -*- coding: utf-8 -*-
"""阶段配置「新增 SKILL」的稳定导入（L3，无 Tk）。

旧做法只把选中的那一个文件 ``copy2`` 进阶段目录：外部包的 references／assets／scripts
全部丢失，同名清单在扫描时被静默丢弃，覆盖不留旧版，引用断链要等到发送时才报。

本模块把一次导入拆成「预检 → 暂存 → 换入 → 试冻结 → 登记」：

- 选中 ``SKILL.md`` 视为外部包，整个包目录一并导入（跳过 ``.git``／``__pycache__``）；
  选中 ``*.skill.md`` 视为单文件清单。
- 硬性拦截（不给"仍要导入"）：读不出、重名、换入后按真实发送流程冻结失败
  （正文为空、引用缺失、引用越界、超过内联上限）。
- 软性问题（字段缺失、声明阶段不一致、目标已存在）仍交给界面二次确认。
- 目标已存在时旧版先经 ``storage_maintenance.recycle_paths`` 移入程序回收站，可恢复；
  试冻结失败则把新版撤回暂存区并恢复旧版，阶段目录回到导入前的样子。
- 暂存目录以 ``.`` 开头，注册表不会在换入前把它当成 SKILL 扫进来；用完同样经回收服务收走。
- 每次成功导入写一行导入台账（来源、内容摘要、时间），供以后检测来源是否更新。
"""
from __future__ import annotations

import hashlib
import os
import shutil
import time
import uuid
from pathlib import Path

import skill_registry
from agent.core import save
from pet_bus import read_json
from storage_maintenance import recycle_paths, restore_recycle_batch

LEDGER_NAME = '导入台账.json'
STAGING_PREFIX = '.导入中-'
IGNORED_PARTS = ('.git', '__pycache__', '.DS_Store')


class ImportBlocked(ValueError):
    """导入被硬性拦截；消息可直接展示给用户。"""


def _kind(source):
    return 'package' if Path(source).name.casefold() == skill_registry.PACKAGE_SKILL_FILENAME.casefold() else 'manifest'


def _tree_digest(path):
    """单文件取内容摘要；包取「相对路径＋内容」的整体摘要，顺序稳定。"""
    path = Path(path)
    digest = hashlib.sha256()
    files = [path] if path.is_file() else sorted(
        (item for item in path.rglob('*') if item.is_file()
         and not (set(item.relative_to(path).parts) & set(IGNORED_PARTS))),
        key=lambda item: item.relative_to(path).as_posix())
    for item in files:
        if path.is_dir():
            digest.update(item.relative_to(path).as_posix().encode('utf-8') + b'\0')
        digest.update(item.read_bytes())
    return digest.hexdigest()


def plan_import(source, target_dir, stage, registry):
    """只读预检：返回导入计划；读不出或重名直接抛 ImportBlocked。"""
    source = Path(source)
    if target_dir is None:
        raise ImportBlocked('未找到本阶段注册目录')
    target_dir = Path(target_dir)
    kind = _kind(source)
    target = (target_dir / source.parent.name / skill_registry.PACKAGE_SKILL_FILENAME
              if kind == 'package' else target_dir / source.name)
    try:
        raw = source.read_text(encoding='utf-8-sig')
    except (OSError, UnicodeError) as exc:
        raise ImportBlocked('读不出源文件（%s）' % exc) from exc
    meta, body = skill_registry.parse(raw, source=str(source))
    problems = []
    if kind == 'package':
        # 外部包由注册表补默认元数据，只检查可显示名称。
        if not (str(meta.get('displayName') or '').strip() or skill_registry.markdown_heading(body)):
            problems.append('未找到可显示的技能名称')
        name = skill_registry.imported_package_meta(meta, body, target.parent, target)['name']
    else:
        skill = skill_registry.Skill(meta, body, path=source)
        known = {item.name for item in registry.getAll()}
        problems.extend(skill_registry.validate_skill(skill, known=known))
        name = skill.name
    declared = skill_registry.stage_id(meta.get('stage', ''))
    if declared and declared != stage:
        problems.append('frontmatter 声明阶段「%s」与本阶段不一致' % declared)
    replaced = Path(os.path.normcase(str(target.resolve())))
    for item in registry.getAll():
        other = getattr(item, 'path', None)
        if not name or item.name != name or other is None:
            continue
        if Path(os.path.normcase(str(Path(other).resolve()))) == replaced:
            continue                     # 重新导入同一位置＝更新，不算重名
        raise ImportBlocked('与已有 SKILL「%s」重名（%s）；同名 SKILL 扫描时会被丢弃。'
                            '请先改名或删除旧的那份再导入。' % (name, other))
    if target.exists():
        problems.append('目标 %s 已存在，继续将覆盖（旧版移入程序回收站，可恢复）' % target.name)
    return {'source': source, 'kind': kind, 'target': target, 'target_dir': target_dir,
            'name': name, 'problems': problems}


def _verify(target):
    """按真实发送流程冻结一次：正文为空、引用缺失／越界、超出上限都在此暴露。"""
    import workflow_settings
    try:
        workflow_settings._inline_skill_report(target, strict=True)
    except (OSError, UnicodeError, ValueError) as exc:
        raise ImportBlocked('导入后试冻结失败，已撤回：%s' % exc) from exc


def _ledger_path(program):
    return Path(program) / 'skills' / LEDGER_NAME


def record(program, plan, digest, now=None):
    """导入台账：按目标相对路径记一行，同一目标再次导入时覆盖该行。"""
    path = _ledger_path(program)
    data = read_json(path) if path.is_file() else {}
    data = data if isinstance(data, dict) else {}
    items = data.get('items') if isinstance(data.get('items'), dict) else {}
    target = plan['target'].parent if plan['kind'] == 'package' else plan['target']
    try:
        key = target.resolve().relative_to((Path(program) / 'skills').resolve()).as_posix()
    except ValueError:
        key = str(target)
    items[key] = {'source': str(plan['source'].parent if plan['kind'] == 'package' else plan['source']),
                  'kind': plan['kind'], 'name': plan['name'], 'sha256': digest,
                  'imported_at': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(now or time.time()))}
    save(path, {'version': 1, 'items': items})
    return path


def perform_import(plan, program, now=None):
    """暂存 → 换入 → 试冻结 → 登记；任一步失败都回到导入前状态并抛出。"""
    program = Path(program)
    target_dir = plan['target_dir']
    target_dir.mkdir(parents=True, exist_ok=True)
    staging = target_dir / (STAGING_PREFIX + uuid.uuid4().hex[:8])
    staging.mkdir()
    package = plan['kind'] == 'package'
    final = plan['target'].parent if package else plan['target']
    staged = staging / final.name
    batch = None
    try:
        if package:
            shutil.copytree(plan['source'].parent, staged, ignore=shutil.ignore_patterns(*IGNORED_PARTS))
        else:
            shutil.copy2(plan['source'], staged)
        digest = _tree_digest(staged)
        if final.exists():
            records = recycle_paths(program, [final], '新增 SKILL 替换旧版：' + final.name, now=now)
            if not records:
                raise ImportBlocked('旧版 %s 未能移入回收站，已取消导入，原文件未改动。' % final.name)
            batch = _batch_of(program, records)
        os.replace(staged, final)
        try:
            _verify(plan['target'])
        except ImportBlocked:
            os.replace(final, staged)
            if batch is not None:
                restore_recycle_batch(program, batch)
            raise
        ledger = record(program, plan, digest, now=now)
        return {'target': plan['target'], 'digest': digest, 'ledger': ledger, 'replaced_batch': batch}
    finally:
        # 暂存区（含撤回的新版）只移走、不永久删除。
        if staging.exists():
            recycle_paths(program, [staging], '新增 SKILL 暂存区收尾', now=now)


def _batch_of(root, records):
    """由回收记录反推批次目录：recycle_path＝批次/原相对路径，去掉原路径的层数即批次。"""
    item = records[0]
    full = Path(root) / str(item['recycle_path'])
    return full.parents[len(Path(str(item['source'])).parts) - 1]

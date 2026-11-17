"""SKILL 生命周期操作（R3091／生命周期任务书 T8）：定位／重命名／启停用／删除入口。

从 ``skill_import_service`` 拆出（模块行数棘轮）：定位、改名、启停用与删除收尾
是导入之后的存续操作，与导入／更新检测分属两组调用方。台账与回收站等底层
助手仍在 ``skill_import_service``，本模块按 ``skill_archive`` 同口径引用其
公开与私有成员；``ImportBlocked`` 异常类不变，既有 ``except`` 兼容。
"""
import re
from pathlib import Path

import skill_import_service
import skill_project_layer
import skill_registry
from agent.core import save, save_text
from contract.pet_bus import read_json
from stage_layout import skill_config_path
from storage_maintenance import recycle_paths

# ── 生命周期操作（T8）：定位／重命名／启停用 ──

_NAME_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$')


def _entry_kind(path):
    """入口文件 → ``manifest``（``*.skill.md``）或 ``package``（包根 ``SKILL.md``）。"""
    return ('package' if Path(path).name.casefold() in
            {name.casefold() for name in skill_import_service._PACKAGE_ENTRY_NAMES}
            else 'manifest')


def _find_disabled_file(registry, name):
    """已禁用 SKILL 的文件兜底定位：清单按文件名干、包按入口名解析。"""
    suffix = skill_registry.SKILL_SUFFIX
    package_names = {item.casefold()
                     for item in skill_import_service._PACKAGE_ENTRY_NAMES}
    for path in registry.files():
        try:
            if path.name == name + suffix:
                return path
            if path.name.casefold() in package_names:
                meta, body = skill_registry.parse(
                    path.read_text(encoding='utf-8-sig'), source=str(path))
                meta = skill_registry.imported_package_meta(meta, body, path.parent, path)
                if str(meta.get('name') or '') == name:
                    return path
        except (OSError, UnicodeError, ValueError):
            continue
    return None


def find_skill_entry(program, registry, name):
    """按注册名定位 SKILL → ``{name,path,kind,layer,project,disabled}``；找不到返回 ``None``。

    ``getAll()`` 只含启用项；已禁用条目先查禁用登记里存的 ``path``，缺失时按文件名兜底，
    供重命名／编辑器打开／启停用／删除共用同一定位口径。用户操作入口先强制刷新，
    不吃 ``FRESH_TTL`` 热窗口里的旧视图。
    """
    name = str(name or '').strip()
    if not name:
        return None
    registry.scan(force=True)
    skill = registry.getById(name)
    if skill is not None and getattr(skill, 'path', None) is not None:
        layer = str(getattr(skill, 'layer', '') or '')
        return {'name': skill.name, 'path': Path(skill.path), 'kind': _entry_kind(skill.path),
                'layer': layer,
                'project': (str(getattr(registry, 'project_root', '') or '')
                            if layer == 'project' else ''),
                'disabled': False}
    for entry in registry.disabled_entries():
        if str(entry.get('name') or '') != name:
            continue
        stored = str(entry.get('path') or '')
        path = Path(stored) if stored else None
        if path is None or not path.is_file():
            path = _find_disabled_file(registry, name)
        if path is None:
            continue
        return {'name': name, 'path': path, 'kind': _entry_kind(path),
                'layer': str(entry.get('layer') or ''),
                'project': str(entry.get('project') or ''), 'disabled': True}
    return None


def set_skill_disabled(program, registry, name, disabled=True):
    """启停用：登记进 ``data/skills/disabled_skills.json``，文件保留、``getAll()`` 滤除。"""
    program = Path(program)
    entry = find_skill_entry(program, registry, name)
    if entry is None:
        raise skill_import_service.ImportBlocked('注册表中没有 SKILL「%s」' % name)
    if entry['layer'] == 'builtin':
        raise skill_import_service.ImportBlocked('内置 SKILL 只读，不能禁用')
    return skill_project_layer.set_disabled(
        skill_registry.default_user_root(program), entry['layer'], entry['name'],
        project=entry['project'] if entry['layer'] == 'project' else '',
        disabled=disabled, path=entry['path'])


def _rewrite_frontmatter_name(text, new_name):
    """改 frontmatter ``name:``；无 frontmatter 或无 name 行返回 ``None``（包可由目录名派生）。"""
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != '---':
        return None
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == '---'), None)
    if end is None:
        return None
    for i in range(1, end):
        if re.match(r'^name\s*:', lines[i]):
            eol = '\r\n' if '\r\n' in lines[i] else '\n'
            lines[i] = 'name: %s' % new_name + eol
            return ''.join(lines)
    return None


def _iter_project_roots(program, extra=''):
    """项目根枚举：``projects.json`` 登记项＋调用方补充项（去重、保持登记顺序）。"""
    roots, seen = [], set()
    info = read_json(Path(program) / 'projects.json')
    info = info if isinstance(info, dict) else {}
    candidates = [record.get('path') for record in info.get('projects') or ()
                  if isinstance(record, dict)]
    if extra:
        candidates.append(extra)
    for value in candidates:
        if not value:
            continue
        root = Path(value)
        try:
            key = str(root.resolve())
        except OSError:
            key = str(root)
        if key not in seen:
            seen.add(key)
            roots.append(root)
    return roots


def _project_ref_counts(program, old, extra=''):
    """只读预检：统计引用旧名的项目配置 → ``{项目路径: 命中阶段数}``。"""
    hits = {}
    for root in _iter_project_roots(program, extra):
        cfg = skill_config_path(root)
        if not cfg.is_file():
            continue
        data = read_json(cfg)
        if not isinstance(data, dict):
            continue
        count = sum(1 for entry in data.values()
                    if isinstance(entry, dict)
                    and isinstance(entry.get('skills'), (list, tuple))
                    and any(str(value) == old for value in entry['skills']))
        if count:
            hits[str(root)] = count
    return hits


def _migrate_project_refs(program, old, new, extra=''):
    """把所有项目 ``skill_config.json`` 里的旧名改写成新名；返回受影响项目路径列表。"""
    affected = []
    for root in _iter_project_roots(program, extra):
        cfg = skill_config_path(root)
        if not cfg.is_file():
            continue
        data = read_json(cfg)
        if not isinstance(data, dict):
            continue
        changed = False
        for entry in data.values():
            if not isinstance(entry, dict) or not isinstance(entry.get('skills'), list):
                continue
            mapped = [new if str(value) == old else value for value in entry['skills']]
            if mapped == entry['skills']:
                continue
            dedup = []
            for value in mapped:
                if value not in dedup:
                    dedup.append(value)
            entry['skills'] = dedup
            changed = True
        if changed:
            save(cfg, data)
            affected.append(str(root))
    return affected


def _ledger_key_for(program, target):
    """已安装目标 → 台账键：与 ``record()`` 同一口径（层根内相对路径，其余绝对路径）。"""
    target = Path(target).resolve()
    for root in (skill_registry.default_user_root(program), skill_registry.default_root(program)):
        root = root.resolve()
        if target.is_relative_to(root):
            return target.relative_to(root).as_posix()
    return str(target)


def _rename_ledger_targets(program, plan):
    """台账行随安装目标改名：按旧目标解析重定键，刷新 ``name`` 与 ``sha256``。"""
    program = Path(program)
    items = skill_import_service._read_items(skill_import_service.ledger_path(program))
    if not items:
        return 0
    old_target = Path(plan['target_old']).resolve()
    # 改名后旧目标已进回收站，``_resolve_ledger_target`` 按存在性解析会落空；
    # 台账键本身是稳定标识，先按 ``_ledger_key_for`` 同口径直配，再退解析兜底。
    old_key = _ledger_key_for(program, plan['target_old'])
    moved = 0
    for key in list(items):
        row = items.get(key)
        if not isinstance(row, dict):
            continue
        resolved = skill_import_service._resolve_ledger_target(program, key)
        if (str(key) != old_key
                and (resolved is None or Path(resolved).resolve() != old_target)):
            continue
        items.pop(key)
        row['name'] = plan['new']
        try:
            row['sha256'] = skill_import_service._tree_digest(plan['target_new'])
        except OSError:
            pass
        items[_ledger_key_for(program, plan['target_new'])] = row
        moved += 1
    if moved:
        save(skill_import_service.ledger_path(program), {'version': 1, 'items': items})
    return moved


def rename_plan(program, registry, name, new_name, project=None):
    """重命名预检（只读）：解析目标、校验新名、统计受影响项目 → 计划 dict。"""
    program = Path(program)
    old = str(name or '').strip()
    new = str(new_name or '').strip()
    if not old or not new:
        raise skill_import_service.ImportBlocked('SKILL 名称不能为空')
    if old == new:
        raise skill_import_service.ImportBlocked('新旧名称相同，无需改名')
    if not _NAME_RE.match(new):
        raise skill_import_service.ImportBlocked('新名称只允许字母、数字与 . _ -，且以字母或数字开头')
    entry = find_skill_entry(program, registry, old)
    if entry is None:
        raise skill_import_service.ImportBlocked('注册表中没有 SKILL「%s」' % old)
    if registry.getById(new) is not None:
        raise skill_import_service.ImportBlocked('已存在 SKILL「%s」，请换一个名字' % new)
    if entry['kind'] == 'manifest':
        target_old = entry['path']
        target_new = entry['path'].with_name(new + skill_registry.SKILL_SUFFIX)
    else:
        target_old = entry['path'].parent
        target_new = target_old.with_name(new)
    if target_new.exists():
        raise skill_import_service.ImportBlocked('目标位置已存在：%s' % target_new.name)
    extra = project or entry.get('project') or ''
    affected = _project_ref_counts(program, old, extra=extra)
    return {'old': old, 'new': new, 'kind': entry['kind'], 'entry_path': entry['path'],
            'target_old': target_old, 'target_new': target_new,
            'layer': entry['layer'], 'project': entry.get('project') or '',
            'disabled': bool(entry.get('disabled')),
            'affected_projects': affected, 'affected_count': len(affected)}


def apply_rename(program, plan):
    """执行重命名计划：先落盘改名，再迁项目引用、台账与禁用登记；返回摘要。

    清单＝写新文件再回收旧文件；包＝改入口 ``name`` 字段（无字段由目录名派生）后整目录改名。
    同步标记由下一次 agent 技能同步按注册表自动重算（改名后旧名目录按孤儿回收）。
    """
    program = Path(program)
    old_path, new_path = Path(plan['target_old']), Path(plan['target_new'])
    if plan['kind'] == 'manifest':
        text = old_path.read_text(encoding='utf-8-sig')
        rewritten = _rewrite_frontmatter_name(text, plan['new'])
        if rewritten is None:
            raise skill_import_service.ImportBlocked('清单缺少 frontmatter name，无法安全改名')
        save_text(new_path, rewritten)
        records = recycle_paths(program, [old_path],
                                '重命名 SKILL：%s → %s' % (plan['old'], plan['new']))
        if not records:
            raise skill_import_service.ImportBlocked('旧文件 %s 未能移入回收站；新文件已写入，请人工处理'
                                                     % old_path.name)
    else:
        entry_path = Path(plan['entry_path'])
        text = entry_path.read_text(encoding='utf-8-sig')
        rewritten = _rewrite_frontmatter_name(text, plan['new'])
        if rewritten is not None:
            save_text(entry_path, rewritten)
        new_path.parent.mkdir(parents=True, exist_ok=True)
        old_path.rename(new_path)
    affected = _migrate_project_refs(program, plan['old'], plan['new'],
                                     extra=plan.get('project') or '')
    moved = _rename_ledger_targets(program, plan)
    skill_project_layer.rename_disabled(
        skill_registry.default_user_root(program), plan['old'], plan['new'],
        layer=plan.get('layer') or '', project=plan.get('project') or '',
        new_path=plan['target_new'])
    return {'old': plan['old'], 'new': plan['new'], 'kind': plan['kind'],
            'target': str(new_path), 'affected_projects': affected,
            'ledger_rows': moved, 'affected_count': len(affected)}


def uninstall_skill_entry(program, registry, name):
    """删除入口：启用项走 ``uninstall_skill``；已禁用项按登记路径回收并摘禁用登记。"""
    program = Path(program)
    entry = find_skill_entry(program, registry, name)
    if entry is None:
        raise skill_import_service.ImportBlocked('注册表中没有 SKILL「%s」' % name)
    if not entry['disabled']:
        return skill_import_service.uninstall_skill(program, registry, name)
    if entry['layer'] == 'builtin':
        raise skill_import_service.ImportBlocked('内置 SKILL 只读，不能删除')
    path = Path(entry['path'])
    roots = list(skill_registry.skill_roots(program))
    project_skills = getattr(registry, 'project_skills', None)
    if isinstance(project_skills, (str, Path)):
        roots.append(Path(project_skills).resolve())
    target = path.parent if entry['kind'] == 'package' else path
    if (not target.exists()
            or not any(target.resolve().is_relative_to(root) for root in roots)):
        raise skill_import_service.ImportBlocked('SKILL「%s」不在可卸载目录' % name)
    records = recycle_paths(program, [target], '删除已禁用 SKILL：' + name)
    if not records:
        raise skill_import_service.ImportBlocked('SKILL「%s」未能移入回收站' % name)
    skill_import_service.forget_ledger_targets(program, [target])
    skill_project_layer.set_disabled(
        skill_registry.default_user_root(program), entry['layer'], name,
        project=entry['project'] if entry['layer'] == 'project' else '',
        disabled=False)
    return {'name': name, 'target': str(target), 'disabled': True}

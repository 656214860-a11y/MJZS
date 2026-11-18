"""Script-Skill registry reports.

This is an orchestration/reporting concern, kept outside ``script_contract``
so core script facts remain usable without loading the stage Skill registry.
"""
from pathlib import Path

from contract.script_contract import AUDIT, CATEGORIES, MERGED, MERGE_LANDING, MERGE_OWNER, MERGE_PART, PRODUCER_SKILLS, SCRIPT_SKILL_STAGES, STAGE, program_root


def unlisted_skills(program=None):
    """剧本阶段有 SKILL、审计表里却没有它的（正常是空的）。"""
    known = {skill for skill, _category, _owner, _reason in AUDIT}
    return tuple(row['skill'] for row in manifest_rows(program) if row['skill'] not in known)


def support_rows(program=None):
    """任务 3 的收口表：那两个重叠／支撑的 SKILL 现在挂在哪、产物并到哪里去。"""
    rows = []
    for row in audit_rows(program):
        landing = MERGE_LANDING.get(row['skill'])
        if landing is None:
            continue
        merged = dict(row)
        merged['owner'] = MERGE_OWNER
        merged['part'] = MERGE_PART[row['skill']]
        merged['landing'] = landing
        rows.append(merged)
    return tuple(rows)


def manifest_rows(program=None):
    """Return the live script-Skill registry as report rows."""
    from orchestrator.skill_registry import default_registry
    root = program_root(program)
    registry = default_registry(str(root))
    rows = []
    for stage in SCRIPT_SKILL_STAGES:
        for skill in registry.getByStage(stage):
            # ``pipeline-*`` 是阶段执行编排入口，不是本报告审计的剧本内容
            # SKILL；它们仍由阶段配置展示和执行，但不应污染内容产物审计。
            if skill.name.startswith('pipeline-'):
                continue
            path = Path(skill.path) if skill.path else Path('')
            try:
                shown = path.relative_to(root).as_posix()
            except ValueError:
                shown = path.as_posix()
            rows.append({'skill': skill.name, 'display': skill.displayName, 'path': shown,
                         'input': tuple(skill.input), 'output': tuple(skill.output),
                         'format': 'JSON' if skill.name in PRODUCER_SKILLS else 'Markdown（人读）'})
    return tuple(sorted(rows, key=lambda row: row['skill']))


def audit_rows(program=None):
    """Return the classification and migration report for every script Skill."""
    known = {row['skill']: dict(row) for row in manifest_rows(program)}
    out = []
    for skill, category, owner, reason in AUDIT:
        # 审计只描述当前注册表实际加载到的入口。外部包目录未随项目分发时，不能
        # 生成空路径的“幽灵 SKILL”并让面板或验收误认为它可用。
        row = known.get(skill)
        if row is None:
            continue
        row['category'] = category
        row['action'] = CATEGORIES.get(category, '')
        row['owner'] = owner
        row['reason'] = reason
        out.append(row)
    return tuple(out)


def merge_problems(program=None):
    """验证合并后的 SKILL 归属；这是报告层，不让 L0 契约层依赖注册表。"""
    root = program_root(program)
    from orchestrator.skill_registry import default_registry
    owner_skill = default_registry(root).getById(MERGE_OWNER)
    if owner_skill is None:
        return ('归属者的 SKILL 文件读不到：%s' % MERGE_OWNER,)
    owner = owner_skill.path
    try:
        text = owner.read_text(encoding='utf-8-sig')
    except OSError:
        return ('归属者的 SKILL 文件读不到：%s' % MERGE_OWNER,)
    out = []
    for skill, part, landing in MERGED:
        if skill not in text:
            out.append('%s 没在归属者 %s 的说明里写出子步骤' % (skill, MERGE_OWNER))
        if part not in text:
            out.append('%s 没写清并回的是哪一段（%s）' % (skill, part))
        if landing.startswith('docs/'):
            import contract.stage_layout as stage_layout
            row = stage_layout.stage_dir(STAGE)
            stage_name = row[0] if row else STAGE
            names = tuple(item[0] for item in stage_layout.DOCS.get(stage_name, ()))
            if landing.split('/', 1)[1] not in names:
                out.append('%s 落到 %s，但 %s/docs 的清单里没有它' % (skill, landing, stage_name))
    return tuple(out)

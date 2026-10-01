"""统筹模式迁移工具：默认生成只读报告，--apply 才写入项目 skill_config.json。"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import stage_config
import workflow_settings


def registered_projects(program):
    """读取唯一项目登记表；活动项目即使登记项异常也按独立候选返回。"""
    try:
        raw = json.loads((Path(program) / 'projects.json').read_text(encoding='utf-8-sig'))
    except (OSError, ValueError):
        return ()
    raw = raw if isinstance(raw, dict) else {}
    values = [item.get('path') for item in raw.get('projects', ()) if isinstance(item, dict)]
    values.append(raw.get('active'))
    return tuple(sorted({Path(value) for value in values if str(value or '').strip()}))


def project_dirs(roots):
    """只把含任一既有配置文件的目录视为项目，避免猜测用户目录。"""
    found = set()
    for root in roots:
        root = Path(root)
        if not root.exists():
            continue
        for name in ('skill_config.json', '工作流任务/工作流调用设置.json'):
            for item in root.rglob(name):
                found.add(item.parent if item.name == 'skill_config.json' else item.parent.parent)
    return sorted(found)


def legacy_skills(project):
    settings = project / '工作流任务' / '工作流调用设置.json'
    try:
        raw = json.loads(settings.read_text(encoding='utf-8-sig'))
    except (OSError, ValueError):
        return set()
    result = set()
    for flow in (raw.get('flows') or {}).values():
        for profile in (flow.get('profiles') or {}).values():
            values = profile.get('skills', profile.get('skill', ()))
            if isinstance(values, str):
                values = (values,)
            result.update(str(value) for value in values or ())
    return result


def legacy_skill_ids(project, registry=None):
    """把旧工作流保存的路径/注册 id 归一为当前注册表 id，旧值仍只读。"""
    registry = registry or __import__('skill_registry').default_registry()
    by_path = {str(item.path.resolve()): item.name for item in registry.getAll() if item.path}
    result = set()
    for value in legacy_skills(project):
        raw = str(value).strip()
        if registry.getById(raw):
            result.add(registry.canonical_id(raw))
            continue
        try:
            canonical = str(Path(raw).resolve())
        except OSError:
            canonical = ''
        if canonical in by_path:
            result.add(by_path[canonical])
    return result


def candidate(project):
    old = legacy_skill_ids(project)
    best_name, best_hits = '', 0
    for name, preset in workflow_settings.WORKFLOW_PRESETS.items():
        ids = {item for values in preset.get('stage_skills', {}).values() for item in values}
        hits = len(old & ids)
        if hits > best_hits:
            best_name, best_hits = name, hits
    return best_name, best_hits, len(old)


def report_row(project):
    name, hits, total = candidate(project)
    preset = workflow_settings.WORKFLOW_PRESETS.get(name, {})
    diffs = stage_config.workflow_differences(project, preset) if name else {}
    locks = stage_config.workflow_lock(project)
    missing = [row['label'] for row in preset.get('locks', ()) if not locks.get(row['key'])]
    return {'project': str(project), 'candidate': name or '无（零覆盖）',
            'coverage': '%d/%d' % (hits, total), 'differences': diffs,
            'missing_locks': missing}


def markdown_report(rows):
    """稳定、可人工确认的干跑报告；不含任何项目正文或凭据。"""
    lines = ['# 统筹迁移干跑报告', '', '本报告只读；未写入任何项目。', '']
    for row in rows:
        lines.extend(['## ' + row['project'], '', '- 推断统筹候选：`%s`' % row['candidate'],
                      '- 旧清单覆盖：`%s`' % row['coverage'],
                      '- 锁值缺项：' + ('、'.join(row['missing_locks']) or '无')])
        differences = row['differences'] or {}
        if differences:
            lines.append('- 阶段勾选与展开表差异：')
            for stage, values in differences.items():
                lines.append('  - `%s`：当前 `%s`；建议 `%s`' %
                             (stage, ', '.join(values['current']) or '空',
                              ', '.join(values['suggested']) or '空'))
        else:
            lines.append('- 阶段勾选与展开表差异：无候选或无登记阶段。')
        lines.append('')
    return '\n'.join(lines) + '\n'


def apply(project):
    name, hits, _total = candidate(project)
    if not name or not hits:
        return False
    preset = workflow_settings.WORKFLOW_PRESETS[name]
    old = stage_config.current_workflow(project)
    workflow = dict(old)
    workflow.update({'name': name, 'skill_ref': preset['package'], 'lock': dict(old.get('lock') or {})})
    before = stage_config._workflow_data(project)
    stage_config.apply_workflow_empty_stages(project, workflow, preset)
    return before != stage_config._workflow_data(project)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true', help='只输出报告（默认行为）')
    parser.add_argument('--apply', action='store_true', help='确认报告后才执行回写')
    parser.add_argument('--root', action='append', default=[], help='额外扫描根目录，可重复')
    parser.add_argument('--report', help='干跑 Markdown 报告目标（默认写入维护记录）')
    args = parser.parse_args(argv)
    program = Path(__file__).resolve().parents[1]
    projects = set(registered_projects(program))
    for root in args.root:
        projects.update(project_dirs((root,)))
    rows = [report_row(project) for project in sorted(projects)]
    if not args.apply:
        target = Path(args.report) if args.report else (
            program / '维护记录' / ('统筹迁移干跑_' + __import__('datetime').date.today().strftime('%Y%m%d') + '.md'))
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(markdown_report(rows), encoding='utf-8')
        print(str(target))
        return 0
    print(json.dumps({'mode': 'apply', 'projects': rows}, ensure_ascii=False, indent=2))
    if args.apply:
        changed = sum(1 for row in rows if apply(Path(row['project'])))
        print('changed=%d' % changed)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

# -*- coding: utf-8 -*-
"""阶段任务模板：仅解析本项目四步 YAML 模板，不依赖第三方 YAML 库。"""
from dataclasses import dataclass
from pathlib import Path

import contract.pet_bus as pet_bus
from orchestrator.skill_registry import scalar, split_pair


@dataclass(frozen=True)
class TemplateStep:
    index: int
    name: str
    action: str
    needs_confirmation: bool = False
    question: str = ''


@dataclass(frozen=True)
class StageTemplate:
    name: str
    stage_id: str
    process_id: str
    steps: tuple
    path: Path


def template_root(program=None):
    return Path(program or Path(__file__).resolve().parents[1]) / 'skills' / 'templates'


def parse_template(text, path='<memory>'):
    """解析模板允许的标量和 ``steps`` 列表，并对运行所需字段做严格校验。"""
    meta, rows, current = {}, [], None
    for raw in str(text).lstrip('\ufeff').replace('\r\n', '\n').split('\n'):
        if not raw.strip() or raw.lstrip().startswith('#'):
            continue
        indent = len(raw) - len(raw.lstrip())
        pair = split_pair(raw)
        if indent == 0 and pair:
            key, value = pair
            if key == 'steps':
                current = None
            else:
                meta[key] = scalar(value)
            continue
        if indent == 2 and raw.strip().startswith('- ') and pair:
            key, value = pair
            current = {key: scalar(value)}
            rows.append(current)
            continue
        if indent >= 4 and current is not None and pair:
            key, value = pair
            current[key] = scalar(value)
    stage_id = str(meta.get('stage_id') or '')
    if stage_id not in pet_bus.STAGES:
        raise ValueError('%s：未知 stage_id %s' % (path, stage_id or '（空）'))
    steps = []
    for expected, row in enumerate(rows, 1):
        if int(row.get('index') or 0) != expected:
            raise ValueError('%s：步骤编号必须连续且从 1 开始' % path)
        if not all(str(row.get(key) or '').strip() for key in ('name', 'action')):
            raise ValueError('%s：步骤 %d 缺少 name 或 action' % (path, expected))
        if not isinstance(row.get('needs_confirmation'), bool):
            raise ValueError('%s：步骤 %d 的 needs_confirmation 必须是布尔值' % (path, expected))
        steps.append(TemplateStep(expected, str(row['name']), str(row['action']),
                                  row['needs_confirmation'], str(row.get('question') or '')))
    if not steps:
        raise ValueError('%s：模板没有步骤' % path)
    return StageTemplate(str(meta.get('name') or stage_id), stage_id, str(meta.get('process_id') or ''),
                         tuple(steps), Path(path))


def load_template(stage_id, program=None):
    """按规范阶段 ID 取得唯一模板；缺失或重复都显式报错，不猜测。"""
    wanted = str(stage_id or '').strip()
    found = []
    root = template_root(program)
    paths = set(root.glob('*_process_template.yaml'))
    animatic = root / 'animatic.yaml'
    if animatic.is_file():
        paths.add(animatic)
    for path in sorted(paths):
        template = parse_template(path.read_text(encoding='utf-8'), path)
        if template.stage_id == wanted:
            found.append(template)
    if len(found) != 1:
        raise ValueError('阶段 %s 的模板数量应为 1，实际为 %d' % (wanted or '（空）', len(found)))
    return found[0]


def step_groups(names, step_count):
    """将当前阶段已启用的细粒度 SKILL 平均归入业务模板步骤，确保不会漏跑。"""
    rows = list(names or ())
    groups, start = [], 0
    for index in range(step_count):
        remaining = len(rows) - start
        slots = step_count - index
        size = (remaining + slots - 1) // slots if remaining else 0
        groups.append(rows[start:start + size])
        start += size
    return groups

def step_summary(rows):
    if isinstance(rows, dict):
        return str(rows.get('summary') or rows.get('detail') or rows.get('text') or '已执行')[:160]
    if isinstance(rows, (list, tuple)):
        return '；'.join(str(row.get('detail') or row.get('skill') or '') for row in rows
                        if isinstance(row, dict))[:160] or '已执行'
    return str(rows or '已执行')[:160]


def resume_index(step, count):
    try:
        step = int(step)
    except (TypeError, ValueError):
        return 1
    return min(max(step, 1), count + 1)


DONE = 'done'
PENDING = 'pending'
BUDGET = 'budget'
FAILED = 'failed'
BLOCKED = 'blocked'


class StageTemplateRun:
    """模板执行体：编排器注入自己与 Run 工厂，本模块不反向依赖编排器。"""

    def __init__(self, orchestrator, stage_id, mode, wait_for_user, broadcast, execute_action, run_factory):
        self.orchestrator = orchestrator
        self.template = load_template(stage_id)
        self.manual = mode != 'auto'
        self.wait_for_user = wait_for_user
        self.emit = broadcast if callable(broadcast) else (lambda text: None)
        self.execute_action = execute_action
        self.run_factory = run_factory

    def run(self, context, names, start_step, _prior=None):
        orch = self.orchestrator
        template = self.template
        context = dict(context or {})
        emit = self.emit
        manual = self.manual
        start_step = resume_index(start_step, len(template.steps))
        # R2905：names=None 才表示「没指定」→ 该阶段全部已启用 SKILL；显式空表
        # 是「一个都没勾」，绝不能回退成全跑——那会让取消勾选形同虚设。
        selected = [item for item in (names if names is not None
                                      else [row.name for row in orch.registry.getByStage(template.stage_id)])
                    if orch.skill(item) is not None and orch.skill(item).stage == template.stage_id]
        if not callable(self.execute_action) and not selected:
            message = '【阻塞】%s 未启用可执行 SKILL' % template.name
            emit(message)
            return self.run_factory({'ok': False, 'results': [], 'failed': [], 'errors': [message], 'text': message})
        stage_number = list(pet_bus.STAGES).index(template.stage_id) + 1
        emit('【阶段 %d/%d】%s' % (stage_number, len(pet_bus.STAGES), template.name))
        if not callable(self.execute_action):
            dag = orch.buildDAG(selected)
            if dag['problems']:
                message = '【阻塞】' + '；'.join(dag['problems'])
                emit(message)
                return self.run_factory({'ok': False, 'results': [], 'failed': [], 'errors': dag['problems'], 'text': message})
            selected = dag['order']
        groups = step_groups(selected, len(template.steps))
        if not callable(self.execute_action):
            completed = {row['skill'] for row in (_prior or {}).get('results', [])
                         if row.get('status') == DONE and row.get('skill')}
            remaining = [name for group in groups[start_step-1:] for name in group if name not in completed]
            check = orch.validate(remaining, context)
            for item in check['missing_deps']:
                dep = item['missing']
                if dep not in selected and orch.skill(dep).stage == template.stage_id:
                    check['errors'].append('%s 缺少已启用的前置步骤 %s' % (item['skill'], dep))
            if check['errors']:
                message = '【阻塞】' + '；'.join(check['errors'])
                emit(message)
                return self.run_factory({'ok': False, 'results': [], 'failed': [], 'errors': check['errors'],
                                         'outcome': BUDGET if check['over_budget'] else 'invalid', 'text': message})
        results = [row for row in (_prior or {}).get('results', []) if row.get('status') == DONE]
        skipped = list((_prior or {}).get('skipped', []))
        failed = []
        skipped_skills = {name for step, group in zip(template.steps, groups) if step.name in skipped
                          for name in group}
        for step, group in zip(template.steps, groups):
            if step.index < start_step:
                continue
            emit('【步骤 %d/%d】%s' % (step.index, len(template.steps), step.name))
            if step.needs_confirmation and manual and not (_prior and step.index == start_step):
                question = step.question.format(count=context.get('count', 0))
                emit('【门禁】%s' % question)
                answer = str(self.wait_for_user(question) if callable(self.wait_for_user) else '').strip()
                if answer not in ('确认', '需要', '继续', '是', 'yes', 'YES', 'Yes'):
                    skipped.append(step.name)
                    skipped_skills.update(group)
                    emit('【警告】未确认，已跳过%s' % step.name)
                    continue
            try:
                orch.before_step(template.stage_id, step, [str(name) for name in group])
                step_context = dict(context, _template_step=step)
                if callable(self.execute_action):
                    outcome = self.execute_action(step.action, step_context)
                    rows = [outcome]
                else:
                    rows = []
                    for name in group:
                        if name in completed:
                            continue
                        unmet = skipped_skills.intersection(orch._deps(name))
                        row = (orch._result(name, BLOCKED, False, detail='未确认前置步骤：' + '、'.join(sorted(unmet)))
                               if unmet else orch.execute(name, step_context))
                        rows.append(row)
                        if row['status'] != DONE:
                            break
            except (OSError, TypeError, ValueError) as exc:
                rows = [orch._result(step.action, FAILED, False, detail=str(exc))]
            results.extend(rows)
            bad = [row for row in rows if isinstance(row, dict)
                   and (not row.get('ok', False) or row.get('status', DONE) != DONE)]
            if bad:
                failed.extend(bad)
                detail = step_summary(bad)
                emit('【阻塞】%s：%s' % (step.name, detail))
                break
            emit('【完成】%s：%s' % (step.name, step_summary(rows)))
        ok = not failed and not skipped
        text = ('%s已完成' % template.name) if ok else ('%s未完成' % template.name)
        if ok:
            orch.clear_checkpoint(template.stage_id)
            emit('【完成】%s' % text)
        run = self.run_factory({'ok': ok, 'results': results, 'failed': failed, 'skipped': skipped,
                                'errors': [row.get('detail', '') for row in failed], 'text': text,
                                'template': str(template.path)})
        run.orchestrator, run.context = orch, context
        run['pending'] = [row for row in failed if row.get('status') == PENDING]
        if run['pending'] and not callable(self.execute_action):
            def resume(approved_context):
                return self.run(approved_context, selected, step.index, run)
            run.resume_template = resume
        return run

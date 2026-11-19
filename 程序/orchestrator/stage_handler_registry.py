"""L3 三虎阶段启动适配器。

三虎只经 ``start`` 发出阶段指令；界面层提供未拆分阶段的回调，分镜阶段的
选择与去重决策则由文件服务产出工作计划。
"""
from enum import Enum, auto

import infra.app_logging as app_logging
import orchestrator.stage_flow as stage_flow
from contract.pet_bus import STAGES
from orchestrator.storyboard_plan_service import storyboard_work_plan


class StagePresentation(Enum):
    REPORT_STORYBOARD = auto()
    OPEN_STORYBOARD = auto()
    SHOW_ANIMATIC = auto()


def _workflow_lock_error(project, stage, trigger):
    """制作锁门禁：手动与自动同样阻断（R2862 起不再依赖总控预设）。

    必填口径统一走契约 ``stage_lock_requirements``（含项目创建日期过滤）；
    手动剧本准备不经这里（简报采集对话本身在收集制作锁，由简报门禁负责）。
    """
    from contract.script_contract import (PRODUCTION_LOCK_DEFINITIONS, STAGE_LOCK_REQUIREMENTS,
                                          lock_stage, stage_lock_requirements)
    if not project or (stage == 'script' and trigger != 'auto'):
        return ''
    if lock_stage(stage) not in STAGE_LOCK_REQUIREMENTS:
        return ''
    import orchestrator.stage_config as stage_config
    required_keys = stage_lock_requirements(stage, stage_config.project_created_at(project))
    if not required_keys:
        return ''
    labels = {item['key']: dict.get(item, 'label') or item['key'] for item in PRODUCTION_LOCK_DEFINITIONS}
    selected = stage_config.workflow_lock(project)
    missing = [labels[key] for key in required_keys if not str.strip(str(dict.get(selected, key) or ''))]
    if not missing:
        return ''
    return '请先在 01 剧本准备 的发送框内写明制作锁：' + str.join('、', missing)


def unchecked_skip_text(stage):
    from contract.pet_bus import STAGE_NAMES
    name = STAGE_NAMES.get(stage, stage)
    return '「%s」没有勾选 SKILL，三虎自动已跳过这一步' % name


def _start_storyboard(desktop, trigger):
    """返回启动提示、失败原因和可选的呈现指令。"""
    if getattr(desktop, 'root', None) is None:
        return '', '', None
    pet = getattr(desktop, 'pet', None)
    try:
        plan = storyboard_work_plan(desktop.root)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return '', '读取结构剧本输入失败：' + str(exc), None
    if not plan['scripts']:
        return '', '未选择结构剧本，无法制作分镜', None
    if not plan['todo'] and not plan['revise']:
        auto = getattr(pet, 'auto', None)
        if trigger == 'auto' and getattr(auto, 'active', None) == 'storyboard':
            text = '已确认所有已选结构剧本的分镜均已生成并采用'
            return text, '', StagePresentation.REPORT_STORYBOARD
        return '', '', None
    return ('已经在准备分镜任务：' + str(len(plan['todo']) + len(plan['revise']))
            + ' 份输入交给 Agent，做完会自动提示；没做完的会自动采用。'), '', StagePresentation.OPEN_STORYBOARD


def _start_pet_performance(desktop, kind):
    """三虎优化检查同样经 L3 启动入口，返回既有轮询会话。"""
    from stage_execution_service import start_pet_performance_check
    pet = getattr(desktop, 'pet', None)
    program = getattr(pet, 'program', None)
    project = getattr(desktop, 'root', None)
    if not program or project is None:
        raise RuntimeError('缺少优化检查所需的程序或项目路径')
    return start_pet_performance_check(program, project, kind=kind)


def poll_pet_performance(session, at=None):
    """三虎优化检查的 L3 轮询入口，负责继续向 L2 注入发布器。"""
    from stage_execution_service import poll_pet_performance_check
    return poll_pet_performance_check(session, at=at)


def _start_pet_test(desktop, text):
    """三虎增量自检经统一 L3 启动入口，返回既有轮询会话。"""
    from stage_execution_service import start_pet_test_check
    pet = getattr(desktop, 'pet', None)
    program = getattr(pet, 'program', None)
    if not program or getattr(desktop, 'root', None) is None:
        raise RuntimeError('缺少增量自检所需的程序或项目路径')
    return start_pet_test_check(program, text)


def poll_pet_test(session, project, at=None):
    """三虎增量自检的 L3 轮询入口，继续注入账本发布器。"""
    from stage_execution_service import poll_pet_test_check
    return poll_pet_test_check(session, project, at=at)


def start(desktop, stage, trigger='auto', fallback=None, *, skip_action=None,
          run_action=None, **options):
    """三虎唯一的 L3 启动指令入口。"""
    if stage not in (*STAGES, 'pet_performance', 'pet_test'):
        raise ValueError(f'未知阶段指令：{stage!r}')
    if stage in STAGES and run_action is not None:
        readiness = run_action(desktop, stage, trigger)
        if readiness is False or (isinstance(readiness, str) and readiness):
            return readiness
    error = _workflow_lock_error(getattr(desktop, 'root', None), stage, trigger)
    if not error and trigger == 'auto' and stage_flow.unchecked(getattr(desktop, 'root', None), stage):
        # R2905：自动编排只认阶段配置里勾上的 SKILL 列表；一个都没勾就跳过并提示，
        # 不再回退去跑「该阶段全部 SKILL」，也不让空阶段把自动链卡住。
        if callable(skip_action):
            return skip_action(desktop, stage)
        if getattr(desktop, 'pet', None) is not None:
            raise RuntimeError('缺少未勾选 SKILL 阶段的跳过动作')
        return unchecked_skip_text(stage)
    reply, presentation = error, None
    if not error and stage == 'storyboard':
        reply, error, presentation = _start_storyboard(desktop, trigger)
    elif not error and stage == 'animatic':
        presentation = StagePresentation.SHOW_ANIMATIC
        error = '分镜预演需要选择参考图与临时声音，生成后请您确认节奏、时长和对白同步'
    if presentation is not None:
        if run_action is None:
            raise RuntimeError('缺少阶段呈现动作')
        presented = run_action(desktop, stage, trigger, presentation=presentation, text=reply)
        if presented is False:
            return False
    if error:
        if trigger != 'auto':
            return reply
        if getattr(desktop, 'pet', None) is None:
            return ''
        if run_action is not None:
            try:
                run_action(desktop, stage, trigger, error=error)
            except Exception:
                app_logging.swallowed()
        return error
    if stage in ('storyboard', 'animatic'):
        return reply
    if stage == 'pet_performance':
        return _start_pet_performance(desktop, dict.get(options, 'kind', 'startup'))
    if stage == 'pet_test':
        return _start_pet_test(desktop, dict.get(options, 'text', ''))
    if callable(fallback):
        return fallback(stage, trigger)
    return ''

"""L3 三虎阶段启动适配器。

三虎只经 ``start`` 发出阶段指令；界面层提供未拆分阶段的回调，分镜阶段的
选择与去重决策则由文件服务产出工作计划。
"""
import app_logging
import orchestrator.stage_flow as stage_flow
from orchestrator.storyboard_plan_service import storyboard_work_plan


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
    import stage_config
    required_keys = stage_lock_requirements(stage, stage_config.project_created_at(project))
    if not required_keys:
        return ''
    labels = {item['key']: item.get('label') or item['key'] for item in PRODUCTION_LOCK_DEFINITIONS}
    selected = stage_config.workflow_lock(project)
    missing = [labels[key] for key in required_keys if not str(selected.get(key) or '').strip()]
    if not missing:
        return ''
    return '请先在 01 剧本准备 的发送框内写明制作锁：' + '、'.join(missing)


def _account_gate_error(desktop, stage):
    """会员闸门（设计文档 §5.2）：付费阶段在未登录、过期或离线超宽限时拦截，手动与自动一致。

    判定由宿主挂载的 ``account``（``account_controller.AccountController``）只读本机会话完成，
    不联网；没有挂载账号编排的宿主（如无界面测试替身）不设闸，只有字符串才算拦截原因。
    """
    account = getattr(desktop, 'account', None)
    gate = getattr(account, 'stage_gate', None)
    reason = gate(stage) if callable(gate) else ''
    return reason if isinstance(reason, str) else ''


def skip_unchecked(desktop, stage):
    """自动档下「一个 SKILL 都没勾」的阶段：标 skipped、放行自动链、说一句人话（R2905）。

    勾选列表为空不是失败——是用户在阶段配置里明确关掉了这一步的自动执行；
    状态机落 skipped（与 success 同属已收场），自动链照常推进到下一阶段，
    也不发 stage.completed——那要过产物核验，跳过的阶段没有产物可验。
    """
    import contract.pet_bus as pet_bus
    name = pet_bus.STAGE_NAMES.get(stage, stage)
    text = '「%s」没有勾选 SKILL，三虎自动已跳过这一步' % name
    pet = getattr(desktop, 'pet', None)
    if pet is not None:
        try:
            machine = pet.machine
            if machine is not None:
                machine.skip(stage, '未勾选 SKILL')
                machine.save()
        except Exception:
            app_logging.swallowed()
        try:
            auto = getattr(pet, 'auto', None)
            if auto is not None:
                auto.done(stage, True)
        except Exception:
            app_logging.swallowed()
        try:
            pet.broadcast('【警告】' + text + '（阶段配置里勾选后可重跑）')
        except Exception:
            app_logging.swallowed()
    return text


def _fail(desktop, stage, trigger, error):
    pet = getattr(desktop, 'pet', None)
    if trigger == 'auto' and pet is not None:
        try:
            pet._emit('stage.failed', stage=stage, error=error)
        except Exception:
            app_logging.swallowed()
        return error
    return ''


def _start_storyboard(desktop, trigger):
    if getattr(desktop, 'root', None) is None:
        return ''
    pet = getattr(desktop, 'pet', None)
    try:
        plan = storyboard_work_plan(desktop.root)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return _fail(desktop, 'storyboard', trigger, '读取结构剧本输入失败：' + str(exc))
    if not plan['scripts']:
        return _fail(desktop, 'storyboard', trigger, '未选择结构剧本，无法制作分镜')
    if not plan['todo'] and not plan['revise']:
        auto = getattr(pet, 'auto', None)
        if trigger == 'auto' and getattr(auto, 'active', None) == 'storyboard':
            text = '已确认所有已选结构剧本的分镜均已生成并采用'
            desktop.pet_report('storyboard', text)
            return text
        return ''
    desktop.open_storyboard_skill(None)
    return ('已经在准备分镜任务：' + str(len(plan['todo']) + len(plan['revise']))
            + ' 份输入交给 Agent，做完会自动提示；没做完的会自动采用。')


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


def start(desktop, stage, trigger='auto', fallback=None, **options):
    """三虎唯一的 L3 启动指令入口。"""
    error = _account_gate_error(desktop, stage) or _workflow_lock_error(getattr(desktop, 'root', None), stage, trigger)
    if error:
        # 手动路径也阻断：直接把原因交回调用方展示，不经三虎失败事件。
        return _fail(desktop, stage, trigger, error) if trigger == 'auto' else error
    if trigger == 'auto' and stage_flow.unchecked(getattr(desktop, 'root', None), stage):
        # R2905：自动编排只认阶段配置里勾上的 SKILL 列表；一个都没勾就跳过并提示，
        # 不再回退去跑「该阶段全部 SKILL」，也不让空阶段把自动链卡住。
        return skip_unchecked(desktop, stage)
    if stage == 'storyboard':
        return _start_storyboard(desktop, trigger)
    if stage == 'animatic':
        from contract.pet_bus import STAGES
        desktop.show(STAGES.index('animatic'))
        return _fail(desktop, stage, trigger, '分镜预演需要选择参考图与临时声音，生成后请您确认节奏、时长和对白同步')
    if stage == 'pet_performance':
        return _start_pet_performance(desktop, options.get('kind', 'startup'))
    if stage == 'pet_test':
        return _start_pet_test(desktop, options.get('text', ''))
    if callable(fallback):
        return fallback(stage, trigger)
    return ''

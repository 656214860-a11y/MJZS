"""L3 三虎阶段启动适配器。

三虎只经 ``start`` 发出阶段指令；界面层提供未拆分阶段的回调，分镜阶段的
选择与去重决策则由文件服务产出工作计划。
"""
from storyboard_plan_service import storyboard_work_plan


def _workflow_lock_error(project, stage, trigger):
    """自动剧本链须有统筹声明的全部锁；手动路径永远不拦。"""
    if trigger != 'auto' or stage != 'script' or not project:
        return ''
    import stage_config
    import workflow_settings
    workflow = stage_config.current_workflow(project)
    preset = workflow_settings.WORKFLOW_PRESETS.get(workflow.get('name'), {})
    required = tuple(preset.get('locks') or ())
    if not required:
        return ''
    selected = stage_config.workflow_lock(project)
    missing = [item.get('label') or item.get('key') for item in required
               if not str(selected.get(item.get('key')) or '').strip()]
    if not missing:
        return ''
    return '请先在 01 剧本准备 的发送框内写明制作锁（故事画幅／视频模型／交付形态）：' + '、'.join(missing)


def _fail(desktop, stage, trigger, error):
    pet = getattr(desktop, 'pet', None)
    if trigger == 'auto' and pet is not None:
        try:
            pet._emit('stage.failed', stage=stage, error=error)
        except Exception:
            pass
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
    error = _workflow_lock_error(getattr(desktop, 'root', None), stage, trigger)
    if error:
        return _fail(desktop, stage, trigger, error)
    if stage == 'storyboard':
        return _start_storyboard(desktop, trigger)
    if stage == 'animatic':
        from pet_bus import STAGES
        desktop.show(STAGES.index('animatic'))
        return _fail(desktop, stage, trigger, '分镜预演需要选择参考图与临时声音，生成后人工确认节奏、时长和对白同步')
    if stage == 'pet_performance':
        return _start_pet_performance(desktop, options.get('kind', 'startup'))
    if stage == 'pet_test':
        return _start_pet_test(desktop, options.get('text', ''))
    if callable(fallback):
        return fallback(stage, trigger)
    return ''

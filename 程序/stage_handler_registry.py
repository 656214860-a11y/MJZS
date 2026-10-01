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
    return '自动化要求先在“填写创作信息”补齐制作锁：' + '、'.join(missing)


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


def start(desktop, stage, trigger='auto', fallback=None):
    """三虎唯一的 L3 启动指令入口。"""
    error = _workflow_lock_error(getattr(desktop, 'root', None), stage, trigger)
    if error:
        return _fail(desktop, stage, trigger, error)
    if stage == 'storyboard':
        return _start_storyboard(desktop, trigger)
    if callable(fallback):
        return fallback(stage, trigger)
    return ''

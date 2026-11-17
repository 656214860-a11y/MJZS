"""无编排依赖的项目阶段模型只读访问。"""

from file_cache import read_json
import contract.stage_layout as stage_layout
from contract.pet_bus import STAGES


def value(project, stage):
    """返回已保存的阶段模型；空值、自动或损坏配置均返回空串。"""
    if stage not in STAGES:
        raise ValueError('没登记的阶段：' + str(stage))
    try:
        data = read_json(stage_layout.skill_config_path(project))
    except (OSError, ValueError, TypeError):
        return ''
    entry = data.get(stage) if isinstance(data, dict) else None
    return str(entry.get('model') or '').strip() if isinstance(entry, dict) else ''


def reasoning(project, stage):
    """返回已保存的阶段推理等级；自动、空值或损坏配置均返回空串。"""
    if stage not in STAGES:
        raise ValueError('没登记的阶段：' + str(stage))
    try:
        data = read_json(stage_layout.skill_config_path(project))
    except (OSError, ValueError, TypeError):
        return ''
    entry = data.get(stage) if isinstance(data, dict) else None
    level = str(entry.get('reasoning') or '').strip().lower() if isinstance(entry, dict) else ''
    return '' if level in ('', 'auto') else level


def reasoning_options(project, stage):
    """并入请求 options 的推理等级项；「自动」与无配置返回空表。"""
    level = reasoning(project, stage)
    return {'reasoning': level} if level else {}


def production_locks(project):
    """项目制作锁只读访问：优先顶层 ``production_locks``（弹窗预选的现行存储）；
    旧项目只在 ``workflow.lock.<统筹名>`` 里有值时按原命名空间回退读取。
    旧试验版曾把中文标签直接写成键；继续可读，但新写只使用受控英文键。"""
    if not project:
        return {}
    try:
        data = read_json(stage_layout.skill_config_path(project))
    except (OSError, ValueError, TypeError):
        return {}
    data = data if isinstance(data, dict) else {}
    flat = data.get('production_locks')
    if isinstance(flat, dict):
        value = dict(flat)
    else:
        workflow = data.get('workflow')
        workflow = workflow if isinstance(workflow, dict) else {}
        name = str(workflow.get('name') or '').strip()
        locks = workflow.get('lock')
        value = (dict(locks.get(name) or {})
                 if name and isinstance(locks, dict) and isinstance(locks.get(name), dict) else {})
    aliases = {'画幅': 'aspect_ratio', '交付形态': 'delivery_format', '视频模型版本': 'video_model_version'}
    for legacy, canonical in aliases.items():
        if canonical not in value and value.get(legacy):
            value[canonical] = value[legacy]
    return value

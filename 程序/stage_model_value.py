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

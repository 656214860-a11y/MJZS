"""无编排依赖的项目阶段模型只读访问。"""
from pathlib import Path

from file_cache import read_json
from pet_bus import STAGES


def value(project, stage):
    """返回已保存的阶段模型；空值、自动或损坏配置均返回空串。"""
    if stage not in STAGES:
        raise ValueError('没登记的阶段：' + str(stage))
    try:
        data = read_json(Path(project) / 'skill_config.json')
    except (OSError, ValueError, TypeError):
        return ''
    entry = data.get(stage) if isinstance(data, dict) else None
    return str(entry.get('model') or '').strip() if isinstance(entry, dict) else ''

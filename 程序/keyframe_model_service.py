"""首帧生产模型的无界面解析规则。"""
import app_logging
from pathlib import Path

from agent.core import read


def production_choices(project):
    """返回首帧阶段可选生产模型，不加载手动制作窗口。"""
    from contract.production_model_contract import LOCAL_KEYFRAME_MODEL, SEEDREAM_KEYFRAME_MODEL
    items = [(LOCAL_KEYFRAME_MODEL, LOCAL_KEYFRAME_MODEL),
             (SEEDREAM_KEYFRAME_MODEL, SEEDREAM_KEYFRAME_MODEL)]
    try:
        from importlib import import_module
        settings = import_module('workflow_settings')
        config = settings.load(project, 'assets')
        for engine_name, display in settings.ENGINES.items():
            name = str(config['profiles'][engine_name].get('model', '') or '').strip() or display
            while any(name == value for value, _label in items):
                name += ' · ' + display
            items.append((name, name))
    except Exception:
        app_logging.swallowed()
    return tuple(items)


def current_model(project):
    """阶段配置优先；未迁移旧项目才读取旧首帧偏好。"""
    from contract.production_model_contract import LOCAL_KEYFRAME_MODEL
    from stage_model_value import value as configured_value
    try:
        value = configured_value(project, 'keyframe')
    except Exception:
        value = ''
    choices = [item[0] for item in production_choices(project)]
    if value in choices:
        return value
    if value not in choices:
        path = Path(project) / 'ui_settings.json'
        prefs = read(path) if path.is_file() else {}
        saved = prefs.get('frame_production', {}) if isinstance(prefs, dict) else {}
        legacy = str(saved.get('model', '')).strip() if isinstance(saved, dict) else ''
        if legacy in choices:
            return legacy
    return LOCAL_KEYFRAME_MODEL

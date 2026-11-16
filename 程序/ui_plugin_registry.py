"""L4 UI 延迟加载登记表。

桌面界面仅能通过 :func:`module` 延迟加载此处登记的插件，避免各页面散落
``__import__``，同时保留“打开页面时才加载”的启动行为。
"""
from importlib import import_module


UI_PLUGINS = frozenset({
    'agent.shot_assets', 'agent_dispatch', 'asset_batch', 'asset_skill_batch', 'asset_prompt_check_dialog',
    'asset_reference_images', 'asset_reference_import', 'background_characters',
    'cloud_video', 'desktop_voice_input', 'keyframe_comfy', 'local_previs', 'native_assets', 'reference_wall',
    'skill_panel', 'stage_exec', 'stage_flow', 'pet_ui', 'previs_automation',
    'desktop_launcher', 'workflow_settings', 'task_center_ui',
    'agent.prompt_optimizer',
})


def module(name):
    """返回一个已登记的 UI 延迟加载模块；未知名称必须显式登记。"""
    text = str(name or '').strip()
    if text not in UI_PLUGINS:
        raise ValueError('未登记的 UI 延迟加载插件：' + text)
    return import_module(text)

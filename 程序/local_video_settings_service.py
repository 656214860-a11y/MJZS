"""本地视频设置的受控发布。"""
import os
import shutil
from pathlib import Path

from agent.core import file_hash, save, save_bytes, temporary_path
from file_cache import remove_temporary_file


def save_local_video_settings(project, current_config, options):
    """发布经 UI 预检的本地工作流副本与项目设置，失败时恢复旧状态。"""
    project = Path(project).resolve()
    if not isinstance(current_config, dict) or not isinstance(options, dict):
        raise ValueError('本地视频设置格式错误')
    source = Path(str(options.get('workflow', '')).strip()).resolve()
    if not source.is_file() or source.suffix.lower() != '.json' or source.stat().st_size <= 0:
        raise ValueError('请选择存在且非空的 ComfyUI API JSON 工作流')
    workflow_dir = (project / 'workflows').resolve()
    if not workflow_dir.is_relative_to(project):
        raise ValueError('项目工作流目录越界')
    target = (workflow_dir / ('video_' + file_hash(source)[:16] + '.json')).resolve()
    config_file = project / 'config.json'
    old_config = config_file.read_bytes() if config_file.is_file() else None
    old_target = target.read_bytes() if target.is_file() else None
    temporary = temporary_path(target, '.workflow')
    copied = source != target
    updated = {**current_config, 'local_video': dict(options), 'video_backend': 'comfy'}
    updated['local_video']['workflow'] = str(target)
    try:
        if copied:
            workflow_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, temporary)
            os.replace(temporary, target)
        save(config_file, updated)
    except Exception:
        if copied:
            if old_target is None:
                remove_temporary_file(target)
            else:
                save_bytes(target, old_target)
        if old_config is None:
            remove_temporary_file(config_file)
        elif not config_file.is_file() or config_file.read_bytes() != old_config:
            save_bytes(config_file, old_config)
        raise
    finally:
        remove_temporary_file(temporary)
    return updated

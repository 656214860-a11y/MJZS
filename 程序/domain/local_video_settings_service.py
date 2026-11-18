"""本地视频设置的受控发布。"""
from pathlib import Path

from agent.core import file_hash, temporary_path
import infra.app_logging as app_logging
from infra import unit_of_work
from infra.file_cache import remove_temporary_file
from contract.project_context import ProjectContext


def save_local_video_settings(context, current_config, options, *, gateway=None):
    """发布经 UI 预检的本地工作流副本与项目设置，失败时恢复旧状态。"""
    if not isinstance(context, ProjectContext):
        raise TypeError('本地视频设置需要由 L3 注入 ProjectContext。')
    if not isinstance(gateway, dict) or not all(callable(gateway.get(name)) for name in
                                                ('publish_json', 'publish_bytes', 'copy_file', 'replace_file',
                                                 'published')):
        raise TypeError('本地视频设置需要由 L3 注入发布网关。')
    project = context.root.resolve()
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
    temporary = temporary_path(target, '.workflow')
    copied = source != target
    updated = {**current_config, 'local_video': dict(options), 'video_backend': 'comfy'}
    updated['local_video']['workflow'] = str(target)
    # 工作流副本与项目配置同进退；取消与进程中断也由事务 journal 恢复（R3310 轮 6）。
    token = unit_of_work.begin((target, config_file))
    try:
        if copied:
            workflow_dir.mkdir(parents=True, exist_ok=True)
            gateway['copy_file'](source, temporary)
            gateway['replace_file'](temporary, target)
            gateway['published'](target)
        gateway['publish_json'](config_file, updated)
        gateway['published'](config_file)
        unit_of_work.commit(token)
    except BaseException:
        try:
            unit_of_work.rollback(token)
        except Exception:
            app_logging.swallowed('local_video_settings_service.save_local_video_settings.rollback')
        raise
    finally:
        remove_temporary_file(temporary)
    return updated

"""L3 云视频与 TTS 网关：云视频设置、配音发布与音频清单入口装配。

自 stage_execution_service 拆出；那边按原名重新导出，旧调用点与测试补丁点不变。
"""
from pathlib import Path
from project_context_factory import project_context
from contract.stage_path_service import write_dir
from orchestrator.stage_asset_gateways import _json_gateway


def refresh_audio_manifests(project):
    """配音字幕成果变化后重写 voice／subtitles／audio_manifest；清单写入失败只记警告，不回滚已发布成果。"""
    import logging
    from agent.core import save
    from domain.audio_import_service import audio_manifests
    try:
        folder = write_dir(project, 'audio') / 'output'
        for name, payload in audio_manifests(project).items():
            save(folder / name, payload)
    except OSError:
        logging.getLogger('stage_gate_gateways').warning('配音字幕清单写入失败', exc_info=True)


def media_import_publisher(project, kind):
    from stage_completion_service import publish_imported_media
    from agent.core import read
    from agent.media import validate_import
    from contract.platform_tools import tool_path
    def publish(target, source):
        config_path = Path(project) / 'config.json'
        config = dict(read(config_path)) if config_path.is_file() else {}
        for name in ('ffmpeg', 'ffprobe'):
            config[name] = config.get(name) or tool_path(name)
        return publish_imported_media(target, source, lambda temporary: validate_import(temporary, config, kind), kind)
    return publish


def tts_gateway():
    """L3 为 TTS 服务装配唯一的正式发布器；L2 不可自行写设置或阶段成果。"""
    from agent.core import save, save_bytes
    return {'publish_json': save, 'publish_bytes': save_bytes}


def save_tts_key(base_url, model, voice, key, voices=None, speeds=None):
    from domain.tts_api import save_key
    return save_key(base_url, model, voice, key, voices, speeds, gateway=tts_gateway())


def publish_tts_full_track(project, signature, raw):
    from domain.tts_api import publish_full_track
    result = publish_full_track(project_context(project), signature, raw, gateway=tts_gateway())
    refresh_audio_manifests(project)
    return result


def reusable_tts_full_track(project, signature):
    """L3 为整段配音复用检查注入项目上下文。"""
    from domain.tts_api import reusable_full_track
    return reusable_full_track(project_context(project), signature)


def run_tts_lines(lines, folder, generate=None, report=None, stop=None, episode=None, project=None):
    from domain.tts_api import run_lines
    result = run_lines(lines, folder, generate, report, stop, gateway=tts_gateway(), episode=episode, project=project)
    if project:
        refresh_audio_manifests(project)
    return result


def cloud_video_gateway():
    """L3 为云视频配置服务装配唯一的正式 JSON 发布器。"""
    return _json_gateway()


def cloud_video_session_folder(project, kind, base, model, source):
    """L3 统一注入项目上下文并创建/复用云视频会话目录。"""
    from cloud_video_service import session_folder
    result = session_folder(project_context(project), kind, base, model, source)
    if not result.ok:
        raise ValueError(result.reason)
    return result.data


def cloud_video_saved_provider_key(project, kind, providers, remembered=None, base_url=None, module_file=None):
    """L3 统一注入项目上下文，供 L4 查询旧会话兼容凭据。"""
    from cloud_video_service import saved_provider_key
    return saved_provider_key(project_context(project), kind, providers, remembered, base_url, module_file)


def publish_cloud_video_session_config(config_path, config, prefs_path, prefs):
    from cloud_video_service import publish_session_config
    result = publish_session_config(config_path, config, prefs_path, prefs, gateway=cloud_video_gateway())
    if not result.ok:
        raise ValueError(result.reason)
    return result.data


def publish_cloud_video_workspace_preference(prefs_path, prefs):
    from cloud_video_service import publish_workspace_preference
    result = publish_workspace_preference(prefs_path, prefs, gateway=cloud_video_gateway())
    if not result.ok:
        raise ValueError(result.reason)
    return result.data


def publish_cloud_video_studio_config(config_path, config):
    from cloud_video_service import publish_studio_config
    result = publish_studio_config(config_path, config, gateway=cloud_video_gateway())
    if not result.ok:
        raise ValueError(result.reason)
    return result.data


def video_lifecycle_gateway():
    """L3 向视频生命周期服务注入唯一 JSON 发布器。"""
    return _json_gateway()

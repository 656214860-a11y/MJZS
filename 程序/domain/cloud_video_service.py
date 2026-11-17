"""云视频会话的无界面配置查询服务。"""
import re
from pathlib import Path
from functools import wraps
import logging
from contract.service_contract import SystemError, success

from agent.core import read
from domain.project_naming import dated_path
from contract.project_context import ProjectContext


def _write_result(function):
    @wraps(function)
    def run(*args, **kwargs):
        try:
            return success(function(*args, **kwargs))
        except OSError:
            logging.getLogger('cloud_video_service').exception('云视频工作区保存失败')
            return SystemError('云视频工作区保存失败，请检查文件权限和磁盘空间。')
    return run

PROVIDERS={
    '阿里云百炼 · 万相':('wan','https://dashscope.aliyuncs.com/api/v1','wan2.6-i2v-flash','DASHSCOPE_API_KEY'),
    '火山引擎 · Seedance':('volcengine','https://ark.cn-beijing.volces.com/api/v3','doubao-seedance-1-5-pro-251215','ARK_API_KEY'),
    '自定义 · 万相兼容':('wan','','','DASHSCOPE_API_KEY'),
    '自定义 · Seedance兼容':('volcengine','','','ARK_API_KEY'),
}


def _require_gateway(gateway):
    """L2 的会话配置发布只能使用 L3 注入的正式发布器。"""
    if not isinstance(gateway, dict) or not callable(gateway.get("publish_json")):
        raise TypeError("云视频配置发布必须由 L3 注入 gateway")
    return gateway


@_write_result
def publish_session_config(config_path, config, prefs_path, prefs, *, gateway=None):
    """发布已校验的云视频会话配置及项目工作区偏好。"""
    publish = _require_gateway(gateway)["publish_json"]
    publish(Path(config_path), config)
    publish(Path(prefs_path), prefs)


@_write_result
def publish_workspace_preference(prefs_path, prefs, *, gateway=None):
    """发布云视频当前工作区偏好；调用者负责完成路径边界校验。"""
    _require_gateway(gateway)["publish_json"](Path(prefs_path), prefs)

@_write_result
def publish_studio_config(config_path, config, *, gateway=None):
    """发布已由云视频设置页校验过的工作室会话配置。"""
    _require_gateway(gateway)["publish_json"](Path(config_path), config)

def provider_label(config, providers):
    kind=config.get('cloud_provider','wan');url=config.get('base_url','').rstrip('/')
    for label,(provider,base,_,_) in providers.items():
        if provider==kind and base and url==base:return label
    if not url:return '阿里云百炼 · 万相'
    return '自定义 · 万相兼容' if kind=='wan' else '自定义 · Seedance兼容'


@_write_result
def session_folder(context, kind, base, model, source):
    if not isinstance(context, ProjectContext):
        raise TypeError('云视频会话目录需要由 L3 注入 ProjectContext。')
    parent=context.root/'cloud_video';parent.mkdir(exist_ok=True)
    source=Path(source).resolve()
    for candidate in parent.iterdir():
        config=candidate/'config.json'
        if not candidate.is_dir() or not config.is_file():continue
        saved=read(config)
        if isinstance(saved,dict) and (saved.get('cloud_provider')==kind and saved.get('base_url','').rstrip('/')==base.rstrip('/') and saved.get('model')==model and Path(saved.get('episode_file','')).resolve()==source):return candidate
    provider='火山引擎' if kind=='volcengine' else '阿里云'
    model_name=re.sub(r'[^A-Za-z0-9_-]+','-',model).strip('-_')[:55] or '视频模型'
    return dated_path(parent,provider+'_'+model_name)


def saved_provider_key(context,kind,providers,remembered=None,base_url=None,module_file=None):
    if not isinstance(context, ProjectContext):
        raise TypeError('云视频凭据查询需要由 L3 注入 ProjectContext。')
    key_name='ARK_API_KEY' if kind=='volcengine' else 'DASHSCOPE_API_KEY';configs=[]
    # R505 P0：新保存的云视频会话统一由模型池读取 DPAPI；不会再回填或扫描明文。
    try:
        from model_pool import named_key
        current=named_key(key_name)
        if current:
            return current
    except ValueError:
        pass
    if remembered and remembered.get('cloud_provider')==kind:configs.append(remembered)
    for path in sorted((context.root/'cloud_video').glob('*/config.json'),key=lambda p:p.stat().st_mtime,reverse=True):
        cfg=read(path)
        if isinstance(cfg,dict) and cfg.get('cloud_provider')==kind:configs.append(cfg)
    expected=(base_url or next(spec[1] for spec in providers.values() if spec[0]==kind and spec[1])).rstrip('/')
    # 旧项目会话尚未迁移时保留只读兼容；新会话不再写 project_dir/.env。
    paths=[Path(c['project_dir'])/'.env' for c in configs if c.get('project_dir') and c.get('base_url','').rstrip('/')==expected]
    if module_file and expected in [spec[1] for spec in providers.values() if spec[0]==kind and spec[1]]:paths.append(Path(module_file).resolve().parent/'private/.env')
    import infra.model_secrets as model_secrets
    for path in paths:
        # 按主机绑定：只有与这个主机匹配的 .env 迁过，才认加密存储里同名那把。
        model_secrets.import_env_keys(path)
        if model_secrets.env_imported(path):
            found=model_secrets.load(key_name)
            if found:return found
    return ''

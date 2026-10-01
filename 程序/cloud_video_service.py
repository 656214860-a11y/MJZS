"""云视频会话的无界面配置查询服务。"""
import re
from pathlib import Path

from agent.core import read, save
from project_naming import dated_path

PROVIDERS={
    '阿里云百炼 · 万相':('wan','https://dashscope.aliyuncs.com/api/v1','wan2.6-i2v-flash','DASHSCOPE_API_KEY'),
    '火山引擎 · Seedance':('volcengine','https://ark.cn-beijing.volces.com/api/v3','doubao-seedance-1-5-pro-251215','ARK_API_KEY'),
    '自定义 · 万相兼容':('wan','','','DASHSCOPE_API_KEY'),
    '自定义 · Seedance兼容':('volcengine','','','ARK_API_KEY'),
}


def publish_session_config(config_path, config, prefs_path, prefs):
    """发布已校验的云视频会话配置及项目工作区偏好。"""
    save(Path(config_path), config)
    save(Path(prefs_path), prefs)


def publish_workspace_preference(prefs_path, prefs):
    """发布云视频当前工作区偏好；调用者负责完成路径边界校验。"""
    save(Path(prefs_path), prefs)

def publish_studio_config(config_path, config):
    """发布已由云视频设置页校验过的工作室会话配置。"""
    save(Path(config_path), config)

def provider_label(config, providers):
    kind=config.get('cloud_provider','wan');url=config.get('base_url','').rstrip('/')
    for label,(provider,base,_,_) in providers.items():
        if provider==kind and base and url==base:return label
    if not url:return '阿里云百炼 · 万相'
    return '自定义 · 万相兼容' if kind=='wan' else '自定义 · Seedance兼容'


def session_folder(project, kind, base, model, source):
    parent=Path(project)/'cloud_video';parent.mkdir(exist_ok=True)
    source=Path(source).resolve()
    for candidate in parent.iterdir():
        config=candidate/'config.json'
        if not candidate.is_dir() or not config.is_file():continue
        saved=read(config)
        if isinstance(saved,dict) and (saved.get('cloud_provider')==kind and saved.get('base_url','').rstrip('/')==base.rstrip('/') and saved.get('model')==model and Path(saved.get('episode_file','')).resolve()==source):return candidate
    provider='火山引擎' if kind=='volcengine' else '阿里云'
    model_name=re.sub(r'[^A-Za-z0-9_-]+','-',model).strip('-_')[:55] or '视频模型'
    return dated_path(parent,provider+'_'+model_name)


def saved_provider_key(project,kind,providers,remembered=None,base_url=None,module_file=None):
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
    for path in sorted((Path(project)/'cloud_video').glob('*/config.json'),key=lambda p:p.stat().st_mtime,reverse=True):
        cfg=read(path)
        if isinstance(cfg,dict) and cfg.get('cloud_provider')==kind:configs.append(cfg)
    expected=(base_url or next(spec[1] for spec in providers.values() if spec[0]==kind and spec[1])).rstrip('/')
    # 旧项目会话尚未迁移时保留只读兼容；新会话不再写 project_dir/.env。
    paths=[Path(c['project_dir'])/'.env' for c in configs if c.get('project_dir') and c.get('base_url','').rstrip('/')==expected]
    if module_file and expected in [spec[1] for spec in providers.values() if spec[0]==kind and spec[1]]:paths.append(Path(module_file).resolve().parent/'private/.env')
    for path in paths:
        if not path.is_file():continue
        for line in path.read_text(encoding='utf-8-sig').splitlines():
            if not line.lstrip().startswith('#') and '=' in line:
                name,value=line.split('=',1);value=value.strip().strip(chr(34)).strip(chr(39))
                if name.strip()==key_name and value and value not in ('replace_me','<YOUR_API_KEY>'):return value
    return ''

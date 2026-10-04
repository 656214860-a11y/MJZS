"""Shared asset library and the explicitly adopted storyboard for a project."""
from pathlib import Path
import re
from agent.core import read
from project_context import ProjectContext


def _project_root(project=None, *, context=None):
    """读取项目配置时消费 L3 注入的上下文，兼容旧路径调用。"""
    if context is None:
        return Path(project).resolve()
    if not isinstance(context, ProjectContext):
        raise TypeError('资产上下文需要由 L3 注入 ProjectContext。')
    root = context.root.resolve()
    if project is not None and Path(project).resolve() != root:
        raise ValueError('项目路径与注入的 ProjectContext 不一致。')
    return root


def generated_dir(base):
    """全部模型批量生成图片的统一存放目录。"""
    path=Path(base).resolve()/'生成资产'
    path.mkdir(parents=True,exist_ok=True)
    return path


def ensure_browser_directory(base, kind):
    """创建并返回资产页面可浏览的分类目录，不涉及资产内容发布。"""
    base = Path(base).resolve()
    if kind not in ('all', 'scenes', 'characters', 'props'):
        raise ValueError('资产分类无效')
    path = base / 'assets'
    if kind != 'all':
        path /= kind
    path.mkdir(parents=True, exist_ok=True)
    return path

def library_dir(project=None, fallback=None, *, context=None):
    project=_project_root(project, context=context)
    cfg=read(project/'config.json') if (project/'config.json').is_file() else {}
    from project_stages import assets
    standard=assets(project)
    value=cfg.get('asset_library_dir')
    if not value and ((standard/'assets.json').is_file() or (standard/'assets/资产清单/assets.json').is_file()):
        value=standard
    base=(project/Path(value or fallback or cfg.get('episode_dir','04资产管理'))).resolve()
    if not base.is_relative_to(project):raise ValueError('资产目录超出当前项目')
    return base


def active_source(project=None, storyboard=None, fallback=None, *, context=None):
    # Source resolution is catalog domain logic; depend on the headless service
    # rather than the legacy catalog facade to keep assets out of that cycle.
    from storyboard_catalog_service import resolve_source, default_source
    project=_project_root(project, context=context)
    prefs=read(project/'ui_settings.json') if (project/'ui_settings.json').is_file() else {}
    record=library_dir(project,fallback, context=context)/'assets/资产清单/来源.json'
    remembered=read(record).get('storyboard') if record.is_file() else None
    value=storyboard or prefs.get('frame_json') or remembered
    if value:
        path=resolve_source(context,value)
        if not path.is_file():raise ValueError('当前分镜JSON已移动或删除，请重新采用分镜：'+str(path))
        return path
    for path in (default_source(context),library_dir(project,fallback, context=context)/'episode.json'):
        if path.is_file():return path.resolve()
    raise ValueError('尚未采用分镜JSON，请先在第2步点「手动采用分镜」')


def references(shot):
    """All declared assets, including assets visible only in the first frame."""
    from prop_assets import normalize_shot
    shot=normalize_shot(shot)
    seen=set()
    for prefix,key in [('CHAR','characters'),('LOC','location'),('PROP','props'),(None,'first_frame_assets')]:
        values=shot.get(key,[])
        values=values if isinstance(values,list) else [values] if values else []
        for value in values:
            value=(value.get('id') or value.get('name')) if isinstance(value,dict) else value
            if not isinstance(value,str) or not value.strip():continue
            value=value.strip();kind=prefix
            if kind is None:
                match=re.fullmatch(r'(CHAR|LOC|PROP)_\d{3,}',value)
                if not match:continue
                kind=match[1]
            if (kind,value) not in seen:
                seen.add((kind,value));yield kind,value


def scope_sources(project=None,scope='all', *, context=None):
    from storyboard_adoption_contract import adopted
    project=_project_root(project, context=context)
    result=adopted(project)
    if scope=='current':
        if not result:return []
        current=active_source(project, context=context)
        return [current] if current in result else [result[0]]
    return result

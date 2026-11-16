"""Retire verified working JSONs only after a final and its assets are saved."""
from pathlib import Path
import copy,hashlib
from agent.core import read,fingerprint,file_hash
from contract.project_context import ProjectContext
from domain.storyboard_storage import _references,ALIAS_FILE,resolved_alias
from contract.storyboard_paths import media_root


def _context(value):
    """分镜生命周期的项目路径只能由 L3 注入。"""
    if not isinstance(value, ProjectContext):
        raise TypeError('分镜生命周期项目路径需要由 L3 注入 ProjectContext。')
    return value


def working_roots(context):
    """当前初步分镜目录优先，旧 storyboard 只作为历史读取兼容。"""
    from contract.project_stages import storyboard
    project=_context(context).root.resolve()
    return (storyboard(project).resolve(), (project/'storyboard').resolve())


def is_working_source(context,path):
    path=Path(path).resolve()
    # 新项目的工作稿位于 03初步分镜/分镜文档；旧项目仍可能保留分镜拆分。
    return any(path.parent in (root/'分镜文档',root/'分镜拆分') for root in working_roots(context))


def _safe(context,path,working=True):
    project=_context(context).root.resolve();roots=working_roots(context)
    path=Path(path).absolute()
    root=next((item for item in roots if path.resolve().is_relative_to(item)),None)
    if working and root is None:raise ValueError('只能整理当前项目内的分镜JSON')
    if not working:
        root=project
        if not path.resolve().is_relative_to(root):raise ValueError('定稿必须位于当前项目内')
    for part in [path,*path.parents]:
        if part==root.parent:break
        if part.is_symlink() or part.is_junction():raise ValueError('不整理链接目录中的分镜')
    return path.resolve()


def signature(episode,assets,base):
    """Ignore UI usage counters, but compare all content and actual image bytes."""
    assets=copy.deepcopy(assets)
    for asset in assets.values():
        for key in ('used_in','status'):asset.pop(key,None)
        if asset.get('image'):
            path=(Path(base)/asset['image']).resolve()
            if not path.is_relative_to(Path(base).resolve()) or not path.is_file():return None
            asset['_image_hash']=file_hash(path)
    return fingerprint({'episode':episode,'assets':assets})


def retire(context,source,target,expected,publish=None):
    if not callable(publish):raise TypeError('分镜退役需要 L3 别名发布器。')
    project=_context(context).root.resolve();source=_safe(context,source);target=_safe(context,target,working=False)
    if source==target:return
    if not target.is_file():raise ValueError('定稿未保存，原稿已保留')
    if not source.is_file():return
    raw=source.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=expected:raise ValueError('原稿在生成期间已修改，原稿已保留，请重新生成定稿')
    _references(project,{source:target})
    file=source.parent/ALIAS_FILE
    aliases=read(file) if file.is_file() else {}
    if not isinstance(aliases,dict):aliases={}
    old=source.relative_to(project).as_posix();new=target.relative_to(project).as_posix()
    aliases={key:(new if value==old else value) for key,value in aliases.items()}
    aliases[old]=new;publish(file,aliases)
    if hashlib.sha256(source.read_bytes()).hexdigest()!=expected:raise ValueError('原稿正在写入，已保留')
    # 定稿已验证、别名也已更新；工作原稿必须走统一回收站，失败时保留原稿。
    from storage_maintenance import recycle_paths
    if not recycle_paths(project,[source],'定稿替换原始分镜'):
        raise ValueError('原稿未能安全移入回收站，已保留')


def working_content(episode):
    episode=copy.deepcopy(episode)
    for key in ('missing_assets','assets_ready'):episode.pop(key,None)
    for shot in episode.get('shots',[]):
        for key in ('asset_bindings','asset_status','reference_images'):shot.pop(key,None)
    return episode


def refresh_open_studios(desktop, context):
    project = _context(context).root
    sessions=getattr(desktop,'video_sessions',{})
    studios=[getattr(desktop,'studio',None)]+[getattr(v,'studio',None) for v in sessions.values()]
    for studio in studios:
        if studio is None:continue
        old=Path(studio.episode_path).resolve();source=resolved_alias(project,old)
        if source==old:continue
        studio.episode_path=source;studio.episode_dir=source.parent;studio.media_dir=media_root(source)
        studio.episode=read(source)
        studio.cfg=read(studio.root/'config.json')
    for key,video in list(sessions.items()):
        source=resolved_alias(project,key[1])
        if str(source)!=str(key[1]):
            sessions[(key[0],str(source))]=sessions.pop(key)

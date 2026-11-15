"""Separate production JSON from shared storyboard media; keep legacy packages valid."""
from pathlib import Path

def is_final_dir(name):
    """旧命名「定稿_...」与新命名「EP00X_分镜定稿_...」都识别为定稿目录。"""
    name=str(name)
    return name.startswith('定稿') or '_分镜定稿_' in name


def is_cloud_workspace(path):
    """云端视频工作集位于 <项目>/cloud_video/<名称>/，与本地项目目录区分开。"""
    return Path(path).parent.name=='cloud_video'


def project_root(path):
    """工作集或项目目录 → 所属项目根目录：云端工作集上跳两级，其余原样返回。"""
    path=Path(path)
    return path.parent.parent if is_cloud_workspace(path) else path


def media_root(source):
    source=Path(source).resolve()
    for folder in source.parents:
        # 旧 ``分镜拆分`` 与新 ``03初步分镜/分镜文档`` 共用同一媒体根。
        if folder.name in ('分镜拆分','分镜文档'):
            return folder.parent
    return source.parent


_RESOLVED={}
_LISTINGS={}


def resolved_path(path):
    """Path.resolve() 在 Windows 上约 0.15ms；同一原始路径的结果在进程内复用。"""
    key=str(path)
    hit=_RESOLVED.get(key)
    if hit is None:
        if len(_RESOLVED)>256:_RESOLVED.clear()
        hit=_RESOLVED[key]=Path(path).resolve()
    return hit


def config_listing(folder):
    """cloud_video/*/config.json 的清单；目录自身 mtime 不变（没有工作集增删）就复用上次的 glob。"""
    token=file_signature(folder)
    hit=_LISTINGS.get(str(folder))
    if token is not None and hit and hit[0]==token:return hit[1]
    configs=tuple(sorted(Path(folder).glob('*/config.json')))
    if len(_LISTINGS)>64:_LISTINGS.clear()
    _LISTINGS[str(folder)]=(token,configs)
    return configs


def file_signature(path):
    try:
        stat=Path(path).stat()
    except OSError:
        return None
    return stat.st_mtime_ns,stat.st_size

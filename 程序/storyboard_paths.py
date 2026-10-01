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

# -*- coding: utf-8 -*-
"""阶段页面的目录初始化服务，不依赖 Tk。"""
from pathlib import Path

import project_stages


def ensure_audio_workspace(project):
    """创建并返回配音与字幕两个既有阶段目录。"""
    return _ensure(project_stages.audio(project), project_stages.subtitles(project))


def ensure_storyboard_workspace(project):
    """创建并返回初步分镜阶段目录，供手动 JSON 导入选择来源。"""
    return _ensure(project_stages.storyboard(project))[0]


def ensure_editing_workspace(project):
    """创建并返回后期剪辑阶段目录。"""
    return _ensure(project_stages.editing(project))


def ensure_delivery_workspace(project):
    """创建并返回交付及其导出子目录。"""
    return _ensure(project_stages.delivery(project), project_stages.exports(project))


def _ensure(*directories):
    paths = tuple(Path(directory) for directory in directories)
    for path in paths:
        path.mkdir(parents=True, exist_ok=True)
    return paths

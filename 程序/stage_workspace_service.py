# -*- coding: utf-8 -*-
"""阶段页面的目录初始化服务，不依赖 Tk。"""
from pathlib import Path
import logging
from contract.service_contract import SystemError, success

import contract.project_stages as project_stages

LOGGER = logging.getLogger(__name__)


def ensure_audio_workspace(project):
    """创建并返回配音与字幕两个既有阶段目录。"""
    return _ensure(project_stages.audio(project), project_stages.subtitles(project))


def ensure_storyboard_workspace(project):
    """创建并返回初步分镜阶段目录，供手动 JSON 导入选择来源。"""
    return _ensure(project_stages.storyboard(project), single=True)


def ensure_editing_workspace(project):
    """创建并返回后期剪辑阶段目录。"""
    return _ensure(project_stages.editing(project))


def ensure_delivery_workspace(project):
    """创建并返回交付及其导出子目录。"""
    return _ensure(project_stages.delivery(project), project_stages.exports(project))


def _ensure(*directories, single=False):
    paths = tuple(Path(directory) for directory in directories)
    try:
        for path in paths:
            path.mkdir(parents=True, exist_ok=True)
    except OSError:
        LOGGER.exception('阶段工作区初始化失败')
        return SystemError('阶段工作区初始化失败，请检查文件权限和磁盘空间。')
    return success(paths[0] if single else paths)

# -*- coding: utf-8 -*-
"""项目工作阶段的唯一目录口径。用户可见文件只写入这里，禁止回写旧英文目录。"""
from pathlib import Path

STAGES = {
    'script': '01剧本准备',
    'structure': '02剧本结构',
    'storyboard': '03初步分镜',
    'animatic': '04分镜预演',
    'assets': '05资产管理',
    'continuity': '06连贯性清单',
    'final': '07分镜定稿',
    'frames': '08首帧管理',
    'previs': '09白模预演',
    'video': '10视频生成',
    'audio': '11配音与字幕',
    'editing': '12后期剪辑',
    'delivery': '13质检交付',
}


def stage(project, key):
    """给定项目与阶段键，返回唯一的用户可见目录。"""
    from contract.stage_path_service import write_dir
    return write_dir(project, key)


def writing(project):
    return stage(project, 'script')


def structure(project):
    return stage(project, 'structure')


def storyboard(project):
    return stage(project, 'storyboard')


def assets(project):
    return stage(project, 'assets')


def audio(project):
    return stage(project, 'audio') / '音频'


def subtitles(project):
    return stage(project, 'audio') / '字幕'


def editing(project):
    """后期剪辑阶段的唯一用户可见目录。"""
    return stage(project, 'editing')


def delivery(project):
    """质检交付阶段的唯一用户可见目录。"""
    return stage(project, 'delivery')


def exports(project):
    """自动粗剪和 QC 的可交付输出，归属最终交付阶段。"""
    return delivery(project) / '导出成片'

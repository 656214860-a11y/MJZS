# -*- coding: utf-8 -*-
"""项目工作阶段的唯一目录口径。用户可见文件只写入这里，禁止回写旧英文目录。

R3093（任务书 P0，Q15）：本模块原先另存一份 ``STAGES`` 字典，键拼写与权威
``pet_bus.STAGES`` 不同（``structure``／``frames``／``editing``），是规则 28
「一个动作一个入口」的正面对象——已删除。目录名现在一律从 L0 权威
``contract.stage_layout.STAGES`` 派生（``stage_dirs()``），本模块只保留便捷函数，
所有路径仍经 ``stage_path_service`` 产出。
"""


def stage_dirs():
    """全部阶段目录名，顺序＝``pet_bus.STAGES``；替代原 ``STAGES.values()``。"""
    from contract import stage_layout
    return tuple(row[0] for row in stage_layout.STAGES)


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

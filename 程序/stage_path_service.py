"""L0 阶段路径事实服务：新写唯一目录，旧目录只在淘汰期内可读。"""
from datetime import date
from pathlib import Path

import stage_layout

# 旧英文目录只服务于已存在的历史项目；到期后删除兼容分支前必须迁移并复核调用方。
LEGACY_READ_UNTIL = date(2027, 3, 31)

_STAGES = {
    'script': 'script', 'structure': 'script_structure', 'script_structure': 'script_structure',
    'storyboard': 'storyboard', 'assets': 'assets', 'continuity': 'continuity',
    'final': 'final', 'frames': 'keyframe', 'keyframe': 'keyframe', 'previs': 'previs',
    'video': 'video', 'audio': 'audio', 'editing': 'edit', 'edit': 'edit', 'delivery': 'delivery',
}
_LEGACY = {
    'script': ('writing',),
    'structure': ('writing/结构剧本',),
    'script_structure': ('writing/结构剧本',),
    'storyboard': ('storyboard/分镜拆分',),
    'assets': ('episode/assets/资产清单',),
}


def write_dir(project, stage):
    """返回唯一的当前阶段写入目录；绝不创建或返回旧英文目录。"""
    key = _STAGES.get(str(stage))
    if key is None:
        raise ValueError('未知阶段：' + str(stage))
    folder = next((row[0] for row in stage_layout.STAGES if row[1] == key), None)
    if folder is None:
        raise ValueError('阶段目录契约缺少：' + key)
    return stage_layout.paths(Path(project), folder)['root']


def legacy_read_dirs(project, stage, today=None):
    """返回仍在淘汰期内、且只供读取的历史目录候选。"""
    if (today or date.today()) > LEGACY_READ_UNTIL:
        return ()
    root = Path(project)
    return tuple(root / relative for relative in _LEGACY.get(str(stage), ()))


def read_dirs(project, stage, today=None):
    """当前目录优先，旧目录仅作为只读回退，且不重复。"""
    values = [write_dir(project, stage), *legacy_read_dirs(project, stage, today=today)]
    return tuple(dict.fromkeys(values))

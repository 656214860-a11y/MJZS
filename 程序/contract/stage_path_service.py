"""L0 阶段路径事实服务：新写唯一目录，旧目录只在淘汰期内可读。"""
from datetime import date
from pathlib import Path

import contract.stage_layout as stage_layout

# 旧英文目录只服务于已存在的历史项目；到期后删除兼容分支前必须迁移并复核调用方。
LEGACY_READ_UNTIL = date(2027, 3, 31)

# 阶段键 → 规范阶段 id 的唯一解析口径在 contract.stage_layout
# （canonical_stage_id：STAGE_ALIASES 历史拼写 ＋ STAGES 第 2 列），本模块不再另存阶段表。
# _LEGACY／LEGACY_NUMBERED 的键一律是规范阶段 id，不再为历史拼写各留一份。
_LEGACY = {
    'script': ('writing',),
    'script_structure': ('writing/结构剧本',),
    'storyboard': ('storyboard/分镜拆分',),
    'assets': ('episode/assets/资产清单',),
}

# R1124 插入阶段前的中文目录只供读取，不建立会导致回写旧数据的目录联接。
LEGACY_NUMBERED = {
    'assets': '04资产管理', 'continuity': '05连贯性清单', 'final': '06分镜定稿',
    'keyframe': '07首帧管理', 'previs': '08白模预演', 'video': '09视频生成',
    'audio': '10配音与字幕', 'edit': '11后期剪辑', 'delivery': '12质检交付',
}


def shared_reference_dir(project):
    """预演准备、正式资产复用；正典板与资产提示词仍由资产阶段管理。"""
    return stage_layout.shared_paths(project)['root'] / 'reference_images'


def shared_reference_read_dirs(project):
    """新共享目录优先，旧资产参考图保持原位、只读兼容。"""
    return (shared_reference_dir(project), *(folder / 'assets' / '参考图' for folder in read_dirs(project, 'assets')),
            *(folder / '参考图' for folder in read_dirs(project, 'assets')),
            Path(project) / 'episode' / 'assets' / '参考图')


def write_dir(project, stage):
    """返回唯一的当前阶段写入目录；绝不创建或返回旧英文目录。"""
    key = stage_layout.canonical_stage_id(stage)
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
    return tuple(root / relative for relative in _LEGACY.get(stage_layout.canonical_stage_id(stage), ()))


def read_dirs(project, stage, today=None):
    """当前目录优先，旧目录仅作为只读回退，且不重复。"""
    old = LEGACY_NUMBERED.get(stage_layout.canonical_stage_id(stage))
    values = [write_dir(project, stage)]
    if old:
        values.append(Path(project) / old)
    values.extend(legacy_read_dirs(project, stage, today=today))
    return tuple(dict.fromkeys(values))


def existing_dir(project, stage):
    """只读选择：当前目录有内容时优先，否则回退旧编号目录。

    只检查一层，不在启动路径递归扫描；空的阶段骨架不遮住历史成果。
    """
    candidates = read_dirs(project, stage)
    def material(item):
        return item.is_file() and not item.name.startswith(('README', '目录说明', '共用技能位置'))
    for folder in candidates:
        if folder.is_dir() and any(material(child) or
                                   (child.is_dir() and any(material(item) or item.is_dir()
                                                          for item in child.iterdir()))
                                   for child in folder.iterdir()):
            return folder
    return candidates[0]


def read_file(project, stage, *parts):
    """已有单文件按新目录优先读取；不存在时返回规范路径，不创建目录。"""
    for folder in read_dirs(project, stage):
        path = folder.joinpath(*parts)
        if not path.resolve().is_relative_to(Path(project).resolve()):
            raise ValueError('阶段读取路径越界')
        if path.is_file():
            return path
    return write_dir(project, stage).joinpath(*parts)

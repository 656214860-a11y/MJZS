"""首次修改前的阶段/资产写入准备与旧路径重定位（L3）。

从 `stage_execution_service` 拆出（R1619／Q9）："改之前先把历史成果复制成当前目录"
与"把显式修改目标从旧编号重定位到新编号"是同一件事，与阶段执行编排的其余部分无关。

`stage_execution_service` 仍按原名转发本模块的公开名（含 `prepare_stage_write`、
`prepare_legacy_stage_path` 等既有调用点）。
"""
from __future__ import annotations

import threading
from pathlib import Path

from contract.stage_path_service import write_dir



_STAGE_COPY_LOCK = threading.RLock()


def prepare_stage_write(project, stage, *, source=None):
    with _STAGE_COPY_LOCK:
        return _copy_stage_for_write(project, stage, source=source)


def _copy_stage_for_write(project, stage, *, source=None):
    """首次修改前复制历史成果；只替换当前目录，绝不改动历史目录。

    当前目录中的同名文件优先。先在同卷临时目录完成复制，再切换目录；
    切换失败恢复当前目录。调用方必须在用户修改动作中调用，浏览不调用。
    """
    import os
    import shutil
    import tempfile
    from file_cache import remove_temporary_tree
    from contract.stage_path_service import existing_dir
    root = Path(project).resolve()
    target = write_dir(root, stage)
    origin = Path(source) if source is not None else existing_dir(root, stage)
    origin = origin.resolve()
    if not origin.is_relative_to(root) or origin == root:
        raise ValueError('历史阶段目录超出当前项目')
    if target.is_symlink() or target.resolve() != target or not target.is_relative_to(root):
        raise ValueError('阶段写入目录不能是目录联接或符号链接')
    if origin == target or not origin.is_dir():
        return target
    if target.is_relative_to(origin) or origin.is_relative_to(target):
        raise ValueError('历史与当前阶段目录不能互相包含')
    temporary = Path(tempfile.mkdtemp(prefix='.stage-copy-', dir=root))
    prepared = temporary / 'prepared'
    backup = temporary / 'previous'
    prepared.mkdir()

    def copy_files(folder, *, missing_only):
        for current, directories, files in os.walk(folder, followlinks=False):
            current = Path(current)
            for name in directories + files:
                item = current / name
                if item.is_symlink() or item.resolve() != item:
                    raise ValueError('历史阶段含目录联接或符号链接，未复制')
            relative = current.relative_to(folder)
            (prepared / relative).mkdir(parents=True, exist_ok=True)
            for name in files:
                item, destination = current / name, prepared / relative / name
                if missing_only and destination.exists():
                    continue
                before = item.stat()
                shutil.copy2(item, destination)
                after = item.stat()
                if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                    raise ValueError('复制期间历史文件变化，请停止相关编辑后重试')

    try:
        if target.is_dir():
            copy_files(target, missing_only=False)
        copy_files(origin, missing_only=True)
        if target.exists():
            target.replace(backup)
        try:
            prepared.replace(target)
        except Exception:
            if backup.exists():
                backup.replace(target)
            raise
    finally:
        # Only this call's unpublished scratch / redundant backup is removed.
        # A failed rollback leaves its backup intact for recovery.
        if not backup.exists() or target.exists():
            remove_temporary_tree(temporary)
    return target


def prepare_asset_write(project, base=None):
    from asset_context import library_dir
    from contract.stage_path_service import LEGACY_NUMBERED
    root = Path(project).resolve()
    base = library_dir(root, base)
    # 本轮编号升级不迁移用户另行配置的资产库，保留既有自定义目录契约。
    if base != root / LEGACY_NUMBERED['assets']:
        return base
    return prepare_stage_write(root, 'assets', source=base)


def prepare_legacy_asset_base(base):
    """兼容仍只接收资产库路径的 UI 操作；不推测自定义目录所属项目。"""
    from contract.stage_path_service import LEGACY_NUMBERED
    base = Path(base).resolve()
    if base.name == LEGACY_NUMBERED['assets']:
        return prepare_asset_write(base.parent, base)
    return base


def prepare_legacy_stage_path(path):
    """将显式修改目标重定位到新编号，历史文件保持只读。

    仅识别权威表中的完整旧目录名，不迁移普通目录或英文自定义目录。
    调用方保留空 source 的既有回退语义。
    """
    from contract.stage_path_service import LEGACY_NUMBERED
    if path is None:
        return None
    target = Path(path).absolute()
    stages = {name: stage for stage, name in LEGACY_NUMBERED.items()}
    for ancestor in (target, *target.parents):
        stage = stages.get(ancestor.name)
        if stage is not None:
            current = prepare_stage_write(ancestor.parent, stage, source=ancestor)
            return current / target.relative_to(ancestor)
    return path

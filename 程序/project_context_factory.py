"""L3 项目上下文装配：供编排模块共享，不依赖具体阶段执行器。"""
from pathlib import Path

import file_cache
from contract.project_context import ProjectContext
from contract.stage_path_service import write_dir


def project_context(project, *, settings_snapshot=None, cache=None):
    """固定根目录、阶段路径、设置快照及缓存；不扫描或写入项目。"""
    root = Path(project)
    return ProjectContext.snapshot(
        root, lambda stage: write_dir(root, stage), settings_snapshot,
        file_cache if cache is None else cache)

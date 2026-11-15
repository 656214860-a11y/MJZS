"""L0 项目上下文契约：由 L3 构造并注入领域服务。"""
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Callable, Mapping


@dataclass(frozen=True)
class ProjectContext:
    """一次项目操作的只读依赖快照；L2 只消费，不负责构造。"""

    root: Path
    stage_resolver: Callable[[str], Path]
    settings_snapshot: Mapping[str, Any]
    cache: Any

    @classmethod
    def snapshot(cls, root, stage_resolver, settings_snapshot=None, cache=None):
        """规范化根目录并冻结调用方提供的设置快照。"""
        return cls(Path(root), stage_resolver,
                   MappingProxyType(dict(settings_snapshot or {})), cache)

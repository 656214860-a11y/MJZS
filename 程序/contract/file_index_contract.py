# -*- coding: utf-8 -*-
"""项目文件索引的字段契约（R3093，任务书 P0 轮，DES §3.1）。

索引是**可再生的缓存**：任何时刻损坏或缺失都可以从磁盘重建，因此本契约只负责
「一行是什么」，不负责扫描、不负责写盘——扫描与写盘在 L1 ``infra.file_index``。
路径一律存项目相对 posix（与 ``storage_maintenance`` 的回收清单同一口径），
这样整个项目搬目录不需要改写索引里的路径。

``FileRow`` 用 dataclass 收十个字段（复杂度棘轮要求新代码用 dataclass 或参数对象，
不要抬高 ``test_complexity_ratchet`` 的参数登记值）。
"""
from __future__ import annotations

from dataclasses import dataclass, fields

INDEX_VERSION = 1

# DES §3.1 的字段集合与顺序；序列化按此顺序输出，便于人工 diff。
FIELDS = ('path', 'stage', 'kind', 'status', 'size', 'mtime', 'order', 'title', 'origin', 'missing')

# status 三档：草稿／定稿／归档；旧索引「已发布／已归档」读取时自动归一。
STATUS_DRAFT = '草稿'
STATUS_FINAL = '定稿'
STATUS_PUBLISHED = STATUS_FINAL
STATUS_ARCHIVED = '归档'
STATUSES = (STATUS_DRAFT, STATUS_FINAL, STATUS_ARCHIVED)
LEGACY_STATUS_MAP = {'已发布': STATUS_FINAL, '已归档': STATUS_ARCHIVED}


def normalize_status(value):
    """兼容旧索引的「已发布／已归档」写法，统一收口到「定稿／归档」。"""
    return LEGACY_STATUS_MAP.get(value, value) if isinstance(value, str) else value

# origin 三档。
ORIGIN_SYSTEM = '系统生成'
ORIGIN_USER = '用户上传'
ORIGIN_MODEL = '模型产出'
ORIGINS = (ORIGIN_SYSTEM, ORIGIN_USER, ORIGIN_MODEL)


@dataclass
class FileRow:
    """索引里的一行；字段语义见 DES §3.1。"""

    path: str
    stage: str = ''
    kind: str = '其他'
    status: str = STATUS_DRAFT
    size: int = 0
    mtime: float = 0.0
    order: int = 0
    title: str = ''
    origin: str = ORIGIN_SYSTEM
    missing: bool = False

    def to_dict(self):
        """按 ``FIELDS`` 的固定顺序输出，便于人工 diff 与下游稳定消费。"""
        return {name: getattr(self, name) for name in FIELDS}

    @classmethod
    def from_dict(cls, data):
        """宽容读取：缺字段取默认值，多字段忽略（旧索引可直接读）。"""
        row = data if isinstance(data, dict) else {}
        known = {field.name for field in fields(cls)}
        cleaned = {key: normalize_status(value) if key == 'status' else value
                   for key, value in row.items() if key in known}
        return cls(**cleaned)

    def sort_key(self):
        """侧栏的稳定排序键：阶段 id（字典序）、类型、文件内序号、路径。

        阶段**流程顺序**由索引层用 ``pet_bus.STAGES`` 处理，本契约只保证同一批
        数据在任何调用方都能排出同一个次序。
        """
        return (self.stage, self.kind, self.order, self.path)

# -*- coding: utf-8 -*-
"""会话 checkpoint 树（L2）：append-only 树 + 存引用不存内容。

借鉴 LangGraph 的 ``(thread_id, checkpoint_id, parent_id)`` append-only 树：
每个 checkpoint 一个节点，``parent_id`` 链成树；分支 = 从任意旧节点追加新节点，
**永不覆盖**原链。``state`` 只存小 JSON，产物只存 ``artifact_refs``（路径/ID），
大内容留在原产物里，避免 checkpoint 膨胀。

本模块只做内存持久化与纯查询（无 Tk、无网络、不读写盘）；落盘经 ``snapshot()``／
``restore()`` 交给 L3 的 JSON 网关。**不用 sqlite3**：随附解释器缺少 ``_sqlite3``
扩展（纯标准库精简发行版），故事件树以 JSON 快照持久化，语义一致。
"""
from __future__ import annotations

import time


SCHEMA_VERSION = 2


class CheckpointStore:
    """线程内 checkpoint 的 append-only 树；分支只追加、不覆盖。"""

    def __init__(self, data=None):
        self._items = {}
        self._threads = {}
        self._seq = 0
        if data:
            self.restore(data)

    # ---- 持久化边界（交给 L3） ----
    def restore(self, data):
        """从 ``snapshot()`` 的结构恢复。"""
        self._items = {}
        self._threads = {}
        self._seq = 0
        for item in (data or {}).get('checkpoints') or ():
            if isinstance(item, dict) and item.get('id'):
                self._items[str(item['id'])] = dict(item)
                self._seq = max(self._seq, int(item.get('seq') or 0))
        for key, value in dict((data or {}).get('threads') or {}).items():
            self._threads[str(key)] = str(value)

    def snapshot(self):
        """返回可 JSON 序列化的整体快照。"""
        return {'schema_version': SCHEMA_VERSION,
                'checkpoints': [dict(self._items[key]) for key in self._order()],
                'threads': dict(self._threads)}

    def _order(self):
        return [key for key in sorted(self._items, key=lambda key: int(self._items[key].get('seq') or 0))]

    # ---- 追加与查询 ----
    def create(self, thread_id, checkpoint_id, *, parent_id='', state=None,
               pending_request=None, artifact_refs=None):
        """追加一个 checkpoint；同 id 已存在时报错（append-only，不覆盖）。"""
        if str(checkpoint_id) in self._items:
            raise ValueError('checkpoint 已存在：%s' % checkpoint_id)
        self._seq += 1
        self._items[str(checkpoint_id)] = {
            'id': str(checkpoint_id), 'thread_id': str(thread_id),
            'parent_id': str(parent_id or ''), 'created_at': time.time(), 'seq': self._seq,
            'state': dict(state or {}),
            'pending_request': dict(pending_request) if pending_request is not None else None,
            'artifact_refs': list(artifact_refs or ()),
        }
        if not self.current(thread_id):
            self.set_current(thread_id, checkpoint_id)
        return str(checkpoint_id)

    def get(self, checkpoint_id):
        row = self._items.get(str(checkpoint_id))
        return dict(row) if row is not None else None

    def children(self, checkpoint_id):
        return [dict(self._items[key]) for key in self._order()
                if self._items[key]['parent_id'] == str(checkpoint_id)]

    def history(self, thread_id):
        return [dict(self._items[key]) for key in self._order()
                if self._items[key]['thread_id'] == str(thread_id)]

    def fork(self, thread_id, parent_id, new_id, *, state=None, artifact_refs=None):
        """从旧节点分叉出新分支：新节点 ``parent=parent_id``，原链不动。"""
        parent = self.get(parent_id)
        if parent is None:
            raise ValueError('父 checkpoint 不存在：%s' % parent_id)
        return self.create(thread_id, new_id, parent_id=parent_id,
                           state=state if state is not None else parent.get('state'),
                           artifact_refs=artifact_refs)

    def set_current(self, thread_id, checkpoint_id):
        self._threads[str(thread_id)] = str(checkpoint_id)

    def current(self, thread_id):
        return self._threads.get(str(thread_id), '')

    def prune(self, thread_id, *, keep=50):
        """只保留最近 ``keep`` 个节点；被剪掉父节点的保留节点改挂根，避免悬空引用。"""
        rows = self.history(thread_id)
        if len(rows) <= keep:
            return 0
        keep_ids = {row['id'] for row in rows[-keep:]}
        removed = [row['id'] for row in rows if row['id'] not in keep_ids]
        for checkpoint_id in removed:
            self._items.pop(checkpoint_id, None)
        for row in rows:
            if row['id'] in keep_ids and row['parent_id'] and row['parent_id'] not in keep_ids:
                self._items[row['id']]['parent_id'] = ''
        return len(removed)

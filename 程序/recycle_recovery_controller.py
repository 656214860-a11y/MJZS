"""恢复页面的无 Tk 编排：汇总项目内与项目库两个独立回收站。"""
from pathlib import Path

import recycle_recovery_service as service


class RecycleRecoveryController:
    def __init__(self, project_root, projects_root):
        roots = (project_root, projects_root)
        self._roots = tuple(dict.fromkeys(
            Path(root).resolve() for root in roots if root is not None))

    def list_batches(self):
        records = []
        for root in self._roots:
            scope = '项目内回收站' if root == self._roots[0] and len(self._roots) > 1 else '项目库回收站'
            for record in service.list_batches(root):
                record = dict(record)
                record['scope'] = scope
                records.append(record)
        return sorted(records, key=lambda item: item['batch'].name, reverse=True)

    def restore_batch(self, record):
        result = service.restore_batch(record)
        if not result.ok:
            raise ValueError(result.reason)
        return result.data

    def restore_item(self, record, source):
        result = service.restore_item(record, source)
        if not result.ok:
            raise ValueError(result.reason)
        return result.data

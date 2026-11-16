"""恢复页面的无 Tk 编排：汇总项目内与项目库两个独立回收站。"""
from pathlib import Path

import domain.recycle_recovery_service as service


class RecycleRecoveryController:
    def __init__(self, project_root, projects_root, *, register_restored=None):
        roots = (project_root, projects_root)
        self._roots = tuple(dict.fromkeys(
            Path(root).resolve() for root in roots if root is not None))
        self._projects_root = Path(projects_root).resolve() if projects_root is not None else None
        self._register_restored = register_restored

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
        self._register(record, result.data)
        return result.data

    def restore_item(self, record, source):
        result = service.restore_item(record, source)
        if not result.ok:
            raise ValueError(result.reason)
        self._register(record, result.data)
        return result.data

    def _register(self, record, restored):
        if self._register_restored is None or Path(record['root']).resolve() != self._projects_root:
            return
        projects = [path for path in restored
                    if path.parent == self._projects_root and path.is_dir()]
        if not projects:
            return
        try:
            result = self._register_restored(projects)
        except ValueError as exc:
            raise ValueError('内容已恢复，但项目登记失败：' + str(exc)) from exc
        if not result.ok:
            raise ValueError('内容已恢复，但项目登记失败：' + result.reason)

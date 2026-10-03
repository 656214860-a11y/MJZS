"""通用回收站恢复的领域服务：只投影清单，恢复仍委托唯一底层入口。"""
from pathlib import Path
import logging
from service_contract import SystemError, UserError, success

from storage_maintenance import read_recycle_batch, recycle_base, restore_recycle_batch

LOGGER = logging.getLogger(__name__)


def _restore(record, sources=None):
    root, batch = record['root'], record['batch']
    try:
        try:
            return success(restore_recycle_batch(root, batch, sources=sources))
        except ValueError as exc:
            # 底层把磁盘错误包装为 ValueError；不能误标成用户校验错误。
            if isinstance(exc.__cause__, OSError):
                raise exc.__cause__
            return UserError(str(exc))
    except OSError:
        LOGGER.exception('回收内容恢复失败')
        return SystemError('回收内容恢复失败，请检查文件权限和磁盘空间。')


def list_batches(root):
    """列出一个根目录的一级回收批次；坏清单显示为不可恢复而非猜测内容。"""
    root = Path(root).resolve()
    base = recycle_base(root)
    if not base.is_dir():
        return []
    batches = []
    for batch in base.iterdir():
        if not batch.is_dir() or batch.is_symlink() or batch.is_junction():
            continue
        try:
            record = read_recycle_batch(root, batch)
        except ValueError as exc:
            record = {'batch': batch.resolve(), 'created_at': '', 'reason': '恢复清单不可用：' + str(exc),
                      'items': [], 'unavailable': True}
        else:
            # 清单是历史事实，恢复后不改写它；列表只呈现仍在这一批次中的可恢复条目。
            record['items'] = [item for item in record['items']
                               if (root / item['recycle_path']).resolve().is_relative_to(record['batch'])
                               and (root / item['recycle_path']).is_file()
                               and not (root / item['recycle_path']).is_symlink()
                               and not (root / item['recycle_path']).is_junction()]
        record['root'] = root
        batches.append(record)
    return sorted(batches, key=lambda item: item['batch'].name, reverse=True)


def restore_batch(record):
    """恢复完整批次；安全边界由 storage_maintenance 再校验。"""
    return _restore(record)


def restore_item(record, source):
    """只恢复清单中这一原位置对应的条目，不连带同批其它用户文件。"""
    return _restore(record, sources=(source,))

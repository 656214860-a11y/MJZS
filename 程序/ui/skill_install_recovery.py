"""SKILL 换入与回收失败时使用既有发布事务和回收批次恢复。"""

from contextlib import contextmanager
import hashlib
import os
from pathlib import Path

from agent import publication
from infra.storage_maintenance import restore_recycle_batch


class ImportBlocked(ValueError):
    """导入被硬性拦截；消息可直接展示给用户。"""


def installed_version(path):
    """换入版本需区分同内容的替换，并保护包内新增的文件。"""
    if (path.is_symlink() or path.is_junction()):
        raise ImportBlocked('SKILL 目标已变成链接：%s' % path)
    nodes = [path]
    if path.is_dir():
        nodes.extend(sorted(path.rglob('*')))
    entries = []
    for node in nodes:
        if (node.is_symlink() or node.is_junction()):
            raise ImportBlocked('SKILL 包内出现链接：%s' % node)
        stat = node.stat()
        digest = None
        if node.is_file():
            with node.open('rb') as stream:
                digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        entries.append((node.relative_to(path), stat.st_dev, stat.st_ino, stat.st_size,
                        stat.st_mtime_ns, digest))
    return entries


@contextmanager
def ledger_transaction():
    original = None
    try:
        with publication.transaction():
            try:
                yield
            except BaseException as error:
                original = error
                raise
    except Exception as error:
        if original is not None and error is not original:
            raise ImportBlocked('SKILL 台账操作失败：%s。台账恢复失败：%s。'
                                '下次访问时将重试发布事务恢复。' % (original, error)) from original
        raise


def restore_skill(program, target, batch, original, *, staged=None, version=None):
    try:
        if version is not None:
            if installed_version(target) != version:
                raise ImportBlocked('目标在操作期间已被修改')
            target.rename(staged)
        elif os.path.lexists(target):
            raise ImportBlocked('恢复目标已被占用')
        if batch is not None:
            restore_recycle_batch(program, batch)
    except Exception as recovery:
        raise ImportBlocked('SKILL 操作失败：%s。恢复失败：%s。目标：%s。回收批次：%s'
                            % (original, recovery, target, batch or '无旧版')) from original


def batch_of(root, records):
    """由回收记录反推批次目录：recycle_path＝批次/原相对路径，去掉原路径的层数即批次。"""
    item = records[0]
    full = Path(root) / str(item['recycle_path'])
    return full.parents[len(Path(str(item['source'])).parts) - 1]

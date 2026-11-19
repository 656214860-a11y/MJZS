"""Recoverable publication transactions, serialized across this installation's processes.

The journal is private runtime data, never a project artifact. It is first written
when the first target enrolls; before each replacement the old version is kept (a
hard link for a plain file on the same volume, otherwise a flushed copy) and the
journal listing the old and prospective target versions is flushed. Deleting the
journal commits; a pending journal rolls back versions attributable to the transaction.
"""
from contextlib import contextmanager
import hashlib
import json
import logging
import os
from pathlib import Path
import shutil
import stat
import threading
import time
import uuid

from contract.infra_errors import ConfigError, CorruptDataError, ProcessError, StorageError

ROOT = Path(__file__).resolve().parents[1] / 'outputs' / 'publication-transactions'
_LOCK = threading.RLock()
_LOCAL = threading.local()
_LOG = logging.getLogger(__name__)


def _version(path):
    try:
        with Path(path).open('rb') as stream:
            stat = os.fstat(stream.fileno())
            digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    except FileNotFoundError:
        return None
    return [stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, digest]


def _may_restore(target, expected):
    if _version(target) != expected:
        _LOG.warning('发布恢复保留后来修改的成果：%s', target)
        return False
    return True


def _copy(source, target):
    with Path(source).open('rb') as src, Path(target).open('wb') as dst:
        shutil.copyfileobj(src, dst, 1024 * 1024)
        dst.flush()
        os.fsync(dst.fileno())


def _write(folder, record):
    temp = folder / 'journal.tmp'
    with temp.open('w', encoding='utf-8') as stream:
        json.dump(record, stream, ensure_ascii=False)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temp, folder / 'journal.json')


# 云盘占位、HSM 脱机文件的内容可能不在本机，链过去的备份未必读得回旧版，这类照旧复制。
_NOT_LOCAL = 0x400 | 0x1000 | 0x40000 | 0x400000  # REPARSE_POINT、OFFLINE、RECALL_ON_OPEN、RECALL_ON_DATA_ACCESS


def _backup(source, target):
    """留住旧版本：同卷本机普通文件建硬链接（替换只改目录项，旧内容留在链接上），否则复制并落盘。"""
    # 登记失败可能留下同名链接，必须先删掉名字；否则回退复制时会顺着链接截断原成果。
    target.unlink(missing_ok=True)
    if not os.stat(source).st_file_attributes & _NOT_LOCAL:
        try:
            os.link(source, target)
            return
        except OSError:  # 跨卷、FAT、链接数已满
            pass
    _copy(source, target)


def _commit(folder):
    # 删掉待回滚日志即提交：没有日志的事务目录恢复时按已提交丢弃。
    (folder / 'journal.json').unlink(missing_ok=True)


def _discard(folder):
    folder = folder.resolve()
    if folder.parent != ROOT.resolve() or len(folder.name) != 32:
        raise ConfigError('非法发布事务目录，已停止清理')
    int(folder.name, 16)
    from infra.file_cache import remove_temporary_tree
    remove_temporary_tree(folder)
    if folder.exists():
        raise StorageError('发布事务临时目录清理未完成：' + str(folder), detail=str(folder))


def _recover(folder):
    journal = folder / 'journal.json'
    if not journal.exists():
        # 还没登记（日志落盘前不替换任何目标），或已提交（日志已删）：都没有旧版要恢复。
        _discard(folder)
        return
    try:
        record = json.loads(journal.read_text(encoding='utf-8'))
        version = record['version']
        if version not in (1, 2) or record['state'] not in ('pending', 'committed', 'rolled_back'):
            raise ValueError('unsupported transaction')
        entries = record['entries']
        for index, entry in enumerate(entries):
            target = Path(entry['target'])
            if not target.is_absolute() or entry['backup'] != str(index):
                raise ValueError('invalid transaction path')
            if 'recycled' in entry:
                if version != 2 or not Path(entry['recycled']).is_absolute() or not entry['original']:
                    raise ValueError('invalid recycle entry')
            elif record['state'] == 'pending' and entry['existed'] and not (folder / str(index)).is_file():
                raise ValueError('missing backup')
            if version == 2:
                for key in ('original', 'prior', 'replacement'):
                    stamp = entry[key]
                    if stamp is not None and (not isinstance(stamp, list) or len(stamp) != 5
                                              or any(type(part) is not int for part in stamp[:4])
                                              or not isinstance(stamp[4], str) or len(stamp[4]) != 64):
                        raise ValueError('invalid artifact version')
    except (KeyError, TypeError, ValueError, OSError) as exc:
        raise ProcessError('发布事务日志损坏，已停止读取以保护旧成果：' + str(folder), detail=str(folder)) from exc
    if record['state'] == 'pending':
        if version == 1 and entries:
            raise ProcessError('旧版发布日志缺少目标版本，已保留备份，需核对成果后恢复：' + str(folder), detail=str(folder))
        for entry in reversed(entries):
            target = Path(entry['target'])
            if 'recycled' in entry:
                _recover_recycled(target, Path(entry['recycled']), entry['original'])
                continue
            current = _version(target)
            if current == entry['original']:
                continue
            if current not in (entry['prior'], entry['replacement']):
                _LOG.warning('发布恢复保留后来修改的成果：%s', target)
                continue
            if entry['existed']:
                target.parent.mkdir(parents=True, exist_ok=True)
                temp = target.with_name(target.name + '.' + uuid.uuid4().hex + '.recover')
                try:
                    _copy(folder / entry['backup'], temp)
                    if not _may_restore(target, current):
                        continue
                    os.replace(temp, target)
                finally:
                    temp.unlink(missing_ok=True)
            else:
                target.unlink(missing_ok=True)
            from infra.file_cache import published
            published(target)
        record['state'] = 'rolled_back'
        _write(folder, record)
    _discard(folder)


def _recover_recycled(target, recycled, original):
    # A missing original alone proves nothing. Windows rename also refuses
    # to overwrite a target that appears after this check.
    if (os.path.lexists(target) or target.parent.resolve() != target.parent
            or recycled.resolve() != recycled):
        return
    try:
        regular = stat.S_ISREG(recycled.lstat().st_mode)
        parent_exists = stat.S_ISDIR(target.parent.stat().st_mode)
    except FileNotFoundError:
        return
    if not regular or not parent_exists or _version(recycled) != original:
        return
    try:
        recycled.rename(target)
    except FileExistsError:
        return
    from infra.file_cache import published
    published(target)
    published(recycled)


def recycle_file(source, destination):
    """Enroll a same-volume, no-overwrite move in the active publication."""
    active = getattr(_LOCAL, 'active', None)
    if active is None:
        raise ProcessError('回收移动需要发布事务')
    folder, record = active
    source, destination = Path(source), Path(destination)
    if source.resolve() != source or destination.resolve() != destination or not source.is_file():
        raise ConfigError('回收移动只接受普通文件及真实路径：' + str(source))
    original = _version(source)
    if original is None:
        raise FileNotFoundError(source)
    record['entries'].append({'target': str(source), 'backup': str(len(record['entries'])),
                              'existed': True, 'original': original, 'prior': original,
                              'replacement': None, 'recycled': str(destination)})
    _write(folder, record)
    if not _may_restore(source, original):
        raise ProcessError('回收前源文件已被修改：' + str(source), detail=str(source))
    source.rename(destination)


@contextmanager
def _file_access(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'a+b') as stream:
        if stream.seek(0, 2) == 0:
            stream.write(b'0')
            stream.flush()
        if os.name != 'nt':
            raise ProcessError('发布事务锁仅支持随附的 Windows 运行环境')
        import msvcrt
        deadline = time.monotonic() + 30
        while True:
            try:
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                break
            except OSError as exc:
                if time.monotonic() >= deadline:
                    raise ProcessError('发布事务忙，未读取或覆盖未提交成果') from exc
                time.sleep(0.01)
        try:
            yield
        finally:
            stream.seek(0)
            msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)


@contextmanager
def access(*, lock_path=None):
    """Serialize access and recover stale publication transactions for the default lock."""
    if lock_path is not None:
        with _file_access(Path(lock_path)):
            yield
        return
    with _LOCK:
        if getattr(_LOCAL, 'depth', 0):
            _LOCAL.depth += 1
            try:
                yield
            finally:
                _LOCAL.depth -= 1
            return
        with _file_access(ROOT / 'writer.lock'):
            _LOCAL.depth = 1
            try:
                for folder in ROOT.iterdir():
                    if folder.is_dir() and len(folder.name) == 32:
                        _recover(folder)
                yield
            finally:
                _LOCAL.depth = 0


def before_replace(target, source=None):
    """Record the prospective version before replacing or unlinking a target."""
    active = getattr(_LOCAL, 'active', None)
    if active is None:
        return
    folder, record = active
    target = Path(target).resolve()
    if target.exists() and not target.is_file():
        raise ConfigError('成果目标不是普通文件')
    prior = _version(target)
    replacement = None if source is None else _version(source)
    if source is not None and replacement is None:
        raise FileNotFoundError(source)
    for item in record['entries']:
        if item['target'] == str(target):
            if prior not in (item['prior'], item['replacement']):
                raise ProcessError('成果在发布期间已被修改：' + str(target), detail=str(target))
            item.update(prior=prior, replacement=replacement)
            _write(folder, record)
            return
    index = str(len(record['entries']))
    existed = prior is not None
    if existed:
        _backup(target, folder / index)
    record['entries'].append({'target': str(target), 'backup': index, 'existed': existed,
                              'original': prior, 'prior': prior, 'replacement': replacement})
    _write(folder, record)


@contextmanager
def transaction():
    with access():
        if getattr(_LOCAL, 'active', None) is not None:
            # Inner publication belongs to the outer commit, including its index.
            try:
                yield
            except BaseException:
                _LOCAL.active[1]['rollback_only'] = True
                raise
            return
        folder = ROOT / uuid.uuid4().hex
        folder.mkdir()
        record = {'version': 2, 'state': 'pending', 'entries': []}
        _LOCAL.active = (folder, record)
        try:
            yield
            if record.get('rollback_only'):
                raise ProcessError('嵌套发布失败，整包成果已回滚')
            _commit(folder)
        except BaseException:
            _LOCAL.active = None
            _recover(folder)
            raise
        finally:
            _LOCAL.active = None
        # 成果已提交：清理事务目录失败不能让调用方误判为发布失败。
        # 残留目录已没有日志，下一次 access() 里会按已提交再清一遍。
        try:
            _discard(folder)
        except OSError:
            _LOG.warning('发布事务临时目录清理未完成，下次访问时重试：%s', folder)


def recover_pending():
    if ROOT.exists():
        with access():
            pass

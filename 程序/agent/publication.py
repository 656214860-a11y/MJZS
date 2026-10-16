"""Recoverable publication transactions, serialized across this installation's processes.

The journal is private runtime data, never a project artifact. Backups and the
journal are flushed before each target replacement. A committed marker selects
the new version; otherwise readers recover the old version before opening files.
"""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import shutil
import threading
import time
import uuid

ROOT = Path(__file__).resolve().parents[1] / 'outputs' / 'publication-transactions'
_LOCK = threading.RLock()
_LOCAL = threading.local()


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


def _discard(folder):
    folder = folder.resolve()
    if folder.parent != ROOT.resolve() or len(folder.name) != 32:
        raise RuntimeError('非法发布事务目录，已停止清理')
    int(folder.name, 16)
    from file_cache import remove_temporary_tree
    remove_temporary_tree(folder)
    if folder.exists():
        raise OSError('发布事务临时目录清理未完成：' + str(folder))


def _recover(folder):
    journal = folder / 'journal.json'
    if not journal.exists():
        # No target may be changed before the first journal is durable.
        _discard(folder)
        return
    try:
        record = json.loads(journal.read_text(encoding='utf-8'))
        if record['version'] != 1 or record['state'] not in ('pending', 'committed', 'rolled_back'):
            raise ValueError('unsupported transaction')
        entries = record['entries']
        for index, entry in enumerate(entries):
            target = Path(entry['target'])
            if not target.is_absolute() or entry['backup'] != str(index):
                raise ValueError('invalid transaction path')
            if record['state'] == 'pending' and entry['existed'] and not (folder / str(index)).is_file():
                raise ValueError('missing backup')
    except (KeyError, TypeError, ValueError, OSError) as exc:
        raise RuntimeError('发布事务日志损坏，已停止读取以保护旧成果：' + str(folder)) from exc
    if record['state'] == 'pending':
        for entry in reversed(entries):
            target = Path(entry['target'])
            if entry['existed']:
                target.parent.mkdir(parents=True, exist_ok=True)
                temp = target.with_name(target.name + '.' + uuid.uuid4().hex + '.recover')
                try:
                    _copy(folder / entry['backup'], temp)
                    os.replace(temp, target)
                finally:
                    temp.unlink(missing_ok=True)
            else:
                target.unlink(missing_ok=True)
            from file_cache import published
            published(target)
        record['state'] = 'rolled_back'
        _write(folder, record)
    _discard(folder)


@contextmanager
def access():
    """Block conflicting readers/writers; recover stale transactions once locked."""
    with _LOCK:
        if getattr(_LOCAL, 'depth', 0):
            _LOCAL.depth += 1
            try:
                yield
            finally:
                _LOCAL.depth -= 1
            return
        ROOT.mkdir(parents=True, exist_ok=True)
        with open(ROOT / 'writer.lock', 'a+b') as stream:
            if stream.seek(0, 2) == 0:
                stream.write(b'0')
                stream.flush()
            if os.name != 'nt':
                raise RuntimeError('发布事务锁仅支持随附的 Windows 运行环境')
            import msvcrt
            deadline = time.monotonic() + 30
            while True:
                try:
                    stream.seek(0)
                    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                    break
                except OSError as exc:
                    if time.monotonic() >= deadline:
                        raise RuntimeError('发布事务忙，未读取或覆盖未提交成果') from exc
                    time.sleep(0.01)
            _LOCAL.depth = 1
            try:
                for folder in ROOT.iterdir():
                    if folder.is_dir() and len(folder.name) == 32:
                        _recover(folder)
                yield
            finally:
                _LOCAL.depth = 0
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)


def before_replace(target):
    """Enroll each artifact/index written by core.replace in the active transaction."""
    active = getattr(_LOCAL, 'active', None)
    if active is None:
        return
    folder, record = active
    target = Path(target).resolve()
    if any(item['target'] == str(target) for item in record['entries']):
        return
    index = str(len(record['entries']))
    existed = target.is_file()
    if target.exists() and not existed:
        raise ValueError('成果目标不是普通文件')
    if existed:
        _copy(target, folder / index)
    record['entries'].append({'target': str(target), 'backup': index, 'existed': existed})
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
        record = {'version': 1, 'state': 'pending', 'entries': []}
        _write(folder, record)
        _LOCAL.active = (folder, record)
        try:
            yield
            if record.get('rollback_only'):
                raise RuntimeError('嵌套发布失败，整包成果已回滚')
            record['state'] = 'committed'
            _write(folder, record)
        except BaseException:
            _LOCAL.active = None
            _recover(folder)
            raise
        finally:
            _LOCAL.active = None
        _discard(folder)


def recover_pending():
    if ROOT.exists():
        with access():
            pass

"""按文件签名与内容哈希记忆 JSON／文本读取结果。

分镜表、镜头列表、内容预览会在每次页面重排、每次选中变化、每 1.5 秒的文件轮询里
各自读同一个 JSON；一个 60 镜的分镜稿会被解析 3 次以上。这里按文件签名缓存，
读缓存验证文件身份及变更时间。应用发布和外部适配器也可显式失效缓存。
每次返回一份新拷贝（只拷 dict／list 骨架，比重新解析便宜）：调用方改了也不会污染缓存。
"""
import ctypes
import hashlib
import json
import os
import shutil
import struct
import sys
import tempfile
from threading import RLock
from collections import OrderedDict
from itertools import chain
from pathlib import Path
from contract.infra_errors import CorruptDataError, StorageError
from agent.core import read  # read：兼容仍由外部替换的历史测试钩子。
from agent.publication import access


def _key(path):
    return os.path.normcase(os.path.abspath(str(path)))

_ENTRY_LIMIT = 64
_CONTENT_BUDGET = 8 * 1024 * 1024
_DIGEST_BUDGET = 64 * 1024
_CACHE_LOCK = RLock()
_epoch = 0


class _BoundedCache(OrderedDict):
    """调用者持有 _CACHE_LOCK；权重涵盖缓存保留的键、元数据与值。"""

    def __init__(self, limit, budget):
        super().__init__()
        self.limit = limit
        self.budget = budget
        self.weight = 0

    def discard(self, key):
        entry = self.pop(key, None)
        if entry is None:
            return False
        self.weight -= entry[-1]
        return True

    def put(self, key, token, digest, value, weight):
        self.discard(key)
        if weight > self.budget:
            return
        self[key] = (token, digest, value, weight)
        self.weight += weight
        while len(self) > self.limit or self.weight > self.budget:
            _, entry = self.popitem(last=False)
            self.weight -= entry[-1]

    def clear(self):
        super().clear()
        self.weight = 0


def _weight(limit, *values):
    size = 256  # OrderedDict 节点、条目元组及记账开销的预留。
    levels = [iter(values)]
    while levels and size <= limit:
        value = next(levels[-1], _END)
        if value is _END:
            levels.pop()
            continue
        size += sys.getsizeof(value)
        if isinstance(value, dict):
            levels.append(chain(value.keys(), value.values()))
        elif isinstance(value, (tuple, list)):
            levels.append(iter(value))
    return size


_END = object()


_CACHE = _BoundedCache(_ENTRY_LIMIT, _CONTENT_BUDGET)
_TEXT_CACHE = _BoundedCache(32, _CONTENT_BUDGET)
_BYTES_CACHE = _BoundedCache(32, _CONTENT_BUDGET)
_DIGEST_CACHE = _BoundedCache(_ENTRY_LIMIT, _DIGEST_BUDGET)


if os.name == 'nt':
    from ctypes import wintypes

    class _FileBasicInfo(ctypes.Structure):
        _fields_ = [('created', ctypes.c_int64), ('accessed', ctypes.c_int64),
                    ('modified', ctypes.c_int64), ('changed', ctypes.c_int64),
                    ('attributes', wintypes.DWORD)]

    class _FileStandardInfo(ctypes.Structure):
        _fields_ = [('allocation', ctypes.c_int64), ('size', ctypes.c_int64),
                    ('links', wintypes.DWORD), ('pending', ctypes.c_ubyte),
                    ('directory', ctypes.c_ubyte)]

    class _FileIdInfo(ctypes.Structure):
        _fields_ = [('volume', ctypes.c_uint64), ('file_id', ctypes.c_ubyte * 16)]

    _kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    _open_attributes = _kernel.CreateFileW
    _open_attributes.argtypes = (wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                 wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD,
                                 wintypes.HANDLE)
    _open_attributes.restype = wintypes.HANDLE
    _query_info = _kernel.GetFileInformationByHandleEx
    _query_info.argtypes = (wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID,
                            wintypes.DWORD)
    _query_info.restype = wintypes.BOOL
    _device_control = _kernel.DeviceIoControl
    _device_control.argtypes = (wintypes.HANDLE, wintypes.DWORD, wintypes.LPVOID,
                                wintypes.DWORD, wintypes.LPVOID, wintypes.DWORD,
                                ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID)
    _device_control.restype = wintypes.BOOL
    _close_handle = _kernel.CloseHandle
    _close_handle.argtypes = (wintypes.HANDLE,)
    _close_handle.restype = wintypes.BOOL
    _INVALID_HANDLE = ctypes.c_void_p(-1).value


def _windows_usn(handle):
    """查询该文件最新的 USN。时间戳在 Windows 上可能因时钟粒度碰撞。"""
    versions = struct.pack('<HH', 2, 3)
    record = ctypes.create_string_buffer(1024)
    returned = wintypes.DWORD()
    # FSCTL_READ_FILE_USN_DATA，返回 USN_RECORD_V2 或 V3。
    if not _device_control(handle, 0x900EB, versions, len(versions), record,
                           len(record), ctypes.byref(returned), None):
        return None
    version = struct.unpack_from('<H', record, 4)[0]
    if version == 2 and returned.value >= 32:
        return struct.unpack_from('<q', record, 24)[0] or None
    if version == 3 and returned.value >= 48:
        return struct.unpack_from('<q', record, 40)[0] or None
    return None


def _signature(path):
    if os.name != 'nt':
        stat = path.stat()
        return stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns

    # FILE_READ_ATTRIBUTES, share read/write/delete, OPEN_EXISTING.
    # Python 的 Windows st_ctime 可能是创建时间，普通 stat 不暴露 ChangeTime。
    handle = _open_attributes(os.fspath(path), 0x80, 7, None, 3, 0x02000000, None)
    if handle == _INVALID_HANDLE:
        path.stat()  # 保留 Python 对缺失路径等错误的异常类型。
        return None
    try:
        basic, standard, identity = _FileBasicInfo(), _FileStandardInfo(), _FileIdInfo()
        if (_query_info(handle, 0, ctypes.byref(basic), ctypes.sizeof(basic))
                and _query_info(handle, 1, ctypes.byref(standard), ctypes.sizeof(standard))
                and _query_info(handle, 18, ctypes.byref(identity), ctypes.sizeof(identity))
                and basic.changed and any(identity.file_id)):
            usn = _windows_usn(handle)
            if usn is not None:
                return (identity.volume, bytes(identity.file_id), standard.size,
                        basic.modified, basic.changed, usn)
        # 意外不支持强签名的文件系统走读盘，不能降级为按 size/mtime 命中。
        return None
    finally:
        _close_handle(handle)


def _lookup(cache, key, path):
    with _CACHE_LOCK:
        epoch = _epoch
    try:
        token = _signature(path)
    except OSError:
        with _CACHE_LOCK:
            cache.discard(key)
        raise
    with _CACHE_LOCK:
        hit = cache.get(key)
        if epoch == _epoch and token is not None and hit is not None and hit[0] == token:
            cache.move_to_end(key)
            return token, hit, epoch
        return token, None, epoch


def _store(cache, key, token, epoch, digest, value):
    if token is None:
        return
    weight = _weight(cache.budget, key, token, digest, value)
    with _CACHE_LOCK:
        if epoch == _epoch:
            cache.put(key, token, digest, value, weight)


def _read_through(cache, key, path, parse):
    path = Path(path)
    for _ in range(3):
        token, hit, epoch = _lookup(cache, key, path)
        if hit is not None:
            return hit[2]
        with _CACHE_LOCK:
            previous = cache.get(key)
        raw = path.read_bytes()
        if token is None:
            return parse(raw)
        if token != _signature(path):
            continue
        digest = hashlib.sha256(raw).digest()
        try:
            value = previous[2] if previous is not None and previous[1] == digest else parse(raw)
        except (ValueError, RecursionError):
            with _CACHE_LOCK:
                if cache.get(key) is previous:
                    cache.discard(key)
            raise
        _store(cache, key, token, epoch, digest, value)
        return value
    raise StorageError(f'读取期间文件持续变化：{path}', code='E-IO-READ', detail=str(path))


def _json_copy(value):
    """JSON 树的结构拷贝：叶子都是不可变的 str/数字/None，只需重建 dict 与 list。"""
    if isinstance(value, dict):
        return {key: _json_copy(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_copy(item) for item in value]
    return value


@access()
def read_json(path):
    return _json_copy(_read_through(_CACHE, _key(path), path, json.loads))


def read_json_shared(path):
    """共享只读 JSON。身份和变更时间一致时跳过发布事务锁。"""
    path = Path(path)
    key = _key(path)
    try:
        _, hit, _ = _lookup(_CACHE, key, path)
    except OSError:
        # 发布事务可能留下待恢复的正式路径，由慢路径先恢复。
        hit = None
    if hit is not None:
        return hit[2]
    return _locked_json_shared(path, key)


@access()
def _locked_json_shared(path, key):
    return _read_through(_CACHE, key, path, json.loads)


@access()
def read_text(path, encoding='utf-8-sig', errors=None):
    """读取用于 UI 预览的文本，并在文件未变时复用结果。"""
    return _read_through(_TEXT_CACHE, (_key(path), encoding, errors), path,
                         lambda raw: raw.decode(encoding, errors=errors or 'strict'))


@access()
def read_bytes(path):
    """读取大文本的原始字节并按文件签名复用，供编码探测类预览使用。"""
    return _read_through(_BYTES_CACHE, _key(path), path, bytes)


@access()
def path_key(path):
    """路径的短指纹（resolve＋casefold 后 sha1 前 16 位），用作「每个项目一份」的本机文件名。"""
    return hashlib.sha1(str(Path(path).resolve()).casefold().encode('utf-8')).hexdigest()[:16]


def file_digest(path):
    """流式计算 SHA-256，缓存中仅保留摘要与文件签名。"""
    path = Path(path)
    key = _key(path)
    for _ in range(3):
        token, hit, epoch = _lookup(_DIGEST_CACHE, key, path)
        if hit is not None:
            return hit[2]
        digest = hashlib.sha256()
        with path.open('rb') as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b''):
                digest.update(block)
        if token is not None and token != _signature(path):
            continue
        value = digest.hexdigest()
        _store(_DIGEST_CACHE, key, token, epoch, None, value)
        return value
    raise StorageError(f'计算摘要期间文件持续变化：{path}', code='E-IO-READ', detail=str(path))


@access()
def read_stable_json_snapshot(path):
    """读取写入中的工作 JSON，并确认本次读取前后文件签名没有变化。

    这类工作文件不能复用缓存：调用方需要原始字节、末次 stat，且必须拒绝
    正在被外部流程覆盖的半份内容。因此把完整性边界集中在这里，而非让
    service 自行读文件并解析 JSON。
    """
    path = Path(path)
    before = path.stat()
    raw = path.read_bytes()
    after = path.stat()
    if (before.st_mtime_ns, before.st_size) != (after.st_mtime_ns, after.st_size):
        raise CorruptDataError('文件正在写入', detail=str(path))
    return json.loads(raw.decode('utf-8-sig')), raw, after


def clear():
    global _epoch
    with _CACHE_LOCK:
        _epoch += 1
        for cache in (_CACHE, _TEXT_CACHE, _BYTES_CACHE, _DIGEST_CACHE):
            cache.clear()


def invalidate(path):
    """丢弃某一正式路径的所有读取缓存，返回是否确实命中过缓存。"""
    global _epoch
    key = _key(path)
    with _CACHE_LOCK:
        _epoch += 1
        removed = _CACHE.discard(key)
        removed = _BYTES_CACHE.discard(key) or removed
        removed = _DIGEST_CACHE.discard(key) or removed
        for text_key in tuple(_TEXT_CACHE):
            if text_key[0] == key:
                removed = _TEXT_CACHE.discard(text_key) or removed
        return removed


def published(path):
    """正式成果原子发布完成事件：下一次读取必须重新取磁盘内容。"""
    return invalidate(path)


def recycled(paths):
    """用户成果移入回收站事件，同时失效移出和移入两个路径。

    ``paths`` 接受 ``(source, recycle_path)`` 对；恢复时也可传入
    ``(recycle_path, restored_path)``，因此同一事件原语不会遗漏旧路径。
    """
    removed = False
    for source, target in paths:
        removed = invalidate(source) or removed
        removed = invalidate(target) or removed
    return removed


def externally_overwritten(path):
    """外部导入/覆盖完成事件，供不经过 ``agent.core`` 的适配器显式调用。"""
    return invalidate(path)


def remove_temporary_file(path):
    """清理调用方刚创建的临时文件或可再生缓存；失败保持静默。"""
    try:
        Path(path).unlink(missing_ok=True)
        return True
    except OSError:
        return False


def probe_writable(path, *, create=True):
    """检查目录能否落文件：试建（可选）并写一个探针文件，成功即删除。

    这是「先问能不能写」的最小主机适配。目录不存在时 ``create=False`` 只看最近一个已存在
    父目录，不建任何目录；失败原样抛 ``OSError``，由调用方翻成用户提示。实际写入留在这一层，
    领域服务（L2）不直接写盘。
    """
    path = Path(path); target = path
    if not path.exists():
        if not create:
            for parent in path.parents:
                if parent.exists():
                    target = parent
                    break
            else:
                raise FileNotFoundError(2, '路径所在盘符或目录不存在', str(path))
        else:
            path.mkdir(parents=True, exist_ok=True)
            target = path
    descriptor, temporary = tempfile.mkstemp(prefix='.write-probe-', dir=str(target))
    os.close(descriptor)
    remove_temporary_file(temporary)
    return True


def remove_temporary_tree(path):
    """删除调用方刚创建的临时目录；不接受用户项目目录的清理职责。"""
    try:
        shutil.rmtree(Path(path), ignore_errors=True)
        return True
    except OSError:
        return False

"""按文件签名与内容哈希记忆 JSON／文本读取结果。

分镜表、镜头列表、内容预览会在每次页面重排、每次选中变化、每 1.5 秒的文件轮询里
各自读同一个 JSON；一个 60 镜的分镜稿会被解析 3 次以上。这里按文件签名缓存，
文件一旦被 save() 覆盖（mtime/大小变化）自动失效，所以不会读到旧内容。
返回的是共享对象，调用方只读、不得修改（需要改的用 agent.core.read 重新读）。
"""
import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path
from agent.core import read  # 兼容仍由外部替换的历史测试钩子。


def _key(path):
    return os.path.normcase(os.path.abspath(str(path)))

_CACHE = {}
_TEXT_CACHE = {}
_BYTES_CACHE = {}
_DIGEST_CACHE = {}


def _digest(data):
    return hashlib.sha256(data).digest()


def _cached_content(cache, key, token, data):
    """签名变动后仅在内容真的变了时才丢弃已解析的对象。"""
    digest = _digest(data)
    hit = cache.get(key)
    if hit is not None and hit[1] == digest:
        cache[key] = (token, digest, hit[2])
        return hit[2]
    return None


def read_json(path):
    key = _key(path)
    try:
        stat = Path(path).stat()
    except OSError:
        _CACHE.pop(key, None)
        raise
    token = (stat.st_mtime_ns, stat.st_size)
    hit = _CACHE.get(key)
    if hit is not None and hit[0] == token:
        return hit[2]
    raw = Path(path).read_bytes()
    cached = _cached_content(_CACHE, key, token, raw)
    if cached is not None:
        return cached
    data = json.loads(raw)
    _CACHE[key] = (token, _digest(raw), data)
    return data


def read_text(path, encoding='utf-8-sig', errors=None):
    """读取用于 UI 预览的文本，并在文件未变时复用结果。"""
    key = (_key(path), encoding, errors)
    try:
        stat = Path(path).stat()
    except OSError:
        _TEXT_CACHE.pop(key, None)
        raise
    token = (stat.st_mtime_ns, stat.st_size)
    hit = _TEXT_CACHE.get(key)
    if hit is not None and hit[0] == token:
        return hit[2]
    raw = Path(path).read_bytes()
    cached = _cached_content(_TEXT_CACHE, key, token, raw)
    if cached is not None:
        return cached
    data = raw.decode(encoding, errors=errors or 'strict')
    _TEXT_CACHE[key] = (token, _digest(raw), data)
    return data


def read_bytes(path):
    """读取大文本的原始字节并按文件签名复用，供编码探测类预览使用。"""
    key = _key(path)
    try:
        stat = Path(path).stat()
    except OSError:
        _BYTES_CACHE.pop(key, None)
        raise
    token = (stat.st_mtime_ns, stat.st_size)
    hit = _BYTES_CACHE.get(key)
    if hit is not None and hit[0] == token:
        return hit[2]
    data = Path(path).read_bytes()
    cached = _cached_content(_BYTES_CACHE, key, token, data)
    if cached is not None:
        return cached
    _BYTES_CACHE[key] = (token, _digest(data), data)
    return data


def file_digest(path):
    """流式 sha256 校验和（十六进制），按文件签名缓存；从不把整份文件读进内存。

    animatic 这类成果含整段视频与音频，反复校验时若用 read_bytes＋sha256 会把大媒体
    整份读进内存。这里只按 1 MiB 块喂给 sha256，并按 (mtime_ns, size) 复用上一次结果，
    未改动的大文件不会重复计算。
    """
    path = Path(path)
    key = _key(path)
    try:
        stat = path.stat()
    except OSError:
        _DIGEST_CACHE.pop(key, None)
        raise
    token = (stat.st_mtime_ns, stat.st_size)
    hit = _DIGEST_CACHE.get(key)
    if hit is not None and hit[0] == token:
        return hit[1]
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(block)
    value = digest.hexdigest()
    _DIGEST_CACHE[key] = (token, value)
    return value


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
        raise ValueError('文件正在写入')
    return json.loads(raw.decode('utf-8-sig')), raw, after


def clear():
    _CACHE.clear()
    _TEXT_CACHE.clear()
    _BYTES_CACHE.clear()
    _DIGEST_CACHE.clear()


def invalidate(path):
    """丢弃某一正式路径的所有读取缓存，返回是否确实命中过缓存。

    这是缓存一致性的唯一失效原语。调用方不得靠重建页面或修改缓存字典来让
    新成果可见；文件生命周期边界应改用下面带业务语义的三个事件。
    """
    key = _key(path)
    removed = _CACHE.pop(key, None) is not None
    removed = _BYTES_CACHE.pop(key, None) is not None or removed
    removed = _DIGEST_CACHE.pop(key, None) is not None or removed
    for text_key in tuple(_TEXT_CACHE):
        if text_key[0] == key:
            _TEXT_CACHE.pop(text_key, None)
            removed = True
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

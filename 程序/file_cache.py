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
from pathlib import Path
from agent.core import read  # 兼容仍由外部替换的历史测试钩子。


def _key(path):
    return os.path.normcase(os.path.abspath(str(path)))

_CACHE = {}
_TEXT_CACHE = {}
_BYTES_CACHE = {}


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


def clear():
    _CACHE.clear()
    _TEXT_CACHE.clear()
    _BYTES_CACHE.clear()


def invalidate(path):
    """丢弃某一正式路径的所有读取缓存，返回是否确实命中过缓存。

    这是缓存一致性的唯一失效原语。调用方不得靠重建页面或修改缓存字典来让
    新成果可见；文件生命周期边界应改用下面带业务语义的三个事件。
    """
    key = _key(path)
    removed = _CACHE.pop(key, None) is not None
    removed = _BYTES_CACHE.pop(key, None) is not None or removed
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


def remove_temporary_tree(path):
    """删除调用方刚创建的临时目录；不接受用户项目目录的清理职责。"""
    try:
        shutil.rmtree(Path(path), ignore_errors=True)
        return True
    except OSError:
        return False

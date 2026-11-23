"""共享锁的租约：持有者每 30 秒刷新心跳，静默满 3 分钟才允许回收。

打不开进程不算死亡。没有 heartbeat_at 的旧锁才退回调用方给出的 PID 判断，
或者退回 created_at／started_at 的年龄。回收前核对文件身份，避免删掉刚换上的新锁。
持有者一直开着文件句柄，活进程在 Windows 上删不掉自己的锁。
"""
from __future__ import annotations

import io
import json
import os
import secrets
import threading
import time


LOCK_HEARTBEAT_SECONDS = 30.0
LOCK_STALE_SECONDS = 180.0

_GUARD = threading.Lock()
_HELD: dict[str, tuple[int, threading.Event, threading.Thread]] = {}


def payload(pid: int, **extra: object) -> dict:
    """新锁的正文。heartbeat_at 从创建时起算，线程随后每 30 秒刷新。"""
    now = time.time()
    body = {
        "pid": pid,
        "token": secrets.token_hex(16),
        "heartbeat_at": now,
        "created_at": now,
        "started_at": now,
    }
    body.update(extra)
    return body


def is_live(holder, now=None, legacy_pid_alive=None) -> bool:
    """心跳还在 3 分钟内就是活的，不再看进程句柄能不能打开。"""
    now = time.time() if now is None else now
    if not isinstance(holder, dict) or not holder:
        return False
    beat = holder.get("heartbeat_at")
    if beat is not None:
        try:
            return (now - float(beat)) < LOCK_STALE_SECONDS
        except (TypeError, ValueError):
            return False
    if legacy_pid_alive is not None:
        started = holder.get("started_at")
        if started is None:
            started = holder.get("created_at")
        return bool(legacy_pid_alive(holder.get("pid"), started))
    for key in ("created_at", "started_at"):
        if holder.get(key) is None:
            continue
        try:
            return (now - float(holder[key])) < LOCK_STALE_SECONDS
        except (TypeError, ValueError):
            return False
    return False


def _identity(snapshot) -> tuple:
    """不含访问时间：读一次锁就会改 atime，不能把它当成文件被换掉。"""
    return (snapshot.st_dev, snapshot.st_ino, snapshot.st_size,
            getattr(snapshot, "st_mtime_ns", snapshot.st_mtime))


def _read(path):
    with io.open(path, encoding="utf-8") as handle:
        text = handle.read()
    if not text.strip():
        raise ValueError("empty lock")
    holder, _end = json.JSONDecoder().raw_decode(text)
    if not isinstance(holder, dict):
        raise ValueError("lock is not an object")
    return holder


def inspect(path, legacy_pid_alive=None):
    """返回 missing／live／stale／unknown、锁正文、以及读到时的 stat。"""
    try:
        before = os.stat(path)
    except FileNotFoundError:
        return "missing", {}, None
    except PermissionError:
        return "unknown", {}, None
    try:
        holder = _read(path)
        after = os.stat(path)
    except FileNotFoundError:
        return "missing", {}, None
    except OSError:
        return "unknown", {}, before
    except ValueError:
        try:
            after = os.stat(path)
        except FileNotFoundError:
            return "missing", {}, None
        if _identity(after) != _identity(before):
            return "unknown", {}, after
        age = time.time() - after.st_mtime
        state = "stale" if age >= LOCK_STALE_SECONDS else "unknown"
        return state, {}, after
    if _identity(after) != _identity(before):
        return "unknown", {}, after
    if is_live(holder, legacy_pid_alive=legacy_pid_alive):
        return "live", holder, after
    return "stale", holder, after


def reclaim(path, legacy_pid_alive=None) -> bool:
    """静默锁且文件仍是刚才那一个时删除。删不掉视为仍被占用。文件已不在也算回收完成。"""
    state, _holder, snapshot = inspect(path, legacy_pid_alive=legacy_pid_alive)
    if state == "missing":
        return True
    if state != "stale" or snapshot is None:
        return False
    try:
        if _identity(os.stat(path)) != _identity(snapshot):
            return False
        os.unlink(path)
        return True
    except FileNotFoundError:
        return True
    except OSError:
        return False


def _key(path) -> str:
    return os.path.normcase(os.path.abspath(path))


def _beat(path: str, fd: int, token: str, stop: threading.Event) -> None:
    while not stop.wait(LOCK_HEARTBEAT_SECONDS):
        try:
            holder = _read(path)
        except (OSError, ValueError):
            return
        if holder.get("token") != token:
            return
        holder["heartbeat_at"] = time.time()
        data = json.dumps(holder, ensure_ascii=False).encode("utf-8")
        try:
            os.lseek(fd, 0, os.SEEK_SET)
            os.write(fd, data)
        except OSError:
            return


def arm(path) -> None:
    """记下句柄并启动心跳。没有 token 的旧锁不接管。重复调用无效果。"""
    key = _key(path)
    with _GUARD:
        if key in _HELD:
            return
        try:
            holder = _read(key)
        except (OSError, ValueError):
            return
        token = holder.get("token")
        if not token:
            return
        flags = os.O_RDWR
        if hasattr(os, "O_BINARY"):
            flags |= os.O_BINARY
        try:
            fd = os.open(key, flags)
        except OSError:
            return
        stop = threading.Event()
        thread = threading.Thread(
            target=_beat, args=(key, fd, token, stop), name="lock-lease", daemon=True)
        thread.start()
        _HELD[key] = (fd, stop, thread)


def release(path) -> None:
    """停心跳并关掉句柄。不删除锁文件。"""
    key = _key(path)
    with _GUARD:
        item = _HELD.pop(key, None)
    if item is None:
        return
    fd, stop, thread = item
    stop.set()
    thread.join(timeout=1.0)
    try:
        os.close(fd)
    except OSError:
        pass

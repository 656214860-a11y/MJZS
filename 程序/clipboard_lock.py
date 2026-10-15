# -*- coding: utf-8 -*-
"""剪贴板锁（第 65 期第 12 条）。

剪贴板是**整台机器共用**的一块。全量自检是 8 路并行跑的，好几个用例都会往剪贴板里写
（提示词、详情、邮箱那几个「复制」按钮）：写进去到读回来这一小段里被别的进程插一脚，
读到的就是别人的内容——随机红，而且红的样子跟被测功能没有关系。

这里给「写＋读」那一小段加一把跨进程的锁：拿到锁的进程才许碰剪贴板，别的排队等。
用 msvcrt 的字节区锁，与 codex_tasks／engine 里那几处同一套做法。

用法：
    import clipboard_lock
    with clipboard_lock.hold():
        ...写／读剪贴板...
"""
import app_logging
import os
import time
import threading
from importlib import import_module
from contextlib import contextmanager

LOCK_NAME = 'drama_clipboard.lock'
_LOCAL = threading.local()


def lock_path():
    """锁文件落在临时目录里：与项目、与哪个用户目录无关。"""
    return os.path.join(os.environ.get('TEMP') or os.environ.get('TMP') or '/tmp', LOCK_NAME)


@contextmanager
def hold(timeout=30.0, poll=0.02):
    """占住剪贴板这一小会儿；等不到也不硬等（超时就照旧往下走，最多还是原来那样红）。"""
    if getattr(_LOCAL, 'depth', 0):
        _LOCAL.depth += 1
        try:
            yield True
        finally:
            _LOCAL.depth -= 1
        return
    handle = _acquire(timeout, poll)
    acquired = handle is not None
    if acquired:
        _LOCAL.depth = 1
    try:
        yield acquired
    finally:
        if acquired:
            _LOCAL.depth = 0
        _release(handle)


def _acquire(timeout, poll):
    if os.name == 'nt':
        import msvcrt
        lock = lambda handle: msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
    else:
        # Windows 裁剪运行环境没有 Unix 专用 fcntl；只在非 Windows 实际走到此分支时加载。
        fcntl = import_module('fcntl')
        lock = lambda handle: fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    deadline = time.time() + max(0.0, float(timeout))
    while True:
        try:
            handle = open(lock_path(), 'a+b')
        except OSError:
            return None
        try:
            handle.seek(0)
            lock(handle)
            return handle
        except OSError:
            try:
                handle.close()
            except Exception:
                app_logging.swallowed()
            if time.time() >= deadline:
                return None
        time.sleep(poll)


def _release(handle):
    if handle is None:
        return
    try:
        handle.seek(0)
        if os.name == 'nt':
            import msvcrt
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            fcntl = import_module('fcntl')
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    except Exception:
        app_logging.swallowed()
    try:
        handle.close()
    except Exception:
        app_logging.swallowed()

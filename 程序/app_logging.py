"""程序级统一日志与崩溃钩子的唯一安装入口。

各模块已用 ``logging.getLogger(__name__)`` 记录，但此前没有任何处理器，pythonw 下 stderr
又不存在，记录会直接丢失。这里给根 logger 挂一个滚动文件（``logs/app.log``，轮转名
``app.log.1``–``.3`` 与 ``log_maintenance`` 的受管名一致），并接管主线程、后台线程、Tk 回调
和 C 层崩溃（faulthandler）。写入前经本模块的 ``redact`` 脱敏；任何一步失败都
静默降级，日志问题不得拖垮启动。只处理程序自己的 ``logs/``，不碰用户项目。
"""
from __future__ import annotations

import atexit
import contextlib
import faulthandler
import json
import logging
import re
import sys
import threading
import time
from collections import deque
from logging.handlers import RotatingFileHandler
from pathlib import Path

PROGRAM = Path(__file__).resolve().parent
LOGS = PROGRAM / "logs"
APP_LOG = LOGS / "app.log"
FAULT_LOG = LOGS / "faulthandler.log"
PERF_FILE = LOGS / "perf_metrics.json"
MAX_BYTES = 5 * 1024 * 1024
BACKUPS = 3
FORMAT = "%(asctime)s %(levelname)s %(threadName)s %(name)s: %(message)s"

_installed = False
_fault_stream = None
_crash_sink = None
_SECRET = re.compile(
    r"(?i)(?:api[ _-]?key|secret|token|password|credential)\s*[:=]\s*[^\s,;}]+|"
    r"authorization\s*[:=]\s*bearer\s+[^\s,;}]+|"
    r"[?&](?:api[_-]?key|access[_-]?token|refresh[_-]?token|token|secret|password|"
    r"signature|sig)=[^&\s,;}\"']+"
)
_swallow_counts: dict = {}
_recent_swallowed: deque = deque(maxlen=20)
_swallow_lock = threading.Lock()
SWALLOW_LOG_EVERY = 100


def redact(value: object) -> str:
    """凭据脱敏的唯一实现；``diagnostic_capture`` 复用它。"""
    return _SECRET.sub("[已脱敏]", str(value))


_metrics: dict = {}
_counters: dict = {}


def count(name: str, amount: int = 1) -> None:
    """事件计数（成功／失败原因等），随 ``perf_metrics.json`` 一起落盘；不抛异常。"""
    try:
        with _swallow_lock:
            _counters[name] = _counters.get(name, 0) + amount
    except Exception:
        pass


class timed(contextlib.ContextDecorator):
    """计时：既可 ``with timed('x', 500):`` 也可 ``@timed('x', 500)``。

    只在内存累计 次数／总耗时／最大耗时，超过 ``warn_ms`` 才写一条 WARNING；进程退出时
    汇总写入 ``logs/perf_metrics.json``。不抛异常、不改变被包裹代码的返回与异常。
    """

    def __init__(self, name: str, warn_ms: float = 1000.0):
        self.name = name
        self.warn_ms = warn_ms

    def _recreate_cm(self):
        # 装饰器每次调用新建实例：并发（后台线程里的模型请求）或递归时起点互不覆盖。
        return timed(self.name, self.warn_ms)

    def __enter__(self):
        self._start = time.perf_counter()
        return self

    def __exit__(self, *exc):
        try:
            elapsed = (time.perf_counter() - self._start) * 1000.0
            with _swallow_lock:
                row = _metrics.setdefault(self.name, {"count": 0, "total_ms": 0.0, "max_ms": 0.0, "slow": 0})
                row["count"] += 1
                row["total_ms"] += elapsed
                row["max_ms"] = max(row["max_ms"], elapsed)
                if elapsed >= self.warn_ms:
                    row["slow"] += 1
            if elapsed >= self.warn_ms:
                logging.getLogger("perf").warning("慢操作 %s %.0fms（阈值 %.0fms）", self.name, elapsed, self.warn_ms)
        except Exception:
            pass
        return False


def metrics_snapshot() -> dict:
    with _swallow_lock:
        data = {name: {k: round(v, 1) if isinstance(v, float) else v for k, v in row.items()}
                for name, row in _metrics.items()}
        if _counters:
            data["counters"] = dict(_counters)
        return data


def flush_metrics() -> None:
    """把本次运行的计时汇总写盘；无数据或失败都静默。"""
    try:
        data = metrics_snapshot()
        if data:
            from agent.core import save_text
            save_text(PERF_FILE, json.dumps({"at": time.strftime("%Y-%m-%d %H:%M:%S"), "metrics": data},
                                            ensure_ascii=False, indent=2))
    except Exception:
        pass


def recent_swallowed() -> list:
    """最近被忽略的异常（最多 20 条，最新在后），供「运行状况」面板读取。"""
    with _swallow_lock:
        return list(_recent_swallowed)


def build_commit() -> str:
    """读 ``.git/HEAD`` 得到当前提交短号；不起子进程，读不到返回空串（分发副本没有 .git）。"""
    try:
        git = PROGRAM.parent / ".git"
        if git.is_file():
            text = git.read_text(encoding="utf-8").strip()
            git = (PROGRAM.parent / text.split(":", 1)[1].strip()).resolve()
        head = (git / "HEAD").read_text(encoding="utf-8").strip()
        if head.startswith("ref:"):
            ref = head.split(":", 1)[1].strip()
            target = git / ref
            if not target.is_file():
                common = (git / "commondir")
                base = (git / common.read_text(encoding="utf-8").strip()).resolve() if common.is_file() else git
                target = base / ref
            head = target.read_text(encoding="utf-8").strip() if target.is_file() else ""
        return head[:10]
    except Exception:
        return ""


def swallowed(note: str = "") -> None:
    """在 ``except`` 块里代替 ``pass``：照旧吞掉异常，但留下带位置的一条记录。

    同一位置同一异常类型只记第 1 次和之后每 ``SWALLOW_LOG_EVERY`` 次，避免高频 UI 路径刷屏。
    本身绝不抛异常。
    """
    try:
        kind, value, trace = sys.exc_info()
        if value is None:
            return
        frame = sys._getframe(1)
        key = (frame.f_code.co_filename, frame.f_lineno, kind.__name__)
        with _swallow_lock:
            count = _swallow_counts[key] = _swallow_counts.get(key, 0) + 1
            _recent_swallowed.append("%s %s:%s %s: %s" % (time.strftime("%H:%M:%S"), Path(key[0]).name,
                                                          key[1], kind.__name__, redact(value)[:160]))
        if count != 1 and count % SWALLOW_LOG_EVERY:
            return
        logging.getLogger("swallowed").warning(
            "%s:%s 已忽略 %s: %s%s%s", Path(key[0]).name, key[1], kind.__name__, value,
            "（第 %d 次）" % count if count > 1 else "", " " + note if note else "")
    except Exception:
        pass


class _Redact(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            record.msg = redact(record.getMessage())
            record.args = None
            if record.exc_info:
                import traceback
                record.msg += "\n" + redact("".join(traceback.format_exception(*record.exc_info)))
                record.exc_info = None
                record.exc_text = None
        except Exception:
            pass
        return True


def _crash(kind: str, exc: BaseException, trace=None) -> None:
    logging.getLogger("crash").critical("%s: %s", kind, exc, exc_info=(type(exc), exc, trace or exc.__traceback__))
    if _crash_sink is not None:
        try:
            _crash_sink(exc, trace)
        except Exception:
            pass


def install(root=None, crash_sink=None) -> bool:
    """安装一次；``root`` 为 Tk 根窗口时一并接管回调异常。返回是否已生效。

    ``crash_sink(exc, trace)`` 由入口注入（通常是 ``diagnostic_capture.record_crash``），
    本模块不反向依赖诊断层，以便基础模块也能安全导入。
    """
    global _installed, _fault_stream, _crash_sink
    if crash_sink is not None:
        _crash_sink = crash_sink
    if root is not None:
        previous = getattr(root, "report_callback_exception", None)

        def tk_hook(kind, value, trace):
            _crash("tk-callback", value, trace)
            if callable(previous):
                try:
                    previous(kind, value, trace)
                except Exception:
                    pass
        try:
            root.report_callback_exception = tk_hook
        except Exception:
            pass
    if _installed:
        return True
    try:
        LOGS.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(APP_LOG, maxBytes=MAX_BYTES, backupCount=BACKUPS, encoding="utf-8")
        handler.setFormatter(logging.Formatter(FORMAT))
        handler.addFilter(_Redact())
        logger = logging.getLogger()
        logger.addHandler(handler)
        if logger.level in (logging.NOTSET, logging.WARNING):
            logger.setLevel(logging.INFO)
    except Exception:
        return False
    _installed = True
    try:
        from app_metadata import VERSION
        logging.getLogger("startup").info("启动 %s commit=%s Python %s", VERSION, build_commit() or "-", sys.version.split()[0])
    except Exception:
        pass
    atexit.register(flush_metrics)
    previous_hook = sys.excepthook

    def main_hook(kind, value, trace):
        _crash("main-thread", value, trace)
        previous_hook(kind, value, trace)
    sys.excepthook = main_hook

    def thread_hook(args):
        if args.exc_type is not SystemExit:
            _crash("thread:" + (args.thread.name if args.thread else "?"), args.exc_value, args.exc_traceback)
    threading.excepthook = thread_hook
    try:
        _fault_stream = open(FAULT_LOG, "a", encoding="utf-8")
        faulthandler.enable(_fault_stream)
    except Exception:
        pass
    return True

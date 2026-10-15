"""程序级统一日志与崩溃钩子的唯一安装入口。

各模块已用 ``logging.getLogger(__name__)`` 记录，但此前没有任何处理器，pythonw 下 stderr
又不存在，记录会直接丢失。这里给根 logger 挂一个滚动文件（``logs/app.log``，轮转名
``app.log.1``–``.3`` 与 ``log_maintenance`` 的受管名一致），并接管主线程、后台线程、Tk 回调
和 C 层崩溃（faulthandler）。写入前经 ``diagnostic_capture.redact`` 脱敏；任何一步失败都
静默降级，日志问题不得拖垮启动。只处理程序自己的 ``logs/``，不碰用户项目。
"""
from __future__ import annotations

import faulthandler
import logging
import sys
import threading
from logging.handlers import RotatingFileHandler
from pathlib import Path

PROGRAM = Path(__file__).resolve().parent
LOGS = PROGRAM / "logs"
APP_LOG = LOGS / "app.log"
FAULT_LOG = LOGS / "faulthandler.log"
MAX_BYTES = 5 * 1024 * 1024
BACKUPS = 3
FORMAT = "%(asctime)s %(levelname)s %(threadName)s %(name)s: %(message)s"

_installed = False
_fault_stream = None


class _Redact(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            from diagnostic_capture import redact
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
    try:
        import diagnostic_capture
        diagnostic_capture.record_crash(exc, trace)
    except Exception:
        pass


def install(root=None) -> bool:
    """安装一次；``root`` 为 Tk 根窗口时一并接管回调异常。返回是否已生效。"""
    global _installed, _fault_stream
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

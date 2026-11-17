"""程序级可导出的脱敏诊断采集。

这里只处理程序拥有的 ``logs/``；不遍历项目目录，也不读取私有配置。所有落盘经
``agent.core`` 原子发布，导出时仅打包白名单文件并逐行剔除凭据。
"""
from __future__ import annotations

import io
import json
import os
import re
import threading
import traceback
import zipfile
from datetime import datetime, timedelta
from pathlib import Path

import app_logging
from agent.core import read_json, save_bytes, save_text
from infra.log_maintenance import RETENTION_DAYS


PROGRAM = Path(__file__).resolve().parents[1]
LOGS = PROGRAM / "logs"
ERROR_LOG = LOGS / "启动错误.log"
STATE_FILE = LOGS / "diagnostics" / "latest.json"
# 自检与本地 CI 设置 DRAMA_SUPPRESS_DIAGNOSTICS=1：测试故意触发的报错不写进程序自己的这份
# 记录，免得临时项目混进用户的运行状况与诊断导出；测试把 STATE_FILE 改指到临时文件时照常写。
SUPPRESS_DIAGNOSTICS_ENV = "DRAMA_SUPPRESS_DIAGNOSTICS"
_PROGRAM_STATE_FILE = STATE_FILE
_SECRET = app_logging._SECRET
_PRIVATE_NAME = re.compile(r"(?i)(?:\.env$|\.dpapi$|private|credential|secret)")
_LOCK = threading.Lock()


def redact(value: object) -> str:
    """给别的模块共用的脱敏入口：同样的规则，同样的替换词。"""
    return _clean(value)

def _state() -> dict:
    try:
        value = read_json(STATE_FILE, default={})
    except (OSError, ValueError):
        value = {}
    return value if isinstance(value, dict) else {}


def _save_state(value: dict) -> None:
    if os.environ.get(SUPPRESS_DIAGNOSTICS_ENV) == "1" and STATE_FILE == _PROGRAM_STATE_FILE:
        return
    save_text(STATE_FILE, json.dumps(value, ensure_ascii=False, indent=2))


def _clean(value: object) -> str:
    return app_logging.redact(value)


def record_degradation(exc: BaseException, *, page: str = "", stage: str = "",
                       project: str = "", automatic_daily_open: bool = False) -> None:
    """记录一次已降级异常；调用方仍保持原有容错/返回语义。"""
    with _LOCK:
        state = _state()
        rows = list(state.get("degradations") or [])[-49:]
        rows.append({"at": datetime.now().isoformat(timespec="seconds"),
                     "exception": type(exc).__name__, "message": _clean(exc),
                     "page": _clean(page), "stage": _clean(stage),
                     "project": _clean(project), "automatic_daily_open": bool(automatic_daily_open)})
        state["degradations"] = rows
        _save_state(state)


def record_startup_timing(name: str, elapsed_ms: float) -> None:
    """启动阶段仅记耗时，不触碰目录扫描或项目内容。"""
    with _LOCK:
        state = _state()
        timings = dict(state.get("startup_timings") or {})
        timings[str(name)] = round(float(elapsed_ms), 2)
        state["startup_timings"] = timings
        _save_state(state)


def record_gate_result(name: str, result: str) -> None:
    with _LOCK:
        state = _state()
        state["last_gate"] = {"name": _clean(name), "result": _clean(result),
                              "at": datetime.now().isoformat(timespec="seconds")}
        _save_state(state)


def record_crash(exc: BaseException, trace=None) -> None:
    """追加到既有启动错误日志，不另建崩溃日志。"""
    with _LOCK:
        previous = ERROR_LOG.read_text(encoding="utf-8", errors="replace") if ERROR_LOG.exists() else ""
        detail = "".join(traceback.format_exception(type(exc), exc, trace or exc.__traceback__))
        save_text(ERROR_LOG, previous + "\n[diagnostics] " + _clean(detail) + "\n")


def export_candidates() -> tuple[Path, ...]:
    """固定白名单，避免在启动或导出时递归枚举日志目录。"""
    return tuple(path for path in (ERROR_LOG, LOGS / "sanhu_progress.log", STATE_FILE) if path.is_file())


def preview() -> tuple[str, ...]:
    return tuple(str(path) for path in export_candidates())


def retention_note() -> str:
    """把保留期限说清楚：程序日志按 log_maintenance 的政策保留这么多天。"""
    return "程序日志保留 %d 天（按 log_maintenance 政策）；导出只含下面白名单文件，不含项目与密钥。" % RETENTION_DAYS


def preview_detail() -> tuple[dict, ...]:
    """诊断预览：白名单文件 ＋ 大小／修改时间／保留期限；只看不动文件。"""
    now = datetime.now()
    rows = []
    for path in export_candidates():
        try:
            stat = path.stat()
        except OSError:
            continue
        modified = datetime.fromtimestamp(stat.st_mtime)
        expires = modified + timedelta(days=RETENTION_DAYS)
        rows.append({"name": path.name, "path": str(path), "bytes": stat.st_size,
                     "modified": modified.isoformat(timespec="seconds"),
                     "keep_days": RETENTION_DAYS,
                     "expires_at": expires.isoformat(timespec="seconds"),
                     "expired": expires <= now})
    return tuple(rows)

def _safe_member(path: Path) -> str:
    if _PRIVATE_NAME.search(path.name):
        raise ValueError("诊断包包含受保护文件，已拒绝导出：" + path.name)
    return "logs/" + path.name if path.parent == LOGS else "logs/diagnostics/" + path.name


def export(destination: str | Path) -> Path:
    """把脱敏后的白名单日志写成单个 ZIP；任一受保护项立即拒绝。"""
    bundle = io.BytesIO()
    with zipfile.ZipFile(bundle, "w", zipfile.ZIP_DEFLATED) as archive:
        manifest = []
        for source in export_candidates():
            member = _safe_member(source)
            text = source.read_text(encoding="utf-8", errors="replace")
            cleaned = "\n".join(_clean(line) for line in text.splitlines())
            if _SECRET.search(cleaned):
                raise ValueError("诊断包仍含凭据形态，已拒绝导出。")
            archive.writestr(member, cleaned)
            manifest.append(member)
        archive.writestr("manifest.json", json.dumps({"included": manifest, "secret_policy": "redacted"}, ensure_ascii=False))
    output = Path(destination)
    if output.suffix.lower() != ".zip":
        output = output.with_suffix(".zip")
    save_bytes(output, bundle.getvalue())
    return output

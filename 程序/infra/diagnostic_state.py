"""共享程序诊断状态，供降级记录与启动诊断使用。"""
from __future__ import annotations

import json
import os
import threading
from datetime import datetime
from pathlib import Path

import contract.artifact_schema as artifact_schema
import infra.app_logging as app_logging
from agent.core import read_json, save_text


STATE_FILE = app_logging.LOGS / "diagnostics" / "latest.json"
_PROGRAM_STATE_FILE = STATE_FILE
SUPPRESS_DIAGNOSTICS_ENV = "DRAMA_SUPPRESS_DIAGNOSTICS"
STATE_LOCK = threading.Lock()


def read_state(path: Path) -> dict:
    try:
        value = read_json(path, default={})
    except (OSError, ValueError):
        value = {}
    return value if isinstance(value, dict) else {}


def artifact_state_rows() -> dict:
    """产物版本分类计数快照（``artifact_schema`` 内存计数 → 诊断账本，G8/D4-d）。"""
    try:
        return artifact_schema.read_state_counts() or {}
    except Exception:
        return {}


def save_state(path: Path, value: dict) -> None:
    if os.environ.get(SUPPRESS_DIAGNOSTICS_ENV) == "1" and path == _PROGRAM_STATE_FILE:
        return
    rows = artifact_state_rows()
    if rows:
        value = dict(value)
        value["artifact_versions"] = rows
    save_text(path, json.dumps(value, ensure_ascii=False, indent=2))


def record_degradation(exc: BaseException, *, page: str = "", stage: str = "",
                       project: str = "", automatic_daily_open: bool = False,
                       error_code: str = "", state_file: Path | None = None) -> None:
    """记录一次已降级异常；调用方仍保持原有容错/返回语义。``error_code`` 用 L0 码表已有码（如 E-IO-WRITE）。"""
    path = STATE_FILE if state_file is None else state_file
    with STATE_LOCK:
        state = read_state(path)
        rows = list(state.get("degradations") or [])[-49:]
        rows.append({"at": datetime.now().isoformat(timespec="seconds"),
                     "exception": type(exc).__name__, "message": app_logging.redact(exc),
                     "page": app_logging.redact(page), "stage": app_logging.redact(stage),
                     "project": app_logging.redact(project), "automatic_daily_open": bool(automatic_daily_open),
                     "code": app_logging.redact(error_code)})
        state["degradations"] = rows
        save_state(path, state)

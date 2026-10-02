# -*- coding: utf-8 -*-
"""三类离线基准共用的历史归档工具；不参与应用启动路径。"""
from __future__ import annotations

import json
import os
import platform
import re
import statistics
from datetime import datetime, timezone
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
PROGRAM_ROOT = SCRIPT_DIR.parents[1]
HISTORY_PATH = PROGRAM_ROOT / "维护记录" / "基准历史.json"
MAX_HISTORY = 30


def current_round() -> int | None:
    """从台账读取当前轮次，绝不把轮次硬编码在探针里。"""
    status = PROGRAM_ROOT / "project_status.md"
    try:
        matched = re.search(r"当前轮次：(\d+)", status.read_text(encoding="utf-8"))
        return int(matched.group(1)) if matched else None
    except OSError:
        return None


def registered_project() -> dict:
    """只从程序登记表取项目名称/路径；探针不接受硬编码项目路径。"""
    registry = PROGRAM_ROOT / "projects.json"
    try:
        data = json.loads(registry.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    projects = data.get("projects", []) if isinstance(data, dict) else []
    active = data.get("active") if isinstance(data, dict) else None
    item = next((row for row in projects if row.get("path") == active), None)
    item = item or (projects[0] if projects else {})
    return {
        "project_name": item.get("name") or "未登记项目",
        "project_path_source": "程序/projects.json",
        "project_registered": bool(item),
    }


def measurement_conditions(*, cache_state: str, first_frame: bool,
                           includes_real_credentials: bool = False) -> dict:
    return {
        "machine": {
            "system": platform.system(), "release": platform.release(),
            "machine": platform.machine(), "processor": platform.processor(),
        },
        "cache_state": cache_state,
        "first_frame": bool(first_frame),
        "includes_real_credentials": bool(includes_real_credentials),
        **registered_project(),
    }


def append_history(*, family: str, condition: dict, metrics: dict,
                   source_result: str, round_number: int | None = None,
                   history_path: Path = HISTORY_PATH) -> dict:
    """追加一条可比较记录并保留最近 MAX_HISTORY 条，历史文件始终是唯一归档源。"""
    try:
        existing = json.loads(history_path.read_text(encoding="utf-8"))
        history = existing if isinstance(existing, list) else []
    except (OSError, ValueError):
        history = []
    record = {
        "round": current_round() if round_number is None else round_number,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "family": family,
        "condition": condition,
        "metrics": metrics,
        "source_result": source_result,
        "success": True,
    }
    history.append(record)
    history_path.parent.mkdir(parents=True, exist_ok=True)
    history_path.write_text(json.dumps(history[-MAX_HISTORY:], ensure_ascii=False, indent=2), encoding="utf-8")
    return record


def comparable_records(history: list[dict], current: dict, metric: str) -> list[dict]:
    """只选择同一基准族和同一冷/热、首帧、凭据条件的成功历史。"""
    condition = current.get("condition", {})
    fields = ("cache_state", "first_frame", "includes_real_credentials")
    workload = current.get("metrics", {}).get("row_count")
    return [row for row in history if row is not current and row.get("success") is True
            and row.get("family") == current.get("family")
            and all(row.get("condition", {}).get(key) == condition.get(key) for key in fields)
            and (workload is None or row.get("metrics", {}).get("row_count") == workload)
            and isinstance(row.get("metrics", {}).get(metric), (int, float))]


def median_baseline(history: list[dict], current: dict, metric: str, sample_size: int = 5) -> float | None:
    previous = comparable_records(history, current, metric)[-sample_size:]
    return statistics.median(row["metrics"][metric] for row in previous) if previous else None

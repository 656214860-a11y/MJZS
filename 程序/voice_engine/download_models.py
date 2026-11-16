#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""FunASR 模型下载与本地缓存解析（移植自 vocotype-cli app/download_models.py，Apache-2.0）。

策略：先 ``local_files_only=True`` 命中本地缓存（不联网），未命中再在线
``modelscope.snapshot_download``；模型一律落在用户数据目录（默认
``程序/data/voice_models``，可用 ``VOICE_ASR_MODEL_CACHE`` 覆盖），不进源码树与 Git。
可作为独立 CLI 运行做预下载，stdout 输出 JSON Lines 进度。
"""

import json
import os
import sys
import threading
from pathlib import Path

from voice_engine import funasr_config


def default_cache_root() -> str:
    """默认模型缓存根目录：``程序/data/voice_models``（用户数据区，升级保留）。"""
    override = os.environ.get("VOICE_ASR_MODEL_CACHE")
    if override:
        return override
    program_root = Path(__file__).resolve().parents[1]
    return str(program_root / "data" / "voice_models")


def _cache_model_dir(cache_root: str, model_name: str) -> Path:
    """modelscope 缓存布局：``<cache_root>/hub/models/<org>/<short>``。"""
    short = model_name.split("/")[-1] if "/" in model_name else model_name
    org = model_name.split("/")[0] if "/" in model_name else "iic"
    return Path(cache_root) / "hub" / "models" / org / short


def _has_model_files(model_dir: Path) -> bool:
    return (model_dir / "model_quant.onnx").exists() or (model_dir / "model.onnx").exists()


def get_model_cache_path(model_name: str, revision: str, cache_root: str = None):
    """离线优先获取模型目录：本地命中直接返回，否则 snapshot_download（先离线后在线）。

    ``cache_root`` 非空时把 ``MODELSCOPE_CACHE`` 指到该目录，使模型落在用户数据区；
    返回值始终是 modelscope 实际给出的目录（权威路径），本地预检仅为快速路径。
    """
    root = cache_root or default_cache_root()
    os.environ["MODELSCOPE_CACHE"] = root
    fast = _cache_model_dir(root, model_name)
    if _has_model_files(fast):
        return str(fast)

    from modelscope.hub.snapshot_download import snapshot_download

    try:
        return snapshot_download(model_name, revision=revision, local_files_only=True)
    except Exception:
        pass
    return snapshot_download(model_name, revision=revision)


def ensure_all_models(progress=None, cache_root: str = None) -> dict:
    """并行下载全部配置模型；``progress(type, stage, pct, error)`` 回调进度。

    返回 ``{type: {"success": bool, ...}}``；全部成功时不抛异常。
    """
    models = funasr_config.get_models_for_download()
    revision = funasr_config.MODEL_REVISION
    results = {}
    lock = threading.Lock()

    def worker(config):
        model_type = config["type"]
        try:
            if progress:
                progress(model_type, "downloading", 0, None)
            get_model_cache_path(config["name"], revision, cache_root)
            result = {"success": True, "model": model_type}
        except Exception as exc:  # noqa: BLE001 —— 逐模型隔离，汇总上报
            result = {"success": False, "model": model_type, "error": str(exc)}
        with lock:
            results[model_type] = result
            if progress:
                progress(model_type,
                         "completed" if result["success"] else "error",
                         100 if result["success"] else 0,
                         result.get("error"))

    threads = [threading.Thread(target=worker, args=(m,), daemon=True) for m in models]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    return results


def _send_json(obj):
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def main(argv=None):
    """独立预下载入口：``python -m voice_engine.download_models [--cache DIR]``。"""
    cache_root = default_cache_root()
    if argv:
        if "--cache" in argv:
            idx = argv.index("--cache")
            if idx + 1 < len(argv):
                cache_root = argv[idx + 1]
    done = {"asr": False, "vad": False, "punc": False}

    def progress(model_type, stage, pct, error):
        _send_json({"type": "progress", "model": model_type, "stage": stage,
               "percent": pct, "error": error})
        if stage in ("completed", "error"):
            done[model_type] = stage == "completed"

    try:
        results = ensure_all_models(progress=progress, cache_root=cache_root)
    except Exception as exc:  # noqa: BLE001
        _send_json({"type": "error", "message": "模型下载失败：%s" % exc})
        return 1
    failed = [k for k, v in results.items() if not v.get("success")]
    if failed:
        _send_json({"type": "error", "message": "以下模型下载失败：%s" % "、".join(failed),
               "failed": failed})
        return 1
    _send_json({"type": "done", "cache_root": cache_root})
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

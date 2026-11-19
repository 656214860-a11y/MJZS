#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""FunASR 模型配置（移植自 vocotype-cli app/funasr_config.py，Apache-2.0）。

统一管理模型名称、版本；可用环境变量覆盖，便于离线/自定义模型切换。
"""

import json
import os
from pathlib import Path

_LOCK = json.loads((Path(__file__).with_name('models.lock.json')).read_text(encoding='utf-8'))

# 模型版本，可通过环境变量覆盖
MODEL_REVISION = os.environ.get("FUNASR_MODEL_REVISION", _LOCK["revision"])

# 模型配置（默认使用 ONNX 版本，仍可通过环境变量覆盖）
MODELS = {
    "asr": {
        "name": os.environ.get(
            "FUNASR_ASR_MODEL",
            _LOCK["models"]["asr"],
        ),
        "type": "asr",
    },
    "vad": {
        "name": os.environ.get(
            "FUNASR_VAD_MODEL",
            _LOCK["models"]["vad"],
        ),
        "type": "vad",
    },
    "punc": {
        "name": os.environ.get(
            "FUNASR_PUNC_MODEL",
            _LOCK["models"]["punc"],
        ),
        "type": "punc",
    },
}


def get_models_for_download():
    """返回用于下载的模型配置列表。"""
    return [
        {"name": MODELS["asr"]["name"], "type": "asr"},
        {"name": MODELS["vad"]["name"], "type": "vad"},
        {"name": MODELS["punc"]["name"], "type": "punc"},
    ]

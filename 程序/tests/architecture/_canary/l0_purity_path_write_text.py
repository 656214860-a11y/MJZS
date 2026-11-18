"""L0 纯度坏样本：Path 禁用写方法，门禁必须变红。"""
from pathlib import Path


def dump(path):
    return Path(path).write_text("x", encoding="utf-8")

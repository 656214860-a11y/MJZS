"""Persistence boundary for user-edited storyboard JSON documents."""
from pathlib import Path

from agent.core import save


def save_edited_json(path, data):
    """Atomically persist an already-validated JSON document and return its path."""
    target = Path(path).resolve()
    if target.suffix.lower() != '.json':
        raise ValueError('分镜编辑只能保存 JSON 文件')
    save(target, data)
    return target

"""Persistence boundary for user-edited storyboard JSON documents."""
from pathlib import Path

def save_edited_json(path, data, publish=None):
    """Atomically persist an already-validated JSON document and return its path."""
    if not callable(publish):
        raise TypeError('分镜编辑发布必须由 L3 注入。')
    target = Path(path).resolve()
    if target.suffix.lower() != '.json':
        raise ValueError('分镜编辑只能保存 JSON 文件')
    publish(target, data)
    return target

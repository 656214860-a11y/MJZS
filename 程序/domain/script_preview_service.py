"""剧本文本预览的读取策略。

小文件保持同步读取，保证切换文件时立即可见；超过阈值的文件由 UI 放到
后台线程读取，避免网络盘或超长剧本阻塞 Tk 主线程。实际读取仍复用
``file_cache`` 的按文件签名缓存。
"""
from pathlib import Path


ASYNC_PREVIEW_BYTES = 512 * 1024
PREVIEW_CHUNK_CHARS = 32 * 1024
LOADING_PREVIEW = '正在后台加载大剧本预览…'
READ_ERROR = '剧本内容读取失败，请手动打开剧本目录查看。'


def should_load_async(path, threshold=ASYNC_PREVIEW_BYTES):
    """仅对确实存在且超过阈值的文件启用后台预览。"""
    try:
        return Path(path).is_file() and Path(path).stat().st_size > int(threshold)
    except (OSError, TypeError, ValueError):
        return False


def read_preview(path, empty=''):
    """读取可展示的文本；文件不存在时返回页面提供的空态文案。"""
    try:
        source = Path(path) if path else None
        if source is None or not source.is_file():
            return empty
        from infra.file_cache import read_text
        return read_text(source, encoding='utf-8-sig')
    except (OSError, UnicodeError):
        return READ_ERROR


def preview_chunks(value, chunk_size=PREVIEW_CHUNK_CHARS):
    """把大预览拆成可由 Tk 空闲回调逐块投递的文本片段。"""
    value = str(value)
    chunk_size = max(1, int(chunk_size))
    return (value[index:index + chunk_size] for index in range(0, len(value), chunk_size))

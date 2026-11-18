"""遗留临时文件的受控清扫（L1 任务书轮 2 R2-g）。

只匹配 ``agent.core.temporary_path`` 产出的 ``<原名>.<32位hex>.<后缀>``
形态；用户自起的 ``剧本.tmp`` 之类没有 32 位十六进制段，永远不会命中。
物理删除经 ``file_cache.remove_temporary_file``（删除白名单内的唯一入口），
不跟随符号链接展开到项目根之外。
"""
import logging
import os
import re
import threading
import time
from pathlib import Path

import infra.app_logging as app_logging
import infra.file_cache as file_cache

TEMP_SWEEP_MAX_AGE_SECONDS = 24 * 3600
_TEMP_NAME_RE = re.compile(r'\.[0-9a-fA-F]{32}\.(?:tmp|download|recover|partial\.mp4)$')


def is_stale_temporary_name(name):
    return bool(_TEMP_NAME_RE.search(name))


def sweep_stale_temporary_files(root, *, now=None, max_age_seconds=TEMP_SWEEP_MAX_AGE_SECONDS):
    """删除项目内超过时限的遗留临时文件，返回删除数；单个失败跳过不挡其余。"""
    root = Path(root)
    cutoff = (time.time() if now is None else float(now)) - float(max_age_seconds)
    removed = 0
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames[:] = [d for d in dirnames if not os.path.islink(os.path.join(dirpath, d))]
        for name in filenames:
            if not is_stale_temporary_name(name):
                continue
            target = Path(dirpath) / name
            try:
                if target.stat().st_mtime < cutoff and file_cache.remove_temporary_file(target):
                    removed += 1
            except OSError:
                continue
    return removed


def schedule_stale_temporary_sweep(root):
    """项目打开后的后台清扫入口：目录遍历只发生在线程里，不占启动／UI 路径（规则 33）。"""
    target = Path(root)

    def work():
        try:
            removed = sweep_stale_temporary_files(target)
            if removed:
                logging.getLogger(__name__).info('遗留临时文件清扫完成：%s 删除 %d 个', target, removed)
        except Exception:
            app_logging.swallowed()

    threading.Thread(target=work, daemon=True, name='stale-temporary-sweep').start()

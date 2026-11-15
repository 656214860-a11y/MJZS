"""配置覆盖前的环形快照（U10）：固定 ``SLOTS`` 个槽位轮流覆盖，不需要删除旧文件。

调用方只在写入前调一次 ``keep(path, folder, prefix)``；失败只记日志，绝不拦住真正的保存。
"""
import os
from pathlib import Path

import app_logging
from agent.core import save_bytes

SLOTS = 20


def keep(path, folder, prefix, slots=SLOTS):
    """把 ``path`` 现有内容复制进 ``folder`` 里最久没写的槽位；源文件不存在则什么也不做。"""
    try:
        path = Path(path)
        if not path.is_file():
            return None
        folder = Path(folder)
        names = [folder / ('%s_%02d.json' % (prefix, index)) for index in range(slots)]
        target = min(names, key=lambda item: os.path.getmtime(item) if item.exists() else 0.0)
        save_bytes(target, path.read_bytes())
        return target
    except OSError:
        app_logging.swallowed()
        return None

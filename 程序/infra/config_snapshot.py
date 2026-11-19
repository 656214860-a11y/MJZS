"""共享模型配置的路径、只读探针和配置覆盖前的环形快照（U10）。

快照固定使用 ``SLOTS`` 个槽位轮流覆盖。调用方只在写入前调用 ``keep``；
快照失败时记录日志，继续保存配置。
"""
import os
from pathlib import Path

import infra.app_logging as app_logging
from agent.core import read, save_bytes

MODEL_CONFIG_PATH = ('配置', '宠物', '配置.json')
SLOTS = 20


def model_config_file(program):
    return Path(program).joinpath(*MODEL_CONFIG_PATH)


def has_stored_models(program) -> bool:
    """配置文件缺失视为空池，其他读取错误交给调用方处理。"""
    try:
        config = read(model_config_file(program))
    except FileNotFoundError:
        return False
    models = config.get('models') if isinstance(config, dict) else None
    return isinstance(models, dict) and bool(models)


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

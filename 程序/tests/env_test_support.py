"""环境变量隔离：用例里改 os.environ 一律走这里，用例结束自动还原，不再各写一份 addCleanup。"""
import os
from unittest import mock


def patched_env(test, **values):
    """在用例期间设置环境变量；值为 None 表示先移除。用例结束（含失败）后整体还原。"""
    patcher = mock.patch.dict(os.environ)
    patcher.start()
    test.addCleanup(patcher.stop)
    for name, value in values.items():
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = str(value)

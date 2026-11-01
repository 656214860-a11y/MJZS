"""测试里隔离本机加密存储：落到临时目录，加解密换成可逆假实现，绝不碰真实 private/。"""
import tempfile
from pathlib import Path
from unittest import mock

import model_secrets


def isolate_secret_store(case):
    """返回临时程序目录；case 结束时自动还原 PROGRAM 与 PROTECTOR。"""
    folder = tempfile.TemporaryDirectory()
    case.addCleanup(folder.cleanup)
    root = Path(folder.name)
    for patcher in (mock.patch.object(model_secrets, 'PROGRAM', root),
                    mock.patch.object(model_secrets, 'PROTECTOR', lambda data, decrypt=False, label='': (
                        bytes(data)[len(b'enc:'):] if decrypt else b'enc:' + bytes(data)))):
        patcher.start()
        case.addCleanup(patcher.stop)
    return root

"""L0 纯度坏样本：函数体内 try 里的禁用模块 import，门禁必须变红。"""


def probe():
    try:
        import subprocess
    except ImportError:
        subprocess = None
    return subprocess

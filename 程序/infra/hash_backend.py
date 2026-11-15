# -*- coding: utf-8 -*-
"""hashlib 的后端选择：能走内置实现就别拉 OpenSSL 进来（第 34 期第 10 条）。

本版解释器的 `hashlib` 一被 import 就会连带 import `_hashlib`（OpenSSL），把
`libcrypto-3.dll`（镜像 5.0 MB，实测主界面工作集 +4 MB）常驻进内存。而程序本体、
skills、附加工具、批量工具里只用到 sha256／sha1／md5，这三个算法的实现在本版解释器里
是内置的（`_sha2`／`_sha1`／`_md5` 都在 `sys.builtin_module_names` 里），不依赖 OpenSSL。

`install()` 在 `import hashlib` 之前把 `_hashlib` 标成不可用，`hashlib` 自动回退到内置实现；
HTTPS 不受影响——`_ssl` 真要用 OpenSSL 时自己会加载，那时也不需要 hashlib 帮忙。

两点要记住：

* 代价只有一处：`hashlib.pbkdf2_hmac` 与 `hashlib.scrypt` 由 OpenSSL 提供，回退后不再
  可用。`test_hash_backend.py` 里有一条守卫用例盯着这条约束，全仓库出现这两个名字就会红。
* 速度：sha256 打 2 MB 数据，内置实现约 12.6 ms、OpenSSL 约 2.4 ms（5 倍），量级上仍是
  毫秒——资产指纹是触发一次算一次并写盘缓存，实际感觉不到。

要恢复原样：把调用方那句 `hash_backend.install()` 删掉即可，本模块其余部分不影响任何东西。
"""
import sys

BLOCKED = "_hashlib"
# 回退实现算得对不对，用已知答案盯住（三个都是 sha256/md5/sha1 对 b"abc" 的标准答案）。
SHA256_ABC = "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
MD5_ABC = "900150983cd24fb0d6963f7d28e17f72"
SHA1_ABC = "a9993e364706816aba3e25717850c26c9cd0d89d"


def builtins_ready():
    """回退目标在不在：三个内置实现模块都得有，而且都得算对已知答案。"""
    if not all(name in sys.builtin_module_names for name in ("_sha2", "_sha1", "_md5")):
        return False
    try:
        import _md5, _sha1, _sha2
    except ImportError:
        return False
    try:
        return (_sha2.sha256(b"abc").hexdigest() == SHA256_ABC
                and _sha1.sha1(b"abc").hexdigest() == SHA1_ABC
                and _md5.md5(b"abc").hexdigest() == MD5_ABC)
    except Exception:
        return False


def install():
    """让 hashlib 走内置实现；返回是否生效。任何一步不放心就原样返回 False，绝不硬来。"""
    if sys.modules.get(BLOCKED) is not None:
        return False                    # OpenSSL 后端已经加载过了，这会儿换已经晚了
    if not builtins_ready():
        return False                    # 这台机器上内置实现不可用，别赌
    sys.modules[BLOCKED] = None         # 从此 `import _hashlib` 直接失败
    import hashlib
    if (hashlib.sha256(b"abc").hexdigest() != SHA256_ABC
            or hashlib.md5(b"abc").hexdigest() != MD5_ABC
            or hashlib.sha1(b"abc").hexdigest() != SHA1_ABC):
        sys.modules.pop(BLOCKED, None)  # 兜底：算错就放开，后面的 import 还能走 OpenSSL
        return False
    return True

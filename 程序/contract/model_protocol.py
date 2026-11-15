# -*- coding: utf-8 -*-
"""模型基础设施之间共享的最小协议。

这里故意只声明边界，不放 DPAPI、HTTP、配置读写等实现。这样密钥存储、模型池、
客户端和供应商适配器可以沿单向链组合，而不会为了一个工具函数反向 import 对方。
"""
from typing import Protocol


class BytesProtector(Protocol):
    """Windows 用户范围的字节加解密能力。"""

    def __call__(self, data: bytes, decrypt: bool = False, label: str = '') -> bytes:
        """加密或解密 ``data``；失败时抛出调用方可显示的异常。"""


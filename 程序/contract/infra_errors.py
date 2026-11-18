# -*- coding: utf-8 -*-
"""L1 技术异常层级（L1 任务书 L1-H7／I6）。

L1 各模块只抛本模块定义的异常，不再直接抛 ``ValueError``/
``RuntimeError``/``OSError`` 等裸内置异常。约定：

- 每个异常带 ``code``：``contract.error_codes`` 已登记的错误码
  （构造时校验，未登记或超出族内允许集即 ``ValueError``）；
- ``detail``：技术事实载荷（errno、路径、返回码等），上层不直接
  展示给用户；用户文案由上层经 ``error_codes.describe()`` 翻译；
- 兼容继承：族基类多重继承对应的内置异常，旧 ``except`` 子句
  （``OSError``/``ValueError``/``RuntimeError``/``PermissionError``）
  仍能捕获，迁移不破坏既有调用方。
"""
from __future__ import annotations

from contract import error_codes


class InfraError(Exception):
    """技术异常根。``code`` 必须是 ``error_codes`` 已登记码。"""

    code = 'E-UNKNOWN'
    _allowed = frozenset({'E-UNKNOWN'})

    def __init__(self, message='', *, code=None, detail=None):
        chosen = code or type(self).code
        if (chosen not in type(self)._allowed
                or chosen not in error_codes.CODES):
            raise ValueError('未登记的%s错误码：%r' % (type(self).__name__, chosen))
        self.code = chosen
        self.detail = detail
        super().__init__(message)


class NetworkError(InfraError, OSError):
    """网络族失败；兼容 ``except OSError``。"""

    code = 'E-NET-UNREACHABLE'
    _allowed = frozenset({'E-NET-TIMEOUT', 'E-NET-UNREACHABLE',
                          'E-NET-RATE-LIMIT', 'E-NET-SERVER', 'E-NET-CLIENT'})


class StorageError(InfraError, OSError):
    """存储族失败（读写文件）；兼容 ``except OSError``。"""

    code = 'E-IO-WRITE'
    _allowed = frozenset({'E-IO-READ', 'E-IO-WRITE'})


class CorruptDataError(InfraError, ValueError):
    """数据损坏或不完整；兼容 ``except ValueError``。"""

    code = 'E-IO-CORRUPT'
    _allowed = frozenset({'E-IO-CORRUPT', 'E-CONTRACT-VIOLATION'})


class ProcessError(InfraError, RuntimeError):
    """外部进程族失败（拉起、退出码、超时）；兼容 ``except RuntimeError``。"""

    code = 'E-TOOL-FAILED'
    _allowed = frozenset({'E-TOOL-MISSING', 'E-TOOL-FAILED', 'E-TOOL-TIMEOUT'})


class QuotaError(InfraError, RuntimeError):
    """配额/限流族；兼容 ``except RuntimeError``。"""

    code = 'E-QUOTA-EXCEEDED'
    _allowed = frozenset({'E-QUOTA-EXCEEDED', 'E-NET-RATE-LIMIT'})


class AuthError(InfraError, PermissionError):
    """凭据族；兼容 ``except PermissionError``（亦是 ``OSError``）。"""

    code = 'E-AUTH-REJECTED'
    _allowed = frozenset({'E-AUTH-MISSING', 'E-AUTH-REJECTED'})


class ConfigError(InfraError, ValueError):
    """配置族（缺失、非法、未注入）；兼容 ``except ValueError``。"""

    code = 'E-CONFIG-INVALID'
    _allowed = frozenset({'E-CONFIG-INVALID'})


__all__ = [
    'InfraError', 'NetworkError', 'StorageError', 'CorruptDataError',
    'ProcessError', 'QuotaError', 'AuthError', 'ConfigError',
]
"""L1 只允许抛出本表异常（L1-H7）。"""
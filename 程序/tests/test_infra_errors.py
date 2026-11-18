# -*- coding: utf-8 -*-
"""L1-H7 技术异常层级单元测试（L1 任务书 I6）。

断言三件事：① 每个异常的 ``code`` 都能被 ``error_codes.lookup()``
解析回同一码；② 兼容继承——旧 ``except OSError/ValueError/
RuntimeError/PermissionError`` 仍能捕获；③ ``code`` 只允许族内
已登记码，越界或未登记即 ``ValueError``。
"""
import unittest

from contract import error_codes, infra_errors as ie


# 族 → 兼容基类（L1-H7 兼容继承表）。
FAMILIES = {
    'InfraError': (Exception,),
    'NetworkError': (OSError,),
    'StorageError': (OSError,),
    'CorruptDataError': (ValueError,),
    'ProcessError': (RuntimeError,),
    'QuotaError': (RuntimeError,),
    'AuthError': (PermissionError,),
    'ConfigError': (ValueError,),
}


class InfraErrorsRegistryTests(unittest.TestCase):
    def test_every_class_code_resolves(self):
        for name in ie.__all__:
            cls = getattr(ie, name)
            with self.subTest(cls=name):
                self.assertIn(cls.code, error_codes.CODES)
                self.assertEqual(error_codes.lookup(cls.code).code, cls.code)

    def test_all_exports_are_exceptions(self):
        for name in ie.__all__:
            cls = getattr(ie, name)
            with self.subTest(cls=name):
                self.assertTrue(issubclass(cls, ie.InfraError))
                self.assertTrue(issubclass(cls, Exception))

    def test_compat_inheritance(self):
        for name, bases in FAMILIES.items():
            cls = getattr(ie, name)
            with self.subTest(cls=name):
                for base in bases:
                    self.assertTrue(issubclass(cls, base), '%s should subclass %s' % (name, base.__name__))

    def test_catch_by_legacy_type(self):
        cases = [
            (ie.NetworkError('n'), OSError),
            (ie.StorageError('s'), OSError),
            (ie.CorruptDataError('c'), ValueError),
            (ie.ProcessError('p'), RuntimeError),
            (ie.QuotaError('q'), RuntimeError),
            (ie.AuthError('a'), PermissionError),
            (ie.ConfigError('g'), ValueError),
        ]
        for exc, base in cases:
            with self.subTest(exc=type(exc).__name__):
                with self.assertRaises(base):
                    raise exc

    def test_message_and_detail(self):
        exc = ie.StorageError('写盘失败', detail={'path': 'x', 'errno': 5})
        self.assertEqual(str(exc), '写盘失败')
        self.assertEqual(exc.detail, {'path': 'x', 'errno': 5})
        self.assertEqual(exc.code, 'E-IO-WRITE')
        self.assertEqual(exc.args, ('写盘失败',))


class InfraErrorsCodeGateTests(unittest.TestCase):
    def test_family_code_override_allowed(self):
        exc = ie.StorageError('m', code='E-IO-READ')
        self.assertEqual(exc.code, 'E-IO-READ')
        exc = ie.NetworkError('m', code='E-NET-TIMEOUT')
        self.assertEqual(exc.code, 'E-NET-TIMEOUT')

    def test_out_of_family_code_rejected(self):
        with self.assertRaises(ValueError):
            ie.ConfigError('m', code='E-NET-TIMEOUT')
        with self.assertRaises(ValueError):
            ie.NetworkError('m', code='E-QUOTA-EXCEEDED')

    def test_unregistered_code_rejected(self):
        with self.assertRaises(ValueError):
            ie.InfraError('m', code='E-NOPE-NOT-REAL')
        with self.assertRaises(ValueError):
            ie.ProcessError('m', code='E-IO-WRITE')

    def test_default_codes(self):
        expected = {
            'InfraError': 'E-UNKNOWN',
            'NetworkError': 'E-NET-UNREACHABLE',
            'StorageError': 'E-IO-WRITE',
            'CorruptDataError': 'E-IO-CORRUPT',
            'ProcessError': 'E-TOOL-FAILED',
            'QuotaError': 'E-QUOTA-EXCEEDED',
            'AuthError': 'E-AUTH-REJECTED',
            'ConfigError': 'E-CONFIG-INVALID',
        }
        for name, code in expected.items():
            with self.subTest(cls=name):
                self.assertEqual(getattr(ie, name).code, code)


if __name__ == '__main__':
    unittest.main()

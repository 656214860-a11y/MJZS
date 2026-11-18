# -*- coding: utf-8 -*-
"""I7 迁移回归：三个模块的技术异常已切换到 ``contract.infra_errors`` 族。

断言两类契约：
- 用户可见消息逐字不变（上层 ``str(exc)`` 直接展示的口径）；
- 旧的内置 ``except`` 子句继续命中（I6 多重继承兼容）。
"""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from contract.infra_errors import InfraError
from infra import comfy_service, request_ledger, unit_of_work as uow


class UnitOfWorkMigrationTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        patcher = mock.patch.object(uow, 'JOURNAL_ROOT', self.root / 'journal', create=True)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_foreign_token_typeerror_compat(self):
        with self.assertRaises(TypeError) as cm:
            uow.commit(object())
        exc = cm.exception
        self.assertIsInstance(exc, InfraError)
        self.assertEqual(exc.code, 'E-CONFIG-INVALID')
        self.assertEqual(str(exc), 'unit_of_work 令牌必须来自 begin()')

    def test_directory_entry_configerror_compat(self):
        with self.assertRaises(ValueError) as cm:
            uow.begin([self.root])
        exc = cm.exception
        self.assertIsInstance(exc, InfraError)
        self.assertEqual(exc.code, 'E-CONFIG-INVALID')
        self.assertIn('事务原语只登记文件，不登记目录', str(exc))

    def test_commit_after_rollback_message(self):
        target = self.root / 'a.txt'
        target.write_text('x', encoding='utf-8')
        token = uow.begin([target])
        uow.rollback(token)
        with self.assertRaises(ValueError) as cm:
            uow.commit(token)
        exc = cm.exception
        self.assertIsInstance(exc, InfraError)
        self.assertEqual(str(exc), '事务已回滚，不能再提交')

    def test_rollback_failed_runtimeerror_compat(self):
        self.assertTrue(issubclass(uow.RollbackFailedError, RuntimeError))
        self.assertTrue(issubclass(uow.RollbackFailedError, InfraError))
        exc = uow.RollbackFailedError('回滚失败', failures=[])
        self.assertEqual(exc.failures, [])
        self.assertIsInstance(exc, RuntimeError)


class RequestLedgerMigrationTests(unittest.TestCase):
    def test_quantity_validation_message_and_compat(self):
        for bad in (True, 'abc', -1, float('nan')):
            with self.subTest(bad=bad), self.assertRaises(ValueError) as cm:
                request_ledger.RequestLedger._quantity(bad)
            exc = cm.exception
            self.assertIsInstance(exc, InfraError)
            self.assertEqual(exc.code, 'E-CONFIG-INVALID')
            self.assertEqual(str(exc), '用量或费率必须是有限非负数')

    def test_budget_rejected_quota_code(self):
        exc = request_ledger.BudgetRejected('预留未通过')
        self.assertIsInstance(exc, ValueError)
        self.assertIsInstance(exc, InfraError)
        self.assertEqual(exc.code, 'E-QUOTA-EXCEEDED')
        self.assertEqual(str(exc), '预留未通过')

    def test_lock_timeout_unknown_code(self):
        exc = request_ledger.LedgerLockTimeout('锁超时')
        self.assertIsInstance(exc, ValueError)
        self.assertIsInstance(exc, InfraError)
        self.assertEqual(exc.code, 'E-UNKNOWN')

    def test_corrupt_detail_carries_path(self):
        with tempfile.TemporaryDirectory() as d:
            project = Path(d)
            path = request_ledger.request_ledger_path(project)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('{bad', encoding='utf-8')
            ledger = request_ledger.RequestLedger(project=project)
            # load() 把损坏内容翻成 CorruptDataError，detail 带路径与原因
            try:
                ledger.load()
            except ValueError as exc:
                self.assertIsInstance(exc, InfraError)
                self.assertIsNotNone(getattr(exc, 'detail', None))
            else:
                self.fail('损坏台账应抛 ValueError 族异常')


class ComfyMigrationTests(unittest.TestCase):
    def test_url_validation_message_and_compat(self):
        with self.assertRaises(ValueError) as cm:
            comfy_service.Comfy('http://example.com')
        exc = cm.exception
        self.assertIsInstance(exc, InfraError)
        self.assertEqual(exc.code, 'E-CONFIG-INVALID')
        self.assertEqual(str(exc), '请输入本机ComfyUI地址，例如 http://127.0.0.1:8189')

    def test_safetensors_corrupt_message_and_compat(self):
        with tempfile.TemporaryDirectory() as d:
            target = Path(d) / 'm.safetensors'
            target.write_bytes(b'\x00' * 4)
            with self.assertRaises(ValueError) as cm:
                comfy_service.validate_safetensors(target)
        exc = cm.exception
        self.assertIsInstance(exc, InfraError)
        self.assertEqual(str(exc), '不是有效safetensors文件，可能下载到了网页')

    def test_exception_class_compat(self):
        self.assertTrue(issubclass(comfy_service.ComfyGenerationFailed, ValueError))
        self.assertTrue(issubclass(comfy_service.ComfyGenerationFailed, RuntimeError))
        self.assertTrue(issubclass(comfy_service.ComfyGenerationFailed, InfraError))
        for cls in (comfy_service.ComfySubmissionUncertain,
                    comfy_service.ComfyRecoveryUnavailable):
            self.assertTrue(issubclass(cls, RuntimeError))
            self.assertTrue(issubclass(cls, InfraError))
        self.assertEqual(comfy_service.ComfyGenerationFailed('x').code, 'E-TOOL-FAILED')


if __name__ == '__main__':
    unittest.main()

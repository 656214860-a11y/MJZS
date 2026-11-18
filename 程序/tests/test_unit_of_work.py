# -*- coding: utf-8 -*-
"""L2 领域服务层优化任务书轮 5（功能轮）：``infra/unit_of_work`` 事务原语。

覆盖 ``begin``／``commit``／``rollback`` 三件套的行为契约：

- 多路径原子恢复：登记两路径、写两处新内容后失败，第一处也必须恢复原状；
- 取消路径：``BaseException``（自定义 ``Cancelled``）与 ``finally`` 里的回滚同样生效，
  不只在 ``except Exception`` 内；
- 进程中断路径：令牌随进程消失后磁盘 journal 仍在，下一次 ``begin``（或显式
  ``recover_pending``）按「原本不存在」与「原内容」语义恢复；
- 边界：原本不存在的路径回滚后被删除、commit 后 rollback 幂等空操作、
  rollback 后 commit 报错、空登记、重复登记、外来令牌、目录拒绝、
  rollback 内部失败时调用方原异常经 ``__context__`` 仍可见且其余路径仍尽力恢复。
"""
import gc
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from infra import unit_of_work as uow


class Cancelled(BaseException):
    """任务书说的取消路径：``BaseException`` 而非 ``Exception``，``except Exception`` 接不住。"""


class UnitOfWorkTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.journal_root = self.root / 'journal'
        # journal 根隔离到临时目录：本文件绝不碰真实 outputs/ 运行数据。
        # create=True：实现落地前空壳还没有 JOURNAL_ROOT，先红阶段也要能打到 NotImplementedError。
        patcher = mock.patch.object(uow, 'JOURNAL_ROOT', self.journal_root, create=True)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(gc.collect)

    # ── helpers ─────────────────────────────────────────────────
    def _write(self, path, data):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data if isinstance(data, bytes) else data.encode('utf-8'))

    def _target(self, name, content=b'original'):
        path = self.root / 'targets' / name
        self._write(path, content)
        return path

    def _absent(self, name):
        return self.root / 'targets' / name

    # ── 用例 1：多路径原子恢复 ──────────────────────────────────
    def test_rollback_restores_every_registered_path(self):
        a = self._target('a.json', b'{"a":1}')
        b = self._target('b.json', b'{"b":2}')
        token = uow.begin([a, b])
        self._write(a, b'{"a":9}')
        self._write(b, b'{"b":9}')
        try:
            raise RuntimeError('写第二处时模拟抛错')
        except RuntimeError:
            uow.rollback(token)
        self.assertEqual(a.read_bytes(), b'{"a":1}')
        self.assertEqual(b.read_bytes(), b'{"b":2}')

    # ── 用例 2：rollback 内部失败不掩盖调用方原异常 ─────────────
    def test_rollback_failure_keeps_original_exception_visible(self):
        a = self._target('a.json', b'orig-a')
        b = self._target('b.json', b'orig-b')
        token = uow.begin([a, b])
        self._write(a, b'new-a')
        self._write(b, b'new-b')
        # 制造 b 的恢复失败：b.json 置只读，原子替换在 Windows 上必炸（WinError 5），
        # 且失败不破坏现场——b 仍保持事务写入内容，正好验证「失败不覆盖原内容」。
        b.chmod(0o444)
        try:
            raise RuntimeError('original-work-boom')
        except RuntimeError:
            with self.assertRaises(uow.RollbackFailedError) as ctx:
                uow.rollback(token)
        # 原异常经 __context__ 链仍然可见。
        self.assertIsInstance(ctx.exception.__context__, RuntimeError)
        self.assertEqual(str(ctx.exception.__context__), 'original-work-boom')
        # 尽力恢复：a 已还原；b 失败保持事务写入内容。
        self.assertEqual(a.read_bytes(), b'orig-a')
        self.assertEqual(b.read_bytes(), b'new-b')
        # journal 保留：修好现场（去只读）后同一令牌可以重试成功。
        b.chmod(0o666)
        uow.rollback(token)
        self.assertEqual(b.read_bytes(), b'orig-b')

    # ── 用例 3：取消路径（BaseException）触发回滚 ──────────────
    def test_cancelled_path_rolls_back(self):
        a = self._target('a.json', b'orig-a')
        b = self._target('b.json', b'orig-b')
        token = uow.begin([a, b])
        with self.assertRaises(Cancelled):
            try:
                self._write(a, b'new-a')
                self._write(b, b'new-b')
                raise Cancelled()
            except BaseException:
                uow.rollback(token)
                raise
        self.assertEqual(a.read_bytes(), b'orig-a')
        self.assertEqual(b.read_bytes(), b'orig-b')

    def test_finally_path_rolls_back(self):
        a = self._target('a.json', b'orig-a')
        token = uow.begin([a])
        with self.assertRaises(ValueError):
            try:
                self._write(a, b'new-a')
                raise ValueError('finally 前的失败')
            finally:
                uow.rollback(token)
        self.assertEqual(a.read_bytes(), b'orig-a')

    # ── 进程中断路径：磁盘 journal ＋ 锁活性 ＋ begin 自动恢复 ──
    def test_process_death_recovered_by_next_begin(self):
        a = self._target('a.json', b'orig-a')
        b = self._target('b.json', b'orig-b')
        token = uow.begin([a, b])
        self._write(a, b'new-a')
        self._write(b, b'new-b')
        # 模拟进程死亡：不 commit／rollback，令牌被回收（锁释放、journal 留盘）。
        del token
        gc.collect()
        # 下一次 begin 先清扫陈旧 journal：a、b 必须恢复成 begin 时内容。
        c = self._absent('c.json')
        token2 = uow.begin([c])
        try:
            self.assertEqual(a.read_bytes(), b'orig-a')
            self.assertEqual(b.read_bytes(), b'orig-b')
        finally:
            uow.commit(token2)

    def test_recover_pending_restores_without_new_begin(self):
        a = self._target('a.json', b'orig-a')
        token = uow.begin([a])
        self._write(a, b'new-a')
        del token
        gc.collect()
        uow.recover_pending()
        self.assertEqual(a.read_bytes(), b'orig-a')

    # ── 边界：原本不存在 → 删除 ─────────────────────────────────
    def test_absent_path_is_deleted_on_rollback(self):
        existing = self._target('existing.json', b'orig')
        absent = self._absent('new.json')
        token = uow.begin([existing, absent])
        self._write(existing, b'changed')
        self._write(absent, b'created-by-transaction')
        uow.rollback(token)
        self.assertEqual(existing.read_bytes(), b'orig')
        self.assertFalse(absent.exists())

    # ── 边界：commit 语义 ───────────────────────────────────────
    def test_commit_keeps_new_content_and_rolls_back_nothing(self):
        a = self._target('a.json', b'orig-a')
        token = uow.begin([a])
        self._write(a, b'new-a')
        uow.commit(token)
        self.assertEqual(a.read_bytes(), b'new-a')
        # commit 后 rollback 是安全空操作：不报错、不改内容。
        uow.rollback(token)
        self.assertEqual(a.read_bytes(), b'new-a')
        # 重复 commit 幂等。
        uow.commit(token)
        self.assertEqual(a.read_bytes(), b'new-a')

    def test_commit_after_rollback_is_rejected(self):
        a = self._target('a.json', b'orig-a')
        token = uow.begin([a])
        uow.rollback(token)
        with self.assertRaises(ValueError):
            uow.commit(token)

    def test_second_rollback_is_idempotent_noop(self):
        a = self._target('a.json', b'orig-a')
        token = uow.begin([a])
        self._write(a, b'first-change')
        uow.rollback(token)
        self.assertEqual(a.read_bytes(), b'orig-a')
        # 回滚后的再次修改不属于事务：第二次 rollback 不得回滚它。
        self._write(a, b'post-rollback-edit')
        uow.rollback(token)
        self.assertEqual(a.read_bytes(), b'post-rollback-edit')

    # ── 边界：空登记与重复登记 ──────────────────────────────────
    def test_empty_paths_begin_commit_rollback(self):
        token = uow.begin([])
        uow.commit(token)
        token2 = uow.begin([])
        uow.rollback(token2)

    def test_duplicate_paths_registered_once(self):
        a = self._target('a.json', b'orig-a')
        token = uow.begin([a, a, self._target('b.json', b'orig-b')])
        self._write(a, b'new-a')
        uow.rollback(token)
        self.assertEqual(a.read_bytes(), b'orig-a')

    # ── 边界：令牌与路径校验 ────────────────────────────────────
    def test_foreign_token_rejected(self):
        with self.assertRaises(TypeError):
            uow.commit(object())
        with self.assertRaises(TypeError):
            uow.rollback('not-a-token')

    def test_directory_path_rejected_at_begin(self):
        folder = self.root / 'targets' / 'adir'
        folder.mkdir(parents=True)
        with self.assertRaises(ValueError):
            uow.begin([folder])

    def test_begin_failure_leaves_no_journal(self):
        folder = self.root / 'targets' / 'adir2'
        folder.mkdir(parents=True)
        with self.assertRaises(ValueError):
            uow.begin([self._target('ok.json', b'x'), folder])
        # 失败的 begin 不得留下会被自动恢复的 journal。
        self.assertFalse(self.journal_root.exists() and any(self.journal_root.iterdir()))


if __name__ == '__main__':
    unittest.main()

"""Broadcaster 回归测试。"""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import infra.broadcaster as broadcaster_module
from infra.broadcaster import Broadcaster
import pet_bus
import ui.pet_ui as pet_ui
class BroadcasterTests(unittest.TestCase):
    def test_broadcast_creates_utf8_timestamped_log(self):
        with tempfile.TemporaryDirectory() as directory:
            log_path = Path(directory) / "nested" / "sanhu_progress.log"
            message = Broadcaster.stage(3, "资产管理")
            result = Broadcaster(str(log_path)).broadcast(message)

            expected = Broadcaster.stage(3, "资产管理")
            self.assertEqual(result, expected)
            line = log_path.read_text(encoding="utf-8").strip()
            self.assertTrue(line.endswith(" " + expected))

    def test_broadcast_rejects_message_without_prefix(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "规定前缀"):
                Broadcaster(str(Path(directory) / "sanhu_progress.log")).broadcast("资产管理")

    def test_step_and_fixed_prefixes_are_valid(self):
        with tempfile.TemporaryDirectory() as directory:
            broadcaster = Broadcaster(str(Path(directory) / "sanhu_progress.log"))
            self.assertEqual(broadcaster.step(2, 4, "生成正典板"), "【步骤 2/4】生成正典板")
            for message in ("【门禁】上游输出完整，通过", "【警告】资产 CHR-05 正典板缺失",
                            "【阻塞】上游JSON不完整", "【完成】资产管理已完成",
                            "【恢复】检测到中断，从步骤 3 继续", "【下一阶段】连贯性清单",
                            "【模式】已切换到全自动模式"):
                self.assertEqual(broadcaster.broadcast(message), message)

    def test_pet_output_is_prefixed_and_recorded(self):
        with tempfile.TemporaryDirectory() as directory:
            pet = pet_ui.Pet.__new__(pet_ui.Pet)
            pet.errors = []
            pet.snapshot = lambda: {'stage': 'assets'}
            log_path = Path(directory) / 'sanhu_progress.log'
            pet.broadcaster = Broadcaster(str(log_path))

            message = pet._record_output('资产管理正在处理')

            expected = Broadcaster.stage(pet_bus.STAGES.index('assets') + 1, '资产管理正在处理')
            self.assertEqual(message, expected)
            self.assertIn(message, log_path.read_text(encoding='utf-8'))


class WarnOnceTests(unittest.TestCase):
    """R3298 轮 4B：属主写路径的「发一次【警告】」内部通道——同键去重、写日志、失败静默。"""

    def setUp(self):
        self._saved_log = broadcaster_module._PROGRAM_LOGS
        self.addCleanup(setattr, broadcaster_module, '_PROGRAM_LOGS', self._saved_log)
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.log_path = Path(self._tmp.name) / 'logs' / 'sanhu_progress.log'
        broadcaster_module._PROGRAM_LOGS = self.log_path
        self._saved_warned = set(broadcaster_module._WARNED)
        self.addCleanup(broadcaster_module._WARNED.clear)
        self.addCleanup(broadcaster_module._WARNED.update, self._saved_warned)

    def test_warn_once_writes_single_prefixed_line_per_key(self):
        key = 'artifact_future:test_kind'
        broadcaster_module._WARNED.discard(key)
        self.assertTrue(broadcaster_module.warn_once(key, '产物是更新版本写的'))
        self.assertFalse(broadcaster_module.warn_once(key, '产物是更新版本写的'))
        lines = [line for line in self.log_path.read_text(encoding='utf-8').splitlines()
                 if '【警告】产物是更新版本写的' in line]
        self.assertEqual(len(lines), 1)                      # 同键只落一行
        self.assertTrue(broadcaster_module.warn_once(key + ':other', '另一类产物'))
        self.assertEqual(len(self.log_path.read_text(encoding='utf-8').splitlines()), 2)

    def test_warn_once_swallows_write_failure(self):
        broadcaster_module._WARNED.discard('artifact_future:fail_kind')
        with mock.patch('builtins.open', side_effect=OSError('disk full')):
            self.assertFalse(broadcaster_module.warn_once('artifact_future:fail_kind', 'x'))
        # 失败也占位去重：同一 key 不会在故障期间反复重试刷日志
        self.assertFalse(broadcaster_module.warn_once('artifact_future:fail_kind', 'x'))


if __name__ == "__main__":
    unittest.main()

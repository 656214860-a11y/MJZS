"""commit_round：等锁逻辑只在锁持有进程存活时阻塞；失效锁被回收，超时不吞暂存区。"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

PROGRAM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROGRAM / 'scripts'))
import commit_round  # noqa: E402
import run_selftests  # noqa: E402


class CommitRoundTests(unittest.TestCase):
    def lock(self, common, pid):
        path = Path(common) / run_selftests.FULL_SAFE_LOCK_NAME
        path.write_text(json.dumps({'pid': pid, 'round': 1}), encoding='utf-8')
        return path

    def test_no_lock_passes_immediately(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertTrue(commit_round.wait_for_lock(Path(tmp), 0, out=lambda _: None))

    def test_dead_holder_lock_is_reclaimed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.lock(tmp, 2 ** 22 + 12345)
            self.assertTrue(commit_round.wait_for_lock(Path(tmp), 5, poll=0.01, out=lambda _: None))
            self.assertFalse(path.exists())

    def test_live_holder_times_out_and_lock_stays(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.lock(tmp, os.getpid())
            self.assertFalse(commit_round.wait_for_lock(Path(tmp), 0.05, poll=0.01, out=lambda _: None))
            self.assertTrue(path.exists())


if __name__ == '__main__':
    unittest.main()

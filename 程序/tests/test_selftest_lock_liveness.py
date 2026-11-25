"""锁活性判定与提交等锁上限：陈旧心跳可回收，新鲜／未来／旧格式锁不误杀，默认等锁 5 分钟。

用例全部落在替身 holder 字典与临时锁文件上：不创建真实全局锁、不起 Tk 窗口。
"""
import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

PROGRAM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROGRAM))
sys.path.insert(0, str(PROGRAM / 'scripts'))

import selftest_env as env  # noqa: E402
import commit_round  # noqa: E402


class LockLivenessTests(unittest.TestCase):
    """_holder_stalled 与 reclaim_stale_lock 的同一静默口径。"""

    def _lock_file(self, directory, holder):
        path = Path(directory) / env.FULL_SAFE_LOCK_NAME
        path.write_text(json.dumps(holder), encoding='utf-8')
        return path

    def test_stalled_holder_is_reclaimable(self):
        now = time.time()
        holder = {'pid': os.getpid(), 'round': 1, 'token': 'stalled',
                  'heartbeat_at': now - 300, 'started_at': now - 400, 'created_at': now - 400}
        self.assertTrue(env._holder_stalled(holder, now=now))
        self.assertFalse(env._holder_stalled(holder, now=now, stale=600))
        with tempfile.TemporaryDirectory() as tmp:
            path = self._lock_file(tmp, holder)
            self.assertTrue(env.reclaim_stale_lock(str(path)))
            self.assertFalse(path.exists())

    def test_live_heartbeat_is_not_reclaimed(self):
        now = time.time()
        for beat in (now, now - 30):
            holder = {'pid': os.getpid(), 'round': 1, 'heartbeat_at': beat, 'started_at': now - 400}
            self.assertFalse(env._holder_stalled(holder, now=now))
        with tempfile.TemporaryDirectory() as tmp:
            holder = {'pid': os.getpid(), 'round': 1, 'token': 'live',
                      'heartbeat_at': now, 'started_at': now - 400}
            path = self._lock_file(tmp, holder)
            self.assertFalse(env.reclaim_stale_lock(str(path)))
            self.assertTrue(path.exists())

    def test_legacy_lock_without_heartbeat_falls_back(self):
        now = time.time()
        fresh = {'pid': os.getpid(), 'round': 1, 'started_at': now}
        stale = {'pid': os.getpid(), 'round': 1, 'started_at': now - 400}
        legacy_field = {'pid': os.getpid(), 'round': 1, 'heartbeat': now}
        created_only = {'pid': os.getpid(), 'created_at': now - 400}
        self.assertFalse(env._holder_stalled(fresh, now=now))
        self.assertFalse(env._holder_stalled(legacy_field, now=now))
        self.assertTrue(env._holder_stalled(stale, now=now))
        self.assertTrue(env._holder_stalled(created_only, now=now))

    def test_future_heartbeat_not_stalled(self):
        now = time.time()
        for beat in (now + 60, now + 3600):
            holder = {'pid': os.getpid(), 'heartbeat_at': beat, 'started_at': now - 400}
            self.assertFalse(env._holder_stalled(holder, now=now))
        self.assertFalse(env._holder_stalled({'pid': os.getpid(), 'started_at': now + 600}, now=now))

    def test_empty_or_invalid_holder_is_stalled(self):
        now = time.time()
        for bad in (None, {}, {'heartbeat_at': 'not-a-number'}, 'holder', []):
            self.assertTrue(env._holder_stalled(bad, now=now))

    def test_commit_round_default_wait_is_five(self):
        seen = []
        with patch.object(commit_round, 'commit', lambda args: seen.append(args.wait_minutes) or 0):
            commit_round.main(['-m', 'R1: 默认等锁上限'])
        self.assertEqual(seen, [5.0])


if __name__ == '__main__':
    unittest.main()

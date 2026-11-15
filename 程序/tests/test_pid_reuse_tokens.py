"""跨树令牌的持有者记录必须能识别 PID 复用；只用临时目录，不碰真实 common-dir。"""
import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

import run_selftests as runner
import selftest_env


class PidReuseTokenTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.common = Path(self.folder.name)
        self.addCleanup(self.folder.cleanup)
        self.addCleanup(runner._GUI_LOCK_DEPTH.clear)
        self.addCleanup(runner._FULL_LOCK_DEPTH.clear)

    def test_current_pid_with_old_record_is_dead_but_recent_record_is_alive(self):
        self.assertTrue(runner._pid_is_alive(os.getpid(), time.time()),
                        '创建时间取不到时必须退回只按 PID 判断')
        self.assertFalse(runner._pid_is_alive(os.getpid(), time.time() - 86400))

    def test_dead_gui_ticket_is_dropped_and_new_ticket_becomes_first(self):
        queue = self.common / runner.GUI_QUEUE_NAME
        queue.mkdir()
        dead = queue / ('%020d-%d-000000.ticket' % (1, os.getpid()))
        dead.write_text(json.dumps({'pid': os.getpid(), 'started_at': time.time() - 86400}),
                        encoding='utf-8')
        runner._drop_dead_gui_tickets(str(queue))
        self.assertFalse(dead.exists())
        new_ticket = runner._join_gui_queue(str(queue))
        self.assertTrue(runner._gui_queue_is_first(str(queue), new_ticket))

    def test_live_gui_ticket_is_not_dropped(self):
        queue = self.common / runner.GUI_QUEUE_NAME
        queue.mkdir()
        live = queue / ('%020d-%d-000000.ticket' % (1, os.getpid()))
        live.write_text(json.dumps({'pid': os.getpid(), 'started_at': time.time()}),
                        encoding='utf-8')
        runner._drop_dead_gui_tickets(str(queue))
        self.assertTrue(live.exists())
        runner._GUI_LOCK_DEPTH.clear()

    def test_gui_lock_old_record_is_reclaimed_but_live_record_rejects(self):
        path = self.common / runner.GUI_LOCK_NAME
        old = {'pid': os.getpid(), 'started_at': time.time() - 86400}
        path.write_text(json.dumps(old), encoding='utf-8')
        token = runner.acquire_gui_lock(str(self.common), wait=0)
        self.assertEqual(runner.lock_holder(token)['pid'], os.getpid())
        self.assertNotEqual(runner.lock_holder(token)['started_at'], old['started_at'])
        runner.release_gui_lock(token)
        path.write_text(json.dumps({'pid': os.getpid(), 'started_at': time.time()}),
                        encoding='utf-8')
        with self.assertRaisesRegex(RuntimeError, 'PID %d' % os.getpid()):
            runner.acquire_pid_lock(runner.GUI_LOCK_NAME, str(self.common))

    def test_creation_time_failure_falls_back_to_pid_check(self):
        with mock.patch.object(selftest_env, '_process_created_at', return_value=None):
            self.assertTrue(runner._pid_is_alive(os.getpid(), time.time() - 86400))
        # 不存在的 PID：OpenProcess 失败，取不到创建时间，只能沿用“只看 PID”的判死结果。
        missing = 0x7FFFFFF0
        self.assertIsNone(runner._process_created_at(missing))
        self.assertFalse(runner._pid_is_alive(missing, time.time() - 86400))


if __name__ == '__main__':
    unittest.main()

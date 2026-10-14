# -*- coding: utf-8 -*-
"""后台自动全量：钩子里起的子进程不得继承 git 导出的 GIT_* 变量，未到触发点或已有任务时不起进程。"""
import importlib.util
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

PROGRAM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROGRAM))
spec = importlib.util.spec_from_file_location('auto_full_safe_for_tests', PROGRAM / 'scripts' / 'auto_full_safe.py')
auto = importlib.util.module_from_spec(spec)
spec.loader.exec_module(auto)


class AutoFullSafeTests(unittest.TestCase):
    def test_spawn_strips_git_environment(self):
        with mock.patch.object(auto, 'status', return_value={'auto_due': True}), \
             mock.patch.object(auto, '_already_running', return_value=False), \
             mock.patch.dict(os.environ, {'GIT_INDEX_FILE': 'x', 'GIT_DIR': 'y', 'KEEP_ME': '1'}), \
             mock.patch.object(auto.subprocess, 'Popen') as popen:
            self.assertEqual(auto.spawn(), 0)
        env = popen.call_args.kwargs['env']
        self.assertFalse([key for key in env if key.startswith('GIT_')])
        self.assertEqual(env.get('KEEP_ME'), '1')

    def test_spawn_does_nothing_when_not_due_or_already_running(self):
        for due, running in ((False, False), (True, True)):
            with self.subTest(due=due, running=running), \
                 mock.patch.object(auto, 'status', return_value={'auto_due': due}), \
                 mock.patch.object(auto, '_already_running', return_value=running), \
                 mock.patch.object(auto.subprocess, 'Popen') as popen:
                self.assertEqual(auto.spawn(), 0)
                popen.assert_not_called()

    def test_hook_entry_swallows_errors(self):
        with mock.patch.object(auto, 'spawn', side_effect=RuntimeError('boom')):
            self.assertEqual(auto.main(['--spawn']), 0)


if __name__ == '__main__':
    unittest.main()

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


class FailureNoticeTests(unittest.TestCase):
    def test_red_modules_are_read_from_the_log_in_order_without_duplicates(self):
        log = '### test_core（1 条红）\n\nx\n### test_asset_gating（2 条红）\n### test_core（3 条红）\n'
        self.assertEqual(auto.red_modules(log), ['test_core', 'test_asset_gating'])

    def test_notice_only_for_a_failed_last_run(self):
        failed = {'head': 'abcdef1234', 'returncode': 1, 'finished_at': 't', 'red': ['test_core'], 'log': 'L'}
        with mock.patch.object(auto, 'last_result', return_value=failed):
            text = auto.failure_notice()
        self.assertIn('abcdef1', text)
        self.assertIn('test_core', text)
        for result in ({}, {'returncode': 0}):
            with mock.patch.object(auto, 'last_result', return_value=result):
                self.assertEqual(auto.failure_notice(), '')

    def test_notice_flag_prints_and_never_fails(self):
        with mock.patch.object(auto, 'failure_notice', return_value='boom-text'), \
             mock.patch('builtins.print') as shown:
            self.assertEqual(auto.main(['--notice']), 0)
        shown.assert_called_once_with('boom-text')
        with mock.patch.object(auto, 'failure_notice', side_effect=RuntimeError('x')):
            self.assertEqual(auto.main(['--notice']), 0)

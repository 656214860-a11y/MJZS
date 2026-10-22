"""引擎子进程启动：异常打断时必须先结束进程再注销，不能留下登记表之外的孤儿（R1777 审计）。"""
import unittest
from unittest import mock

import workflow_engines


class _Process:
    pid = 4321
    returncode = None

    def __init__(self, error=None):
        self.error = error

    def communicate(self, prompt):
        if self.error:
            raise self.error
        self.returncode = 0
        return '', ''


class RunCleanupTests(unittest.TestCase):
    def _run(self, process):
        with mock.patch.object(workflow_engines.subprocess, 'Popen', return_value=process), \
             mock.patch.object(workflow_engines, 'register_process') as register, \
             mock.patch.object(workflow_engines, 'forget_process') as forget, \
             mock.patch.object(workflow_engines, 'terminate_process_tree') as terminate:
            try:
                code = workflow_engines._run(['x'], 'proj', 'prompt', None, None)
            except RuntimeError:
                code = 'raised'
        return code, register, forget, terminate

    def test_interrupted_run_terminates_then_forgets(self):
        code, register, forget, terminate = self._run(_Process(RuntimeError('pipe')))
        self.assertEqual(code, 'raised')
        register.assert_called_once()
        terminate.assert_called_once()
        forget.assert_called_once()

    def test_normal_run_does_not_terminate(self):
        code, _register, forget, terminate = self._run(_Process())
        self.assertEqual(code, 0)
        terminate.assert_not_called()
        forget.assert_called_once()


if __name__ == '__main__':
    unittest.main()

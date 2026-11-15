"""引擎子进程启动：异常打断时必须先结束进程再注销，不能留下登记表之外的孤儿（R1777 审计）。"""
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import workflow_engines
import workflow_process_registry


class _Process:
    pid = 4321
    returncode = None

    def __init__(self, error=None):
        self.error = error

    def communicate(self, prompt, timeout=None):
        if self.error:
            raise self.error
        self.returncode = 0
        return '', ''


class RunCleanupTests(unittest.TestCase):
    def _run(self, process):
        with mock.patch.object(workflow_engines.subprocess, 'Popen', return_value=process), \
             mock.patch.object(workflow_process_registry, 'register_process') as register, \
             mock.patch.object(workflow_process_registry, 'forget_process') as forget, \
             mock.patch('contract.platform_tools.terminate_process_tree') as terminate:
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


class BackgroundRunTests(unittest.TestCase):
    """Codex 把输出写进运行日志；Claude 以 JSON 回复，成功才落制作报告，失败或未授权都报错。"""

    def run_engine(self, engine, returncode, output=''):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        report, logfile = root / '报告.md', root / 'run.log'

        def fake_run(args, project, prompt, stdout, stderr, timeout, on_output=None):
            self.assertEqual((['cmd'], 'proj', '任务', 42), (args, project, prompt, timeout))
            stdout.write(output)
            return returncode
        with mock.patch.object(workflow_engines, '_run', fake_run),              mock.patch.object(workflow_engines, 'background_command', return_value=['cmd']),              mock.patch.object(workflow_engines, 'ensure_request_context', lambda prompt, stage: prompt),              mock.patch.object(workflow_engines, 'reserve_stage_process_slot', return_value='slot'),              mock.patch.object(workflow_engines, 'release_process_slot') as release:
            try:
                workflow_engines.run_background({'engine': engine, 'stage': '剧本', 'timeout_seconds': 42},
                                                'proj', root / 'out', report, logfile, '任务')
                error = None
            except ValueError as exc:
                error = str(exc)
        release.assert_called_once_with('slot')
        return root, report, logfile, error

    def test_codex_output_goes_to_the_log(self):
        _, report, logfile, error = self.run_engine('codex', 0, '跑完了')
        self.assertIsNone(error)
        self.assertEqual('跑完了', logfile.read_text(encoding='utf-8'))
        self.assertFalse(report.exists())
        _, _, _, error = self.run_engine('codex', 2)
        self.assertEqual(workflow_engines.ENGINES['codex'] + ' 执行失败，请查看运行日志（安装版本、登录、额度或权限）', error)

    def test_claude_json_reply_becomes_the_report(self):
        root, report, _, error = self.run_engine('claude', 0, json.dumps({'result': ' 报告正文 '}))
        self.assertIsNone(error)
        self.assertEqual('报告正文', report.read_text(encoding='utf-8'))
        self.assertEqual(['run.log', '报告.md', '报告.response.json'], sorted(p.name for p in root.iterdir()))

    def test_claude_empty_denied_or_failed_runs_raise(self):
        _, report, _, error = self.run_engine('claude', 0, json.dumps({'result': '  '}))
        self.assertEqual('Claude 未返回制作报告正文，请查看响应记录', error)
        self.assertFalse(report.exists())
        _, report, _, error = self.run_engine('claude', 0, json.dumps({'result': '半成品', 'permission_denials': ['Write']}))
        self.assertEqual('Claude 未完成任务或所需操作未获授权，请查看制作报告及响应记录', error)
        self.assertEqual('半成品', report.read_text(encoding='utf-8'))
        root, _, _, error = self.run_engine('claude', 1, 'oops')
        self.assertIn('执行失败', error)
        self.assertEqual(['run.log'], sorted(p.name for p in root.iterdir()))


if __name__ == '__main__':
    unittest.main()

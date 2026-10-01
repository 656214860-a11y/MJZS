# -*- coding: utf-8 -*-
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class InteractiveLaunchTests(unittest.TestCase):
    def test_interactive_launch_checks_budget_before_creating_task_files(self):
        import qwen_adapter
        with tempfile.TemporaryDirectory() as td, \
             patch.object(qwen_adapter, 'ensure_request_context', side_effect=ValueError('提示词过长')):
            with self.assertRaisesRegex(ValueError, '提示词过长'):
                qwen_adapter.launch_interactive(td, 'writing', '标题', '提示词', {})
            self.assertFalse((Path(td) / '工作流任务').exists())

    def test_interactive_launch_uses_platform_process_boundary(self):
        import qwen_adapter

        class Process:
            pass

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            executable = root / 'qwen.exe'
            executable.write_bytes(b'')
            process = Process()
            with patch.object(qwen_adapter, 'command', return_value=[str(executable), '--cli']), \
                 patch('qwen_setup.environment', return_value={'OPENAI_MODEL': 'qwen'}), \
                 patch.object(qwen_adapter, 'launch_windows_app', return_value=process) as launch, \
                 patch.object(qwen_adapter.threading, 'Thread') as thread:
                result = qwen_adapter.launch_interactive(root, 'writing', '标题', '提示词', {})
            self.assertIs(result['process'], process)
            args = launch.call_args.kwargs['args']
            self.assertEqual(args[:2], [str(executable), '--cli'])
            self.assertEqual(launch.call_args.args, (str(executable), 'Qwen Code'))
            self.assertEqual(launch.call_args.kwargs['cwd'], root)
            thread.return_value.start.assert_called_once_with()
            from workflow_process_registry import forget_process
            forget_process(root, process)

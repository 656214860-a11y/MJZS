# -*- coding: utf-8 -*-
from tests.architecture._scan import desktop_text  # R1490：Desktop 方法分布在 desktop.py 与迁出的 Mixin 模块
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

    def test_qwen_readiness_waits_stay_off_the_desktop_callback(self):
        """续发和启动后的命名都可能等待 Qwen 就绪，必须经后台边界。"""
        root = Path(__file__).resolve().parents[1]
        adapter = (root / 'qwen_adapter.py').read_text(encoding='utf-8')
        desktop = desktop_text()
        self.assertIn(
            "threading.Thread(target=name_when_ready,args=(process,),daemon=True).start()",
            adapter)
        start = desktop.index("if key in sessions and sessions[key].poll() is None:")
        end = desktop.index("            def launched(result):", start)
        continuation = desktop[start:end]
        self.assertIn("from qwen_adapter import submit_existing", continuation)
        self.assertIn("self.async_(submit,submitted);return", continuation)

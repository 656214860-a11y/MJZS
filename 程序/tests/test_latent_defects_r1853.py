"""R1853 体检发现的潜伏缺陷：每条先复现，再验证修复。

1 共享缓存被调用方就地改写；2 引擎子进程无超时；3 Codex 输出坏字节误报未登录；
4 进程登记表路径写法不同就找不到；5 三虎错误列表无上限；6 带 BOM 的 Qwen 设置被当成空；
7 资产绑定绕过 Windows 替换重试。
"""
import io
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import file_cache


class SharedCacheCopyTests(unittest.TestCase):
    def setUp(self):
        file_cache.clear()

    def test_mutating_a_read_does_not_leak_into_the_next_read(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'a.json'
            path.write_text(json.dumps({'engines': {'codex': {'ok': True}}, 'shots': [1]}), encoding='utf-8')
            first = file_cache.read_json(path)
            first['engines']['codex']['ok'] = False
            first['shots'].append(2)
            first['extra'] = 1
            self.assertEqual(file_cache.read_json(path), {'engines': {'codex': {'ok': True}}, 'shots': [1]})

    def test_failed_ledger_write_leaves_cache_matching_disk(self):
        from infra import engine_probe
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'ledger.json'
            path.write_text(json.dumps({'schema': 1, 'engines': {}}), encoding='utf-8')
            file_cache.read_json(path)
            row = {'engine': 'codex', 'at': 'now', 'verdict': 'ok'}
            with patch('line_endings.write_text', side_effect=OSError('disk full')):
                with self.assertRaises(OSError):
                    engine_probe.record(row, path)
            self.assertEqual(file_cache.read_json(path), {'schema': 1, 'engines': {}})


class EngineTimeoutTests(unittest.TestCase):
    def test_hung_engine_is_killed_and_unregistered_after_timeout(self):
        import workflow_engines
        from infra.workflow_process_registry import processes
        with tempfile.TemporaryDirectory() as td:
            args = [sys.executable, '-I', '-c', 'import time; time.sleep(60)']
            start = time.monotonic()
            with open(os.devnull, 'w') as sink:
                with self.assertRaises(ValueError) as caught:
                    workflow_engines._run(args, Path(td), '', sink, sink, timeout=1)
            self.assertLess(time.monotonic() - start, 20)
            self.assertIn('超时', str(caught.exception))
            self.assertEqual(processes(Path(td)), [])

    def test_default_timeout_is_two_hours_and_config_overrides(self):
        import workflow_engines
        self.assertEqual(workflow_engines.engine_timeout({}), 2 * 3600)
        self.assertEqual(workflow_engines.engine_timeout({'timeout_seconds': 90}), 90)


class CodexDecodeTests(unittest.TestCase):
    def test_invalid_utf8_line_does_not_close_the_connection(self):
        import codex_tasks
        reply = b'\xff\xfe garbage\n' + json.dumps({'id': 1, 'result': {}}).encode() + b'\n'

        class FakeProcess:
            def __init__(self, args, **kwargs):
                self.stdout = io.TextIOWrapper(io.BytesIO(reply), encoding=kwargs.get('encoding'),
                                               errors=kwargs.get('errors') or 'strict')
                self.stdin = io.StringIO()
                self.pid = 0
            def poll(self):
                return 0
            def wait(self, timeout=None):
                return 0

        client = codex_tasks.RPC.__new__(codex_tasks.RPC)
        with patch('codex_tasks.shutil.which', return_value='codex.exe'), \
             patch('codex_tasks.subprocess.Popen', FakeProcess), \
             patch.object(codex_tasks.RPC, 'environment', lambda self: {}):
            entered = client.__enter__()
            # 乱码行被跳过后，随后的合法 id=1 应答必须被读到：initialize 成功、连接没被关闭。
            self.assertIs(entered, client)
            entered.__exit__(None, None, None)


class ProcessRegistryKeyTests(unittest.TestCase):
    def test_same_folder_spelled_differently_finds_the_process(self):
        from infra.workflow_process_registry import register_process, forget_process, processes
        with tempfile.TemporaryDirectory() as td:
            marker = object()
            register_process(Path(td), marker)
            try:
                self.assertEqual(processes(td.replace('\\', '/') + '/'), [marker])
            finally:
                forget_process(Path(td), marker)
            self.assertEqual(processes(Path(td)), [])


class BoundedErrorLogTests(unittest.TestCase):
    def test_error_log_keeps_recent_entries_and_counts_all(self):
        import pet_bus
        log = pet_bus.ErrorLog()
        for number in range(pet_bus.ERROR_LIMIT * 3):
            log.append(('pump', str(number)))
        self.assertEqual(len(log), pet_bus.ERROR_LIMIT)
        self.assertEqual(log[-1], ('pump', str(pet_bus.ERROR_LIMIT * 3 - 1)))
        self.assertEqual(log.total, pet_bus.ERROR_LIMIT * 3)
        self.assertEqual(pet_bus.ErrorLog(), [])

    def test_stage_queue_and_agent_errors_are_bounded(self):
        import pet_bus, pet_agent, pet_ui
        holders = (pet_ui.StageQueue('script'), pet_agent.Agent(persist=False))
        for holder in holders:
            for number in range(pet_bus.ERROR_LIMIT + 10):
                pet_bus.emit_safe(_Broken(), holder.errors, 'x')
            self.assertEqual(len(holder.errors), pet_bus.ERROR_LIMIT, type(holder).__name__)


class _Broken:
    def emit(self, kind, **payload):
        raise RuntimeError('boom')


class QwenSettingsBomTests(unittest.TestCase):
    def test_settings_saved_with_bom_keep_user_values(self):
        import qwen_setup
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'qwen-api.json'
            path.write_bytes('﻿'.encode('utf-8') + json.dumps({'model': 'my-model'}).encode('utf-8'))
            with patch('qwen_setup.settings_path', return_value=path), \
                 patch('qwen_setup.unified_key', return_value=''):
                self.assertEqual(qwen_setup.load()['model'], 'my-model')


class AssetBindingReplaceRetryTests(unittest.TestCase):
    def test_transient_sharing_violation_is_retried(self):
        from agent.core import save
        from stage_execution_service import bind_asset_canonical_view
        with tempfile.TemporaryDirectory() as td:
            project = Path(td) / 'project'
            base = project / '05资产管理'
            save(project / 'config.json', {'episode_dir': '05资产管理'})
            save(base / 'assets/资产清单/assets.json', {'CHAR_001': {'name': '小满'}})
            source = project / 'source.png'
            source.write_bytes(b'png-data')
            real = os.replace
            failed = []

            def flaky(src, dst):
                if Path(dst).suffix == '.png' and not failed:
                    failed.append(dst)
                    raise PermissionError(13, '拒绝访问')
                return real(src, dst)
            with patch('os.replace', flaky):
                dest = bind_asset_canonical_view(project, base, 'CHAR_001', 'front', source)
            self.assertTrue(failed)
            self.assertEqual(Path(dest).read_bytes(), b'png-data')


if __name__ == '__main__':
    unittest.main()

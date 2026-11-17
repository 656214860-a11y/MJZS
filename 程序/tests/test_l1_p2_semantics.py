# -*- coding: utf-8 -*-
"""L1 任务书轮4（P2 语义与可观测）：broadcaster 并发不交错、临时文件写失败清理、
cloud_assets 列表一致性、预留槽位异常释放、Job Object 随父退出、native_apps 按登记进程号结束。"""
import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

import infra.aigc_lint as aigc_lint
import infra.native_apps as native_apps
import infra.workflow_process_registry as registry
import orchestrator.workflow_engines as workflow_engines
from infra.broadcaster import Broadcaster
from infra.cloud_assets import graph as cloud_graph
from skip_reasons import PLATFORM_WINDOWS_ONLY

PROGRAM = Path(__file__).resolve().parents[1]


class BroadcasterConcurrencyTests(unittest.TestCase):
    def test_ten_threads_hundred_lines_no_interleave(self):
        with tempfile.TemporaryDirectory() as td:
            log = Path(td) / 'progress.log'
            caster = Broadcaster(str(log))
            errors = []

            def worker(tag):
                try:
                    for i in range(10):
                        caster.broadcast('【警告】%s-%d' % (tag, i))
                except Exception as exc:                       # noqa: BLE001
                    errors.append(exc)

            threads = [threading.Thread(target=worker, args=('t%d' % n,)) for n in range(10)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(30)
            self.assertFalse(errors)
            lines = log.read_text(encoding='utf-8').splitlines()
            self.assertEqual(len(lines), 100)
            for line in lines:
                # 每行必须是「时间戳＋一个完整前缀消息」，不允许两行内容被写进同一物理行。
                self.assertRegex(line, r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} 【警告】t\d-\d+$')
            caster.close()


class AigcLintTempTests(unittest.TestCase):
    def test_write_temp_failure_leaves_no_residue(self):
        with tempfile.TemporaryDirectory() as td:
            old = os.environ.get('TMPDIR')
            os.environ['TMPDIR'] = td
            os.environ['TEMP'] = td
            os.environ['TMP'] = td
            try:
                broken = mock.MagicMock()
                broken.write.side_effect = OSError('disk full')
                with mock.patch.object(aigc_lint.tempfile, 'NamedTemporaryFile', return_value=broken):
                    with self.assertRaises(OSError):
                        aigc_lint._write_temp('剧本正文')
            finally:
                for key, value in (('TMPDIR', old), ('TEMP', old), ('TMP', old)):
                    if value is None:
                        os.environ.pop(key, None)
                    else:
                        os.environ[key] = value
            self.assertEqual(list(Path(td).iterdir()), [])

    def test_feed_path_removes_file_on_error(self):
        with tempfile.TemporaryDirectory() as td:
            os.environ['TMP'] = td
            try:
                with self.assertRaises(RuntimeError):
                    with aigc_lint._feed_path('x'):
                        raise RuntimeError('boom')
            finally:
                os.environ.pop('TMP', None)
            self.assertEqual([p for p in Path(td).iterdir() if p.suffix == '.md'], [])


class CloudAssetsGraphTests(unittest.TestCase):
    def _asset(self, paths):
        return {'reference_images': paths, 'reference_roles': {}}

    def test_length_mismatch_between_images_and_paths_raises(self):
        asset = self._asset(['a.png'])
        # images 2 张、paths 只有 1 条 → 长度不一致必须报错而不是静默贴错角色
        with self.assertRaises(ValueError) as ctx:
            cloud_graph(mock.Mock(url='http://127.0.0.1:1'), 'aid', asset, 'prompt',
                        ['a.png', 'b.png'], {'backend': 'Seedream 5.0 Pro'})
        self.assertIn('不一致', str(ctx.exception))

    def test_missing_reference_file_raises_before_upload(self):
        with tempfile.TemporaryDirectory() as td:
            gone = str(Path(td) / 'gone.png')
            asset = self._asset([gone])                  # paths 与 images 等长，走到 is_file()
            with self.assertRaises(ValueError) as ctx:
                cloud_graph(mock.Mock(url='http://127.0.0.1:1'), 'aid', asset, 'prompt',
                            [gone], {'backend': 'Seedream 5.0 Pro'})
            self.assertIn('不存在', str(ctx.exception))


class SlotReleaseOnErrorTests(unittest.TestCase):
    def test_launch_oserror_releases_reserved_slot(self):
        with tempfile.TemporaryDirectory() as td:
            project = Path(td)
            config = {'engine': 'claude'}
            with mock.patch.object(workflow_engines, 'find_program', return_value='C:/fake/claude.exe'), \
                 mock.patch.object(workflow_engines, 'gui_claude_program', return_value=False), \
                 mock.patch.object(workflow_engines, 'launch_windows_app',
                                   side_effect=OSError('winerror 2')), \
                 mock.patch.object(workflow_engines, 'reserve_stage_process_slot', return_value='slot'), \
                 mock.patch.object(workflow_engines, 'release_process_slot') as release:
                with self.assertRaises(OSError):
                    workflow_engines.launch_interactive(project, '剧本', '标题', '提示', config)
            release.assert_called_with('slot')

    def test_release_process_slot_is_idempotent(self):
        token = registry.reserve_process_slot('p', 's', stage_limit=2, global_limit=4)
        registry.release_process_slot(token)
        registry.release_process_slot(token)          # 重复释放安全
        token2 = registry.reserve_process_slot('p', 's', stage_limit=2, global_limit=4)
        self.assertIsNot(token2, token)
        registry.release_process_slot(token2)


class JobObjectTests(unittest.TestCase):
    @unittest.skipUnless(os.name == 'nt', PLATFORM_WINDOWS_ONLY)
    def test_registered_child_dies_with_parent_crash(self):
        """登记进子进程后父进程被强杀（os._exit），Job Object 的 KILL_ON_JOB_CLOSE 应带走子进程。"""
        import time
        program = str(PROGRAM)
        script = (
            "import os, sys\n"
            "sys.path.insert(0, sys.argv[1])\n"
            "import subprocess\n"
            "from infra import workflow_process_registry as reg\n"
            "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(120)'])\n"
            "reg.register_process(None, child)\n"
            "print('ready %d' % child.pid, flush=True)\n"
            "os._exit(1)\n"                                   # 模拟崩溃：不跑 finally、不关句柄
        )
        parent = subprocess.Popen([sys.executable, '-B', '-c', script, program],
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                  creationflags=subprocess.CREATE_NO_WINDOW)
        line = parent.stdout.readline()
        self.assertIn('ready', line)
        child_pid = int(line.split()[-1])
        parent.wait(timeout=30)
        # KILL_ON_JOB_CLOSE：父进程退出、Job 句柄关闭后，登记子进程应在数秒内被结束。
        deadline = time.time() + 15
        alive = True
        while time.time() < deadline:
            check = subprocess.run(['tasklist', '/FI', 'PID eq %d' % child_pid, '/NH'],
                                   capture_output=True, text=True, timeout=10,
                                   creationflags=subprocess.CREATE_NO_WINDOW)
            if str(child_pid) not in (check.stdout or ''):
                alive = False
                break
            time.sleep(0.5)
        self.assertFalse(alive, '登记子进程在父进程强杀后仍存活')


class NativeAppsCloseTests(unittest.TestCase):
    def test_no_image_name_taskkill_and_guidance_when_empty(self):
        calls = []

        def fake_run(args, **kwargs):
            calls.append(list(args))
            result = mock.Mock()
            result.returncode = 0
            result.stdout = b''
            return result

        with mock.patch.object(native_apps, 'comfy_server_pids', return_value=[]), \
             mock.patch.object(registry, 'all_processes', return_value=[]), \
             mock.patch.object(native_apps.subprocess, 'run', side_effect=fake_run), \
             mock.patch.object(native_apps, 'require_windows', lambda *a, **k: None):
            message = native_apps.force_close_comfy({})
        self.assertIn('手动关闭', message)
        self.assertFalse(any('/IM' in arg for call in calls for arg in call))

    def test_registered_pid_is_killed_by_pid_not_image(self):
        proc = mock.Mock()
        proc.pid = 4321
        calls = []

        def fake_run(args, **kwargs):
            calls.append(list(args))
            result = mock.Mock()
            result.returncode = 0
            result.stdout = b''
            return result

        with mock.patch.object(native_apps, 'comfy_server_pids', return_value=[8765]), \
             mock.patch.object(registry, 'all_processes', return_value=[proc]), \
             mock.patch.object(native_apps.subprocess, 'run', side_effect=fake_run), \
             mock.patch.object(native_apps, 'require_windows', lambda *a, **k: None):
            message = native_apps.force_close_comfy({})
        pids = {call[call.index('/PID') + 1] for call in calls if '/PID' in call}
        self.assertEqual(pids, {'8765', '4321'})
        self.assertFalse(any('/IM' in call for call in calls))
        self.assertIn('已强制关闭', message)


if __name__ == '__main__':
    unittest.main()

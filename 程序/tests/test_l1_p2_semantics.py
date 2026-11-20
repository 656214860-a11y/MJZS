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


class RegistryRequestCoverageTests(unittest.TestCase):
    """登记表请求/槽位 API 的双向分支（分支覆盖棘轮补齐，不改变既有断言）。"""

    def tearDown(self):
        for items in list(registry._slots.values()):
            for token in list(items):
                registry.release_process_slot(token)
        registry._slots.clear()
        registry._queued[:] = []
        registry._requests.clear()

    def test_register_request_rejects_second_handle_for_same_project(self):
        class Handle:
            def cancel(self):
                pass
        first, second = Handle(), Handle()
        self.assertTrue(registry.register_request('proj-a', first))
        self.assertFalse(registry.register_request('proj-a', second))
        self.assertTrue(registry.register_request('proj-b', second))

    def test_forget_request_only_removes_matching_handle(self):
        class Handle:
            def __init__(self):
                self.cancelled = 0
            def cancel(self):
                self.cancelled += 1
        kept, other = Handle(), Handle()
        registry.register_request('proj-c', kept)
        registry.forget_request('proj-c', other)          # 错误 handle：不摘除
        self.assertEqual(registry.cancel_project_requests('proj-c'), 1)
        self.assertEqual(kept.cancelled, 1)
        registry.register_request('proj-c', kept)
        registry.forget_request('proj-c', kept)           # 正确 handle：摘除
        self.assertEqual(registry.cancel_project_requests('proj-c'), 0)

    def test_cancel_project_requests_without_handle_returns_zero(self):
        self.assertEqual(registry.cancel_project_requests('proj-missing'), 0)

    def test_cancel_slot_request_scans_queue_for_ticket(self):
        registry.reserve_process_slot('pa', 'script', stage_limit=1)
        first = registry.request_process_slot('pb', 'script', stage_limit=1)['ticket']
        second = registry.request_process_slot('pc', 'script', stage_limit=1)['ticket']
        self.assertTrue(registry.cancel_slot_request(second))   # 跳过 first 命中 second
        self.assertFalse(registry.cancel_slot_request({'id': 'ghost'}))  # 扫完全队列未命中
        registry.cancel_slot_request(first)

    def test_release_process_slot_pops_stage_key_when_set_empties(self):
        registry.release_process_slot(None)             # 空 token 直接返回
        first = registry.reserve_process_slot('pd', 'script', stage_limit=2)
        second = registry.reserve_process_slot('pd', 'script', stage_limit=2)
        registry.release_process_slot(object())          # 未知 token：遍历不命中
        registry.release_process_slot(first)             # 集合仍剩 second
        registry.release_process_slot(second)            # 集合清空 → 摘除 stage 键
        self.assertNotIn('script', registry._slots)

    def test_claim_process_slot_rejects_non_dict_ticket(self):
        self.assertEqual(registry.claim_process_slot('ticket-ish')['state'], 'cancelled')
        self.assertEqual(registry.claim_process_slot(None)['state'], 'cancelled')

    def test_request_process_slot_grants_when_capacity_free(self):
        result = registry.request_process_slot('pe', 'script', stage_limit=1)
        self.assertEqual(result['state'], 'granted')
        registry.release_process_slot(result['slot'])

    def test_reap_exited_processes_tolerates_poll_errors(self):
        bad = mock.Mock()
        bad.poll.side_effect = OSError('gone')
        good = mock.Mock()
        good.poll.return_value = None
        registry.register_process('pf', bad)
        registry.register_process('pg', good)
        self.addCleanup(registry.forget_process, 'pf', bad)
        self.addCleanup(registry.forget_process, 'pg', good)
        registry.reserve_process_slot('ph', 'script')    # 触发 _reap_exited_processes


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

    def test_job_object_short_circuits_off_windows(self):
        with mock.patch.object(os, 'name', 'posix'):
            self.assertIsNone(registry._job_object())
            registry._assign_to_job(mock.Mock())       # 非 Windows：直接返回，不建 Job

    @unittest.skipUnless(os.name == 'nt', PLATFORM_WINDOWS_ONLY)
    def test_job_object_create_and_setinfo_failures_return_none(self):
        import ctypes
        kernel32 = ctypes.windll.kernel32
        saved = registry._JOB
        try:
            registry._JOB = None
            with mock.patch.object(kernel32, 'CreateJobObjectW', return_value=0):
                self.assertIsNone(registry._job_object())
            registry._JOB = None
            with mock.patch.object(kernel32, 'SetInformationJobObject', return_value=0):
                self.assertIsNone(registry._job_object())
            registry._JOB = None
            with mock.patch.object(kernel32, 'CreateJobObjectW', side_effect=OSError('no')):
                self.assertIsNone(registry._job_object())
        finally:
            registry._JOB = saved

    @unittest.skipUnless(os.name == 'nt', PLATFORM_WINDOWS_ONLY)
    def test_assign_to_job_returns_when_job_unavailable(self):
        with mock.patch.object(registry, '_job_object', return_value=None):
            registry._assign_to_job(mock.Mock())

    @unittest.skipUnless(os.name == 'nt', PLATFORM_WINDOWS_ONLY)
    def test_assign_to_job_validates_handle_and_pid_types(self):
        proc = mock.Mock()
        proc._handle = 'not-an-int'
        proc.pid = 'not-an-int'
        registry._assign_to_job(proc)                   # 全部非 int：不触碰 ctypes
        proc2 = mock.Mock()
        proc2._handle = None
        proc2.pid = 'still-not-int'
        registry._assign_to_job(proc2)                  # pid 非 int：跳过 OpenProcess

    @unittest.skipUnless(os.name == 'nt', PLATFORM_WINDOWS_ONLY)
    def test_assign_to_job_uses_existing_int_handle(self):
        proc = mock.Mock()
        proc._handle = 12345                        # 任意正整数：无效句柄由 AssignProcessToJobObject 静默拒绝
        proc.pid = os.getpid()
        registry._assign_to_job(proc)

    @unittest.skipUnless(os.name == 'nt', PLATFORM_WINDOWS_ONLY)
    def test_assign_to_job_opens_and_closes_handle_for_pid_only_process(self):
        proc = mock.Mock()
        proc._handle = None
        proc.pid = os.getpid()                         # OpenProcess 自身 → 真实句柄 → 用后即关
        registry._assign_to_job(proc)

    @unittest.skipUnless(os.name == 'nt', PLATFORM_WINDOWS_ONLY)
    def test_assign_to_job_swallows_kernel_errors(self):
        import ctypes
        kernel32 = ctypes.windll.kernel32
        proc = mock.Mock()
        proc._handle = None
        proc.pid = 12345
        with mock.patch.object(kernel32, 'OpenProcess', side_effect=OSError('denied')):
            registry._assign_to_job(proc)               # OpenProcess 抛错 → swallowed，不外抛


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

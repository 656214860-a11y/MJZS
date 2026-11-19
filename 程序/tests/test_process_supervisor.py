# -*- coding: utf-8 -*-
"""I8 进程监督器：L1-H9 种类登记、spawn 契约、Job Object 兜底与错误归类。"""
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from contract.infra_errors import ConfigError, InfraError, ProcessError
from infra import workflow_process_registry as wpr
from skip_reasons import PLATFORM_JOB_OBJECT, PLATFORM_WINDOWS_ONLY


def _sleep_command(seconds=60):
    return [sys.executable, '-c', 'import time; time.sleep(%d)' % seconds]


class ProcessKindRegistryTests(unittest.TestCase):
    """I8-1：L1-H9 每个种类都有默认超时；spawn 不带超时抛 ConfigError。"""

    EXPECTED_KINDS = {'engine_cli', 'comfy', 'ffmpeg', 'asr',
                      'blender', 'optimizer', 'test_runner', 'detached'}

    def test_all_kinds_registered_with_defaults(self):
        self.assertEqual(set(wpr.PROCESS_KINDS), self.EXPECTED_KINDS)
        for kind in self.EXPECTED_KINDS - {'detached'}:
            spec = wpr.PROCESS_KINDS[kind]
            self.assertIsInstance(spec['timeout'], (int, float), kind)
            self.assertGreater(spec['timeout'], 0, kind)
            self.assertIs(spec['job'], True, kind)
        self.assertIs(wpr.PROCESS_KINDS['detached']['job'], False)

    def test_spawn_requires_explicit_timeout(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(ConfigError):
                wpr.spawn('ffmpeg', ['x'], project=td, stage='test')
            with self.assertRaises(ConfigError):
                wpr.spawn('ffmpeg', ['x'], project=td, stage='test', timeout=None)
            with self.assertRaises(ConfigError):
                wpr.spawn('ffmpeg', ['x'], project=td, stage='test', timeout=0)
            with self.assertRaises(ConfigError):
                wpr.spawn('ffmpeg', ['x'], project=td, stage='test', timeout=-5)
            with self.assertRaises(ConfigError):
                wpr.spawn('ffmpeg', ['x'], project=td, stage='test', timeout='abc')
            with self.assertRaises(ConfigError):
                wpr.spawn('no_such_kind', ['x'], project=td, stage='test', timeout=10)

    def test_spawn_unknown_kind_is_config_error_compat(self):
        with tempfile.TemporaryDirectory() as td:
            try:
                wpr.spawn('nope', ['x'], project=td, stage='t', timeout=1)
            except ValueError as exc:
                self.assertIsInstance(exc, InfraError)
                self.assertEqual(exc.code, 'E-CONFIG-INVALID')
            else:
                self.fail('未登记种类应抛 ConfigError')


class SpawnContractTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.project = Path(self._tmp.name)

    def tearDown(self):
        for process in wpr.all_processes():
            try:
                if process.poll() is None:
                    process.kill()
            except Exception:
                pass
        # 清掉本测试登记的项目进程，避免污染其他用例
        key = wpr._key(self.project)
        with wpr._lock:
            wpr._running.pop(key, None)

    def test_spawn_registers_and_returns_handle(self):
        handle = wpr.spawn('test_runner', _sleep_command(30),
                           project=self.project, stage='t', timeout=30)
        self.assertIsInstance(handle, wpr.SupervisedProcess)
        self.assertEqual(handle.kind, 'test_runner')
        self.assertEqual(handle.timeout, 30.0)
        self.assertIn(handle.process, wpr.processes(self.project))
        self.assertIsNotNone(handle.pid)
        info = wpr.supervised_info(handle.process)
        self.assertEqual(info.get('kind'), 'test_runner')
        self.assertEqual(info.get('stage'), 't')
        self.assertEqual(info.get('project'), str(self.project))
        self.assertIs(info.get('in_job'), True)
        handle.terminate()
        handle.process.wait(timeout=10)

    def test_spawn_missing_executable_is_tool_missing(self):
        with self.assertRaises(ProcessError) as cm:
            wpr.spawn('ffmpeg', ['definitely-not-a-real-exe-xyz.exe'],
                      project=self.project, stage='t', timeout=5)
        exc = cm.exception
        self.assertIsInstance(exc, RuntimeError)
        self.assertEqual(exc.code, 'E-TOOL-MISSING')

    def test_spawn_oserror_is_tool_failed(self):
        # 命令形态非法（空列表）触发 OSError/IndexError 路径之外的失败归类
        with self.assertRaises(ProcessError) as cm:
            wpr.spawn('ffmpeg', [], project=self.project, stage='t', timeout=5)
        self.assertIn(cm.exception.code, ('E-TOOL-FAILED', 'E-TOOL-MISSING'))


@unittest.skipUnless(os.name == 'nt', PLATFORM_WINDOWS_ONLY)
class JobObjectSupervisionTests(unittest.TestCase):
    """I8-2：宿主结束 Job 句柄后受监督子进程被系统结束；detached 不受影响。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.project = Path(self._tmp.name)
        self._job = wpr._job_object()
        if self._job is None:
            self.skipTest(PLATFORM_JOB_OBJECT)

    def tearDown(self):
        for handle in getattr(self, '_handles', []):
            try:
                if handle.process.poll() is None:
                    handle.process.kill()
                    handle.process.wait(timeout=10)
            except Exception:
                pass
        key = wpr._key(self.project)
        with wpr._lock:
            wpr._running.pop(key, None)

    def _close_job_and_recreate(self):
        import ctypes
        job = wpr._job_object()
        if job:
            ctypes.windll.kernel32.CloseHandle(job)
        wpr._JOB = None

    def test_job_close_kills_supervised_but_not_detached(self):
        import ctypes
        self._handles = []
        supervised = wpr.spawn('ffmpeg', _sleep_command(120),
                               project=self.project, stage='t', timeout=120)
        detached = wpr.spawn('detached', _sleep_command(120),
                             project=self.project, stage='t', timeout=120)
        self._handles = [supervised, detached]
        # 确认受监督进程已进 Job：detached 不进
        self.assertTrue(supervised.in_job)
        self.assertFalse(detached.in_job)
        # 模拟应用退出：关闭 Job 句柄（KILL_ON_JOB_CLOSE）
        self._close_job_and_recreate()
        deadline = time.monotonic() + 15
        while supervised.process.poll() is None and time.monotonic() < deadline:
            time.sleep(0.2)
        self.assertIsNotNone(supervised.process.poll(),
                             '关闭 Job 句柄后受监督子进程应被系统结束')
        # detached 不在 Job 内，应仍存活；随后手动清理
        time.sleep(0.5)
        self.assertIsNone(detached.process.poll(),
                          'detached 种类不应被 Job 关闭误杀')
        detached.process.kill()
        detached.process.wait(timeout=10)

    def test_assign_to_job_refuses_self_and_non_children(self):
        """回归：pid 指向自身或非子进程不得挂入 Job——否则宿主退出/关 Job 时自杀。"""
        import ctypes
        import struct
        from ctypes import wintypes
        job = wpr._job_object()
        if job is None:
            self.skipTest(PLATFORM_JOB_OBJECT)
        kernel32 = ctypes.windll.kernel32

        def member_pids():
            buf = ctypes.create_string_buffer(8 + 8 * 4096)
            ret = wintypes.DWORD(0)
            self.assertTrue(kernel32.QueryInformationJobObject(
                job, 3, buf, ctypes.sizeof(buf), ctypes.byref(ret)))
            listed = struct.unpack_from('<I', buf, 4)[0]
            return {struct.unpack_from('<Q', buf, 8 + 8 * i)[0]
                    for i in range(min(listed, 4096))}

        before = member_pids()
        proc = mock.Mock()
        proc._handle = None
        proc.pid = os.getpid()                    # OpenProcess 自身：必须被父子校验拦下
        wpr._assign_to_job(proc)
        self.assertEqual(member_pids(), before)   # 集合未变：自身未入列
        stray = mock.Mock()
        stray._handle = 12345                     # 无效句柄：GetProcessId→0，同样被拦
        stray.pid = 12345
        wpr._assign_to_job(stray)
        self.assertEqual(member_pids(), before)


class ExitClassificationTests(unittest.TestCase):
    """I8-3：超时／找不到可执行文件／非零退出各归一类 error_codes 码。"""

    def test_timeout_classifies_tool_timeout(self):
        self.assertEqual(wpr.classify_exit(None, timed_out=True), 'E-TOOL-TIMEOUT')

    def test_missing_executable_classifies_tool_missing(self):
        self.assertEqual(
            wpr.classify_exit(1, stderr_tail='xxx is not recognized as an internal or external command'),
            'E-TOOL-MISSING')
        self.assertEqual(
            wpr.classify_exit(127, stderr_tail='/bin/sh: ffmpeg: No such file or directory'),
            'E-TOOL-MISSING')

    def test_nonzero_exit_classifies_tool_failed(self):
        self.assertEqual(wpr.classify_exit(1, stderr_tail='decode error'), 'E-TOOL-FAILED')
        self.assertEqual(wpr.classify_exit(2), 'E-TOOL-FAILED')

    def test_success_and_running_classify_empty(self):
        self.assertEqual(wpr.classify_exit(0), '')
        self.assertEqual(wpr.classify_exit(None), '')

    def test_codes_resolve_in_registry(self):
        from contract.error_codes import CODES
        for code in ('E-TOOL-TIMEOUT', 'E-TOOL-MISSING', 'E-TOOL-FAILED'):
            self.assertIn(code, CODES)

    def test_supervised_stderr_tail(self):
        import subprocess
        handle = wpr.SupervisedProcess(
            'test_runner', Path('.'), 't', 5, None,
            subprocess.Popen([sys.executable, '-c',
                              'import sys; sys.stderr.write("tail-line\\n"); sys.stderr.flush()'],
                             stderr=subprocess.PIPE), in_job=False)
        handle.start_pump()
        self.assertEqual(handle.wait(timeout=30), 0)
        self.assertIn('tail-line', handle.stderr_tail())
        self.assertEqual(handle.error_code(), '')


class SupervisedLifecycleTests(unittest.TestCase):
    """I9a：popen 注入缝、communicate 自动注销、按项目/阶段/种类统一取消。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.project = Path(self._tmp.name)

    def tearDown(self):
        for process in wpr.all_processes():
            try:
                if process.poll() is None:
                    process.kill()
            except Exception:
                pass
        key = wpr._key(self.project)
        with wpr._lock:
            wpr._running.pop(key, None)

    def test_spawn_popen_injection_and_communicate_forgot(self):
        class FakeProc:
            pid = 0
            returncode = 0
            def __init__(self):
                self.stderr = None
            def poll(self):
                return self.returncode
            def communicate(self, input=None, timeout=None):
                return ('out', 'err')
            def wait(self, timeout=None):
                return self.returncode
        fake = FakeProc()
        handle = wpr.spawn('ffmpeg', ['x'], project=self.project, stage='t',
                           timeout=5, popen=lambda *a, **k: fake)
        self.assertIs(handle.process, fake)
        self.assertIn(fake, wpr.processes(self.project))
        self.assertEqual(handle.communicate(timeout=5), ('out', 'err'))
        self.assertNotIn(fake, wpr.processes(self.project))

    def test_cancel_supervised_filters_by_stage_and_kind(self):
        first = wpr.spawn('ffmpeg', _sleep_command(60),
                          project=self.project, stage='cut', timeout=60)
        second = wpr.spawn('ffmpeg', _sleep_command(60),
                           project=self.project, stage='mix', timeout=60)
        third = wpr.spawn('test_runner', _sleep_command(60),
                          project=self.project, stage='cut', timeout=60)
        try:
            self.assertEqual(
                wpr.cancel_supervised(self.project, stage='cut', kind='ffmpeg'), 1)
            self.assertNotIn(first.process, wpr.processes(self.project))
            self.assertIn(second.process, wpr.processes(self.project))
            self.assertIn(third.process, wpr.processes(self.project))
            self.assertEqual(wpr.cancel_supervised(self.project, kind='test_runner'), 1)
            self.assertNotIn(third.process, wpr.processes(self.project))
            self.assertIn(second.process, wpr.processes(self.project))
        finally:
            for handle in (first, second, third):
                try:
                    handle.process.kill()
                    handle.process.wait(timeout=10)
                except Exception:
                    pass


if __name__ == '__main__':
    unittest.main()

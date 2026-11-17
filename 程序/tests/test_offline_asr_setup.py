# -*- coding: utf-8 -*-
"""任务书 M6：离线语音包下载控制器（domain.offline_asr_setup）测试。

全部用假进程/假探测/假目录跑通事件流——不建真实 venv、不联网、不下载模型，
可在随附零依赖解释器下运行。
"""
import io
import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

PROGRAM = Path(__file__).resolve().parents[1]
if str(PROGRAM) not in sys.path:
    sys.path.insert(0, str(PROGRAM))

import domain.offline_asr_client as client  # noqa: E402
import domain.offline_asr_setup as setup_mod  # noqa: E402


def wait_for(predicate, timeout=5.0):
    import time
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return predicate()


class FakeProc:
    """最小假 Popen：喂定好的 stdout 行，wait 返回预设退出码，记 kill。"""

    def __init__(self, lines, returncode=0):
        self.stdout = io.StringIO(''.join(lines))
        self.returncode = returncode
        self.killed = False
        self._wait = threading.Event()
        self._wait.set()                    # stdout 迭代完 wait 立即返回；Hang 子类用 stdout 阻塞

    def wait(self, timeout=None):
        # R3205：生产侧收敛为带超时的 wait（Popen.wait 同名签名），替身对齐。
        self._wait.wait(5)
        return self.returncode

    def kill(self):
        self.killed = True
        self._wait.set()


class ResolveTests(unittest.TestCase):
    def test_resolve_prefers_env_then_version_window(self):
        """候选顺序＝环境变量 > 显式设置 > 启动器/PATH；只收 3.10–3.12。"""
        probes = []

        def probe(argv):
            probes.append(list(argv))
            return {'C:/py312/python.exe': 'C:/py312/python.exe'}.get(argv[0])

        with mock.patch.dict('os.environ', {'VOICE_ASR_PYTHON': 'C:/py312/python.exe'}):
            exe = setup_mod.resolve_base_python({}, probe=probe)
        self.assertEqual(exe, 'C:/py312/python.exe')
        self.assertEqual(probes, [['C:/py312/python.exe']])

    def test_probe_rejects_out_of_window_and_missing_exe(self):
        with tempfile.TemporaryDirectory() as td:
            real = Path(td) / 'python.exe'
            real.write_bytes(b'x')
            good = lambda argv: b''
            version_out = '%s\n3.12\n' % real

            class R:
                returncode = 0
                stdout = version_out
                stderr = ''

            # 3.14 被拒
            class Bad:
                returncode = 0
                stdout = '%s\n3.14\n' % real
                stderr = ''

            with mock.patch('subprocess.run', return_value=Bad()):
                self.assertIsNone(setup_mod._probe(['whatever']))
            with mock.patch('subprocess.run', return_value=R()):
                self.assertEqual(setup_mod._probe(['whatever']), str(real))
            # 子进程起不来 / 非零退出 → None
            with mock.patch('subprocess.run', side_effect=OSError('no such')):
                self.assertIsNone(setup_mod._probe(['whatever']))


class EnvironmentTests(unittest.TestCase):
    def test_default_venv_missing_gives_actionable_guidance(self):
        """任务书 M6 验收①：默认 venv 缺失的提示不含内部路径与『缺少 python.exe』。"""
        with tempfile.TemporaryDirectory() as td:
            with mock.patch.object(client, 'VENV_DIR', Path(td) / 'venv'):
                reason = client.environment_problem({'backend': 'offline', 'offline': {}})
        self.assertIn('离线语音包未安装', reason)
        self.assertIn('模型管理', reason)
        self.assertIn('云端密钥', reason)
        self.assertNotIn('python.exe', reason)
        self.assertNotIn('voice_asr_venv', reason)

    def test_explicit_python_missing_names_the_setting(self):
        """显式解释器失效仍点名用户设置值（对照修正用）。"""
        with tempfile.TemporaryDirectory() as td:
            fake = {'backend': 'offline',
                    'offline': {'python': str(Path(td) / 'nope.exe')}}
            reason = client.environment_problem(fake)
        self.assertIn('离线识别环境未安装', reason)
        self.assertIn('nope.exe', reason)

    def test_models_ready_requires_hub_onnx(self):
        with tempfile.TemporaryDirectory() as td:
            cache = Path(td) / 'models'
            settings = {'offline': {'cache_dir': str(cache)}}
            self.assertFalse(setup_mod.models_ready(settings))
            onnx = cache / 'hub' / 'models' / 'iic' / 'demo' / 'model_quant.onnx'
            onnx.parent.mkdir(parents=True)
            onnx.write_bytes(b'x')
            self.assertTrue(setup_mod.models_ready(settings))

    def test_cleanup_only_removes_incomplete_venv(self):
        """半成品（目录在、解释器不在）才清；建好的 venv 留下续跑。"""
        with tempfile.TemporaryDirectory() as td:
            venv = Path(td) / 'venv'
            venv.mkdir()
            self.assertTrue(setup_mod.cleanup_incomplete_venv(venv))
            self.assertFalse(venv.exists())
            venv.mkdir()
            marker = client.venv_python(venv)
            marker.parent.mkdir(parents=True)
            marker.write_bytes(b'x')
            self.assertFalse(setup_mod.cleanup_incomplete_venv(venv))
            self.assertTrue(venv.exists())


class RunnerTests(unittest.TestCase):
    def _patch_dirs(self, td):
        venv = Path(td) / 'venv'
        self._venv = venv
        return mock.patch.multiple(setup_mod, VENV_DIR=venv,
                                   MODELS_DIR=Path(td) / 'models')

    def test_missing_base_python_reports_guidance(self):
        """找不到 3.10–3.12 基座：一句带两条出路的错误，不启动进程。"""
        events = []
        with tempfile.TemporaryDirectory() as td, self._patch_dirs(td):
            runner = setup_mod.OfflineSetupRunner({}, events.append,
                                                  launcher=lambda *a, **k: FakeProc([]),
                                                  probe=lambda argv: None)
            runner.start()
            self.assertTrue(wait_for(lambda: not runner.running))
        self.assertEqual([e['type'] for e in events], ['error'])
        self.assertIn('Python', events[0]['message'])
        self.assertIn('云端', events[0]['message'])

    def test_two_phase_commands_and_progress_events(self):
        """venv 阶段跑 bootstrap.py，models 阶段跑 venv 内 -m download_models。"""
        events, commands = [], []

        def launcher(command, **kw):
            commands.append(list(command))
            if 'bootstrap.py' in command[1]:
                return FakeProc(['{"type":"progress","message":"创建环境"}\n',
                                 '{"type":"done","venv":"x"}\n'])
            return FakeProc(['{"type":"progress","model":"asr","stage":"downloading"}\n',
                             '{"type":"done","cache_root":"x"}\n'])

        with tempfile.TemporaryDirectory() as td, self._patch_dirs(td), \
                mock.patch.object(setup_mod, 'models_ready', return_value=True):
            venv = self._venv
            runner = setup_mod.OfflineSetupRunner({}, events.append,
                                                  launcher=launcher,
                                                  probe=lambda argv: 'C:/base/python.exe')
            runner.start()
            self.assertTrue(wait_for(lambda: not runner.running))
        self.assertEqual(len(commands), 2)
        self.assertIn('bootstrap.py', commands[0][1])
        self.assertIn('--python', commands[0])
        self.assertIn('-m', commands[1])
        self.assertIn('voice_engine.download_models', commands[1])
        self.assertEqual(str(self._venv), str(Path(commands[1][0]).parents[1]))
        kinds = [e['type'] for e in events]
        self.assertIn('progress', kinds)
        self.assertEqual(kinds[-1], 'done')

    def test_venv_failure_cleans_incomplete_and_reports(self):
        """bootstrap 失败：半成品 venv（无解释器）被清，事件给原因与续传口径。"""
        events = []
        with tempfile.TemporaryDirectory() as td, self._patch_dirs(td):
            venv = self._venv
            half = venv / 'partial'
            half.mkdir(parents=True)
            def launcher(command, **kw):
                venv.mkdir(exist_ok=True)
                return FakeProc(['{"type":"error","message":"依赖安装失败"}\n'], returncode=3)
            runner = setup_mod.OfflineSetupRunner({}, events.append,
                                                  launcher=launcher,
                                                  probe=lambda argv: 'C:/base/python.exe')
            runner.start()
            self.assertTrue(wait_for(lambda: not runner.running))
            self.assertFalse(venv.exists(), '无解释器的半成品 venv 应被清理')
        self.assertEqual(events[-1]['type'], 'error')
        self.assertIn('依赖安装失败', [e.get('message') for e in events][-1] or '')

    def test_cancel_emits_cancelled_and_keeps_resumable_state(self):
        """取消：杀当前子进程、发 cancelled、已建好的 venv/模型缓存不清。"""
        events = []
        started = threading.Event()
        blocker = FakeProc([])          # stdout 空迭代，wait 被 kill 唤醒

        class HangingProc(FakeProc):
            def __init__(self):
                super().__init__([])
                self.stdout = self._iter()

            def _iter(self):
                import time
                started.set()
                yield '{"type":"progress","message":"创建环境"}\n'
                while True:             # 永不再出数据：模拟下载中
                    time.sleep(0.02)
                    if self.killed:
                        return
            def __iter__(self):
                return self.stdout

        with tempfile.TemporaryDirectory() as td, self._patch_dirs(td):
            venv = self._venv
            venv.mkdir()
            marker = client.venv_python(venv)
            marker.parent.mkdir(parents=True)
            marker.write_bytes(b'x')     # 已建好的 venv：取消后必须留下续跑
            hanging = HangingProc()
            runner = setup_mod.OfflineSetupRunner(
                {}, events.append,
                launcher=lambda command, **kw: hanging,
                probe=lambda argv: 'C:/base/python.exe')
            runner.start()
            self.assertTrue(started.wait(5))
            runner.cancel()
            self.assertTrue(wait_for(lambda: not runner.running))
            self.assertTrue(hanging.killed)
            self.assertTrue(marker.exists(), '已建好的 venv 在取消后应保留（续传口径）')
        self.assertIn('cancelled', [e['type'] for e in events])

    def test_start_twice_is_rejected(self):
        """同实例重入被拒（按钮二次点击不产生第二条下载链）。"""
        blocker = threading.Event()
        proc = FakeProc([])

        class Hang(FakeProc):
            def _iter(self):
                import time
                while not self.killed:
                    time.sleep(0.02)
                    yield ''
            def __init__(self):
                super().__init__([])
                self.stdout = self._iter()

        hanging = Hang()
        with tempfile.TemporaryDirectory() as td, self._patch_dirs(td):
            runner = setup_mod.OfflineSetupRunner(
                {}, lambda e: None,
                launcher=lambda command, **kw: hanging,
                probe=lambda argv: 'C:/base/python.exe')
            self.assertTrue(runner.start())
            self.assertFalse(runner.start())
            runner.cancel()
            self.assertTrue(wait_for(lambda: not runner.running))


if __name__ == '__main__':
    unittest.main()

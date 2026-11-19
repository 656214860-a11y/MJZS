"""R2168：自检不把测试里制造的报错写进程序自己的诊断记录。

``logs/diagnostics/latest.json`` 会显示在运行状况里，也会打进诊断导出包。测试用临时项目
故意触发的报错（如首帧页忙碌时切换分镜）曾混进用户的记录，最近 50 条里占了 21 条。
自检入口设置 ``DRAMA_SUPPRESS_DIAGNOSTICS=1`` 后不再写这份文件；测试把记录改指到临时
文件时照常写；正常运行（没有这个环境变量）照常记录。
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

PROGRAM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROGRAM))

import diagnostic_capture  # noqa: E402
from infra import diagnostic_state  # noqa: E402

ENV = "DRAMA_SUPPRESS_DIAGNOSTICS"
PROGRAM_STATE = PROGRAM / "logs" / "diagnostics" / "latest.json"


def _record_all():
    diagnostic_capture.record_degradation(ValueError("当前操作尚未结束，请稍后"), page="08  首帧管理",
                                          project="C:/Temp/tmpabc/p", automatic_daily_open=True)
    diagnostic_capture.record_startup_timing("desktop_shell_ready", 1.0)
    diagnostic_capture.record_gate_result("SG-01", "pass")


class SelftestDiagnosticsIsolationTests(unittest.TestCase):
    def _writes(self, environ):
        writes = []
        with mock.patch.dict(os.environ, environ, clear=True), \
                mock.patch.object(diagnostic_state, "save_text", lambda path, text: writes.append(Path(path))):
            _record_all()
        return writes

    def _environ_without_flag(self):
        return {key: value for key, value in os.environ.items() if key != ENV}

    def test_selftest_never_writes_program_diagnostics(self):
        """自检环境下降级、启动耗时、门禁结果都不落到程序自己的 latest.json。"""
        environ = dict(self._environ_without_flag(), **{ENV: "1"})
        self.assertNotIn(PROGRAM_STATE, self._writes(environ))

    def test_normal_run_still_records_program_diagnostics(self):
        """正常运行不受影响：三类记录照常写程序自己的 latest.json。"""
        self.assertEqual(self._writes(self._environ_without_flag()), [PROGRAM_STATE] * 3)

    def test_selftest_still_writes_redirected_state_file(self):
        """测试把记录改指到临时文件时照常写，诊断模块自己的测试不受影响。"""
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "latest.json"
            with mock.patch.dict(os.environ, {ENV: "1"}), \
                    mock.patch.object(diagnostic_capture, "STATE_FILE", target):
                _record_all()
            text = target.read_text(encoding="utf-8")
        self.assertIn("当前操作尚未结束", text)
        self.assertIn("desktop_shell_ready", text)

    def test_selftest_entry_points_set_the_flag(self):
        """run_selftests 与 smoke_test 启动后，子进程环境里都带着这个开关。"""
        environ = self._environ_without_flag()
        probes = {
            "run_selftests": "import os, run_selftests; print('FLAG=' + os.environ.get('%s', ''))" % ENV,
            "smoke_test": "import os, smoke_test; smoke_test.main(['--list']); print('FLAG=' + os.environ.get('%s', ''))" % ENV,
        }
        for name, code in probes.items():
            with self.subTest(entry=name):
                result = subprocess.run([sys.executable, "-B", "-c", code], cwd=str(PROGRAM),
                                        env=dict(environ, PYTHONIOENCODING="utf-8"),
                                        capture_output=True, text=True, encoding="utf-8", errors="replace",
                                        timeout=120)
                self.assertEqual(result.returncode, 0, result.stderr[-2000:])
                flags = [line for line in result.stdout.splitlines() if line.startswith("FLAG=")]
                self.assertEqual(flags, ["FLAG=1"])


if __name__ == "__main__":
    unittest.main()

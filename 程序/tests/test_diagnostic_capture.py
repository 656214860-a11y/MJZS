from __future__ import annotations

import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

import diagnostic_capture as subject


class DiagnosticCaptureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.logs = root / "logs"
        self.error = self.logs / "启动错误.log"
        self.state = self.logs / "diagnostics" / "latest.json"
        self.patch = patch.multiple(subject, PROGRAM=root, LOGS=self.logs, ERROR_LOG=self.error, STATE_FILE=self.state)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.addCleanup(self.temp.cleanup)

    def test_export_redacts_fake_credentials_and_never_scans_recursively(self):
        self.logs.mkdir(parents=True)
        (self.logs / "sanhu_progress.log").write_text("token=not-for-export\nok", encoding="utf-8")
        nested = self.logs / "nested" / "secret.log"
        nested.parent.mkdir()
        nested.write_text("TOKEN=must-not-read", encoding="utf-8")
        output = subject.export(Path(self.temp.name) / "diagnostics.zip")
        with zipfile.ZipFile(output) as archive:
            text = "\n".join(archive.read(name).decode("utf-8") for name in archive.namelist())
        self.assertNotIn("not-for-export", text)
        self.assertNotIn("must-not-read", text)
        self.assertIn("[已脱敏]", text)

    def test_destroyed_ui_side_can_record_without_tk(self):
        subject.record_degradation(RuntimeError("window destroyed token=nope"), page="剧本准备")
        state = json.loads(self.state.read_text(encoding="utf-8"))
        self.assertEqual(state["degradations"][-1]["page"], "剧本准备")
        self.assertNotIn("nope", state["degradations"][-1]["message"])

    def test_crash_uses_existing_startup_error_log(self):
        subject.record_crash(ValueError("token=nope"))
        self.assertTrue(self.error.is_file())
        self.assertNotIn("nope", self.error.read_text(encoding="utf-8"))

    def test_latest_gate_result_is_persisted(self):
        subject.record_gate_result("G-01", "passed")
        state = json.loads(self.state.read_text(encoding="utf-8"))
        self.assertEqual(state["last_gate"]["name"], "G-01")
        self.assertEqual(state["last_gate"]["result"], "passed")

    def test_collection_has_no_recursive_scan(self):
        self.logs.mkdir(parents=True)
        with patch.object(Path, "rglob", side_effect=AssertionError("不得递归扫描")), \
             patch.object(Path, "iterdir", side_effect=AssertionError("不得枚举目录")):
            self.assertEqual(subject.preview(), (subject.retention_note(),))

    def test_record_crash_keeps_only_recent_tail(self):
        self.logs.mkdir(parents=True)
        self.error.write_text("HEAD-MARKER\n" + "x" * (200 * 1024), encoding="utf-8")
        subject.record_crash(RuntimeError("first-crash"))
        subject.record_crash(RuntimeError("second-crash"))
        text = self.error.read_text(encoding="utf-8")
        self.assertLess(self.error.stat().st_size, 100 * 1024)
        self.assertNotIn("HEAD-MARKER", text)
        self.assertIn("second-crash", text)

    def test_export_includes_repo_root_startup_error_log(self):
        program = Path(self.temp.name) / "程序"
        program.mkdir()
        launcher_log = Path(self.temp.name) / "启动错误.log"
        launcher_log.write_text("launcher-side failure", encoding="utf-8")
        with patch.object(subject, "PROGRAM", program):
            self.assertIn(str(launcher_log), subject.preview())
            output = subject.export(Path(self.temp.name) / "bundle.zip")
        with zipfile.ZipFile(output) as archive:
            self.assertIn("logs/diagnostics/启动错误.log", archive.namelist())
            self.assertIn("launcher-side failure",
                          archive.read("logs/diagnostics/启动错误.log").decode("utf-8"))

    def test_exported_log_scrubs_email_home_and_username(self):
        import getpass
        self.logs.mkdir(parents=True)
        home, user = str(Path.home()), getpass.getuser() or ""
        (self.logs / "sanhu_progress.log").write_text(
            "mail a.b@example.com dir " + home + "\\cache user " + user, encoding="utf-8")
        output = subject.export(Path(self.temp.name) / "bundle.zip")
        with zipfile.ZipFile(output) as archive:
            text = archive.read("logs/sanhu_progress.log").decode("utf-8")
        self.assertNotIn("a.b@example.com", text)
        self.assertIn("[邮箱]", text)
        self.assertNotIn(home, text)
        self.assertIn("~", text)
        if len(user) >= 3:
            self.assertNotIn(user, text)

    def test_preview_note_states_path_and_username_replacement(self):
        self.assertIn("已把本机路径和用户名替换", subject.retention_note())
        self.assertIn("已把本机路径和用户名替换", "\n".join(subject.preview()))

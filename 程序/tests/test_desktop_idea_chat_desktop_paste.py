# -*- coding: utf-8 -*-
"""REQ-S01-50：Desktop 模型发送必须真的粘贴，或如实说只复制。"""
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import codex_paste


PROGRAM = r"C:/Users/LAIBIAO/AppData/Local/Google/Gemini/Gemini.exe"
DISPLAY = "Google Gemini 4 Argon"


def desktop_class():
    """运行时取 Desktop；本文件不建 Tk，避免被误判为 GUI 端到端测试。"""
    import importlib
    return importlib.import_module("desktop").Desktop


def make_project(root):
    project = Path(root) / "proj"
    project.mkdir(parents=True)
    return project


def desktop_host(project, *, sync=True):
    def run(fn, done):
        return done(fn())
    return SimpleNamespace(
        root=project,
        worker=False,
        win=Mock(),
        status=Mock(),
        notifier=Mock(),
        projects=SimpleNamespace(info={"projects": []}),
        async_=run if sync else Mock(),
        gate_level=lambda: "manual",
    )


class DesktopModelPasteContractTests(unittest.TestCase):
    def test_req_s01_50_desktop_model_pastes_with_program_and_display_name(self):
        Desktop = desktop_class()
        with tempfile.TemporaryDirectory() as td:
            project = make_project(td)
            host = desktop_host(project)
            config = {"engine": "desktop-app", "program": PROGRAM, "model": "",
                      "display_model": DISPLAY}
            receipt = "已粘贴到 " + DISPLAY + "，请检查内容并手动点击发送。"
            with patch("agent_dispatch.claim", return_value={"duplicate": False}), \
                    patch("agent_dispatch.finish") as finish, \
                    patch("prompt_window.copy_text") as copy, \
                    patch("platform_tools.launch_windows_app") as launch, \
                    patch("codex_paste.paste_existing",
                          return_value={"ok": True, "reason": receipt}) as paste:
                Desktop.open_flow_agent(
                    host, "writing", "提取", "提取简报", _config=config, intake_only=True,
                    desktop_paste=True
                )
            launch.assert_called_once_with(PROGRAM, DISPLAY)
            clipboard_text = copy.call_args.args[1]
            self.assertTrue(clipboard_text.startswith("提取"))
            paste.assert_called_once_with(
                project.name + " 提取", clipboard_text, program=PROGRAM,
                app_name=DISPLAY, deadline_seconds=45,
            )
            self.assertEqual(finish.call_args.args[1], "prepared")
            self.assertEqual(finish.call_args.args[2], receipt)
            host.status.set.assert_called_with(receipt)
            host.notifier.info.assert_called_once_with(receipt, title="请检查并发送")

    def test_req_s01_50_paste_failure_is_reported_as_manual_paste(self):
        Desktop = desktop_class()
        with tempfile.TemporaryDirectory() as td:
            project = make_project(td)
            host = desktop_host(project)
            config = {"engine": "desktop-app", "program": PROGRAM, "model": "",
                      "display_model": DISPLAY}
            reason = ("已复制到剪贴板；未能自动粘贴，请在 " + DISPLAY
                      + " 输入框中手动粘贴并发送。")
            with patch("agent_dispatch.claim", return_value={"duplicate": False}), \
                    patch("agent_dispatch.finish") as finish, \
                    patch("prompt_window.copy_text"), \
                    patch("platform_tools.launch_windows_app"), \
                    patch("codex_paste.paste_existing",
                          return_value={"ok": False, "reason": reason}):
                Desktop.open_flow_agent(
                    host, "writing", "创作", "用户要求", _config=config, intake_only=True,
                    desktop_paste=True
                )
            self.assertEqual(finish.call_args.args[1], "failed")
            self.assertEqual(finish.call_args.args[2], reason)
            self.assertIn("剪贴板", reason)
            self.assertIn("手动粘贴", reason)
            self.assertNotIn("已粘贴到", reason)
            host.status.set.assert_called_with(reason)
            host.notifier.info.assert_called_once_with(reason, title="请手动粘贴")


class ScriptSendPathOptInTests(unittest.TestCase):
    def test_req_s01_50_script_send_path_requests_desktop_paste(self):
        Desktop = desktop_class()
        with tempfile.TemporaryDirectory() as td:
            project = make_project(td)
            host = SimpleNamespace(root=project, open_flow_agent=Mock())
            config = {"engine": "desktop-app", "program": PROGRAM, "model": "",
                      "display_model": DISPLAY}
            with patch("workflow_tasks.script_prompt", return_value="任务"), \
                    patch("workflow_tasks.script_followup", return_value="追问"), \
                    patch("workflow_tasks.writing_restart_requested", return_value=False), \
                    patch("workflow_settings.skill_prompt", return_value=""):
                Desktop.start_script_workflow(host, "创作", config=config)
            self.assertTrue(host.open_flow_agent.call_args.kwargs["desktop_paste"])


class PasteTransportAppNameTests(unittest.TestCase):
    def test_req_s01_50_app_name_is_transported_to_powershell(self):
        captured = {}
        def run(args, **kwargs):
            payload = json.loads(Path(args[-1]).read_text(encoding="utf-8"))
            captured.update(payload)
            return SimpleNamespace(stdout='{"ok":true,"send_dispatched":false}',
                                   stderr="", returncode=0)
        with patch.object(codex_paste.subprocess, "run", side_effect=run):
            result = codex_paste.paste_existing(
                "任务", "正文", program=PROGRAM, app_name=DISPLAY
            )
        self.assertTrue(result["ok"])
        self.assertEqual(captured["program"], PROGRAM)
        self.assertEqual(captured["app_name"], DISPLAY)

    def test_req_s01_50_transport_errors_use_the_display_name(self):
        cases = [
            ("timeout", subprocess.TimeoutExpired("powershell", 55)),
            ("oserror", OSError(5, "denied")),
        ]
        for name, error in cases:
            with self.subTest(name=name), \
                    patch.object(codex_paste.subprocess, "run", side_effect=error):
                result = codex_paste.paste_existing(
                    "title", "path", program=PROGRAM, app_name=DISPLAY
                )
                self.assertFalse(result["ok"])
                self.assertIn(DISPLAY, result["reason"])
                self.assertIn("手动", result["reason"])

        with patch.object(codex_paste.subprocess, "run",
                          return_value=SimpleNamespace(stdout="{bad\n", stderr="", returncode=0)):
            result = codex_paste.paste_existing(
                "title", "path", program=PROGRAM, app_name=DISPLAY
            )
        self.assertFalse(result["ok"])
        self.assertIn(DISPLAY, result["reason"])

    def test_req_s01_50_default_names_stay_unchanged(self):
        with patch.object(codex_paste.subprocess, "run",
                          side_effect=subprocess.TimeoutExpired("powershell", 55)):
            claude = codex_paste.paste_existing("t", "p", program="C:/Apps/Claude.exe")
            gpt = codex_paste.paste_existing("t", "p")
        self.assertIn("Claude Desktop", claude["reason"])
        self.assertIn("GPT", gpt["reason"])


class PowerShellTargetMatchTests(unittest.TestCase):
    def run_match(self, process, actual, expected):
        powershell = shutil.which("powershell.exe")
        self.assertIsNotNone(powershell, "Windows 自带 PowerShell 应可用")
        script = Path(codex_paste.__file__).with_suffix(".ps1")
        completed = subprocess.run(
            [powershell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script),
             "-SelfTestTarget", actual, "-SelfTestProcess", process,
             "-SelfTestProgram", expected],
            capture_output=True, text=True, encoding="utf-8", timeout=30,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr[-500:])
        return json.loads(completed.stdout.strip().splitlines()[-1])["match"]

    def test_req_s01_50_gemini_versioned_process_matches_configured_launcher(self):
        expected = r"C:\Users\Example\AppData\Local\Google\Gemini\Gemini.exe"
        actual = r"C:\Users\Example\AppData\Local\Google\Gemini\app-1.15.0\Gemini.exe"
        self.assertTrue(self.run_match("Gemini", actual, expected))
        self.assertTrue(self.run_match("Claude", r"C:\Apps\Claude\app-1.0.0\Claude.exe",
                                       r"C:\Apps\Claude\Claude.exe"))
        self.assertFalse(self.run_match("Chrome", actual, expected))
        self.assertFalse(self.run_match("Gemini", r"C:\Other\Gemini.exe", expected))


if __name__ == "__main__":
    unittest.main()


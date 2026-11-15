# -*- coding: utf-8 -*-
"""REQ-S01-70：桌面模型长任务改为任务文件作附件、输入框只放短指令。"""
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import codex_paste
import desktop_send_choice


PROGRAM = r"C:/Users/LAIBIAO/AppData/Local/Google/Gemini/Gemini.exe"
DISPLAY = "Google Gemini 4 Argon"
LONG_TASK = "长任务" + "甲" * desktop_send_choice.ATTACH_THRESHOLD


def desktop_class():
    import importlib
    return importlib.import_module("desktop").Desktop


def desktop_host(project):
    return SimpleNamespace(
        root=project, worker=False, win=Mock(), status=Mock(), notifier=Mock(),
        projects=SimpleNamespace(info={"projects": []}),
        async_=lambda fn, done: done(fn()), gate_level=lambda: "manual",
    )


class AttachmentPayloadTests(unittest.TestCase):
    def test_req_s01_70_long_desktop_task_becomes_short_instruction_and_attachment(self):
        with tempfile.TemporaryDirectory() as td:
            task = Path(td) / "ef775d77.md"
            task.write_text(LONG_TASK, encoding="utf-8")
            text, attachment = desktop_send_choice.attachment_payload("desktop-app", task, LONG_TASK)
        self.assertEqual(attachment, str(task))
        self.assertIn("「ef775d77.md」", text)
        self.assertIn("没有上传成功", text)
        self.assertIn("【交付方式】", text)
        self.assertNotIn("甲甲甲", text)
        self.assertLess(len(text), 500)

    def test_req_s01_70_short_tasks_and_other_engines_paste_text_unchanged(self):
        with tempfile.TemporaryDirectory() as td:
            task = Path(td) / "task.md"
            task.write_text(LONG_TASK, encoding="utf-8")
            short = "短任务"
            self.assertEqual(desktop_send_choice.attachment_payload("desktop-app", task, short), (short, ""))
            self.assertEqual(desktop_send_choice.attachment_payload("claude-desktop-app", task, LONG_TASK),
                             (LONG_TASK, ""))
            self.assertEqual(desktop_send_choice.attachment_payload("desktop-app", Path(td) / "无.md", LONG_TASK),
                             (LONG_TASK, ""))
            self.assertEqual(desktop_send_choice.attachment_payload("desktop-app", "", LONG_TASK), (LONG_TASK, ""))


class DesktopAttachmentDeliveryTests(unittest.TestCase):
    def send(self, *, desktop_paste, paste_result=None):
        Desktop = desktop_class()
        with tempfile.TemporaryDirectory() as td:
            project = Path(td) / "proj"
            project.mkdir()
            host = desktop_host(project)
            config = {"engine": "desktop-app", "program": PROGRAM, "model": "", "display_model": DISPLAY}
            with patch("agent_dispatch.claim", return_value={"duplicate": False}), \
                    patch("agent_dispatch.finish") as finish, \
                    patch("prompt_window.copy_text") as copy, \
                    patch("contract.platform_tools.launch_windows_app"), \
                    patch("contract.platform_tools.open_path") as opened, \
                    patch("codex_paste.paste_existing") as plain, \
                    patch("codex_paste.paste_attachment", return_value=paste_result) as paste:
                Desktop.open_flow_agent(host, "writing", "提取", LONG_TASK, _config=config,
                                        intake_only=True, desktop_paste=desktop_paste)
            task_files = list((project / "工作流任务" / "writing").glob("*.md"))
            self.assertEqual(len(task_files), 1)
            task = task_files[0]
            self.assertIn("甲" * 100, task.read_text(encoding="utf-8"))
            plain.assert_not_called()
            return SimpleNamespace(host=host, finish=finish, copy=copy, paste=paste,
                                   opened=opened, task=task)

    def test_req_s01_70_auto_paste_sends_task_file_as_attachment(self):
        reason = "已把任务文件作为附件、短指令粘贴到 " + DISPLAY + "；请确认附件已出现再手动发送。"
        sent = self.send(desktop_paste=True, paste_result={"ok": True, "reason": reason})
        clipboard_text = sent.copy.call_args.args[1]
        self.assertIn("「" + sent.task.name + "」", clipboard_text)
        self.assertNotIn("甲" * 100, clipboard_text)
        self.assertEqual(sent.paste.call_args.args[1], clipboard_text)
        self.assertEqual(sent.paste.call_args.args[2], str(sent.task))
        self.assertEqual(sent.paste.call_args.kwargs, {"program": PROGRAM, "app_name": DISPLAY})
        self.assertEqual(sent.finish.call_args.args[1], "prepared")
        sent.opened.assert_not_called()

    def test_req_s01_70_failed_paste_keeps_instruction_and_opens_task_folder(self):
        sent = self.send(desktop_paste=True, paste_result={"ok": False, "reason": "未能自动粘贴"})
        message = sent.finish.call_args.args[2]
        self.assertEqual(sent.finish.call_args.args[1], "failed")
        self.assertIn(str(sent.task), message)
        self.assertIn("附件", message)
        sent.opened.assert_called_once_with(sent.task.parent)

    def test_req_s01_70_copy_only_delivery_tells_user_to_upload_task_file(self):
        sent = self.send(desktop_paste=False)
        sent.paste.assert_not_called()
        self.assertNotIn("甲" * 100, sent.copy.call_args.args[1])
        message = sent.host.status.set.call_args.args[0]
        self.assertIn(str(sent.task), message)
        self.assertIn("作为附件上传", message)
        sent.opened.assert_called_once_with(sent.task.parent)


class AttachmentTransportTests(unittest.TestCase):
    def test_req_s01_70_attachment_path_reaches_powershell_payload(self):
        captured = {}

        def run(args, **kwargs):
            captured.update(json.loads(Path(args[-1]).read_text(encoding="utf-8")))
            return SimpleNamespace(stdout='{"ok":true,"send_dispatched":false}', stderr="", returncode=0)
        with patch.object(codex_paste.subprocess, "run", side_effect=run):
            codex_paste.paste_attachment("任务", "短指令", program=PROGRAM, app_name=DISPLAY,
                                         attachment=r"D:\proj\工作流任务\writing\a.md")
        self.assertEqual(captured["attachment"], r"D:\proj\工作流任务\writing\a.md")
        captured.clear()
        with patch.object(codex_paste.subprocess, "run", side_effect=run):
            codex_paste.paste_existing("任务", "正文", program=PROGRAM, app_name=DISPLAY)
        self.assertNotIn("attachment", captured)


if __name__ == "__main__":
    unittest.main()

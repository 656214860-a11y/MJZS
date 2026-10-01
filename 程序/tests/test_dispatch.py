# -*- coding: utf-8 -*-
"""Agent 调度与自动发送的纯逻辑自检。运行：python test_dispatch.py"""
import os, sys, tempfile, unittest
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.chdir(HERE)

from console_submit import empty_prompt
from agent_dispatch import signature


class EmptyPromptTests(unittest.TestCase):
    def test_gt(self):
        self.assertTrue(empty_prompt(">"))
    def test_gt_space(self):
        self.assertTrue(empty_prompt("> "))
    def test_arrow(self):
        self.assertTrue(empty_prompt("❯"))
    def test_padded(self):
        self.assertTrue(empty_prompt("  >  "))
    def test_has_draft(self):
        self.assertFalse(empty_prompt("> 草稿"))
    def test_empty(self):
        self.assertFalse(empty_prompt(""))


class SignatureTests(unittest.TestCase):
    def test_deterministic(self):
        cfg = {"engine": "codex"}
        ctx = {"scripts": [{"path": "a.md"}]}
        self.assertEqual(signature("writing", "p", "f", cfg, ctx), signature("writing", "p", "f", cfg, ctx))

    def test_prompt_changes_hash(self):
        cfg = {"engine": "codex"}
        ctx = {}
        self.assertNotEqual(signature("writing", "p1", "f", cfg, ctx), signature("writing", "p2", "f", cfg, ctx))


class DispatchStateMachineTests(unittest.TestCase):
    def make_project(self, td):
        proj = Path(td) / "p"; proj.mkdir()
        return proj

    def test_claim_first_then_duplicate(self):
        from agent_dispatch import claim
        with tempfile.TemporaryDirectory() as td:
            proj = self.make_project(td)
            r1 = claim(proj, "key123", "任务")
            self.assertFalse(r1["duplicate"])
            r2 = claim(proj, "key123", "任务")
            self.assertTrue(r2["duplicate"])
            self.assertEqual(r2["state"], "preparing")

    def test_outcome_mapping(self):
        from agent_dispatch import claim, outcome
        with tempfile.TemporaryDirectory() as td:
            proj = self.make_project(td)
            r = claim(proj, "key456", "任务")
            outcome(r, {"ok": True, "reason": "x"})
            from agent.core import read
            self.assertEqual(read(r["record"])["state"], "sent")
            # uncertain
            r2 = claim(proj, "key789", "任务")
            outcome(r2, {"ok": False, "send_dispatched": True, "reason": "x"})
            self.assertEqual(read(r2["record"])["state"], "uncertain")

    def test_only_a_closed_uncertain_dispatch_is_auto_retryable(self):
        from agent_dispatch import retryable
        self.assertTrue(retryable({'duplicate': True, 'state': 'uncertain'}, False))
        self.assertFalse(retryable({'duplicate': True, 'state': 'uncertain'}, True))
        self.assertFalse(retryable({'duplicate': True, 'state': 'sent'}, False))

    def test_corrupt_previous_record_treated_empty(self):
        from agent_dispatch import claim
        from agent.core import read
        with tempfile.TemporaryDirectory() as td:
            proj = self.make_project(td)
            folder = proj / "工作流任务" / "Agent发送记录"; folder.mkdir(parents=True)
            record = folder / "key-corrupt.json"; record.write_text("[]", encoding="utf-8")
            r = claim(proj, "key-corrupt", "任务")
            self.assertFalse(r["duplicate"])
            self.assertEqual(read(record)["state"], "preparing")


class OptimizerErrorTests(unittest.TestCase):
    def classify(self, text):
        from agent.optimizer_mcp_bridge import classify_error
        return classify_error(text)

    def test_quota(self):
        self.assertIn("余额或额度不足", self.classify("insufficient_quota"))

    def test_invalid_key(self):
        self.assertIn("密钥无效", self.classify("401 invalid_api_key"))

    def test_model_not_found(self):
        self.assertIn("模型不存在", self.classify("model_not_found"))

    def test_timeout(self):
        self.assertIn("超时", self.classify("timed out"))

    def test_unknown_falls_back(self):
        self.assertIn("未取得可识别的", self.classify("some unknown failure"))

    def test_permission_denied(self):
        self.assertIn("访问被拒绝", self.classify("403 permission denied"))

    def test_rate_limit(self):
        self.assertIn("频率或额度受限", self.classify("429 rate_limit"))

    def test_connection(self):
        self.assertIn("无法连接", self.classify("connecterror proxy"))

    def test_outcome_failed_when_not_dispatched(self):
        from agent_dispatch import claim, outcome
        from agent.core import read
        with tempfile.TemporaryDirectory() as td:
            proj = Path(td) / "p"; proj.mkdir()
            r = claim(proj, "key-fail", "任务")
            outcome(r, {"ok": False, "send_dispatched": False, "reason": "x"})
            self.assertEqual(read(r["record"])["state"], "failed")


class WorkflowAgentLabelTests(unittest.TestCase):
    def test_no_default_model_text(self):
        from workflow_agents import label
        text = label({"model": "", "skill": ""}, "storyboard", "codex")
        self.assertNotIn("默认模型", text)


class PromptWithSettingsTests(unittest.TestCase):
    def test_wraps_prompt(self):
        from workflow_engines import prompt_with_settings
        text = prompt_with_settings("任务", {"instructions": "", "skill": "", "engine": "codex"})
        self.assertIn("任务", text)
        self.assertIn("简体中文", text)

    def test_appends_instructions(self):
        from workflow_engines import prompt_with_settings
        text = prompt_with_settings("任务", {"instructions": "补充要求", "skill": "", "engine": "codex"})
        self.assertIn("补充要求", text)


if __name__ == "__main__":
    unittest.main(verbosity=2)

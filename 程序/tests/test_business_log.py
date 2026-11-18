# -*- coding: utf-8 -*-
"""L2 领域服务层优化任务书轮 7（功能轮）：``infra.business_log`` 与 8 模块接入回归。

覆盖三层：

1. ``log_event`` 契约——kind 序列化为一行 JSON；白名单外字段丢弃并在
   ``dropped_fields`` 留名；字段值只允许 ``[A-Za-z0-9_.-]`` 短标识符，路径／URL／
   自由文本／数字误用一律丢字段不泄漏；``cost_ms`` 只收有限数值；自身任何异常
   都吞掉不抛。
2. 8 个接入模块主入口各触发一次，断言产生带业务字段（stage／shot_id／asset_id／
   outcome 之一或多个）的 ``business`` 日志记录，且均含 ``cost_ms``。
3. 路径泄漏验收——构造含盘符绝对路径的输入场景，断言捕获的日志文本不含
   ``[A-Za-z]:\\`` 盘符形态、不含临时目录绝对路径。
"""
import json
import logging
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import infra.business_log as business_log
from agent.core import save, save_text
from contract.project_context import ProjectContext
from tests.image_fixtures import png

BUSINESS_LOGGER = "business"
_DRIVE_PATH = re.compile(r"[A-Za-z]:[\\/]")


def _context(root):
    """最小 ProjectContext：L2 只校验类型并取 ``.root``（与 test_domain_cache_locks 同口径）。"""
    root = Path(root)
    return ProjectContext.snapshot(root, lambda stage: root / stage)


class _Capture(logging.Handler):
    """捕获 ``business`` logger 的原始消息文本，供 JSON 解析与泄漏断言共用。"""

    def __init__(self):
        super().__init__()
        self.messages = []

    def emit(self, record):
        self.messages.append(record.getMessage())


class BusinessLogCase(unittest.TestCase):
    """每个用例挂一只捕获 handler；setUp 里把 business logger 级别钉在 INFO。"""

    def setUp(self):
        self.capture = _Capture()
        self.logger = logging.getLogger(BUSINESS_LOGGER)
        self.logger.addHandler(self.capture)
        self.logger.setLevel(logging.INFO)
        self.addCleanup(self.logger.removeHandler, self.capture)

    def payloads(self):
        out = []
        for message in self.capture.messages:
            try:
                out.append(json.loads(message))
            except ValueError:
                out.append(message)
        return out

    def of_kind(self, kind):
        return [item for item in self.payloads()
                if isinstance(item, dict) and item.get("kind") == kind]

    def assert_no_path_leak(self):
        """验收硬指标：任何一条落盘文本都不得含盘符路径形态。"""
        for message in self.capture.messages:
            self.assertIsNone(_DRIVE_PATH.search(message),
                              "日志泄漏盘符路径：%r" % message)


class LogEventContractTests(BusinessLogCase):
    """``log_event`` 自身契约：序列化、白名单处置、值校验、绝不抛。"""

    def test_event_is_one_structured_json_line(self):
        self.assertIsNone(business_log.log_event(
            "recon.run", stage="script", outcome="ok", cost_ms=12.34))
        self.assertEqual(len(self.capture.messages), 1)
        payload = json.loads(self.capture.messages[0])
        self.assertEqual(payload["kind"], "recon.run")
        self.assertEqual(payload["stage"], "script")
        self.assertEqual(payload["outcome"], "ok")
        self.assertEqual(payload["cost_ms"], 12.3)
        self.assertNotIn("dropped_fields", payload)
        # 结构化：整行可解析为 JSON，kind 在场。
        self.assertEqual(self.of_kind("recon.run")[0]["kind"], "recon.run")

    def test_unknown_fields_are_dropped_and_named(self):
        business_log.log_event("idea_chat.receive_brief", stage="script",
                               outcome="ok", cost_ms=1.0,
                               prompt="用户创意全文", project_path="D:/secret/x")
        payload = self.of_kind("idea_chat.receive_brief")[0]
        self.assertNotIn("prompt", payload)
        self.assertNotIn("project_path", payload)
        self.assertEqual(payload["dropped_fields"], ["project_path", "prompt"])
        joined = "\n".join(self.capture.messages)
        self.assertNotIn("用户创意全文", joined)
        self.assertNotIn("D:/secret/x", joined)
        self.assertNotIn("secret", joined)

    def test_unsafe_values_are_dropped_not_leaked(self):
        business_log.log_event(
            "probe.event", stage=r"D:\proj\秘密", shot_id="SH001",
            asset_id="https://a.example/x", outcome="ok 值带空格",
            cost_ms=2.0)
        payload = self.of_kind("probe.event")[0]
        # 四个文本字段中三个值不合法被丢；shot_id 是合法标识符保留。
        self.assertEqual(payload["shot_id"], "SH001")
        self.assertEqual(payload["cost_ms"], 2.0)
        for bad in ("stage", "asset_id", "outcome"):
            self.assertNotIn(bad, payload)
        self.assertEqual(payload["dropped_fields"], ["asset_id", "outcome", "stage"])
        joined = "\n".join(self.capture.messages)
        for leaked in (r"D:\proj", "a.example", "ok 值带空格"):
            self.assertNotIn(leaked, joined)
        self.assert_no_path_leak()

    def test_value_edge_cases(self):
        business_log.log_event("probe.edge", stage="  script  ", shot_id="",
                               asset_id="A" * 200, outcome=None, cost_ms=1)
        payload = self.of_kind("probe.edge")[0]
        self.assertEqual(payload["stage"], "script")   # 首尾空白裁剪后合法
        self.assertEqual(payload["cost_ms"], 1.0)
        for bad in ("shot_id", "asset_id", "outcome"):
            self.assertNotIn(bad, payload)
        self.assertEqual(payload["dropped_fields"], ["asset_id", "outcome", "shot_id"])

    def test_cost_ms_rejects_non_numeric(self):
        for bad in ("12", True, None, float("nan"), float("inf"), object()):
            with self.subTest(bad=bad):
                self.capture.messages.clear()
                business_log.log_event("probe.ms", outcome="ok", cost_ms=bad)
                payload = self.of_kind("probe.ms")[-1]
                self.assertNotIn("cost_ms", payload)
                self.assertIn("cost_ms", payload["dropped_fields"])
        business_log.log_event("probe.ms", outcome="ok", cost_ms=0)
        self.assertEqual(self.of_kind("probe.ms")[-1]["cost_ms"], 0.0)

    def test_kind_is_sanitized(self):
        business_log.log_event("recon run with spaces", outcome="ok")
        self.assertEqual(self.of_kind("unknown")[0]["kind"], "unknown")
        business_log.log_event("a" * 200, outcome="ok")
        self.assertEqual(self.of_kind("unknown")[-1]["kind"], "unknown")
        business_log.log_event("recon.run", outcome="ok")
        self.assertEqual(self.of_kind("recon.run")[-1]["kind"], "recon.run")

    def test_log_event_never_raises(self):
        # 序列化目标整体罢工：日志设施吞掉，不向上抛。
        with mock.patch.object(business_log, "_write_payload", side_effect=RuntimeError("boom")):
            self.assertIsNone(business_log.log_event("x.y", outcome="ok"))
        # 落盘通道罢工（logger.info 抛错）：同样吞掉。
        broken = mock.Mock()
        broken.info.side_effect = RuntimeError("disk full")
        with mock.patch.object(business_log, "_logger", broken):
            self.assertIsNone(business_log.log_event("x.y", outcome="ok"))
        # kind 本身不可 str()：同样吞掉。
        class BadKind:
            def __str__(self):
                raise ValueError("no str")
        self.assertIsNone(business_log.log_event(BadKind(), outcome="ok"))
        # fields 传入非标量值：值校验兜底，不抛。
        self.assertIsNone(business_log.log_event("x.y", outcome={"a": 1},
                                                  shot_id=["SH001"], cost_ms="1"))

    def test_absolute_paths_never_reach_the_log(self):
        tmp = tempfile.mkdtemp()
        business_log.log_event(
            "probe.path", stage=tmp, shot_id=str(Path(tmp) / "sub"),
            asset_id="/home/user/proj/x", outcome=r"C:\data\y", cost_ms=1.0)
        business_log.log_event("probe.path2", stage="normal_stage", outcome="ok")
        self.assert_no_path_leak()
        joined = "\n".join(self.capture.messages)
        self.assertNotIn(tmp, joined)
        self.assertNotIn("home/user", joined)
        self.assertNotIn("data\\y", joined)


class ModuleEntryTests(BusinessLogCase):
    """8 个接入模块主入口：各触发一次，断言业务字段事件与 cost_ms。"""

    def _chat_gateway(self):
        return {"read_json": lambda path: json.loads(Path(path).read_text(encoding="utf-8")),
                "publish_json": save, "publish_text": save_text}

    def test_idea_chat_receive_brief(self):
        import idea_chat
        from stage_execution_service import idea_chat_gateway, project_context
        with tempfile.TemporaryDirectory() as td:
            result = idea_chat.receive_brief(
                project_context(td),
                "故事梗概：夜班照相馆收到一张会显影未来的旧底片。",
                gateway=idea_chat_gateway())
            self.assertTrue(result["raw_path"].is_file())
        payload = self.of_kind("idea_chat.receive_brief")[-1]
        self.assertEqual(payload["stage"], "script")
        self.assertEqual(payload["outcome"], "ok")
        self.assertIsInstance(payload["cost_ms"], (int, float))
        self.assert_no_path_leak()

    def test_white_model_migrate(self):
        import white_model_service
        with tempfile.TemporaryDirectory() as td:
            project = Path(td) / "proj"
            space = Path(td) / "space"
            project.mkdir()
            space.mkdir()
            (project / "config.json").write_text("{}", encoding="utf-8")
            result = white_model_service.migrate_legacy_directories(
                _context(project), publish=save, workspace_path=space)
        self.assertEqual(result["moved"], [])
        payload = self.of_kind("white_model.migrate")[-1]
        self.assertEqual(payload["stage"], "previs")
        self.assertEqual(payload["outcome"], "ok")
        self.assertIsInstance(payload["cost_ms"], (int, float))
        self.assert_no_path_leak()

    def test_recon_run(self):
        import recon_service
        with tempfile.TemporaryDirectory() as td:
            def send(kind, value, count=5):
                if kind == "search":
                    return {"ok": True, "status": 200, "data": {}, "results": [
                        {"title": "t", "url": "https://a.example/1", "rerank_score": 2.4},
                        {"title": "t", "url": "https://b.example/2", "rerank_score": 2.4}]}
                return {"ok": True, "status": 200,
                        "data": {"title": "x"}, "title": "x", "content": "正文"}
            ports = recon_service.ReconPorts(sender=send, pause=lambda _s: None)
            result = recon_service.run(Path(td), {"name": "某剧"}, "对标爆款", ports=ports)
        self.assertTrue(result.ok, getattr(result, "reason", ""))
        payload = self.of_kind("recon.run")[-1]
        self.assertEqual(payload["stage"], "script")
        self.assertEqual(payload["outcome"], "ok")
        self.assertIsInstance(payload["cost_ms"], (int, float))
        # 业务日志与 paid.invoked 总线事件是两条通道：本用例只看本地日志一条 run 事件。
        self.assertEqual(len(self.of_kind("recon.run")), 1)
        self.assert_no_path_leak()

    def test_storyboard_catalog_snapshot(self):
        import storyboard_catalog_service
        with tempfile.TemporaryDirectory() as td:
            snap = storyboard_catalog_service.catalog_snapshot(_context(td))
        self.assertEqual(snap["script"], [])
        self.assertEqual(snap["storyboard"], [])
        payload = self.of_kind("storyboard_catalog.snapshot")[-1]
        self.assertEqual(payload["outcome"], "ok")
        self.assertIsInstance(payload["cost_ms"], (int, float))
        self.assert_no_path_leak()

    def test_idea_transcript_append(self):
        from domain import idea_transcript
        with tempfile.TemporaryDirectory() as td:
            idea_transcript.append(_context(td), "user", "你好", gateway=self._chat_gateway())
            rows = idea_transcript.load(_context(td), gateway=self._chat_gateway())
        self.assertEqual(len(rows), 1)
        payload = self.of_kind("idea_transcript.append")[-1]
        self.assertEqual(payload["stage"], "script")
        self.assertEqual(payload["outcome"], "ok")
        self.assertIsInstance(payload["cost_ms"], (int, float))
        # 对话正文属用户内容：日志里不得出现消息文本。
        joined = "\n".join(self.capture.messages)
        self.assertNotIn("你好", joined)
        self.assert_no_path_leak()

    def test_speech_api_create_session(self):
        from domain import speech_api
        settings = {"backend": "cloud", "model": "asr-x",
                    "base_url": "wss://asr.example.com/v1", "key_env": "NO_SUCH_KEY_ENV_XYZ"}
        session = speech_api.create_session(settings)
        self.assertIsNotNone(session)
        payload = self.of_kind("speech_api.create_session")[-1]
        self.assertEqual(payload["outcome"], "ok")
        self.assertIsInstance(payload["cost_ms"], (int, float))
        self.assert_no_path_leak()

    def test_asset_batch_register_image(self):
        import asset_batch_service
        from stage_execution_service import asset_batch_gateway
        with tempfile.TemporaryDirectory() as td:
            base = Path(td) / "asset-base"
            plan_file = base / "assets" / "资产清单" / "assets.json"
            plan_file.parent.mkdir(parents=True)
            plan = {"CHAR_001": {"name": "角色", "description": "", "image_prompt": "正向",
                                 "negative_prompt": "", "positive_prompt": "正向",
                                 "prompt": "正向", "reference_images": []}}
            plan_file.write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
            image = Path(td) / "gen.png"
            image.write_bytes(png())
            result = asset_batch_service.register_image(
                base, "CHAR_001", plan["CHAR_001"], str(image),
                gateway=asset_batch_gateway())
        self.assertEqual(result, "已生成并导入")
        payload = self.of_kind("asset_batch.register_image")[-1]
        self.assertEqual(payload["stage"], "assets")
        self.assertEqual(payload["asset_id"], "CHAR_001")
        self.assertEqual(payload["outcome"], "ok")
        self.assertIsInstance(payload["cost_ms"], (int, float))
        self.assert_no_path_leak()

    def test_confirm_gates_run(self):
        from domain import confirm_gates as cg
        result = cg.run("G-01", shots=[], assets={}, ledger=None)
        self.assertIn(result["passed"], (True, False))
        payload = self.of_kind("confirm_gates.run")[-1]
        self.assertEqual(payload["stage"], "continuity")
        self.assertIn(payload["outcome"], ("passed", "blocked"))
        self.assertIsInstance(payload["cost_ms"], (int, float))
        self.assert_no_path_leak()

    def test_all_module_entries_emit_cost_ms(self):
        """验收硬指标：8 个模块主入口事件均含 cost_ms（逐个触发后统一核对）。"""
        expected = {
            "idea_chat.receive_brief": self.test_idea_chat_receive_brief,
            "white_model.migrate": self.test_white_model_migrate,
            "recon.run": self.test_recon_run,
            "storyboard_catalog.snapshot": self.test_storyboard_catalog_snapshot,
            "idea_transcript.append": self.test_idea_transcript_append,
            "speech_api.create_session": self.test_speech_api_create_session,
            "asset_batch.register_image": self.test_asset_batch_register_image,
            "confirm_gates.run": self.test_confirm_gates_run,
        }
        for kind, trigger in expected.items():
            with self.subTest(kind=kind):
                self.capture.messages.clear()
                trigger()
                payload = self.of_kind(kind)[-1]
                self.assertIn("cost_ms", payload, "%s 缺耗时字段" % kind)
                self.assertIsInstance(payload["cost_ms"], (int, float))
                self.assertIn("outcome", payload)


if __name__ == "__main__":
    unittest.main()

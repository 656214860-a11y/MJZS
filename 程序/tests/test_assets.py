# -*- coding: utf-8 -*-
"""资产分类/背景人物识别纯逻辑自检。运行：python test_assets.py"""
import json, os, sys, tempfile, unittest
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.chdir(HERE)

from contract.prop_assets import requires_asset, normalize_shot, inline_text
from background_characters import scan
from asset_batch_service import automatic_plan, auto_settings
from stage_execution_service import asset_plan_gateway
from asset_batch_selection_service import all_selected, select_category, set_selection, toggle_excluded


class RequiresAssetTests(unittest.TestCase):
    def test_prop_key(self):
        self.assertTrue(requires_asset("PROP_001", {"prop_importance": "key"}))

    def test_prop_ordinary(self):
        self.assertFalse(requires_asset("PROP_001", {"prop_importance": "ordinary"}))

    def test_prop_bool_false(self):
        self.assertFalse(requires_asset("PROP_001", {"requires_asset": False}))

    def test_prop_legacy_default(self):
        self.assertTrue(requires_asset("PROP_001", {}))

    def test_char_background(self):
        self.assertFalse(requires_asset("CHAR_001", {"character_importance": "background"}))

    def test_char_key(self):
        self.assertTrue(requires_asset("CHAR_001", {"character_importance": "key"}))

    def test_loc_always(self):
        self.assertTrue(requires_asset("LOC_001", {}))


class AssetBatchSelectionTests(unittest.TestCase):
    def setUp(self):
        self.rows = {'CHAR_001': {}, 'CHAR_002': {}, 'LOC_001': {}}

    def test_select_category_only_restores_that_category(self):
        self.assertEqual(select_category(self.rows, {'CHAR_001', 'LOC_001'}, 'CHAR'),
                         {'LOC_001'})

    def test_toggle_excluded_returns_new_toggled_set(self):
        self.assertEqual(toggle_excluded({'CHAR_001'}, ['CHAR_001', 'LOC_001']),
                         {'LOC_001'})

    def test_set_selection_and_all_selected(self):
        excluded = set_selection({'CHAR_001'}, ['CHAR_001', 'LOC_001'], True)
        self.assertEqual(excluded, set())
        self.assertTrue(all_selected(['CHAR_001', 'LOC_001'], excluded))
        excluded = set_selection(excluded, ['LOC_001'], False)
        self.assertEqual(excluded, {'LOC_001'})
        self.assertFalse(all_selected(['CHAR_001', 'LOC_001'], excluded))


class NormalizeShotTests(unittest.TestCase):
    def test_props_none_or_scalar_coerced(self):
        from contract.prop_assets import normalize_shot
        self.assertEqual(normalize_shot({"props": None}, {}).get("props"), [])
        self.assertEqual(normalize_shot({"props": "PROP_001"}, {}).get("props"), ["PROP_001"])
        self.assertEqual(normalize_shot({"props": 123}, {}).get("props"), [])

    def test_ordinary_prop_moves_out(self):
        """REQ-S05-12：普通道具降级为镜头内描述，不分配 PROP 编号、不留在 props/first_frame_assets。"""
        shot = {"id": "SH001", "props": ["PROP_001"], "first_frame_assets": ["PROP_001"]}
        entries = {"PROP_001": {"name": "普通道具", "prop_importance": "ordinary"}}
        out = normalize_shot(shot, entries)
        self.assertEqual(out["props"], [])
        self.assertEqual(out["first_frame_assets"], [])
        self.assertEqual([p["name"] for p in out.get("ordinary_props", [])], ["普通道具"])

    def test_key_prop_kept(self):
        shot = {"id": "SH001", "props": ["PROP_001"]}
        entries = {"PROP_001": {"name": "关键道具", "prop_importance": "key"}}
        out = normalize_shot(shot, entries)
        self.assertEqual(out["props"], ["PROP_001"])
        self.assertNotIn("ordinary_props", out)

    def test_non_dict_shot_returns_empty(self):
        self.assertEqual(normalize_shot(None), {})
        self.assertEqual(normalize_shot("不是对象"), {})
        self.assertEqual(inline_text(None), "")

    def test_inline_text(self):
        """REQ-S05-12：普通道具写进镜头提示词的文字，而不是进入需要独立生图的资产清单。"""
        shot = {"ordinary_props": [{"name": "杯子", "description": "桌上玻璃杯"}]}
        text = inline_text(shot)
        self.assertIn("杯子", text)
        self.assertIn("玻璃杯", text)


class BackgroundScanTests(unittest.TestCase):
    def make(self, td, char):
        proj = Path(td) / "p"
        (proj / "episode" / "assets" / "资产清单").mkdir(parents=True)
        (proj / "episode" / "assets" / "资产清单" / "assets.json").write_text(
            json.dumps({"CHAR_001": char}, ensure_ascii=False), encoding="utf-8")
        (proj / "episode" / "assets.json").write_text("{}", encoding="utf-8")
        return proj

    def test_name_keyword(self):
        with tempfile.TemporaryDirectory() as td:
            proj = self.make(td, {"name": "路人甲", "description": ""})
            cands = scan(proj)
            self.assertEqual(len(cands), 1)
            self.assertEqual(cands[0]["aid"], "CHAR_001")
            self.assertEqual(cands[0]["hit"], "路人")

    def test_locked_skipped(self):
        with tempfile.TemporaryDirectory() as td:
            proj = self.make(td, {"name": "路人甲", "description": "", "appearance_locked": True})
            self.assertEqual(scan(proj), [])


class ReferencesTests(unittest.TestCase):
    def refs(self, shot):
        from asset_context import references
        return list(references(shot))

    def test_basic_refs(self):
        self.assertEqual(self.refs({"characters": ["CHAR_001"], "location": "LOC_001", "props": ["PROP_001"]}),
                         [("CHAR", "CHAR_001"), ("LOC", "LOC_001"), ("PROP", "PROP_001")])

    def test_dict_entry_id(self):
        self.assertEqual(self.refs({"characters": [{"id": "CHAR_002"}]}), [("CHAR", "CHAR_002")])

    def test_first_frame_assets_only_ids(self):
        shot = {"characters": ["CHAR_001"], "first_frame_assets": ["CHAR_001", "PROP_003", "某道具名"]}
        refs = self.refs(shot)
        self.assertIn(("PROP", "PROP_003"), refs)
        self.assertNotIn(("CHAR", "某道具名"), refs)

    def test_dedup(self):
        shot = {"characters": ["CHAR_001"], "first_frame_assets": ["CHAR_001"]}
        self.assertEqual(self.refs(shot).count(("CHAR", "CHAR_001")), 1)


class ImageReadyTests(unittest.TestCase):
    def test_registered_image_ready(self):
        from asset_batch import image_ready
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            (base / "assets" / "characters").mkdir(parents=True)
            png = base / "assets" / "characters" / "CHAR_001.png"
            png.write_bytes(b"x")
            (base / "assets.json").write_text(json.dumps({"CHAR_001": {"image": "assets/characters/CHAR_001.png"}}, ensure_ascii=False), encoding="utf-8")
            self.assertTrue(image_ready(base, "CHAR_001"))

    def test_image_not_ready_missing_file(self):
        from asset_batch import image_ready
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            (base / "assets.json").write_text(json.dumps({"CHAR_001": {"image": "assets/characters/CHAR_001.png"}}, ensure_ascii=False), encoding="utf-8")
            self.assertFalse(image_ready(base, "CHAR_001"))

    def test_image_not_ready_no_registry(self):
        from asset_batch import image_ready
        with tempfile.TemporaryDirectory() as td:
            self.assertFalse(image_ready(Path(td), "CHAR_001"))

    def test_image_ready_reuses_pre_read_registry(self):
        import asset_batch
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            (base / "assets" / "characters").mkdir(parents=True)
            (base / "assets" / "characters" / "CHAR_001.png").write_bytes(b"x")
            (base / "assets.json").write_text(json.dumps({"CHAR_001": {"image": "assets/characters/CHAR_001.png"}}, ensure_ascii=False), encoding="utf-8")
            registry = json.loads((base / "assets.json").read_text(encoding="utf-8"))
            original = asset_batch.read
            asset_batch.read = lambda path: self.fail("传入清单后不应再读资产库")
            try:
                self.assertTrue(asset_batch.image_ready(base, "CHAR_001", registry=registry))
            finally:
                asset_batch.read = original


class BatchCompleteTests(unittest.TestCase):
    """批量是否真的做完：只看落盘结果，不看生成流程返回的文案。"""

    def make_base(self, td, imported, registered):
        base = Path(td)
        (base / "assets" / "characters").mkdir(parents=True)
        registry = {}
        for aid in registered:
            registry[aid] = {"image": "assets/characters/" + aid + ".png"}
            if aid in imported:
                (base / "assets" / "characters" / (aid + ".png")).write_bytes(b"x")
        (base / "assets.json").write_text(json.dumps(registry, ensure_ascii=False), encoding="utf-8")
        return base

    def test_all_imported_is_complete(self):
        from asset_batch import batch_complete
        with tempfile.TemporaryDirectory() as td:
            base = self.make_base(td, ["CHAR_001", "CHAR_002"], ["CHAR_001", "CHAR_002"])
            self.assertTrue(batch_complete(base, ["CHAR_001", "CHAR_002"]))

    def test_partial_import_is_not_complete(self):
        from asset_batch import batch_complete
        with tempfile.TemporaryDirectory() as td:
            base = self.make_base(td, ["CHAR_001"], ["CHAR_001", "CHAR_002"])
            self.assertFalse(batch_complete(base, ["CHAR_001", "CHAR_002"]))

    def test_never_registered_is_not_complete(self):
        from asset_batch import batch_complete
        with tempfile.TemporaryDirectory() as td:
            base = self.make_base(td, [], ["CHAR_001"])
            self.assertFalse(batch_complete(base, ["CHAR_001"]))

    def test_empty_selection_counts_as_complete(self):
        from asset_batch import batch_complete
        with tempfile.TemporaryDirectory() as td:
            self.assertTrue(batch_complete(Path(td), []))


class AssetPromptRulesTests(unittest.TestCase):
    def test_positive_prefers_image_prompt(self):
        from asset_prompt_rules import positive
        self.assertEqual(positive({"image_prompt": "正向", "prompt": "其他"}), "正向")

    def test_positive_falls_back(self):
        from asset_prompt_rules import positive
        self.assertEqual(positive({"prompt": "正向"}), "正向")
        self.assertEqual(positive({}), "")

    def test_issues_missing_name(self):
        from asset_prompt_rules import issues
        self.assertIn("缺少资产名称", issues("CHAR_001", {"image_prompt": "正向"}))

    def test_issues_missing_prompt(self):
        from asset_prompt_rules import issues
        self.assertIn("缺少完整生图提示词", issues("CHAR_001", {"name": "角色"}))

    def test_issues_ok(self):
        from asset_prompt_rules import issues
        self.assertEqual(issues("CHAR_001", {"name": "角色", "image_prompt": "正向"}), [])


class SafetensorsTests(unittest.TestCase):
    def make_valid(self, path):
        import struct, json
        header = {"tensor1": {"dtype": "F32", "shape": [1], "data_offsets": [0, 4]}}
        raw = json.dumps(header).encode("utf-8")
        path.write_bytes(struct.pack("<Q", len(raw)) + raw)

    def test_valid_safetensors(self):
        import tempfile
        from comfy_service import validate_safetensors
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "m.safetensors"
            self.make_valid(p)
            self.assertIsNone(validate_safetensors(p))  # 合法头部：不抛异常

    def test_invalid_safetensors(self):
        import tempfile
        from comfy_service import validate_safetensors
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "m.safetensors"; p.write_bytes(b"not a real file")
            with self.assertRaises(ValueError):
                validate_safetensors(p)


class ReferencePromptTests(unittest.TestCase):
    def test_key_normalizes(self):
        from domain.asset_reference_prompts import key
        self.assertEqual(key("《卡梅隆》"), "卡梅隆")
        self.assertEqual(key("卡 梅 隆"), "卡梅隆")

    def test_fingerprint_deterministic(self):
        from domain.asset_reference_prompts import fingerprint
        self.assertEqual(fingerprint("p", "n"), fingerprint("p", "n"))

    def test_cards_parses(self):
        from domain.asset_reference_prompts import cards
        text = "# 角色卡：卡梅隆\n角色 ID：CHAR_001\n\n## 参考图提示词\n正向提示词：一个男孩，灰卫衣\n负向提示词：模糊\n"
        found = cards(text)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["name"], "卡梅隆")
        self.assertEqual(found[0]["id"], "CHAR_001")
        self.assertEqual(found[0]["positive"], "一个男孩，灰卫衣")
        self.assertEqual(found[0]["negative"], "模糊")

    def test_display_prompt(self):
        from domain.asset_reference_prompts import display_prompt
        self.assertEqual(display_prompt({"image_prompt": "正向", "negative_prompt": "负向"}), "正向\n\n负向提示词：负向")
        self.assertEqual(display_prompt({}), "")

    def test_display_prompt_non_string_negative(self):
        from domain.asset_reference_prompts import display_prompt
        self.assertEqual(display_prompt({"image_prompt": "正向", "negative_prompt": 123}), "正向")

    def test_display_prompt_non_dict_empty(self):
        from domain.asset_reference_prompts import display_prompt
        self.assertEqual(display_prompt(None), "")
        self.assertEqual(display_prompt("不是对象"), "")


class RefIdTests(unittest.TestCase):
    def test_ref_id_string(self):
        from background_characters import _ref_id
        self.assertEqual(_ref_id("CHAR_001"), "CHAR_001")

    def test_ref_id_dict(self):
        from background_characters import _ref_id
        self.assertEqual(_ref_id({"id": "CHAR_002"}), "CHAR_002")


PNG_1PX = __import__("base64").b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=")


class RegisterImageTests(unittest.TestCase):
    def test_bad_id(self):
        from asset_batch import register_image
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(ValueError):
                register_image(Path(td), "BAD", {}, str(Path(td) / "x.png"))

    def test_not_png(self):
        from asset_batch import register_image
        with tempfile.TemporaryDirectory() as td:
            img = Path(td) / "x.png"; img.write_bytes(b"not a png")
            with self.assertRaises(ValueError):
                register_image(Path(td), "CHAR_001", {}, str(img))

    def test_success(self):
        from asset_batch import register_image
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            (base / "assets" / "资产清单").mkdir(parents=True)
            plan = {"CHAR_001": {"name": "角色", "description": "", "image_prompt": "正向",
                                  "negative_prompt": "", "positive_prompt": "正向", "prompt": "正向", "reference_images": []}}
            (base / "assets" / "资产清单" / "assets.json").write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
            img = base / "gen.png"; img.write_bytes(PNG_1PX)
            self.assertEqual(register_image(base, "CHAR_001", plan["CHAR_001"], str(img)), "已生成并导入")


class ComfySubmitRecoveryTests(unittest.TestCase):
    """提交响应中断（超时/断连）时按 client_id 找回任务编号，或明确判定提交失败。"""

    def make_client(self, seen, queue=None, history=None, error=None):
        from comfy_service import Comfy
        client = Comfy("http://127.0.0.1:8189")
        def request(path, data=None, raw=False, timeout=20):
            if path == "/prompt":
                seen["client_id"] = data["client_id"]
                raise error or TimeoutError("响应超时")
            if path == "/queue":
                return {"queue_running": list(queue or []), "queue_pending": []}
            if path == "/history":
                return dict(history or {})
            raise AssertionError(path)
        client.request = request
        return client

    def only_once(self, client):
        """找回逻辑只跑一轮，避免测试里为等待重试多花时间。"""
        from comfy_service import Comfy
        original = Comfy.locate_prompt
        client.locate_prompt = lambda client_id: original(client, client_id, attempts=1, wait=0)
        return client

    def test_lost_response_reattaches_to_queue(self):
        seen = {}
        client = self.only_once(self.make_client(seen))
        now = {}
        def request(path, data=None, raw=False, timeout=20):
            if path == "/prompt":
                now["client_id"] = data["client_id"]
                raise TimeoutError("响应超时")
            if path == "/queue":
                return {"queue_running": [[7, "PID-1", {}, {"client_id": now["client_id"]}, []]], "queue_pending": []}
            if path == "/history":
                return {}
            raise AssertionError(path)
        client.request = request
        with tempfile.TemporaryDirectory() as td:
            record = client.submit_graph(td, "characters", "提示词", {"4": {"class_type": "X", "inputs": {}}})
            job = json.loads(Path(record).read_text(encoding="utf-8"))
            self.assertEqual(job["state"], "queued")
            self.assertEqual(job["prompt_id"], "PID-1")
            self.assertIn("找回", job.get("note", ""))

    def test_history_entry_with_same_client_id_is_found(self):
        seen = {}
        client = self.only_once(self.make_client(seen))
        now = {}
        def request(path, data=None, raw=False, timeout=20):
            if path == "/prompt":
                now["client_id"] = data["client_id"]
                raise ConnectionResetError("连接被重置")
            if path == "/queue":
                return {"queue_running": [], "queue_pending": []}
            if path == "/history":
                return {"PID-9": {"prompt": [3, "PID-9", {}, {"client_id": now["client_id"]}, []], "outputs": {}}}
            raise AssertionError(path)
        client.request = request
        with tempfile.TemporaryDirectory() as td:
            record = client.submit_graph(td, "characters", "提示词", {"4": {"class_type": "X", "inputs": {}}})
            self.assertEqual(json.loads(Path(record).read_text(encoding="utf-8"))["prompt_id"], "PID-9")

    def test_other_client_ids_are_not_adopted(self):
        seen = {}
        client = self.only_once(self.make_client(seen, history={"PID-2": {"prompt": [3, "PID-2", {}, {"client_id": "别人的"}, []]}}))
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(Exception) as ctx:
                client.submit_graph(td, "characters", "提示词", {"4": {"class_type": "X", "inputs": {}}})
            from comfy_service import ComfySubmissionUncertain
            self.assertIsInstance(ctx.exception, ComfySubmissionUncertain)
            record = ctx.exception.record
            self.assertTrue(str(record).startswith(str(Path(td) / "workflows")))
            self.assertEqual(json.loads(Path(record).read_text(encoding="utf-8"))["state"], "unknown")

    def test_restart_recovers_persisted_client_without_resending(self):
        from comfy_service import Comfy, ComfySubmissionUncertain
        from unittest.mock import Mock
        with tempfile.TemporaryDirectory() as td:
            client = self.only_once(self.make_client({}))
            with self.assertRaises(ComfySubmissionUncertain) as caught:
                client.submit_graph(td, 'characters', 'prompt', {})
            record = Path(caught.exception.record)
            job = json.loads(record.read_text(encoding='utf-8'))
            self.assertTrue(job['client_id'])
            restarted = Comfy('http://127.0.0.1:8189')
            restarted.locate_prompt = Mock(return_value='original-task')
            restarted.request = Mock(return_value={})
            self.assertIn('排队', restarted.collect(td, record))
            restarted.locate_prompt.assert_called_once_with(job['client_id'])
            restarted.request.assert_called_once_with('/history/original-task')
            self.assertEqual(json.loads(record.read_text(encoding='utf-8'))['prompt_id'], 'original-task')

    def test_http_rejection_and_server_uncertainty_keep_distinct_states(self):
        from urllib.error import HTTPError
        from comfy_service import ComfyGenerationFailed, ComfySubmissionUncertain
        for code, error_type, state in [(429, ComfyGenerationFailed, 'failed'), (503, ComfySubmissionUncertain, 'unknown')]:
            with self.subTest(code=code), tempfile.TemporaryDirectory() as td:
                client = self.make_client({}, error=HTTPError('http://local/prompt', code, 'error', {}, None))
                with self.assertRaises(error_type):
                    client.submit_graph(td, 'characters', 'prompt', {})
                records = list((Path(td) / 'workflows').glob('comfy_*.json'))
                self.assertEqual(len(records), 1)
                self.assertEqual(json.loads(records[0].read_text(encoding='utf-8'))['state'], state)

    def test_locate_prompt_retries_until_visible(self):
        from comfy_service import Comfy
        client = Comfy("http://127.0.0.1:8189")
        seen = {"calls": 0}
        def request(path, data=None, raw=False, timeout=20):
            if path == "/queue":
                seen["calls"] += 1
                return {"queue_running": [], "queue_pending": ([[1, "PID-3", {}, {"client_id": "abc"}, []]] if seen["calls"] > 1 else [])}
            if path == "/history":
                return {}
            raise AssertionError(path)
        client.request = request
        self.assertEqual(client.locate_prompt("abc", attempts=2, wait=0), "PID-3")
        self.assertGreaterEqual(seen["calls"], 2)

    def test_lost_receipt_and_unreadable_recovery_are_not_reported_as_no_task(self):
        """网络无法读取队列／历史时，不能静默判成“没有提交”。"""
        from comfy_service import Comfy, ComfySubmissionUncertain
        with tempfile.TemporaryDirectory() as td:
            client = Comfy('http://127.0.0.1:8189')
            def request(path, data=None, raw=False, timeout=20):
                raise OSError('connection refused')
            client.request = request
            client = self.only_once(client)
            with self.assertRaises(ComfySubmissionUncertain) as ctx:
                client.submit_graph(td, "characters", "提示词", {"4": {"class_type": "X", "inputs": {}}})
            self.assertIn('无法读取 ComfyUI 队列／历史', str(ctx.exception))
            record = Path(ctx.exception.record)
            self.assertEqual(json.loads(record.read_text(encoding='utf-8'))['state'], 'unknown')

    def test_batch_keeps_uncertain_and_never_resubmits(self):
        import queue as queue_module, threading
        from comfy_service import ComfySubmissionUncertain
        from asset_batch import run_batch
        sent = []
        class Fake:
            def request(self, path, data=None, raw=False, timeout=20):
                if path == "/system_stats":
                    return {}
                raise AssertionError(path)
            def submit(self, *a, **k):
                sent.append(True)
                error = ComfySubmissionUncertain("提交结果不确定，请在本地 ComfyUI 核实任务；未自动重复提交")
                error.record = "workflows/comfy_deadbeef.json"
                raise error
        asset = {"name": "角色", "image_prompt": "一只猫坐在窗边", "negative_prompt": "", "reference_images": []}
        options = {"url": "http://127.0.0.1:8189", "backend": "local", "model": "flux.safetensors",
                   "workflow": "", "node": "6", "field": "text", "aspect_ratio": "1:1", "quality": "标准"}
        with tempfile.TemporaryDirectory() as td:
            base = Path(td) / "episode"
            events = queue_module.Queue()
            result = run_batch(td, base, [("CHAR_001", asset)], options, events, threading.Event(), client_factory=lambda url: Fake())
            self.assertIn("未完成 1", result)
            ledger = json.loads((Path(td) / "workflows" / "资产批量记录.json").read_text(encoding="utf-8"))
            self.assertEqual(ledger["CHAR_001"]["state"], "submitting")
            self.assertEqual(ledger["CHAR_001"]["record"], "workflows/comfy_deadbeef.json")
            run_batch(td, base, [("CHAR_001", asset)], options, events, threading.Event(), client_factory=lambda url: Fake())
            self.assertEqual(len(sent), 1)


class AssetBatchStopTests(unittest.TestCase):
    def test_stop_after_current_asset_then_resume_preserves_imported_image(self):
        import queue, threading
        from agent.core import save
        from orchestrator.asset_batch_execution import run_batch
        from asset_batch_state_service import read_ledger
        from stage_execution_service import prepare_asset_write
        stop = threading.Event()
        sent = []
        class Fake:
            def request(self, path):
                assert path == '/system_stats'
                return {}
            def submit(self, *args):
                sent.append(args[2])
                return Path(args[0]) / ('fixture-task-' + str(len(sent)))
            def collect(self, project, record):
                if len(sent) == 1:stop.set()
                return [Path(project) / 'generated.png']
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            base = prepare_asset_write(root, root / 'episode')
            plan = {f'CHAR_{i:03}': {'name': f'角色{i}', 'image_prompt': f'原创角色{i}站在窗边',
                    'negative_prompt': '', 'reference_images': []} for i in (1, 2)}
            save(base / 'assets/资产清单/assets.json', plan)
            (root / 'generated.png').write_bytes(PNG_1PX)
            options = {'url': 'http://127.0.0.1:8189', 'backend': 'local', 'model': 'fixture',
                       'workflow': '', 'node': '6', 'field': 'text', 'aspect_ratio': '1:1', 'quality': '标准'}
            run = lambda: run_batch(root, base, list(plan.items()), options, queue.Queue(), stop,
                                    client_factory=lambda url: Fake())
            self.assertIn('已停止后续资产', run())
            self.assertEqual(len(sent), 1)
            self.assertEqual(read_ledger(root)['CHAR_001']['state'], 'imported')
            trace = read_ledger(root)['CHAR_001']['execution']
            self.assertEqual(trace['task_id'], 'CHAR_001')
            self.assertTrue(trace['run_id'])
            self.assertNotIn('CHAR_002', read_ledger(root))
            registry = json.loads((base / 'assets.json').read_text(encoding='utf-8'))
            adopted = base / registry['CHAR_001']['image']
            before = (adopted.read_bytes(), adopted.stat().st_mtime_ns)
            stop.clear()
            self.assertIn('成功 1', run())
            self.assertEqual(len(sent), 2)
            self.assertEqual(read_ledger(root)['CHAR_002']['state'], 'imported')
            self.assertEqual(read_ledger(root)['CHAR_001']['execution'], trace)
            self.assertEqual((adopted.read_bytes(), adopted.stat().st_mtime_ns), before)


class ComfyMoneyBudgetTests(unittest.TestCase):
    def test_known_cloud_reference_and_save_nodes_fit_budget(self):
        from comfy_service import Comfy
        from unittest.mock import Mock
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); self.policy(root)
            graph = json.loads(json.dumps(self.GRAPH))
            graph['100'] = {'class_type': 'DramaOptionalReferenceImage', 'inputs': {'image': 'ref.png'}}
            graph['30']['inputs']['references'] = ['100', 0]
            graph['14'] = {'class_type': 'SaveImage', 'inputs': {'images': ['30', 0]}}
            client = Comfy('http://127.0.0.1:8189')
            client.request = Mock(return_value={'prompt_id': 'priced-pid'})
            record = client.submit_graph(root, 'characters', 'test', graph)
            client.request.assert_called_once()
            self.assertIn('cost_request_id', json.loads(record.read_text(encoding='utf-8')))

    def test_mixed_cloud_graph_cannot_hide_another_paid_node(self):
        from comfy_service import Comfy
        from unittest.mock import Mock
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); self.policy(root, cap='100')
            graph = json.loads(json.dumps(self.GRAPH))
            graph['31'] = {'class_type': 'CustomPaidNode', 'inputs': {}}
            client = Comfy('http://127.0.0.1:8189')
            client.request = Mock(return_value={'prompt_id': 'unexpected'})
            with self.assertRaisesRegex(ValueError, '无法预估'):
                client.submit_graph(root, 'characters', 'test', graph)
            client.request.assert_not_called()
            self.assertFalse((root / 'workflows').exists())

    def test_unpriced_workflow_without_cap_keeps_local_submission(self):
        from comfy_service import Comfy
        from unittest.mock import Mock
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / 'cost_profile.json').write_text('{"budget_amount": null}', encoding='utf-8')
            client = Comfy('http://127.0.0.1:8189')
            client.request = Mock(return_value={'prompt_id': 'local-pid'})
            record = client.submit_graph(root, 'characters', 'test',
                                         {'1': {'class_type': 'KSampler', 'inputs': {}}})
            client.request.assert_called_once()
            self.assertEqual(json.loads(record.read_text(encoding='utf-8'))['prompt_id'], 'local-pid')

    def test_unpriced_workflow_cannot_bypass_enabled_budget(self):
        from comfy_service import Comfy
        from unittest.mock import Mock
        for cap in ['0', '100']:
            with self.subTest(cap=cap), tempfile.TemporaryDirectory() as td:
                root = Path(td); self.policy(root, cap)
                client = Comfy('http://127.0.0.1:8189')
                client.request = Mock(return_value={'prompt_id': 'unexpected'})
                graph = {'1': {'class_type': 'CustomPaidNode', 'inputs': {}}}
                with self.assertRaisesRegex(ValueError, '无法预估'):
                    client.submit_graph(root, 'characters', 'test', graph)
                client.request.assert_not_called()
                self.assertFalse((root / 'workflows').exists())

    GRAPH = {'30': {'class_type': 'DramaCloudImage', 'inputs': {
        'model': 'Seedream 5.0 Pro', 'quality': 'medium', 'aspect_ratio': '1:1', 'prompt': 'test'}}}

    def policy(self, root, cap='0.5', rate='0.5'):
        from comfy_service import cloud_price_model
        (root / 'cost_profile.json').write_text(json.dumps({'budget_amount': cap, 'price_table': {
            'currency': 'CNY', 'version': 'fixture-v1',
            'model_rates': {cloud_price_model(self.GRAPH): {'images': rate}}}}), encoding='utf-8')

    def test_over_budget_or_missing_rate_sends_nothing(self):
        from comfy_service import Comfy
        from unittest.mock import Mock
        for cap in ['0.4', '0.5']:
            with self.subTest(cap=cap), tempfile.TemporaryDirectory() as td:
                root = Path(td); self.policy(root, cap)
                graph = json.loads(json.dumps(self.GRAPH))
                if cap == '0.5':graph['30']['inputs']['quality'] = 'high'
                client = Comfy('http://127.0.0.1:8189'); client.request = Mock()
                with self.assertRaises(ValueError):client.submit_graph(root, 'characters', 'test', graph)
                client.request.assert_not_called()
                self.assertFalse((root / 'workflows').exists())

    def test_restart_collection_settles_before_download_and_never_double_charges(self):
        from comfy_service import Comfy
        from pet_llm import RequestLedger
        from unittest.mock import Mock
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); self.policy(root)
            client = Comfy('http://127.0.0.1:8189'); client.request = Mock(return_value={'prompt_id': 'pid'})
            record = client.submit_graph(root, 'characters', 'test', self.GRAPH)
            rid = json.loads(record.read_text(encoding='utf-8'))['cost_request_id']
            self.assertEqual(RequestLedger(root).load()._find(rid)['money_state'], 'reserved')
            self.policy(root, rate='9')
            restarted = Comfy(client.url)
            history = {'pid': {'outputs': {'14': {'images': [{'type': 'output', 'filename': 'x.png'}]}}}}
            restarted.request = Mock(side_effect=[history, OSError('download')])
            with self.assertRaises(OSError):restarted.collect(root, record)
            row = RequestLedger(root).load()._find(rid)
            self.assertEqual((row['money_state'], row['budget_cost']), ('estimated', '0.5'))
            restarted.request = Mock(side_effect=[history, b'\x89PNG\r\n\x1a\nfixture'])
            self.assertEqual(len(restarted.collect(root, record)), 1)
            self.assertEqual(len(RequestLedger(root).load().entries), 1)
            with self.assertRaises(ValueError):client.submit_graph(root, 'characters', 'test', self.GRAPH)
            self.assertEqual(client.request.call_count, 1)

    def test_cloud_batch_over_budget_stops_before_connecting(self):
        import queue, threading
        from unittest.mock import Mock
        from orchestrator.asset_batch_execution import run_batch
        from pet_llm import RequestLedger
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); self.policy(root)
            asset = {'name': '角色', 'image_prompt': '一只猫坐在窗边', 'negative_prompt': '', 'reference_images': []}
            options = {'url': 'http://127.0.0.1:8189', 'backend': 'Seedream 5.0 Pro', 'model': '',
                       'workflow': '', 'node': '6', 'field': 'text', 'aspect_ratio': '1:1', 'quality': 'medium'}
            factory = Mock()
            with self.assertRaisesRegex(ValueError, '超过项目金额预算'):
                run_batch(root, root / 'episode', [('CHAR_001', asset), ('CHAR_002', dict(asset))],
                          options, queue.Queue(), threading.Event(), client_factory=factory)
            factory.assert_not_called()
            self.assertEqual(RequestLedger(root).load().entries, [])

    def test_timeout_keeps_cost_unknown_across_restart(self):
        from comfy_service import Comfy, ComfySubmissionUncertain
        from pet_llm import RequestLedger
        from unittest.mock import Mock
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); self.policy(root)
            client = Comfy('http://127.0.0.1:8189')
            client.request = Mock(side_effect=TimeoutError('timeout')); client.locate_prompt = Mock(return_value=None)
            with self.assertRaises(ComfySubmissionUncertain):client.submit_graph(root, 'characters', 'test', self.GRAPH)
            row = RequestLedger(root).load().entries[0]
            self.assertEqual((row['money_state'], row['budget_cost']), ('unknown', '0.5'))
            with self.assertRaises(ValueError):client.submit_graph(root, 'characters', 'test', self.GRAPH)
            self.assertEqual(client.request.call_count, 1)


class AssetUncertainSubmissionTests(unittest.TestCase):
    """批量提交结果无法确认时只跳过、不自动重提；可接续的旧任务继续取回。"""

    ASSET = {"name": "角色", "image_prompt": "一只猫坐在窗边", "negative_prompt": "", "reference_images": []}

    def options(self):
        return {"url": "http://127.0.0.1:8189", "backend": "local", "model": "flux.safetensors",
                "workflow": "", "node": "6", "field": "text", "aspect_ratio": "1:1", "quality": "标准"}

    def generation(self, options):
        return {key: options.get(key, "") for key in ("backend", "aspect_ratio", "quality", "workflow", "model", "node", "field")}

    def write_record(self, td, state="queued", prompt_id="PID-OLD"):
        folder = Path(td) / "workflows"; folder.mkdir(parents=True, exist_ok=True)
        record = folder / "comfy_old.json"
        record.write_text(json.dumps({"state": state, "prompt_id": prompt_id, "kind": "characters", "prompt": "旧任务"}), encoding="utf-8")
        return record

    def write_ledger(self, td, entries):
        folder = Path(td) / "workflows"; folder.mkdir(parents=True, exist_ok=True)
        (folder / "资产批量记录.json").write_text(json.dumps(entries, ensure_ascii=False), encoding="utf-8")

    def read_ledger(self, td):
        return json.loads((Path(td) / "workflows" / "资产批量记录.json").read_text(encoding="utf-8"))

    def test_uncertain_assets_lists_only_unverifiable(self):
        from asset_batch import uncertain_assets
        with tempfile.TemporaryDirectory() as td:
            record = self.write_record(td)
            self.write_ledger(td, {
                "CHAR_001": {"state": "submitting"},
                "CHAR_002": {"state": "submitting", "record": str(record)},
                "CHAR_003": {"state": "queued", "record": str(record)},
            })
            self.assertEqual(uncertain_assets(td), ["CHAR_001"])

    def test_record_without_task_id_is_still_uncertain(self):
        from asset_batch import uncertain_assets
        with tempfile.TemporaryDirectory() as td:
            record = self.write_record(td, state="unknown", prompt_id="")
            self.write_ledger(td, {"CHAR_001": {"state": "submitting", "record": str(record)}})
            self.assertEqual(uncertain_assets(td), ["CHAR_001"])

    def test_old_failed_unknown_record_is_recovered_and_explicit_release_remains_valid(self):
        from asset_batch import uncertain_assets, release_uncertain
        from asset_batch_state_service import read_ledger
        with tempfile.TemporaryDirectory() as td:
            record = self.write_record(td, state='unknown', prompt_id='')
            self.write_ledger(td, {'CHAR_001': {'state': 'failed', 'record': str(record)}})
            self.assertEqual(uncertain_assets(td), ['CHAR_001'])
            self.assertEqual(read_ledger(td)['CHAR_001']['state'], 'submitting')
            self.assertEqual(release_uncertain(td, ['CHAR_001']), ['CHAR_001'])
            self.assertEqual(read_ledger(td)['CHAR_001']['state'], 'failed')

    def test_release_uncertain_allows_regeneration(self):
        from asset_batch import uncertain_assets, release_uncertain
        with tempfile.TemporaryDirectory() as td:
            self.write_ledger(td, {"CHAR_001": {"state": "submitting"}, "CHAR_002": {"state": "queued"}})
            self.assertEqual(release_uncertain(td, ["CHAR_001", "CHAR_002"]), ["CHAR_001"])
            ledger = self.read_ledger(td)
            self.assertEqual(ledger["CHAR_001"]["state"], "failed")
            self.assertIn("核实", ledger["CHAR_001"]["note"])
            self.assertEqual(ledger["CHAR_002"]["state"], "queued")
            self.assertEqual(uncertain_assets(td), [])

    def test_ledger_service_rejects_non_object_state(self):
        from asset_batch_state_service import save_ledger
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaisesRegex(ValueError, "必须为对象"):
                save_ledger(td, [])

    def test_ledger_service_requires_l3_publisher(self):
        from asset_batch_state_service import save_ledger
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaisesRegex(RuntimeError, "必须由 L3 注入"):
                save_ledger(td, {})

    def fake(self, calls):
        class Fake:
            def request(self, path, data=None, raw=False, timeout=20):
                if path == "/system_stats":
                    return {}
                raise AssertionError(path)
            def submit(self, project, kind, prompt, model, workflow, node, field):
                calls["submit"].append(prompt)
                return str(Path(project) / "workflows" / "comfy_new.json")
            def collect(self, project, record):
                calls["collect"].append(str(record))
                raise OSError("连接中断")
        return Fake()

    def test_batch_resumes_verified_task_without_resubmitting(self):
        import queue as queue_module, threading
        from asset_batch import asset_prompt, run_batch
        from asset_reference_images import snapshot
        options = self.options(); calls = {"submit": [], "collect": []}
        with tempfile.TemporaryDirectory() as td:
            base = Path(td) / "episode"; record = self.write_record(td)
            snap = snapshot(base, self.ASSET)
            self.write_ledger(td, {"CHAR_001": {"state": "submitting", "prompt": asset_prompt(snap, "characters"),
                                               "url": options["url"], "references": snap["_reference_signature"],
                                               "generation": self.generation(options), "record": str(record)}})
            events = queue_module.Queue()
            run_batch(td, base, [("CHAR_001", dict(self.ASSET)), ("CHAR_002", dict(self.ASSET))], options, events,
                      threading.Event(), client_factory=lambda url: self.fake(calls))
            ledger = self.read_ledger(td)
            # 旧任务有任务编号：接续取回，不重新提交。
            self.assertEqual(calls["collect"][0], str(record))
            self.assertEqual(ledger["CHAR_001"]["state"], "queued")
            self.assertIn("接续取回", ledger["CHAR_001"]["note"])
            # 第二个资产照常提交，说明批次没有被拦住。
            self.assertEqual(len(calls["submit"]), 1)
            self.assertEqual(ledger["CHAR_002"]["state"], "queued")

    def test_batch_skips_unverifiable_and_continues(self):
        import queue as queue_module, threading
        from asset_batch import run_batch
        options = self.options(); calls = {"submit": [], "collect": []}
        with tempfile.TemporaryDirectory() as td:
            base = Path(td) / "episode"
            self.write_ledger(td, {"CHAR_001": {"state": "submitting"}})
            events = queue_module.Queue()
            run_batch(td, base, [("CHAR_001", dict(self.ASSET)), ("CHAR_002", dict(self.ASSET))], options, events,
                      threading.Event(), client_factory=lambda url: self.fake(calls))
            ledger = self.read_ledger(td)
            # 未核实的记录保持 submitting，不被静默改判为 failed 后重复生成。
            self.assertEqual(ledger["CHAR_001"]["state"], "submitting")
            self.assertIn("无法确认", ledger["CHAR_001"]["error"])
            self.assertEqual(len(calls["submit"]), 1)
            self.assertEqual(ledger["CHAR_002"]["state"], "queued")


class ComfyCollectFailureTests(unittest.TestCase):
    """任务已执行完但产出不可用时标记记录失败，避免反复取回同一个错、永远没有进展。"""

    def write_record(self, td, prompt_id):
        folder = Path(td) / "workflows"; folder.mkdir(parents=True, exist_ok=True)
        record = folder / "comfy_task.json"
        record.write_text(json.dumps({"state": "queued", "kind": "characters", "prompt_id": prompt_id}), encoding="utf-8")
        return record

    def test_no_images_marks_record_failed(self):
        from comfy_service import Comfy, ComfyGenerationFailed
        with tempfile.TemporaryDirectory() as td:
            record = self.write_record(td, "PID-1")
            client = Comfy("http://127.0.0.1:8189")
            client.request = lambda path, data=None, raw=False, timeout=20: {"PID-1": {"status": {"status_str": "success"}, "outputs": {"9": {"images": []}}}}
            with self.assertRaises(ComfyGenerationFailed):
                client.collect(td, record)
            self.assertEqual(json.loads(record.read_text(encoding="utf-8"))["state"], "failed")

    def test_running_job_is_not_marked_failed(self):
        from comfy_service import Comfy
        with tempfile.TemporaryDirectory() as td:
            record = self.write_record(td, "PID-2")
            client = Comfy("http://127.0.0.1:8189")
            client.request = lambda path, data=None, raw=False, timeout=20: {}
            self.assertEqual(client.collect(td, record), "排队或生成中，稍后再获取")
            self.assertEqual(json.loads(record.read_text(encoding="utf-8"))["state"], "queued")


class AutoAssetTests(unittest.TestCase):
    """无人值守批量资产：只跑本地 ComfyUI，缺图且清单已补齐的才排队，其余只跳过并写明原因。"""

    SETTINGS = {"url": "http://127.0.0.1:8189", "backend": "local", "model": "flux.safetensors",
                "workflow": "", "node": "6", "field": "text", "aspect_ratio": "1:1", "quality": "标准",
                "CHAR": True, "LOC": True, "PROP": False}

    def test_unattended_signature_tracks_ids_and_saved_settings(self):
        from asset_batch_service import unattended_signature
        signature = unattended_signature([('CHAR_001', {}), ('LOC_001', {})], {'model': 'flux', 'quality': '标准'})
        self.assertEqual(signature, (('CHAR_001', 'LOC_001'), (('model', 'flux'), ('quality', '标准'))))

    def test_unattended_signature_changes_when_saved_settings_change(self):
        from asset_batch_service import unattended_signature
        missing = [('CHAR_001', {})]
        self.assertNotEqual(unattended_signature(missing, {'model': 'flux'}),
                            unattended_signature(missing, {'model': 'seedream'}))

    def test_unattended_retry_decision_separates_skip_stop_and_dispatch(self):
        from asset_batch_service import unattended_retry_decision
        self.assertEqual(unattended_retry_decision(('batch',), ('batch',), 0, 3)['action'], 'skip')
        self.assertEqual(unattended_retry_decision(('batch',), None, 3, 3)['action'], 'stop')
        self.assertEqual(unattended_retry_decision(('batch',), None, 2, 3)['action'], 'dispatch')

    def test_eligible_items_excludes_not_required_and_ready_assets(self):
        from orchestrator.asset_batch_execution import eligible_items
        items = [("CHAR_001", {"name": "角色"}), ("PROP_001", {"name": "道具"})]
        self.assertEqual(eligible_items("base", items,
                         lambda aid, asset: aid.startswith("CHAR"),
                         lambda base, aid: aid == "CHAR_001"), [])

    def test_validation_errors_keeps_asset_id_and_all_reasons(self):
        from orchestrator.asset_batch_execution import validation_errors
        self.assertEqual(validation_errors([("CHAR_001", {}), ("LOC_001", {})],
                                           lambda aid, asset: ["名称", "提示词"] if aid == "CHAR_001" else []),
                         ["CHAR_001：名称、提示词"])

    def test_generation_settings_keeps_only_resume_identity_fields(self):
        from orchestrator.asset_batch_execution import generation_settings
        self.assertEqual(generation_settings({"backend": "local", "model": "flux", "ignored": "x"}),
                         {"backend": "local", "aspect_ratio": "", "quality": "", "workflow": "", "model": "flux", "node": "", "field": ""})

    def test_wait_for_comfy_stops_after_failed_probe(self):
        from orchestrator.asset_batch_execution import wait_for_comfy
        class OfflineClient:
            def request(self, path):
                raise OSError("offline")
        class Stopped:
            def wait(self, seconds):
                return True
        self.assertFalse(wait_for_comfy(OfflineClient(), Stopped()))

    def test_wait_for_comfy_reports_timeout(self):
        from orchestrator.asset_batch_execution import wait_for_comfy
        class OfflineClient:
            def request(self, path):
                raise OSError("offline")
        class Waiting:
            def wait(self, seconds):
                return False
        clock = iter((0, 91)).__next__
        with self.assertRaisesRegex(ValueError, "ComfyUI未就绪"):
            wait_for_comfy(OfflineClient(), Waiting(), clock=clock)

    def test_collect_result_returns_completed_files_without_waiting(self):
        from orchestrator.asset_batch_execution import collect_result
        class CompletedClient:
            def collect(self, project, record):
                return ["image.png"]
        self.assertEqual(collect_result(CompletedClient(), "project", "record"), ["image.png"])

    def test_collect_result_reports_timeout_and_keeps_record_for_resume(self):
        from orchestrator.asset_batch_execution import collect_result
        class WaitingClient:
            def collect(self, project, record):
                return "排队中"
        clock = iter((0, 3601)).__next__
        with self.assertRaisesRegex(ValueError, "保留任务编号"):
            collect_result(WaitingClient(), "project", "record", clock=clock)

    def test_resume_record_returns_verified_matching_job(self):
        from orchestrator.asset_batch_execution import resume_record
        job = {"state": "queued", "record": "record.json", "prompt": "提示词", "url": "url",
               "references": ["ref"], "generation": {"model": "flux"}}
        record = resume_record("CHAR_001", job, "提示词", "url", ["ref"], {"model": "flux"}, False,
                               resumable=lambda value: value == "record.json")
        self.assertEqual(record, Path("record.json"))

    def test_resume_record_rejects_changed_resume_identity(self):
        from orchestrator.asset_batch_execution import resume_record
        job = {"state": "queued", "record": "record.json", "prompt": "旧提示词", "url": "url",
               "references": [], "generation": {"model": "flux"}}
        with self.assertRaisesRegex(ValueError, "不同提示词"):
            resume_record("CHAR_001", job, "新提示词", "url", [], {"model": "flux"}, False,
                          resumable=lambda value: True)
        job["prompt"] = "新提示词"
        with self.assertRaisesRegex(ValueError, "其他模型或工作流"):
            resume_record("CHAR_001", job, "新提示词", "url", [], {"model": "sdxl"}, False,
                          resumable=lambda value: True)

    def test_resume_record_never_retries_unconfirmed_submission(self):
        from orchestrator.asset_batch_execution import AssetSubmissionUncertain, resume_record
        with self.assertRaisesRegex(AssetSubmissionUncertain, "CHAR_001.*未重复提交"):
            resume_record("CHAR_001", {"state": "submitting"}, "提示词", "url", [], {}, False)

    def make_project(self, td, settings=None, plan=None):
        proj = Path(td) / "p"
        (proj / "episode" / "frames").mkdir(parents=True)
        (proj / "episode" / "assets" / "资产清单").mkdir(parents=True)
        shots = [{"id": "SH001", "title": "镜头", "duration": 5, "characters": ["CHAR_001"],
                  "location": "LOC_001", "frame": "frames/SH001.png", "video_prompt": "画面",
                  "frame_prompt": "窗边的猫", "dialogue": []}]
        (proj / "episode" / "episode.json").write_text(json.dumps(
            {"episode_id": "EP001", "title": "T", "shots": shots}, ensure_ascii=False), encoding="utf-8")
        (proj / "episode" / "assets.json").write_text("{}", encoding="utf-8")
        (proj / "config.json").write_text(json.dumps({
            "episode_dir": str(proj / "episode"), "episode_file": str(proj / "episode" / "episode.json"),
            "asset_library_dir": str(proj / "episode")}), encoding="utf-8")
        (proj / "storyboard" / "分镜拆分").mkdir(parents=True)
        (proj / "storyboard" / "分镜拆分" / "episode.json").write_text(json.dumps(
            {"episode_id": "EP001", "title": "T", "shots": shots}, ensure_ascii=False), encoding="utf-8")
        full = {"name": "主角", "description": "", "image_prompt": "一只猫坐在窗边", "negative_prompt": ""}
        entries = dict(plan or {"CHAR_001": full})
        (proj / "episode" / "assets" / "资产清单" / "assets.json").write_text(
            json.dumps(entries, ensure_ascii=False), encoding="utf-8")
        prefs = {"adopted_storyboards": ["storyboard/分镜拆分/episode.json"],
                 "frame_json": "storyboard/分镜拆分/episode.json"}
        if settings is not None: prefs["asset_batch"] = settings
        (proj / "ui_settings.json").write_text(json.dumps(prefs, ensure_ascii=False), encoding="utf-8")
        return proj

    def plan(self, proj):
        from asset_batch import auto_plan
        return auto_plan(proj, proj / "episode", [proj / "storyboard" / "分镜拆分" / "episode.json"], "adopted")

    def test_auto_plan_lists_generatable_and_reports_incomplete(self):
        with tempfile.TemporaryDirectory() as td:
            proj = self.make_project(td, settings=dict(self.SETTINGS))
            items, skipped, saved = self.plan(proj)
            self.assertEqual([aid for aid, _ in items], ["CHAR_001"])
            # 场景没有名称和提示词：只跳过并写明原因，不中断整批
            self.assertEqual([aid for aid, _ in skipped], ["LOC_001"])
            self.assertIn("缺少资产名称", skipped[0][1])
            self.assertEqual(saved["model"], "flux.safetensors")

    def test_automatic_plan_service_runs_without_tk(self):
        from project_context_factory import project_context
        with tempfile.TemporaryDirectory() as td:
            proj = self.make_project(td, settings=dict(self.SETTINGS))
            items, skipped = automatic_plan(
                proj, proj / "episode",
                [proj / "storyboard" / "分镜拆分" / "episode.json"],
                dict(self.SETTINGS),
                gateway=asset_plan_gateway(),
                context=project_context(proj),
            )
            self.assertEqual([aid for aid, _ in items], ["CHAR_001"])
            self.assertEqual([aid for aid, _ in skipped], ["LOC_001"])

    def test_service_reads_unattended_settings_without_asset_window(self):
        with tempfile.TemporaryDirectory() as td:
            proj = self.make_project(td, settings=dict(self.SETTINGS))
            self.assertEqual(auto_settings(proj)["model"], "flux.safetensors")

    def test_auto_plan_skips_imported_and_unchecked_kinds(self):
        with tempfile.TemporaryDirectory() as td:
            proj = self.make_project(td, settings={**self.SETTINGS, "LOC": False})
            (proj / "episode" / "assets" / "characters").mkdir(parents=True)
            (proj / "episode" / "assets" / "characters" / "CHAR_001_主角.png").write_bytes(PNG_1PX)
            (proj / "episode" / "assets.json").write_text(json.dumps(
                {"CHAR_001": {"name": "主角", "image": "assets/characters/CHAR_001_主角.png"}}, ensure_ascii=False),
                encoding="utf-8")
            items, skipped, _ = self.plan(proj)
            self.assertEqual(items, [])           # 已有图片 → 不再重复生成
            self.assertEqual(skipped, [])         # 未勾选的类别连原因都不列
            settings = {**self.SETTINGS, "CHAR": False}
            (proj / "ui_settings.json").write_text(json.dumps(
                {"adopted_storyboards": ["storyboard/分镜拆分/episode.json"],
                 "frame_json": "storyboard/分镜拆分/episode.json", "asset_batch": settings}, ensure_ascii=False),
                encoding="utf-8")
            self.assertEqual(self.plan(proj)[0], [])   # 角色类别取消勾选 → 本轮不生成

    def test_auto_plan_requires_saved_settings_and_follows_current_model(self):
        """无人值守用的模型就是「资产图片制作」当前保存的那一个：本地照常排队，云端也不再被拦住。"""
        from cloud_assets import LOCAL, MODELS
        from asset_batch import current_model
        with tempfile.TemporaryDirectory() as td:
            proj = self.make_project(td)
            self.assertEqual(current_model(proj), LOCAL)      # 没保存过设置：显示本地默认模型
            with self.assertRaises(ValueError) as ctx:
                self.plan(proj)
            self.assertIn("批量资产", str(ctx.exception))
            (proj / "ui_settings.json").write_text(json.dumps(
                {"adopted_storyboards": ["storyboard/分镜拆分/episode.json"],
                 "frame_json": "storyboard/分镜拆分/episode.json",
                 "asset_batch": {**self.SETTINGS, "backend": MODELS[0]}}, ensure_ascii=False), encoding="utf-8")
            items, _skipped, saved = self.plan(proj)
            self.assertEqual([aid for aid, _ in items], ["CHAR_001"])
            self.assertEqual(saved["backend"], MODELS[0])
            self.assertEqual(current_model(proj), MODELS[0])

    def test_auto_batch_starts_comfy_and_imports_image(self):
        from unittest.mock import patch
        import native_apps
        from orchestrator.asset_auto_batch_service import auto_batch
        from asset_batch import image_ready
        with tempfile.TemporaryDirectory() as td:
            proj = self.make_project(td, settings=dict(self.SETTINGS))
            image = Path(td) / "generated.png"; image.write_bytes(PNG_1PX)
            waits = []; launched = []; logs = []
            def wait(url, report=None, timeout=90, cancelled=None):
                waits.append((url, timeout))
                if len(waits) == 1: raise ValueError("本地 ComfyUI 未运行")
                return True
            class Fake:
                def request(self, path, data=None, raw=False, timeout=20):
                    if path == "/system_stats": return {}
                    raise AssertionError(path)
                def submit(self, project, kind, prompt, model, workflow, node, field):
                    self.prompt = prompt
                    return str(Path(project) / "workflows" / "comfy_task.json")
                def collect(self, project, record):
                    return [str(image)]
            fake = Fake()
            with patch.object(native_apps, "wait_comfy", wait), \
                 patch('stage_execution_service.require_formal_asset_generation'), \
                 patch.object(native_apps, "open_comfy", lambda settings=None: launched.append(settings)):
                summary = auto_batch(proj, proj / "episode",
                                     [proj / "storyboard" / "分镜拆分" / "episode.json"], "adopted",
                                     logs.append, client_factory=lambda url: fake,
                                     gateway=asset_plan_gateway())
            self.assertEqual(waits, [("http://127.0.0.1:8189", 5), ("http://127.0.0.1:8189", 120)])
            self.assertEqual(launched, [None])            # 探测失败后自动拉起 ComfyUI
            self.assertIn("一只猫坐在窗边", fake.prompt)
            self.assertIn("成功 1", summary)
            self.assertIn("跳过 1 项", summary)
            self.assertIn("LOC_001", summary)
            self.assertTrue(image_ready(proj / "episode", "CHAR_001"))
            self.assertTrue(any("正在启动" in text for text in logs))
            # 图片已就绪后清单为空：不会再排队，直接说明无事可做
            self.assertIn("没有需要独立生成的资产", auto_batch(
                proj, proj / "episode", [proj / "storyboard" / "分镜拆分" / "episode.json"], "adopted",
                logs.append, client_factory=lambda url: fake,
                gateway=asset_plan_gateway()))


if __name__ == "__main__":
    unittest.main(verbosity=2)

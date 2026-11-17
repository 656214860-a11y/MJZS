# -*- coding: utf-8 -*-
"""连贯性清单（第 61 期 v0.8 任务 7）的自检。运行：python test_continuity_ledger.py

盯住四件事：① 附件给的 Agent Prompt 逐字在册；② 冲突识别（职责自相矛盾／多图抢同一件事）与裁决；
③ 每批冻结锚点、跨批次约束、三元组校验、锚点漂移（门禁 G-09）四份结论都对；④ 台账、人读版、
锚点库、三元组字典落到 03_continuity 与 _shared 的约定位置。
"""
import json, os, sys, tempfile, unittest
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.chdir(HERE)

import continuity_ledger as cl
from contract import shot_batches
import stage_layout

ASSETS = {
    "CHAR_001": {"name": "林小满", "character_anchor": "黑短发、杏眼、米色针织衫"},
    "CHAR_002": {"name": "陈默", "character_anchor": "寸头、方脸、灰夹克"},
    "LOC_001": {"name": "咖啡馆", "lighting_direction": "右侧落地窗自然光 5600K",
                "spatial_anchors": [{"object": "壁灯", "position": "左侧墙面 1.5 米处",
                                     "material": "暖黄金属"}],
                "scale_reference": "吧台高约 1.1 米"},
    "PROP_001": {"name": "怀表", "material": "黄铜＋白珐琅表盘", "scale": "直径约 4.5 厘米"},
}


def shot(index, chars=("CHAR_001",), location="LOC_001", seconds=3, roles=None, flags=None,
         props=None, costume=""):
    item = {"id": "SH%03d" % index, "title": "镜头", "duration": seconds,
            "characters": list(chars), "location": location, "video_prompt": "画面",
            "dialogue": []}
    if roles is not None:
        item["reference_roles"] = roles
    if flags:
        item["continuity_flags"] = flags
    if props:
        item["props"] = list(props)
    if costume:
        item["costume_id"] = costume
    return item


class PromptTests(unittest.TestCase):
    def test_the_agent_prompt_is_copied_verbatim(self):
        for text in ("你是一个连贯性检查Agent。输入是初步分镜JSON。",
                     "1.检查character_refs中的参考图职责是否与character_anchor冲突。",
                     "2.检查同一批次内所有镜头的scene_id+character_ids+costume_id是否一致。",
                     "3.识别需要跨批次保持的锚点（如角色服装、场景光源方向）。",
                     "输出：continuity_ledger JSON，包含每个批次的冻结锚点列表和冲突裁决记录。"):
            self.assertIn(text, cl.PROMPT)
        self.assertIn("2 个候选方案", cl.PRESCREEN_PROMPT)


class AnchorTests(unittest.TestCase):
    def test_anchors_of_reads_characters_scenes_and_props(self):
        entries = cl.anchors_of(shot(1, chars=("CHAR_001",), props=("PROP_001",)), ASSETS)
        kinds = {entry["kind"]: entry for entry in entries}
        self.assertEqual(set(kinds), {"character", "scene", "prop"})
        self.assertIn("黑短发", kinds["character"]["anchor"])
        self.assertIn("右侧落地窗自然光", kinds["scene"]["anchor"])
        self.assertIn("壁灯@左侧墙面 1.5 米处", kinds["scene"]["anchor"])
        self.assertIn("尺度：吧台高约 1.1 米", kinds["scene"]["anchor"])
        self.assertIn("黄铜", kinds["prop"]["anchor"])

    def test_unknown_assets_are_skipped(self):
        self.assertEqual(cl.anchors_of(shot(1, chars=("CHAR_999",), location="LOC_999"), ASSETS), ())

    def test_the_state_override_is_folded_into_the_anchor(self):
        assets = {"CHAR_001": dict(ASSETS["CHAR_001"], state_variants=[
            {"state_id": "CST-01", "name": "日常装", "override": "米色针织衫"}]),
            "LOC_001": ASSETS["LOC_001"]}
        entries = cl.anchors_of(shot(1, costume="CST-01"), assets)
        self.assertIn("状态覆盖", entries[0]["anchor"])
        self.assertEqual(entries[0]["state"], "CST-01")


class ConflictTests(unittest.TestCase):
    def test_a_role_that_also_claims_the_scene_is_a_contradiction(self):
        found = cl.conflicts([shot(1, roles={"@图片1": {"responsibility": "面部、场景",
                                                        "exclude": "只排动作"}})], ASSETS)
        self.assertTrue(any(row["kind"] == "职责自相矛盾" for row in found))
        self.assertIn("场景", found[0]["detail"])

    def test_two_refs_claiming_the_same_identity_must_be_adjudicated(self):
        found = cl.conflicts([shot(1, chars=("CHAR_001", "CHAR_002"))], ASSETS)
        rows = [row for row in found if row["kind"] == "多图抢同一件事"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(list(rows[0]["refs"]), ["@图片1", "@图片2"])

    def test_one_character_has_no_conflict(self):
        self.assertEqual(cl.conflicts([shot(1)], ASSETS), ())

    def test_adjudication_puts_the_first_ref_in_charge(self):
        rows = cl.adjudicate(cl.conflicts([shot(1, chars=("CHAR_001", "CHAR_002"))], ASSETS))
        self.assertEqual(rows[0]["priority"], ["@图片1", "@图片2"])
        self.assertIn("负责身份", rows[0]["resolution"])
        self.assertIn("不继承场景、动作、镜头", rows[0]["resolution"])


class LedgerTests(unittest.TestCase):
    def test_triplets_and_cross_batch_report_per_batch(self):
        shots = [shot(1), shot(2), shot(3, chars=("CHAR_002",))]
        rows = cl.triplets(shots)
        self.assertEqual([row["batch_id"] for row in rows], ["B01", "B02"])
        self.assertTrue(all(row["ok"] for row in rows))
        self.assertTrue(B01_ok(cl.cross_batch(shots, ASSETS)), "CHAR_001 的锚点两处一致")

    def test_build_carries_the_four_sections(self):
        ledger = cl.build([shot(1), shot(2, chars=("CHAR_002",))], ASSETS)
        for key in ("prompt", "prescreen_prompt", "batches", "conflicts", "cross_batch",
                    "triplets", "drift", "summary"):
            self.assertIn(key, ledger, key)
        self.assertEqual(ledger["summary"]["shots"], 2)
        self.assertEqual(ledger["summary"]["batches"], 2)
        self.assertTrue(ledger["summary"]["ok"], ledger["summary"]["problems"])
        self.assertEqual(len(ledger["batches"][0]["frozen_anchors"]), 2, "角色锚点＋场景锚点")

    def test_drift_flags_an_asset_whose_anchor_changed(self):
        shots = [shot(1)]
        old = cl.build(shots, {"CHAR_001": {"character_anchor": "旧锚点"}})
        self.assertEqual(list(old["drift"]), [])
        rows = cl.drift(old, {"CHAR_001": {"character_anchor": "新锚点"}})
        self.assertEqual(len(rows), 1)
        self.assertFalse(rows[0]["ok"])
        self.assertIn("漂移", rows[0]["detail"])
        fresh = cl.build(shots, {"CHAR_001": {"character_anchor": "新锚点"}})
        self.assertEqual(list(fresh["drift"]), [], "同一份资产自己跟自己不漂移")

    def test_flags_are_carried_as_must_keep_constraints(self):
        rows = cl.cross_batch([shot(1, flags=["耳环不可变"])], ASSETS)
        self.assertTrue(any(row["kind"] == "flag" and "耳环不可变" in row["detail"] for row in rows))

    def test_ask_gives_two_candidates_per_batch(self):
        ledger = cl.build(shot_batches.assign([shot(1, chars=("CHAR_001", "CHAR_002"))]), ASSETS)
        items = cl.ask(ledger)
        self.assertEqual(len(items), 1)
        self.assertEqual(len(items[0]["candidates"]), 2)
        self.assertEqual(items[0]["recommended"], 0)
        self.assertTrue(items[0]["id"].startswith("G-08"))
        self.assertEqual(items[0]["key"], "conflict:B01")

    def test_gate_and_markdown(self):
        ledger = cl.build([shot(1)], ASSETS)
        ok, problems = cl.gate(ledger)
        self.assertTrue(ok)
        self.assertEqual(problems, ())
        text = cl.markdown(ledger)
        self.assertIn("# 连贯性清单", text)
        self.assertIn("## 参考图裁决", text)
        self.assertIn("## 跨批次连续性", text)
        self.assertIn("## 锚点漂移", text)
        self.assertIn("## 三元组校验", text)

    def test_a_bad_triplet_shows_up_in_problems(self):
        shots = [dict(cl.normalize(shot(1), 0), batch_id="B01"),
                 dict(cl.normalize(shot(2, chars=("CHAR_002",)), 1), batch_id="B01")]
        ledger = cl.build(shots, ASSETS)
        self.assertFalse(ledger["summary"]["ok"])
        self.assertTrue(any("三元组" in text for text in ledger["summary"]["problems"]))


class WriteTests(unittest.TestCase):
    def test_failed_bundle_publication_restores_every_existing_output(self):
        with tempfile.TemporaryDirectory() as td:
            stage_layout.ensure(td)
            ledger = cl.build([shot(1)], ASSETS)
            targets = (stage_layout.paths(td, '03_continuity')['output'] / cl.LEDGER_NAME,
                       stage_layout.paths(td, '03_continuity')['docs'] / cl.LEDGER_DOC,
                       stage_layout.anchors_path(td), stage_layout.triplets_path(td))
            originals = {path: ('old:' + path.name).encode('utf-8') for path in targets}
            for path, raw in originals.items():
                path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(raw)
            from unittest.mock import patch
            real_save, calls = cl.save, 0
            def fail_second_save(path, content):
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise OSError('disk full')
                real_save(path, content)
            with patch.object(cl, 'save', side_effect=fail_second_save):
                with self.assertRaisesRegex(OSError, 'disk full'):
                    cl.write(td, ledger)
            self.assertEqual({path: path.read_bytes() for path in targets}, originals)

    def test_write_lands_in_the_agreed_places(self):
        with tempfile.TemporaryDirectory() as td:
            stage_layout.ensure(td)
            ledger = cl.build([shot(1)], ASSETS)
            file = cl.write(td, ledger)
            self.assertEqual(file.name, "continuity_ledger.json")
            self.assertEqual(file.parent, stage_layout.paths(td, "03_continuity")["output"])
            self.assertTrue((stage_layout.paths(td, "03_continuity")["docs"]
                             / "continuity_ledger.md").is_file())
            self.assertTrue(stage_layout.anchors_path(td).is_file())
            library = json.loads(stage_layout.anchors_path(td).read_text(encoding="utf-8"))
            self.assertIn("CHAR_001", library)
            self.assertEqual(library["CHAR_001"]["anchor"], ASSETS["CHAR_001"]["character_anchor"])
            triplets = json.loads(stage_layout.triplets_path(td).read_text(encoding="utf-8"))
            self.assertEqual(triplets["B01"], ["LOC_001", ["CHAR_001"], ""])
            self.assertEqual(cl.read(td)["summary"]["shots"], 1)

    def test_read_without_a_ledger_is_an_empty_dict(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertEqual(cl.read(td), {})

    def test_write_is_idempotent(self):
        with tempfile.TemporaryDirectory() as td:
            stage_layout.ensure(td)
            ledger = cl.build([shot(1)], ASSETS)
            first = cl.write(td, ledger).read_bytes()
            cl.write(td, ledger)
            self.assertEqual(cl.write(td, ledger).read_bytes(), first)


def B01_ok(rows):
    return all(row["ok"] for row in rows if row["kind"] == "character")


if __name__ == "__main__":
    unittest.main(verbosity=2)

# -*- coding: utf-8 -*-
"""用户确认门禁（第 61 期 v0.8 任务 1）的自检。运行：python test_confirm_gates.py

盯住四件事：① 门禁清单表九条齐全、字段就是交付物 9 要的那五列；② 客观门禁接在已有模块的判据上，
通得过也拦得住；③ 主观门禁每条给 2 个候选＋推荐理由，且**同一角色／同一批次只问一次**
（人工点击量从每镜审核降到每角色一次）；④ 确认记录落在 03_continuity/output 并真的去重。
"""
import json, os, sys, tempfile, unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.chdir(HERE)

from domain import confirm_gates as cg
import infra.continuity_ledger as cl
from contract import shot_batches as sb
import stage_layout

GOOD_ASSETS = {
    "CHAR_001": {"name": "主角", "image_prompt": "黑短发、杏眼、米色针织衫",
                 "character_anchor": "黑短发、杏眼、米色针织衫", "locked": True,
                 "canonical_board": "assets/参考图/CHAR_001/turnaround.png"},
    "LOC_001": {"name": "咖啡馆", "image_prompt": "咖啡馆内景，右侧落地窗",
                "lighting_direction": "右侧落地窗自然光 5600K",
                "spatial_anchors": [{"object": "壁灯", "position": "左侧墙面 1.5 米处"}]},
}


def good_shots(count=2, chars=("CHAR_001",), batch="B01"):
    out = []
    for index in range(1, count + 1):
        item = sb.normalize({"id": "SH%03d" % index, "title": "镜头", "duration": 3,
                             "characters": list(chars), "location": "LOC_001"}, index - 1)
        item["costume_id"] = "CST-01"
        item["batch_id"] = batch
        out.append(item)
    return out


class TableTests(unittest.TestCase):
    def test_the_gate_table_is_the_delivery_table(self):
        rows = cg.table_rows()
        self.assertEqual(len(rows), 9)
        ids = [row[0] for row in rows]
        self.assertEqual(ids, ["G-0%d" % index for index in range(1, 10)])
        for gate_id, kind, judge, condition, reject in rows:
            self.assertIn(kind, (cg.OBJECTIVE, cg.SUBJECTIVE), gate_id)
            self.assertIn(judge, (cg.AUTO, cg.HUMAN), gate_id)
            self.assertTrue(condition and reject, gate_id)

    def test_every_gate_has_exactly_one_judgement(self):
        for row in cg.GATES:
            has_check = bool(row["check"])
            has_ask = bool(row["ask"])
            self.assertNotEqual(has_check, has_ask, row["id"])
            self.assertEqual(has_check, row["type"] == cg.OBJECTIVE, row["id"])
            self.assertEqual(has_ask, row["type"] == cg.SUBJECTIVE, row["id"])
            self.assertIn(row["id"], cg.GATE_STAGES, row["id"] + " 得挂在某个阶段上")

    def test_stage_gates_match_the_workflow(self):
        self.assertEqual(cg.stage_gates("00_script"), ())
        self.assertEqual(cg.stage_gates("02_assets"), ("G-01", "G-03", "G-04", "G-05", "G-06"))
        self.assertIn("G-07", cg.stage_gates("04_storyboard_final"))
        self.assertIn("G-08", cg.stage_gates("03_continuity"))
        self.assertEqual(cg.stage_gates("没有这个"), ())

    def test_objective_and_subjective_split(self):
        self.assertEqual(len(cg.objective_ids()), 6)
        self.assertEqual(len(cg.subjective_ids()), 3)
        self.assertIn("G-06", cg.subjective_ids())
        self.assertIn("G-09", cg.objective_ids())

    def test_unknown_gate_id(self):
        self.assertIsNone(cg.by_id("G-99"))
        with self.assertRaises(ValueError):
            cg.run("G-99")

    def test_detail_rows_add_the_name_and_stages(self):
        rows = cg.detail_rows()
        self.assertEqual(len(rows), 9)
        self.assertEqual(rows[0][1], "字段完整性")
        self.assertIn("05资产管理", rows[0][5])


class ObjectiveTests(unittest.TestCase):
    def test_a_clean_project_passes_every_gate(self):
        shots = good_shots()
        ledger = cl.build(shots, GOOD_ASSETS)
        self.assertTrue(cg.passed(shots=shots, assets=GOOD_ASSETS, ledger=ledger),
                        [row for row in cg.summary(shots=shots, assets=GOOD_ASSETS, ledger=ledger)
                         if not row[3]])

    def test_g01_catches_a_locked_character_without_an_anchor(self):
        result = cg.run("G-01", assets={"CHAR_001": {"name": "主角", "locked": True}}, shots=[])
        self.assertFalse(result["passed"])
        self.assertTrue(any("character_anchor" in text for text in result["problems"]))

    def test_g01_catches_a_bad_shot(self):
        result = cg.run("G-01", assets=GOOD_ASSETS, shots=[{"id": "SH001"}])
        self.assertFalse(result["passed"])
        self.assertTrue(result["problems"])

    def test_g02_reads_the_ledger(self):
        shots = [dict(good_shots(1)[0], batch_id="B01"),
                 dict(sb.normalize({"id": "SH002", "duration": 3, "characters": ["CHAR_001"],
                                    "location": "LOC_001"}, 1), batch_id="B01", costume_id="CST-01")]
        shots[1]["scene_id"] = "LOC_002"
        result = cg.run("G-02", shots=shots)
        self.assertFalse(result["passed"])
        self.assertTrue(any("三元组" in text for text in result["problems"]))

    def test_g03_catches_a_self_contradicting_role(self):
        shots = [dict(good_shots(1)[0], reference_roles={"@图片1": {"responsibility": "面部、场景",
                                                                   "exclude": "只排动作"}})]
        result = cg.run("G-03", shots=shots, assets=GOOD_ASSETS)
        self.assertFalse(result["passed"])
        self.assertIn("场景", result["problems"][0])

    def test_g04_catches_a_missing_asset(self):
        """REQ-S05-15：门禁 G-04 使用 missing_ids 拦下清单里缺名称／提示词的资产。"""
        shots = [sb.normalize({"id": "SH001", "duration": 3, "characters": ["CHAR_007"],
                               "location": "LOC_001"}, 0)]
        result = cg.run("G-04", shots=shots, assets=GOOD_ASSETS)
        self.assertFalse(result["passed"])
        self.assertTrue(any("CHAR_007" in text for text in result["problems"]))

    def test_g07_catches_over_long_batches(self):
        shots = good_shots(count=5)
        result = cg.run("G-07", shots=shots)
        self.assertFalse(result["passed"])
        self.assertTrue(any("超过每批 4 个" in text for text in result["problems"]))

    def test_g09_catches_anchor_drift(self):
        shots = good_shots(1)
        frozen = cl.build(shots, {"CHAR_001": {"character_anchor": "旧锚点"}})
        result = cg.run("G-09", ledger=frozen, assets={"CHAR_001": {"character_anchor": "新锚点"}})
        self.assertFalse(result["passed"])
        self.assertIn("漂移", result["problems"][0])
        result = cg.run("G-09", ledger=cl.build(shots, GOOD_ASSETS), assets=GOOD_ASSETS)
        self.assertTrue(result["passed"])


class SubjectiveTests(unittest.TestCase):
    def test_anchors_are_offered_once_per_character_not_per_shot(self):
        shots = good_shots(count=20, chars=("CHAR_001", "CHAR_002"))
        result = cg.run("G-05", assets={"CHAR_001": {"name": "主角"}, "CHAR_002": {"name": "配角"}},
                        shots=shots)
        self.assertEqual(len(result["ask"]), 2, "20 个镜头也只问 2 次（每角色一次）")
        item = result["ask"][0]
        self.assertEqual(item["gate_id"], "G-05")
        self.assertEqual(item["key"], "anchor:CHAR_001")
        self.assertEqual(len(item["candidates"]), 2)
        self.assertTrue(item["reason"])

    def test_a_declared_and_locked_character_is_not_asked_again(self):
        assets = {"CHAR_001": {"name": "主角", "character_anchor": "锚点", "locked": True,
                               "canonical_board": "a/t.png"}}
        self.assertEqual(cg.run("G-05", assets=assets)["ask"], ())
        self.assertEqual(cg.run("G-06", assets=assets)["ask"], ())

    def test_canon_board_offers_two_schemes(self):
        result = cg.run("G-06", assets={"CHAR_001": {"name": "主角"}})
        self.assertEqual(len(result["ask"]), 1)
        self.assertEqual(result["ask"][0]["key"], "canon:CHAR_001")
        self.assertIn("同背景色", result["ask"][0]["reason"])

    def test_conflict_candidates_are_keyed_per_batch(self):
        shots = sb.assign([{"id": "SH001", "title": "镜头", "duration": 3,
                            "characters": ["CHAR_001", "CHAR_002"], "location": "LOC_001"}])
        result = cg.run("G-08", shots=shots, assets=GOOD_ASSETS)
        self.assertEqual(len(result["ask"]), 1)
        self.assertEqual(result["ask"][0]["key"], "conflict:B01")
        self.assertEqual(len(result["ask"][0]["candidates"]), 2)

    def test_pending_and_record_are_the_memory(self):
        with tempfile.TemporaryDirectory() as td:
            stage_layout.ensure(td)
            items = cg.anchor_candidates(assets={"CHAR_001": {"name": "主角"}})
            self.assertEqual(len(cg.pending(td, items)), 1)
            self.assertEqual(cg.confirm_path(td).name, "gate_confirmations.json")
            from stage_execution_service import record_stage_confirmation, forget_stage_confirmation
            record_stage_confirmation(td, items[0]["key"], "候选一")
            self.assertEqual(cg.pending(td, items), ())
            self.assertTrue(cg.run("G-05", project=td,
                                   assets={"CHAR_001": {"name": "主角"}})["passed"])
            self.assertEqual(cg.confirmations(td)[items[0]["key"]]["choice"], "候选一")
            forget_stage_confirmation(td, items[0]["key"])
            self.assertEqual(len(cg.pending(td, items)), 1)

    def test_duplicate_keys_are_collapsed(self):
        items = ({"key": "anchor:CHAR_001"}, {"key": "anchor:CHAR_001"})
        self.assertEqual(len(cg.pending("", items)), 1)
        self.assertEqual(len(cg.pending("", ({"title": "没钥匙"},))), 1)


class AdoptTransactionTests(unittest.TestCase):
    """O10：准备→落盘→确认是一条可恢复事务，只有落盘成功才计人工确认完成。"""

    KEY = "anchor:CHAR_001"

    def _items(self, key=None):
        return ({"key": key or self.KEY},)

    def test_apply_failure_leaves_failed_never_confirmed(self):
        with tempfile.TemporaryDirectory() as td:
            stage_layout.ensure(td)
            import stage_execution_service as execution
            with mock.patch.object(execution, "apply_asset_plan_gate_choice",
                                   side_effect=OSError("磁盘已满")):
                with self.assertRaisesRegex(OSError, "磁盘已满"):
                    execution.adopt_asset_plan_choice(td, self.KEY, "候选一")
            self.assertEqual(cg.state_of(td, self.KEY), cg.FAILED)
            self.assertEqual(len(cg.pending(td, self._items())), 1, "失败后不许当成已确认")
            self.assertFalse(cg.run("G-05", project=td,
                                    assets={"CHAR_001": {"name": "主角"}})["passed"],
                             "未采用就不能算人工审核通过")

    def test_interrupted_before_apply_stays_pending(self):
        with tempfile.TemporaryDirectory() as td:
            stage_layout.ensure(td)
            import stage_execution_service as execution
            with mock.patch.object(execution, "apply_asset_plan_gate_choice",
                                   side_effect=KeyboardInterrupt()):
                with self.assertRaises(KeyboardInterrupt):
                    execution.adopt_asset_plan_choice(td, self.KEY, "候选一")
            self.assertEqual(cg.state_of(td, self.KEY), cg.PENDING, "中断只留下待办")
            self.assertEqual(len(cg.pending(td, self._items())), 1)

    def test_success_marks_applied_and_stops_asking(self):
        with tempfile.TemporaryDirectory() as td:
            stage_layout.ensure(td)
            import stage_execution_service as execution
            with mock.patch.object(execution, "apply_asset_plan_gate_choice",
                                   return_value={"character_anchor": "候选一"}):
                result = execution.adopt_asset_plan_choice(td, self.KEY, "候选一")
            self.assertEqual(result, {"character_anchor": "候选一"})
            self.assertEqual(cg.state_of(td, self.KEY), cg.APPLIED)
            self.assertEqual(cg.pending(td, self._items()), ())

    def test_double_click_is_idempotent_and_applied(self):
        with tempfile.TemporaryDirectory() as td:
            stage_layout.ensure(td)
            import stage_execution_service as execution
            with mock.patch.object(execution, "apply_asset_plan_gate_choice",
                                   return_value=None) as apply:
                execution.adopt_asset_plan_choice(td, "conflict:B01", "候选一")
                execution.adopt_asset_plan_choice(td, "conflict:B01", "候选一")
            self.assertEqual(apply.call_count, 2)
            self.assertEqual(cg.state_of(td, "conflict:B01"), cg.APPLIED)
            self.assertEqual(cg.pending(td, self._items("conflict:B01")), ())

    def test_a_record_without_state_is_treated_as_applied(self):
        with tempfile.TemporaryDirectory() as td:
            stage_layout.ensure(td)
            cg.confirm_path(td).write_text(
                json.dumps({"version": 1, "confirmed": {
                    self.KEY: {"choice": "旧记录", "by": "人工"}}}, ensure_ascii=False),
                encoding="utf-8")
            self.assertEqual(cg.state_of(td, self.KEY), cg.APPLIED)
            self.assertEqual(cg.pending(td, self._items()), ())

    def test_state_of_unknown_key_is_blank(self):
        with tempfile.TemporaryDirectory() as td:
            stage_layout.ensure(td)
            self.assertEqual(cg.state_of(td, "anchor:没有这个"), "")


class ConfirmationBindingTests(unittest.TestCase):
    """O11：确认要绑住被确认的内容，不只是名字；内容变了只失效受影响的那条。"""

    def _assets(self, brief="黑短发、杏眼"):
        return {"CHAR_001": {"name": "主角", "description": brief},
                "CHAR_002": {"name": "配角", "description": "白衬衣"}}

    @staticmethod
    def _by_key(items):
        return {item["key"]: item for item in items}

    def test_replacing_a_candidate_reopens_only_that_character(self):
        with tempfile.TemporaryDirectory() as td:
            stage_layout.ensure(td)
            from stage_execution_service import record_stage_confirmation
            first = self._by_key(cg.anchor_candidates(assets=self._assets()))
            for key, item in first.items():
                record_stage_confirmation(td, key, "候选一", digest=item["digest"])
            self.assertEqual(cg.pending(td, tuple(first.values())), ())
            changed = self._assets("栗色卷发、圆脸")
            second = self._by_key(cg.anchor_candidates(assets=changed))
            left = [item["key"] for item in cg.pending(td, tuple(second.values()))]
            self.assertEqual(left, ["anchor:CHAR_001"], "只重新问改过的那一个角色")
            self.assertFalse(cg.run("G-05", project=td, assets=changed)["passed"],
                             "候选换过，门禁要重新问")

    def test_changing_the_conflict_priority_reopens_that_batch(self):
        with tempfile.TemporaryDirectory() as td:
            stage_layout.ensure(td)
            from stage_execution_service import record_stage_confirmation
            row = {"kind": "多图抢同一件事", "batch_id": "B01",
                   "priority": ["@图片1", "@图片2"], "reason": "两张都抢面部"}
            item = cg.conflict_candidates(ledger={"conflicts": [row]})[0]
            record_stage_confirmation(td, item["key"], item["candidates"][0], digest=item["digest"])
            self.assertEqual(cg.pending(td, (item,)), ())
            moved = cg.conflict_candidates(ledger={"conflicts": [dict(row, priority=["@图片2", "@图片1"])]})[0]
            self.assertEqual([i["key"] for i in cg.pending(td, (moved,))], ["conflict:B01"],
                             "台账被外部改过优先级就要复核")

    def test_two_episodes_sharing_a_batch_id_do_not_reuse_each_other(self):
        with tempfile.TemporaryDirectory() as td:
            stage_layout.ensure(td)
            from stage_execution_service import record_stage_confirmation
            first = cg.conflict_candidates(ledger={"conflicts": [
                {"kind": "多图抢同一件事", "batch_id": "B01", "priority": ["@A", "@B"]}]})[0]
            record_stage_confirmation(td, first["key"], first["candidates"][0], digest=first["digest"])
            second = cg.conflict_candidates(ledger={"conflicts": [
                {"kind": "多图抢同一件事", "batch_id": "B01", "priority": ["@C", "@D"]}]})[0]
            self.assertEqual(first["key"], second["key"], "跨集同批次 ID 仍共用一个键")
            self.assertEqual(len(cg.pending(td, (second,))), 1, "内容不同就必须复核（宁多问不漏放）")

    def test_an_unrelated_field_change_leaves_others_alone(self):
        with tempfile.TemporaryDirectory() as td:
            stage_layout.ensure(td)
            from stage_execution_service import record_stage_confirmation
            first = self._by_key(cg.anchor_candidates(assets=self._assets()))
            for key, item in first.items():
                record_stage_confirmation(td, key, "候选一", digest=item["digest"])
            assets = self._assets()
            assets["CHAR_002"]["costume_id"] = "CST-99"
            second = self._by_key(cg.anchor_candidates(assets=assets))
            self.assertEqual(cg.pending(td, tuple(second.values())), (), "无关字段变化不扰动")

    def test_a_legacy_confirmation_without_digest_is_kept(self):
        with tempfile.TemporaryDirectory() as td:
            stage_layout.ensure(td)
            from stage_execution_service import record_stage_confirmation
            record_stage_confirmation(td, "anchor:CHAR_001", "候选一")
            left = [item["key"] for item in cg.pending(td, cg.anchor_candidates(assets=self._assets()))]
            self.assertEqual(left, ["anchor:CHAR_002"],
                             "旧记录没有摘要，按升级前口径仍然算已确认")



if __name__ == "__main__":
    unittest.main(verbosity=2)

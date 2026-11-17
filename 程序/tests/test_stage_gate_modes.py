# -*- coding: utf-8 -*-
"""O24 门禁语义自检：浏览放行与正式自动生产分开。运行：python test_stage_gate_modes.py"""
import os, sys, tempfile, unittest
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
os.chdir(HERE)

import infra.continuity_ledger as cl
import pet_agent
import pet_state
import stage_parallel as sp

ASSETS = {"CHAR_001": {"name": "林小满", "character_anchor": "黑短发、杏眼、米色针织衫"},
          "CHAR_002": {"name": "陈默", "character_anchor": "寸头、方脸、灰夹克"},
          "LOC_001": {"name": "咖啡馆", "lighting_direction": "右侧落地窗自然光 5600K"}}


def shot(index, chars=("CHAR_001",), location="LOC_001", seconds=3):
    return {"id": "SH%03d" % index, "title": "镜头", "duration": seconds,
            "characters": list(chars), "location": location, "video_prompt": "画面", "dialogue": []}


def bad_ledger():
    rows = [dict(cl.normalize(shot(1), 0), batch_id="B01"),
            dict(cl.normalize(shot(2, chars=("CHAR_002",)), 1), batch_id="B01")]
    return cl.build(rows, ASSETS)


class GateModeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()

    def skip_upstream(self, stage, reason="用户跳过这一步"):
        pet_state.Machine(self.root, persist=True).load().skip(stage, reason).save()

    def test_browse_keeps_the_old_lenient_semantics(self):
        """默认口径没变：上游没开始仍然通过（浏览／补录／旧项目能打开）。"""
        result = sp.evaluate(self.root, "final")
        self.assertTrue(result["ok"])
        self.assertFalse(result["started"])
        self.assertEqual(result["verdict"], sp.UPSTREAM_BLANK)
        self.assertEqual(result["mode"], sp.BROWSE)
        self.assertEqual(result["missing"], ())
        self.assertEqual(sp.blocked_text(result), "")

    def test_production_treats_a_blank_upstream_as_missing_prerequisites(self):
        """正式自动生产：上游没开始＝前置条件缺失，点明缺哪一步、怎么豁免。"""
        result = sp.production_ready(self.root, "final")
        self.assertFalse(result["ok"])
        self.assertEqual(result["verdict"], sp.UPSTREAM_BLANK)
        self.assertEqual(result["mode"], sp.PRODUCTION)
        self.assertEqual(result["missing"], ("continuity",))
        text = sp.blocked_text(result)
        self.assertIn("连贯性清单", text)
        self.assertIn("已跳过", text)

    def test_a_skipped_upstream_counts_as_a_user_exemption(self):
        """用户把上游标成「已跳过」＝主动豁免，正式生产也放行。"""
        self.assertFalse(sp.production_ready(self.root, "final")["ok"])
        self.skip_upstream("continuity")
        result = sp.production_ready(self.root, "final")
        self.assertTrue(result["ok"])
        self.assertTrue(result["exempt"])
        self.assertTrue(sp.upstream_exempt(self.root, "final"))

    def test_only_the_blank_upstream_case_changes_between_modes(self):
        blocked = {"id": "SG-01", "from": "assets", "to": "continuity", "title": "x",
                   "ok": False, "started": True, "verdict": sp.BLOCKED, "detail": "d",
                   "problems": (), "artifacts": ()}
        applied = sp._apply_mode(blocked, sp.PRODUCTION, self.root)
        self.assertFalse(applied["ok"])
        self.assertEqual(applied["missing"], ())
        passed = dict(blocked, ok=True, started=True, verdict=sp.PASS)
        self.assertTrue(sp._apply_mode(passed, sp.PRODUCTION, self.root)["ok"])

    def test_a_real_block_still_blocks_in_both_modes(self):
        cl.write(self.root, bad_ledger())
        browse = sp.evaluate(self.root, "final")
        self.assertFalse(browse["ok"])
        self.assertEqual(browse["verdict"], sp.BLOCKED)
        self.assertFalse(sp.production_ready(self.root, "final")["ok"])

    def test_a_malformed_ledger_cannot_be_silently_unblocked(self):
        """台账摘要说有问题、却算不出问题行时，不擅自放行。"""
        path = cl.issues_path(self.root)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}", encoding="utf-8")
        ledger_path = self.root / "06连贯性清单" / "output" / "continuity_ledger.json"
        ledger_path.parent.mkdir(parents=True, exist_ok=True)
        ledger_path.write_text('{"summary": {"ok": false, "problems": ["格式异常的一条"]}}',
                               encoding="utf-8")
        self.assertFalse(sp.evaluate(self.root, "final")["ok"])

    def test_verdict_labels_are_explicit(self):
        self.assertEqual(sp.verdict_label({"verdict": sp.PASS}), "通过")
        self.assertEqual(sp.verdict_label({"verdict": sp.UPSTREAM_BLANK}), "上游未开始")
        self.assertEqual(sp.verdict_label({}), "")

    def test_page_and_audit_text_keep_the_two_semantics_visible(self):
        head, line = sp.page_lines(self.root, "final")
        self.assertIn("正式自动生产", line)
        audit = sp.audit_text(self.root)
        self.assertIn("浏览放行", audit)


class AgentGateModeTests(unittest.TestCase):
    """Agent 默认浏览口径，且不再随持久化的档位漂移（干净树／主树都一样）。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()

    def test_the_default_gate_is_browse_whatever_the_level_says(self):
        for level in ("hint", "semi", "auto"):
            agent = pet_agent.Agent(project=self.root, level=level, persist=False)
            result = agent.gate("final")
            self.assertTrue(result["ok"], level)
            self.assertEqual(result["mode"], sp.BROWSE, level)

    def test_an_explicit_production_mode_blocks_a_blank_upstream(self):
        agent = pet_agent.Agent(project=self.root, level="hint", persist=False)
        result = agent.gate("final", mode=sp.PRODUCTION)
        self.assertFalse(result["ok"])
        self.assertEqual(result["missing"], ("continuity",))
        self.assertIn("正式自动生产", agent.blocked_reason("final", mode=sp.PRODUCTION))

    def test_a_skipped_upstream_exempts_the_production_gate(self):
        pet_state.Machine(self.root, persist=True).load().skip("continuity", "用户跳过").save()
        agent = pet_agent.Agent(project=self.root, level="auto", persist=False)
        self.assertTrue(agent.gate("final", mode=sp.PRODUCTION)["exempt"])
        self.assertEqual(agent.blocked_reason("final", mode=sp.PRODUCTION), "")


class PetGateModeTests(unittest.TestCase):
    """无人值守链在推时向 Agent 要正式生产口径；浏览时沿用旧口径。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()

    def pet(self, armed, answer=None):
        import pet_ui
        pet = object.__new__(type("Stub", (pet_ui.Pet,), {"agent": None}))
        pet.errors = []
        pet.desktop = type("D", (), {"root": self.root})()
        pet.auto = type("C", (), {"armed": armed})()
        seen = {}

        def blocked(stage, *, mode=None):
            seen["mode"] = mode
            return (answer or {}).get(mode, "")

        pet.agent = type("A", (), {"blocked_reason": staticmethod(blocked)})()
        pet._seen = seen
        return pet

    def test_the_armed_chain_asks_for_production_semantics(self):
        pet = self.pet(True, {sp.PRODUCTION: "缺连贯性清单"})
        self.assertEqual(pet.gate_reason("continuity"), "缺连贯性清单")
        self.assertEqual(pet._seen["mode"], sp.PRODUCTION)

    def test_a_browsing_pet_keeps_the_lenient_semantics(self):
        pet = self.pet(False, {sp.BROWSE: ""})
        self.assertEqual(pet.gate_reason("continuity"), "")
        self.assertEqual(pet._seen["mode"], sp.BROWSE)

    def test_the_storyboard_exemption_still_wins(self):
        pet = self.pet(True, {sp.PRODUCTION: "应该被豁免"})
        pet.has_structured_script = staticmethod(lambda project: True)
        self.assertEqual(pet.gate_reason("storyboard"), "")


if __name__ == "__main__":
    unittest.main(verbosity=2)

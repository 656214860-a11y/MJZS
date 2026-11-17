# -*- coding: utf-8 -*-
"""O23 连贯性问题闭环自检：稳定编号、不重复新增、修好解除、再变重开、忽略要理由。运行：python test_continuity_issues.py"""
import json, os, sys, tempfile, unittest
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
os.chdir(HERE)

import infra.continuity_ledger as cl
import stage_layout

ASSETS = {
    "CHAR_001": {"name": "林小满", "character_anchor": "黑短发、杏眼、米色针织衫"},
    "CHAR_002": {"name": "陈默", "character_anchor": "寸头、方脸、灰夹克"},
    "LOC_001": {"name": "咖啡馆", "lighting_direction": "右侧落地窗自然光 5600K"},
}


def shot(index, chars=("CHAR_001",), location="LOC_001", seconds=3):
    return {"id": "SH%03d" % index, "title": "镜头", "duration": seconds,
            "characters": list(chars), "location": location, "video_prompt": "画面", "dialogue": []}


def bad_ledger():
    """一批里两种三元组 → 一条三元组不一致问题。"""
    rows = [dict(cl.normalize(shot(1), 0), batch_id="B01"),
            dict(cl.normalize(shot(2, chars=("CHAR_002",)), 1), batch_id="B01")]
    return cl.build(rows, ASSETS)


def bad3_ledger():
    """三种三元组 → 同一条编号，但证据（detail）变了。"""
    rows = [dict(cl.normalize(shot(1), 0), batch_id="B01"),
            dict(cl.normalize(shot(2, chars=("CHAR_002",)), 1), batch_id="B01"),
            dict(cl.normalize(shot(3, location="LOC_002"), 2), batch_id="B01")]
    return cl.build(rows, ASSETS)


def clean_ledger():
    return cl.build([shot(1)], ASSETS)


def save(path, data):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


class IssueTests(unittest.TestCase):
    def test_a_bad_triplet_becomes_a_stable_issue_with_evidence(self):
        rows = cl.issues(bad_ledger())
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["id"], "CI-triplet-B01")
        self.assertEqual(row["kind"], "triplet")
        self.assertEqual(row["severity"], "高")
        self.assertEqual(row["shots"], ["SH001", "SH002"])
        self.assertIn("LOC_001", row["assets"])
        self.assertIn("三元组", row["evidence"])
        self.assertTrue(row["digest"])

    def test_the_same_ledger_always_gives_the_same_id(self):
        self.assertEqual([r["id"] for r in cl.issues(bad_ledger())],
                         [r["id"] for r in cl.issues(bad_ledger())])

    def test_different_batches_with_similar_ids_do_not_collide(self):
        ledger = {"batches": [{"batch_id": "B01", "shot_ids": ["SH001"]},
                              {"batch_id": "B02", "shot_ids": ["SH002"]}],
                  "triplets": [{"batch_id": "B01", "ok": False, "detail": "X"},
                               {"batch_id": "B02", "ok": False, "detail": "X"}],
                  "cross_batch": [{"kind": "character", "id": "CHAR_001", "state": "", "ok": False, "detail": "Y"}],
                  "conflicts": [], "drift": []}
        ids = [row["id"] for row in cl.issues(ledger)]
        self.assertEqual(ids, ["CI-triplet-B01", "CI-triplet-B02", "CI-cross_batch-CHAR_001-"])
        self.assertEqual(len(set(ids)), 3)

    def test_a_clean_ledger_has_no_issues(self):
        self.assertEqual(cl.issues(clean_ledger()), ())

    def test_each_issue_has_a_severity_and_a_kind_label(self):
        rows = cl.issues(bad_ledger())
        self.assertEqual(rows[0]["kind_label"], "三元组不一致")
        self.assertIn(rows[0]["severity"], ("高", "中"))


class MergeTests(unittest.TestCase):
    def test_the_same_problem_is_not_added_twice(self):
        current = cl.issues(bad_ledger())
        register, _ = cl.merge_issues({}, current, now="t1")
        register2, rows2 = cl.merge_issues(register, current, now="t2")
        self.assertEqual(list(register2), ["CI-triplet-B01"])
        self.assertEqual(len(rows2), 1)
        self.assertEqual(rows2[0]["state"], "open")
        self.assertEqual(rows2[0]["first_seen"], "t1")
        self.assertEqual(rows2[0]["last_seen"], "t2")

    def test_a_fixed_problem_is_resolved(self):
        register, _ = cl.merge_issues({}, cl.issues(bad_ledger()), now="t1")
        register, rows = cl.merge_issues(register, cl.issues(clean_ledger()), now="t2")
        self.assertEqual(rows[0]["state"], "resolved")
        self.assertEqual(rows[0]["last_seen"], "t2")

    def test_a_resolved_problem_reopens_when_it_returns(self):
        register, _ = cl.merge_issues({}, cl.issues(bad_ledger()), now="t1")
        register, _ = cl.merge_issues(register, cl.issues(clean_ledger()), now="t2")
        register, rows = cl.merge_issues(register, cl.issues(bad_ledger()), now="t3")
        self.assertEqual(rows[0]["state"], "open")
        notes = [entry["note"] for entry in rows[0]["history"]]
        self.assertIn("曾经解除，这次检查又出现", notes)

    def test_an_ignored_problem_stays_until_its_evidence_changes(self):
        register, _ = cl.merge_issues({}, cl.issues(bad_ledger()), now="t1")
        register["CI-triplet-B01"]["state"] = "ignored"
        register["CI-triplet-B01"]["decision"] = {"value": "ignored", "reason": "人工确认可接受",
                                                  "digest": register["CI-triplet-B01"]["digest"], "at": "t1"}
        register, rows = cl.merge_issues(register, cl.issues(bad_ledger()), now="t2")
        self.assertEqual(rows[0]["state"], "ignored")
        register, rows = cl.merge_issues(register, cl.issues(bad3_ledger()), now="t3")
        self.assertEqual(rows[0]["state"], "open")
        self.assertEqual(rows[0]["decision"], {})
        notes = [entry["note"] for entry in rows[0]["history"]]
        self.assertIn("忽略时依据的那一版证据已变化，需要重新决定", notes)


class DecideTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        stage_layout.ensure(str(self.root))

    def test_ignoring_requires_a_reason(self):
        cl.sync_issues(self.root, bad_ledger(), publish=save)
        with self.assertRaisesRegex(ValueError, "理由"):
            cl.decide_issue(self.root, "CI-triplet-B01", "ignored", "", publish=save)

    def test_ignore_records_reason_and_version(self):
        cl.sync_issues(self.root, bad_ledger(), publish=save)
        cl.decide_issue(self.root, "CI-triplet-B01", "ignored", "人工确认这批可用", publish=save, now="t2")
        rows = cl.sync_issues(self.root, bad_ledger(), publish=save, now="t3")
        row = next(item for item in rows if item["id"] == "CI-triplet-B01")
        self.assertEqual(row["state"], "ignored")
        self.assertEqual(row["reason"], "人工确认这批可用")
        stored = cl.read_issues(self.root)["CI-triplet-B01"]
        self.assertEqual(stored["decision"]["reason"], "人工确认这批可用")
        self.assertEqual(stored["decision"]["digest"], stored["digest"])
        self.assertEqual(stored["decision"]["at"], "t2")

    def test_unknown_issue_is_rejected(self):
        cl.sync_issues(self.root, bad_ledger(), publish=save)
        with self.assertRaisesRegex(ValueError, "没有这条问题"):
            cl.decide_issue(self.root, "CI-triplet-B99", "ignored", "理由", publish=save)

    def test_a_bad_decision_is_rejected(self):
        cl.sync_issues(self.root, bad_ledger(), publish=save)
        with self.assertRaisesRegex(ValueError, "处理决定"):
            cl.decide_issue(self.root, "CI-triplet-B01", "resolved", "理由", publish=save)

    def test_reopen_clears_the_ignore(self):
        cl.sync_issues(self.root, bad_ledger(), publish=save)
        cl.decide_issue(self.root, "CI-triplet-B01", "ignored", "理由", publish=save)
        rows = cl.decide_issue(self.root, "CI-triplet-B01", "open", publish=save)
        self.assertEqual(next(r for r in rows if r["id"] == "CI-triplet-B01")["state"], "open")


class SyncAndGateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        stage_layout.ensure(str(self.root))

    def test_preview_does_not_write_the_register(self):
        rows = cl.sync_issues(self.root, bad_ledger())
        self.assertTrue(rows)
        self.assertFalse(cl.issues_path(self.root).is_file())

    def test_sync_persists_the_register(self):
        cl.sync_issues(self.root, bad_ledger(), publish=save, now="t1")
        self.assertTrue(cl.issues_path(self.root).is_file())
        self.assertIn("CI-triplet-B01", cl.read_issues(self.root))

    def test_read_issues_without_a_file_is_empty(self):
        self.assertEqual(cl.read_issues(self.root), {})

    def test_gate_blocks_open_but_lets_ignored_through(self):
        cl.sync_issues(self.root, bad_ledger(), publish=save)
        ok, blocking = cl.issue_gate(self.root, bad_ledger())
        self.assertFalse(ok)
        self.assertEqual([row["id"] for row in blocking], ["CI-triplet-B01"])
        cl.decide_issue(self.root, "CI-triplet-B01", "ignored", "人工确认", publish=save)
        ok, blocking = cl.issue_gate(self.root, bad_ledger())
        self.assertTrue(ok)
        self.assertEqual(blocking, ())

    def test_gate_clears_when_the_problem_is_fixed(self):
        cl.sync_issues(self.root, bad_ledger(), publish=save)
        ok, blocking = cl.issue_gate(self.root, clean_ledger())
        self.assertTrue(ok)
        self.assertEqual(blocking, ())

    def test_ledger_ready_passes_after_an_issue_is_ignored(self):
        import stage_parallel
        cl.write(self.root, bad_ledger())
        cl.sync_issues(self.root, bad_ledger(), publish=save)
        self.assertFalse(stage_parallel.ledger_ready(str(self.root))["ok"])
        cl.decide_issue(self.root, "CI-triplet-B01", "ignored", "人工确认", publish=save)
        self.assertTrue(stage_parallel.ledger_ready(str(self.root))["ok"])


if __name__ == "__main__":
    unittest.main(verbosity=2)

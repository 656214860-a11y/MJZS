# -*- coding: utf-8 -*-
"""跨重启续跑台账的自检。"""
import json
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

import asset_resume


def project(td):
    """一个最小项目：只要 workflows 目录在，台账就有地方落。"""
    proj = Path(td) / "p"
    (proj / "workflows").mkdir(parents=True, exist_ok=True)
    return proj


def saved(proj):
    return json.loads(asset_resume.path(proj).read_text(encoding="utf-8"))


class ResumeLedgerTests(unittest.TestCase):
    def test_a_round_lands_on_disk_with_the_count_and_the_next_try(self):
        with tempfile.TemporaryDirectory() as td:
            proj = project(td)
            asset_resume.note_round(proj, ["CHAR_001", "LOC_001"], limit=3, now=1000.0)
            self.assertTrue(asset_resume.path(proj).is_file())
            data = saved(proj)
            self.assertEqual(sorted(data), ["CHAR_001", "LOC_001"])
            self.assertEqual(data["CHAR_001"]["attempts"], 1)
            self.assertEqual(data["CHAR_001"]["state"], "waiting")
            self.assertEqual(data["CHAR_001"]["last_try"], 1000.0)
            self.assertEqual(data["CHAR_001"]["next_try"], 1060.0)
            self.assertEqual(asset_resume.attempts(proj), 1)
            self.assertEqual(asset_resume.attempts(proj, ["CHAR_001"]), 1)
            self.assertEqual(asset_resume.attempts(proj, ["PROP_009"]), 0)
            self.assertAlmostEqual(asset_resume.delay(proj, now=1000.0), 60.0)

    def test_a_restart_reads_the_count_and_the_remaining_wait_back(self):
        with tempfile.TemporaryDirectory() as td:
            proj = project(td)
            asset_resume.note_round(proj, ["CHAR_001"], limit=3, now=1000.0)
            asset_resume.note_round(proj, ["CHAR_001"], limit=3, now=1060.0)
            self.assertEqual(asset_resume.attempts(proj), 2)
            self.assertAlmostEqual(asset_resume.delay(proj, now=1060.0), 120.0)
            self.assertAlmostEqual(asset_resume.delay(proj, now=1100.0), 80.0)
            self.assertEqual(asset_resume.delay(proj, now=5000.0), 0.0)

    def test_a_batch_that_hit_the_limit_stays_stopped_after_restart(self):
        with tempfile.TemporaryDirectory() as td:
            proj = project(td)
            for stamp in (1000.0, 1060.0, 1180.0):
                asset_resume.note_round(proj, ["CHAR_001"], limit=3, now=stamp)
            self.assertEqual(asset_resume.attempts(proj), 3)
            self.assertEqual(saved(proj)["CHAR_001"]["state"], "stopped")
            self.assertIsNone(asset_resume.delay(proj, now=1180.0), "到顶了就不再排下一次")

    def test_assets_that_got_their_picture_drop_out_of_the_ledger(self):
        with tempfile.TemporaryDirectory() as td:
            proj = project(td)
            asset_resume.note_round(proj, ["CHAR_001", "LOC_001"], limit=3, now=1000.0)
            asset_resume.note_round(proj, ["LOC_001"], limit=3, now=1060.0)
            data = saved(proj)
            self.assertEqual(sorted(data), ["LOC_001"], "出图了的编号要跟着摘掉")
            self.assertEqual(data["LOC_001"]["attempts"], 2)

    def test_an_empty_round_clears_the_ledger(self):
        with tempfile.TemporaryDirectory() as td:
            proj = project(td)
            asset_resume.note_round(proj, ["CHAR_001"], limit=3, now=1000.0)
            self.assertEqual(asset_resume.note_round(proj, []), {})
            self.assertFalse(asset_resume.path(proj).is_file())
            self.assertIsNone(asset_resume.delay(proj))

    def test_clearing_removes_the_file_and_a_second_clear_is_harmless(self):
        with tempfile.TemporaryDirectory() as td:
            proj = project(td)
            asset_resume.note_round(proj, ["CHAR_001"], limit=3, now=1000.0)
            asset_resume.clear(proj)
            self.assertFalse(asset_resume.path(proj).is_file())
            asset_resume.clear(proj)
            self.assertEqual(asset_resume.load(proj), {})

    def test_clear_delegates_generated_ledger_removal(self):
        with tempfile.TemporaryDirectory() as td:
            proj = project(td)
            with patch("storage_maintenance.clear_generated_workflow_state") as clear_state:
                asset_resume.clear(proj)
            clear_state.assert_called_once_with(
                proj, asset_resume.path(proj), asset_resume.FILE_NAME
            )

    def test_a_broken_ledger_counts_as_no_ledger(self):
        with tempfile.TemporaryDirectory() as td:
            proj = project(td)
            asset_resume.path(proj).write_text("{ 这不是 json", encoding="utf-8")
            self.assertEqual(asset_resume.load(proj), {})
            self.assertEqual(asset_resume.attempts(proj), 0)
            self.assertIsNone(asset_resume.delay(proj))
            asset_resume.clear(proj)
            self.assertFalse(asset_resume.path(proj).is_file())

    def test_entries_that_make_no_sense_are_filtered_out(self):
        with tempfile.TemporaryDirectory() as td:
            proj = project(td)
            asset_resume.path(proj).write_text(json.dumps({
                "CHAR_001": {"attempts": 2, "state": "waiting", "next_try": 5000.0},
                "CHAR_002": {"attempts": 0}, "CHAR_003": "不是字典",
                "CHAR_004": {"attempts": "两次"},
            }, ensure_ascii=False), encoding="utf-8")
            self.assertEqual(sorted(asset_resume.load(proj)), ["CHAR_001"])
            self.assertEqual(asset_resume.attempts(proj), 2)
            self.assertEqual(asset_resume.delay(proj, now=4000.0), 1000.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)

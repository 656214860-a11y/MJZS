# -*- coding: utf-8 -*-
"""O39：清理老视频前先查成果引用图（采用／成片来源／锁定／未结算）。"""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import engine
from contract import project_stages
import storage_maintenance
from agent.core import save as save_json
from storage_maintenance import (RETAIN_APPROVED, RETAIN_EDIT_SOURCE, RETAIN_FRESH, RETAIN_LATEST,
                                 RETAIN_LOCKED, RETAIN_UNSETTLED, VERSION_CLEAN_REASON,
                                 edit_source_versions, version_retention)

NOW = 1_700_000_000


class RetentionReasonTests(unittest.TestCase):
    def retention(self, version, newest=1, referenced=(), digests=(), now=NOW):
        return version_retention(version, "SH001", newest, set(referenced), set(digests), now)

    def test_settled_states_are_the_only_recyclable_ones(self):
        for state in ("queued", "running", "submitting", "unknown", "succeeded", ""):
            with self.subTest(state=state):
                self.assertEqual(self.retention({"version": 1, "state": state, "created": 0}),
                                 RETAIN_UNSETTLED)
        for state in ("failed", "rejected", "downloaded"):
            with self.subTest(state=state):
                self.assertEqual(self.retention({"version": 1, "state": state, "created": 0}, newest=2), "")

    def test_locked_approved_latest_and_fresh_are_kept_with_reasons(self):
        old = {"version": 1, "state": "downloaded", "created": 0}
        self.assertEqual(self.retention(dict(old, locked=True), newest=2), RETAIN_LOCKED)
        self.assertEqual(self.retention(dict(old, review="pass"), newest=2), RETAIN_APPROVED)
        self.assertEqual(self.retention(dict(old), newest=1), RETAIN_LATEST)
        self.assertEqual(self.retention(dict(old, version=2, created=NOW), newest=3), RETAIN_FRESH)
        # 缺 created 的记录没有到期证据，按未到期保守留住。
        self.assertEqual(self.retention({"version": 1, "state": "downloaded"}, newest=2), RETAIN_FRESH)

    def test_published_cut_reference_wins_by_version_or_digest(self):
        old = {"version": 1, "state": "failed", "created": 0, "sha256": "aa"}
        self.assertEqual(self.retention(old, newest=2, referenced=[("SH001", 1)]), RETAIN_EDIT_SOURCE)
        self.assertEqual(self.retention(old, newest=2, digests=[("SH001", "aa")]), RETAIN_EDIT_SOURCE)
        self.assertEqual(self.retention(dict(old, version=2), newest=3, referenced=[("SH001", 1)]), "")

    def test_manifest_names_track_the_engine_authority(self):
        self.assertEqual(set(storage_maintenance.EXPORT_MANIFEST_NAMES),
                         {engine.EDIT_BUNDLE_NAME, engine.EDIT_MANIFEST_NAME})


class EditSourceScanTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)

    def cut(self, name, payload, filename="edit_manifest.json"):
        folder = project_stages.exports(self.root) / name
        folder.mkdir(parents=True, exist_ok=True)
        (folder / filename).write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        return folder

    def test_reads_bundle_and_legacy_manifest_and_ignores_garbage(self):
        self.cut("成片A", {"manifest": [{"shot": "SH001", "version": 2, "sha256": "bb"}]}, "edit_bundle.json")
        self.cut("成片B", [{"shot": "SH002", "version": 1, "sha256": "cc"}, {"nope": 1}, "junk"])
        self.cut("成片C", {"nothing": True}, "edit_bundle.json")
        pairs, digests = edit_source_versions(self.root)
        self.assertEqual(pairs, {("SH001", 2), ("SH002", 1)})
        self.assertEqual(digests, {("SH001", "bb"), ("SH002", "cc")})

    def test_no_published_cut_means_nothing_is_referenced(self):
        self.assertEqual(edit_source_versions(self.root), (set(), set()))


class VideoRetentionCleanupTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.parent = Path(temp.name)
        self.root = self.parent / "库"
        self.root.mkdir()
        (self.root / "config.json").write_text("{}", encoding="utf-8")
        self.session = self.root / "生成"
        self.ledger = self.session / "data" / "state.json"
        self.ledger.parent.mkdir(parents=True)
        self.recycle_base = self.root / "工作流任务" / "回收站"

    def write_state(self, shots):
        save_json(self.ledger, {"schema": 1, "shots": shots})

    def folder(self, sid, number, base=None):
        folder = (base or (self.session / "data" / sid)) / ("v%03d" % number)
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "clip.mp4").write_bytes(b"v%d" % number)
        return folder

    def clean(self):
        with patch.object(storage_maintenance, "downloads_root", lambda: self.parent):
            return storage_maintenance.clean_project(self.root, now=NOW)

    def batches(self):
        return sorted(self.recycle_base.iterdir()) if self.recycle_base.is_dir() else []

    def test_adopted_old_version_survives_while_unreferenced_old_version_is_recycled(self):
        adopted = self.folder("SH001", 1)
        stale = self.folder("SH001", 2)
        self.write_state({"SH001": [
            {"version": 1, "state": "downloaded", "created": 0, "review": "pass", "qc_pass": True,
             "file": "生成/data/SH001/v001/clip.mp4"},
            {"version": 2, "state": "failed", "created": 0},
            {"version": 3, "state": "failed", "created": 0},
        ]})
        self.clean()
        self.assertTrue(adopted.is_dir())
        self.assertFalse(stale.is_dir())
        batches = self.batches()
        self.assertEqual(len(batches), 1)
        self.assertTrue((batches[0] / "生成" / "data" / "SH001" / "v002" / "clip.mp4").is_file())
        versions = json.loads(self.ledger.read_text(encoding="utf-8"))["shots"]["SH001"]
        self.assertEqual([v.get("cleaned_reason") for v in versions], [None, VERSION_CLEAN_REASON, None])
        self.assertEqual([v.get("file") for v in versions], ["生成/data/SH001/v001/clip.mp4", None, None])

    def test_latest_failed_version_and_its_adopted_older_version_both_stay(self):
        adopted = self.folder("SH004", 1)
        newest = self.folder("SH004", 2)
        self.write_state({"SH004": [
            {"version": 1, "state": "downloaded", "created": 0, "review": "pass", "qc_pass": True},
            {"version": 2, "state": "failed", "created": 0},
        ]})
        self.clean()
        self.assertTrue(adopted.is_dir())
        self.assertTrue(newest.is_dir())
        self.assertEqual(self.batches(), [])

    def test_published_cut_reference_protects_an_old_version(self):
        for filename, payload in (("edit_manifest.json", [{"shot": "SH002", "version": 1, "sha256": "aa"}]),
                                  ("edit_bundle.json", {"manifest": [{"shot": "SH002", "version": 1}]})):
            with self.subTest(filename=filename):
                folder = self.folder("SH002", 1)
                self.write_state({"SH002": [
                    {"version": 1, "state": "failed", "created": 0, "sha256": "aa"},
                    {"version": 2, "state": "downloaded", "created": 0, "review": "revise"},
                ]})
                cut = project_stages.exports(self.root) / "成片" / filename
                cut.parent.mkdir(parents=True, exist_ok=True)
                cut.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
                self.clean()
                self.assertTrue(folder.is_dir())
                self.assertEqual(self.batches(), [])
                cut.unlink()

    def test_unsettled_and_locked_versions_are_kept(self):
        folders = {name: self.folder("SH003", number)
                   for name, number in (("locked", 1), ("queued", 2), ("unknown", 3), ("newest", 4))}
        self.write_state({"SH003": [
            {"version": 1, "state": "failed", "created": 0, "locked": True},
            {"version": 2, "state": "queued", "created": 0},
            {"version": 3, "state": "unknown", "created": 0},
            {"version": 4, "state": "failed", "created": 0},
        ]})
        self.clean()
        for name, folder in folders.items():
            with self.subTest(name=name):
                self.assertTrue(folder.is_dir())
        self.assertEqual(self.batches(), [])

    def test_ledger_inside_the_recycle_bin_is_never_treated_as_production(self):
        batch = self.recycle_base / "自动维护_20260101_000000_deadbeef"
        ledger = batch / "生成" / "data" / "state.json"
        old = self.folder("SH009", 1, base=ledger.parent / "SH009")
        save_json(ledger, {"shots": {"SH009": [{"version": 1, "state": "failed", "created": 0},
                                             {"version": 2, "state": "failed", "created": 0}]}})
        self.clean()
        self.assertTrue(old.is_dir())
        self.assertEqual(self.batches(), [batch])
        state = json.loads(ledger.read_text(encoding="utf-8"))
        self.assertNotIn("cleaned_at", state["shots"]["SH009"][0])

    def test_unreadable_ledger_is_skipped_without_touching_anything(self):
        folder = self.folder("SH010", 1)
        self.ledger.write_text("{坏掉的 JSON", encoding="utf-8")
        self.clean()
        self.assertTrue(folder.is_dir())
        self.assertEqual(self.batches(), [])


if __name__ == "__main__":
    unittest.main()

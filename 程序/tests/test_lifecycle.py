# -*- coding: utf-8 -*-
"""资产批次派发状态恢复自检。"""
import json
import tempfile
import unittest
from pathlib import Path

from asset_batch_lifecycle import prepare, status


class LifecycleStatusTests(unittest.TestCase):
    def make_manifest(self, td):
        manifest = Path(td) / "批次" / "批次.json"
        manifest.parent.mkdir(parents=True)
        manifest.write_text("{}", encoding="utf-8")
        return manifest

    def test_legacy_when_no_state(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertEqual(status(self.make_manifest(td))["state"], "legacy")

    def test_execution_state_wins(self):
        with tempfile.TemporaryDirectory() as td:
            manifest = self.make_manifest(td)
            (manifest.parent / "执行状态.json").write_text(json.dumps({"state": "complete"}), encoding="utf-8")
            self.assertEqual(status(manifest)["state"], "complete")

    def test_dispatch_failed_after_timeout(self):
        import time
        with tempfile.TemporaryDirectory() as td:
            manifest = self.make_manifest(td)
            prepare(manifest)
            dispatch = manifest.parent / "派发状态.json"
            data = json.loads(dispatch.read_text(encoding="utf-8"))
            data["created"] = time.time() - 400
            dispatch.write_text(json.dumps(data), encoding="utf-8")
            self.assertEqual(status(manifest)["state"], "failed")

    def test_corrupt_execution_state_returns_legacy(self):
        with tempfile.TemporaryDirectory() as td:
            manifest = self.make_manifest(td)
            (manifest.parent / "执行状态.json").write_text("[]", encoding="utf-8")
            self.assertEqual(status(manifest)["state"], "legacy")

    def test_corrupt_dispatch_state_returns_legacy(self):
        with tempfile.TemporaryDirectory() as td:
            manifest = self.make_manifest(td)
            (manifest.parent / "派发状态.json").write_text("[]", encoding="utf-8")
            self.assertEqual(status(manifest)["state"], "legacy")

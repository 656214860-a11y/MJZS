"""真实临时项目的阶段入口、成果证据与回收恢复探针。"""
import importlib.util
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "维护记录/基准脚本/探针_阶段门禁端到端.py"
SPEC = importlib.util.spec_from_file_location("stage_gate_e2e_probe", SCRIPT)
probe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(probe)


class StageGateE2EProbeTests(unittest.TestCase):
    def test_empty_project_allows_entry_but_not_completed_evidence(self):
        result = probe.run_probe()
        self.assertEqual(len(result["empty"]), 5)
        for row in result["empty"]:
            self.assertTrue(row["entry_ok"], row)
            self.assertFalse(row["started"], row)
            self.assertFalse(row["completed"], row)

    def test_visible_delete_can_restore_identical_file(self):
        result = probe.run_probe()
        self.assertTrue(result["asset_before"]["completed"])
        self.assertFalse(result["deleted"]["file_exists"])
        self.assertTrue(result["deleted"]["recycled_file_exists"])
        self.assertTrue(result["restored"]["same_bytes"])
        self.assertTrue(result["restored"]["completed"])
        self.assertEqual(result["runtime_leaks"], [])

    def test_deleted_asset_cannot_be_certified_by_manifest_text(self):
        result = probe.run_probe()
        self.assertFalse(result["deleted"]["file_exists"])
        self.assertFalse(result["deleted"]["completed"],
                         "SG-01 必须依据实际图片文件，清单中的路径文字不能充当成果凭据")

    def test_real_evidence_opens_every_gate_in_order(self):
        result = probe.run_probe()
        self.assertEqual(result["findings"], [])
        self.assertEqual(result["executed"], ["SG-01", "SG-02", "SG-03", "SG-04", "SG-05"])
        for gate_id, row in result["stages"].items():
            self.assertTrue(row["completed"], (gate_id, row))
            self.assertTrue(row["gate_ok"], (gate_id, row))
            self.assertTrue(row["gate_started"], (gate_id, row))

"""真实临时项目的阶段入口、成果证据与回收恢复探针。"""
import importlib.util
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "维护记录/基准脚本/探针_阶段门禁端到端.py"
SPEC = importlib.util.spec_from_file_location("stage_gate_e2e_probe", SCRIPT)
probe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(probe)


class StageGateE2EProbeTests(unittest.TestCase):
    def test_empty_project_gate_semantics_are_not_uniform(self):
        """空项目：SG-A／SG-B 是“必须有上游成果”的入口闸，SG-01..05 是“上游没做就别拦”。

        两类语义都钉进用例：任一类被悄悄改成另一类，这里就红。
        """
        import stage_parallel
        result = probe.run_probe()
        self.assertEqual(len(result["empty"]), len(stage_parallel.GATE_IDS))
        rows = {row["id"]: row for row in result["empty"]}
        for gate_id in ("SG-A", "SG-B"):
            self.assertFalse(rows[gate_id]["entry_ok"], rows[gate_id])
            self.assertTrue(rows[gate_id]["started"], rows[gate_id])
        for gate_id in ("SG-01", "SG-02", "SG-03", "SG-04", "SG-05"):
            self.assertTrue(rows[gate_id]["entry_ok"], rows[gate_id])
            self.assertFalse(rows[gate_id]["started"], rows[gate_id])
        for row in result["empty"]:
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
        self.assertEqual(result["executed"],
                         ["SG-A", "SG-B", "SG-01", "SG-02", "SG-03", "SG-04", "SG-05"])
        for gate_id, row in result["stages"].items():
            self.assertTrue(row["completed"], (gate_id, row))
            self.assertTrue(row["gate_ok"], (gate_id, row))
            self.assertTrue(row["gate_started"], (gate_id, row))

    def test_gate_chain_is_complete_and_contiguous(self):
        """运行期链路：全部门禁都跑到真实证据，且上游的 to 就是下游的 from。"""
        import stage_parallel
        result = probe.run_probe()
        self.assertEqual(result["gates"], list(stage_parallel.GATE_IDS))
        self.assertEqual(result["executed"], list(stage_parallel.GATE_IDS))
        self.assertEqual(result["missing_gates"], [])
        chain = result["chain"]
        self.assertEqual(chain[0]["from"], "storyboard")
        self.assertEqual(chain[-1]["to"], "video")
        for previous, following in zip(chain, chain[1:]):
            self.assertEqual(previous["to"], following["from"], (previous, following))

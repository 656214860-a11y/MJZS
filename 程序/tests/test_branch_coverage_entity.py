"""分支覆盖率必须读取、跟踪实体，同时保持扁平登记键。"""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import branch_coverage_report as report
from tests.architecture import _layers, _scan, test_branch_coverage_floor as gate


class BranchCoverageEntityTests(unittest.TestCase):
    def _measure(self, source, facade):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            entity = root / "infra" / "probe.py"
            entity.parent.mkdir()
            entity.write_text(source, encoding="utf-8")
            if facade:
                (root / "probe.py").write_text("# compatibility facade\n", encoding="utf-8")
            code = compile(source, str(entity), "exec")
            suite = unittest.TestSuite([unittest.FunctionTestCase(lambda: exec(code, {}))])
            with (mock.patch.object(report, "PROGRAM", root),
                  mock.patch.object(gate, "ROOT", root),
                  mock.patch.dict(_layers.LAYERS, {"probe": 1}, clear=True),
                  mock.patch.object(_scan, "entity_file", return_value=entity),
                  mock.patch.object(gate, "entity_file", return_value=entity, create=True),
                  mock.patch.object(unittest.TestLoader, "loadTestsFromNames", return_value=suite)):
                self.assertEqual(report.l01_modules(), ("probe",))
                self.assertEqual(gate._l01_files(), {"probe.py"})
                return report.measure(("probe_target",))

    def test_zero_branch_facade_does_not_hide_entity_branches(self):
        result = self._measure("def f(value):\n    if value:\n        return 1\n    return 0\nf(True)\nf(False)\n", True)
        self.assertTrue(result["tests_ok"])
        self.assertEqual(result["modules"], [
            {"module": "probe.py", "points": 1, "covered": 1, "percent": 100.0}])

    def test_entity_without_top_level_facade_is_included(self):
        result = self._measure("def f(value):\n    if value:\n        return 1\n    return 0\nf(True)\n", False)
        self.assertTrue(result["tests_ok"])
        self.assertEqual(result["modules"], [
            {"module": "probe.py", "points": 1, "covered": 0, "percent": 0.0}])

    def test_gate_rejects_facade_snapshot_and_accepts_entity_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            entity = Path(directory) / "probe.py"
            entity.write_text("if True:\n    VALUE = 1\n", encoding="utf-8")
            case = gate.BranchCoverageFloorTests()
            with (mock.patch.object(gate, "entity_file", return_value=entity),
                  mock.patch.object(case, "_baseline", return_value={
                      "modules": [{"module": "probe.py", "points": 0}]})):
                with self.assertRaisesRegex(AssertionError, "当前实体"):
                    case.test_baseline_decision_points_match_current_entities()
            with (mock.patch.object(gate, "entity_file", return_value=entity),
                  mock.patch.object(case, "_baseline", return_value={
                      "modules": [{"module": "probe.py", "points": 1}]})):
                case.test_baseline_decision_points_match_current_entities()

    def test_genuinely_branch_free_entity_keeps_zero_point_convention(self):
        result = self._measure("VALUE = 1\n", False)
        self.assertTrue(result["tests_ok"])
        self.assertEqual(result["modules"], [
            {"module": "probe.py", "points": 0, "covered": 0, "percent": 100.0}])


if __name__ == "__main__":
    unittest.main()

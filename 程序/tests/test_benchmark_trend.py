# -*- coding: utf-8 -*-
"""benchmark_trend：全量耗时与启动耗时回退只告警不误报。"""
import tempfile
import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import benchmark_trend as bt


def _rows(*seconds):
    return [{"seconds": s, "round": 1000 + i, "at": "2026-11-15T%02d:00:00" % i}
            for i, s in enumerate(seconds)]


def _startup_rows(branch, *seconds):
    return [{"seconds": s, "branch": branch, "round": 2000 + i,
             "at": "2026-11-15T%02d:00:00" % i} for i, s in enumerate(seconds)]


class TrendTests(unittest.TestCase):
    def test_load_receipts_orders_and_filters(self):
        document = {"full_safe_verified_trees": [
            {"seconds": 100, "at": "2026-11-15T02:00:00"},
            {"seconds": 90, "at": "2026-11-15T01:00:00"},
            {"bad": True}]}
        rows = bt.load_receipts(document)
        self.assertEqual([r["seconds"] for r in rows], [90, 100])

    def test_regression_alerts(self):
        alerts, _s = bt.trend_report(_rows(100, 100, 100, 100, 100, 200))
        self.assertEqual(len(alerts), 1)
        self.assertIn("回退", alerts[0])

    def test_normal_variance_stays_quiet(self):
        alerts, _s = bt.trend_report(_rows(100, 105, 95, 110, 100, 110))
        self.assertEqual(alerts, [])

    def test_too_few_samples_is_quiet(self):
        alerts, summary = bt.trend_report(_rows(300))
        self.assertEqual(alerts, [])
        self.assertIn("不足", summary)


class StartupTrendTests(unittest.TestCase):
    def test_record_appends_jsonl_and_load_reads_back(self):
        with tempfile.TemporaryDirectory() as temporary:
            common = Path(temporary)
            path = bt.record_startup_perf(1.25, "same_day", common_dir=common)
            self.assertEqual(Path(path), common / bt.STARTUP_HISTORY_NAME)
            bt.record_startup_perf(1.5, "first_day", common_dir=common)
            rows = bt.load_startup_rows(common_dir=common)
        self.assertEqual([row["branch"] for row in rows], ["same_day", "first_day"])
        self.assertEqual(rows[0]["seconds"], 1.25)
        self.assertTrue(rows[0]["at"])

    def test_load_skips_blank_and_corrupt_lines(self):
        with tempfile.TemporaryDirectory() as temporary:
            common = Path(temporary)
            bt.record_startup_perf(2.0, "same_day", common_dir=common)
            target = common / bt.STARTUP_HISTORY_NAME
            with target.open("a", encoding="utf-8", newline="") as handle:
                handle.write("\n{bad json\n")
            rows = bt.load_startup_rows(common_dir=common)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["seconds"], 2.0)

    def test_same_branch_regression_alerts(self):
        rows = _startup_rows("same_day", 1.0, 1.0, 1.0, 1.0, 1.0, 2.0)
        alerts, summary = bt.startup_trend_report(rows)
        self.assertEqual(len(alerts), 1)
        self.assertIn("same_day", alerts[0])
        self.assertIn("回退", alerts[0])
        self.assertIn("same_day", summary)

    def test_branches_are_never_compared_with_each_other(self):
        rows = _startup_rows("first_day", 9.0) + _startup_rows("same_day", 1.0, 1.0, 1.0, 1.0, 1.0)
        rows[-1]["seconds"] = 1.1
        alerts, _summary = bt.startup_trend_report(rows)
        self.assertEqual(alerts, [])

    def test_startup_history_is_capped(self):
        with tempfile.TemporaryDirectory() as temporary:
            common = Path(temporary)
            for index in range(bt.STARTUP_HISTORY_KEEP + 3):
                bt.record_startup_perf(float(index), "same_day", common_dir=common)
            lines = (common / bt.STARTUP_HISTORY_NAME).read_text(encoding="utf-8").splitlines()
            rows = bt.load_startup_rows(common_dir=common)
        self.assertEqual(len(lines), bt.STARTUP_HISTORY_KEEP)
        self.assertEqual(rows[-1]["seconds"], float(bt.STARTUP_HISTORY_KEEP + 2))


if __name__ == "__main__":
    unittest.main()

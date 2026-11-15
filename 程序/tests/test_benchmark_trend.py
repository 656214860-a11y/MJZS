# -*- coding: utf-8 -*-
"""benchmark_trend：全量耗时回退只告警不误报。"""
import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import benchmark_trend as bt


def _rows(*seconds):
    return [{"seconds": s, "round": 1000 + i, "at": "2026-11-15T%02d:00:00" % i}
            for i, s in enumerate(seconds)]


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


if __name__ == "__main__":
    unittest.main()

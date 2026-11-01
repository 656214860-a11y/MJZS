"""结果文件按月归档：只归档旧月份，最大轮次号不变。"""
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
for folder in (str(HERE.parent), str(HERE.parent / "scripts"), str(HERE.parent / "维护记录" / "基准脚本")):
    if folder not in sys.path:
        sys.path.insert(0, folder)

import archive_results as archive
import round_claim


def name(n):
    return "tasks_round_%d_result.md" % n


class ArchivePlanTests(unittest.TestCase):
    def test_keeps_recent_months_and_newest_result(self):
        files = [name(1), name(2), name(3), name(4), "other.md"]
        added = {name(1): "2026-09", name(2): "2026-10", name(3): "2026-11", name(4): "2026-09"}
        self.assertEqual(archive.plan(files, added, date(2026, 11, 2), 2), {"2026-09": [name(1)]})
        self.assertEqual(archive.plan(files, added, date(2026, 11, 2), 1),
                         {"2026-09": [name(1)], "2026-10": [name(2)]})

    def test_untracked_files_are_never_moved(self):
        self.assertEqual(archive.plan([name(1), name(2)], {}, date(2026, 11, 2), 1), {})

    def test_months_to_keep_crosses_year(self):
        self.assertEqual(archive.months_to_keep(date(2027, 1, 5), 2), {"2027-01", "2026-12"})


class ArchivedRoundsStayVisibleTests(unittest.TestCase):
    def test_latest_result_round_sees_archived_files(self):
        with tempfile.TemporaryDirectory() as root:
            tasks = Path(root)
            (tasks / "归档" / "2026-10").mkdir(parents=True)
            (tasks / "归档" / "2026-10" / name(9)).write_text("x", encoding="utf-8")
            (tasks / name(5)).write_text("x", encoding="utf-8")
            self.assertEqual(round_claim.latest_result_round(tasks), 9)


if __name__ == "__main__":
    unittest.main()

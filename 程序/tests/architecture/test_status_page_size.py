"""状态页行数上限：project_status.md 只留当前口径，历史细节进结果文件。"""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STATUS = ROOT / 'project_status.md'
MAX_LINES = 500  # 2026-11-02 当前 469 行；超出请把旧条目挪进对应 tasks_round 结果文件，不要调高本数


def overflow(text, limit=MAX_LINES):
    count = len(text.splitlines())
    return max(0, count - limit)


class StatusPageSizeTests(unittest.TestCase):
    def test_overflow_counts_lines_beyond_the_cap(self):
        self.assertEqual(overflow('a\n' * 10, 10), 0)
        self.assertEqual(overflow('a\n' * 13, 10), 3)

    def test_status_page_stays_within_the_line_cap(self):
        text = STATUS.read_text(encoding='utf-8')
        self.assertEqual(overflow(text), 0, 'project_status.md 超过 %d 行 %d 行：把旧条目挪进结果文件' % (
            MAX_LINES, overflow(text)))


if __name__ == '__main__':
    unittest.main()

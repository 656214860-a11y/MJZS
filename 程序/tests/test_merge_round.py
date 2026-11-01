"""合并轮一条命令：状态页抬头与结果文件的纯函数部分。"""
import sys
import unittest
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
for folder in (str(HERE.parent / "scripts"), str(HERE.parent)):
    if folder not in sys.path:
        sys.path.insert(0, folder)

import merge_round

OLD = ("# 项目状态\n\n更新：2026-11-01｜当前轮次：2287（R2286 合并轮：甲合入；断言未动。上一轮：R2271 文档轮。）"
       "｜上一轮：（历史）\n\n正文\n")


class BumpStatusTests(unittest.TestCase):
    def test_header_moves_to_next_round_and_keeps_only_one_previous(self):
        text = merge_round.bump_status(OLD, 2290, "乙合入 master，无冲突。", date(2026, 11, 2))
        self.assertIn("更新：2026-11-02｜当前轮次：2291（R2290 合并轮：乙合入 master，无冲突；断言未动；未跑全量。"
                      "上一轮：R2286 合并轮：甲合入；断言未动。）｜上一轮：（历史）", text)
        self.assertTrue(text.startswith("# 项目状态\n\n") and text.endswith("正文\n"))
        self.assertEqual(text.count("当前轮次："), 1)

    def test_missing_header_is_an_error(self):
        with self.assertRaises(ValueError):
            merge_round.bump_status("没有抬头", 1, "x", date(2026, 11, 2))

    def test_local_settings_change_is_not_a_foreign_change(self):
        self.assertEqual(merge_round.foreign_changes(" M .claude/settings.local.json\n"), [])
        self.assertEqual(merge_round.foreign_changes(" M .claude/settings.local.json\n M a.py\n"), [" M a.py"])

    def test_result_text_names_round_branch_and_unmodified_assertions(self):
        body = merge_round.result_text(2290, "codex/wip-R2289", "说明")
        for part in ("# R2290 合并轮结果", "`codex/wip-R2289`", "断言未动"):
            self.assertIn(part, body)


if __name__ == "__main__":
    unittest.main()

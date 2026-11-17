"""任务书闭环（规则 35，R3039 决策 13）守卫测试：五项机器检查的坏/好样本自审＋真实仓库状态。"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tests.architecture._scan import ROOT

import scripts.taskbook_closure as closure

BOOK = '样例任务书.md'
BOOK_TEXT = '# 样例任务书\n\n- [ ] 任务甲：改一处\n- [x] 任务乙：跑一次\n'
GOOD_DONE = ('# 样例任务书·任务完成.md\n\n'
             '任务甲：改一处 → R3041（tasks_round/tasks_round_3041_result.md，commit abcdef0）\n'
             '任务乙：跑一次 → R3042（commit 1234567）\n')


def _setup(base: Path, book_text: str, done_name: str | None, done_text: str | None):
    base.mkdir(parents=True, exist_ok=True)
    (base / BOOK).write_text(book_text, encoding='utf-8')
    comp = base / '任务完成'
    comp.mkdir(exist_ok=True)
    (comp / closure.README_NAME).write_text('建档', encoding='utf-8')
    if done_name is not None and done_text is not None:
        (comp / done_name).write_text(done_text, encoding='utf-8')


class TaskbookClosureTests(unittest.TestCase):
    def test_good_sample_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            _setup(base, BOOK_TEXT, '样例·任务完成.md', GOOD_DONE)
            self.assertEqual(closure.validate(tasks_round=base, completion_dir=base / '任务完成'), [])

    def test_orphan_completion_file_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            _setup(base, BOOK_TEXT, '没有任务书·任务完成.md', GOOD_DONE)
            problems = closure.validate(tasks_round=base, completion_dir=base / '任务完成')
            self.assertTrue(any('孤儿完成文件' in p for p in problems), problems)

    def test_missing_coverage_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            _setup(base, BOOK_TEXT, '样例·任务完成.md', '# 只覆盖了任务乙：跑一次 → R3042（commit 1234567）\n')
            problems = closure.validate(tasks_round=base, completion_dir=base / '任务完成')
            self.assertTrue(any('缺少条目覆盖：任务甲' in p for p in problems), problems)

    def test_evidence_shortfall_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            text = '任务甲：改一处 → 完成\n任务乙：跑一次 → 完成\n'
            _setup(base, BOOK_TEXT, '样例·任务完成.md', text)
            problems = closure.validate(tasks_round=base, completion_dir=base / '任务完成')
            self.assertTrue(any('证据/处置标记不足' in p for p in problems), problems)

    def test_disposition_without_confirmation_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            text = ('任务甲：改一处 → R3041（tasks_round/tasks_round_3041_result.md，commit abcdef0）\n'
                    '任务乙：跑一次 → 转欠账\n')
            _setup(base, BOOK_TEXT, '样例·任务完成.md', text)
            problems = closure.validate(tasks_round=base, completion_dir=base / '任务完成')
            self.assertTrue(any('处置条目缺用户确认凭据' in p for p in problems), problems)

    def test_real_repo_state_is_clean(self):
        self.assertEqual(closure.validate(), [],
                         '仓库内的任务完成目录应通过校验器（无孤儿、README 建档、已有完成文件覆盖其任务书）')

    def test_exempt_whitelist_only_shrinks(self):
        self.assertEqual(closure.EXEMPT_TASKBOOKS, frozenset({'docs/review/优化任务书_SWE2_20261115.md'}),
                         '豁免白名单只许减少，不许新增')

    def test_declares_closure_triggers(self):
        self.assertTrue(closure.declares_closure('R3042: 任务书收尾', []))
        self.assertTrue(closure.declares_closure('R3042: 输出任务完成文件', []))
        self.assertFalse(closure.declares_closure('R3042: 修个 bug', []))
        self.assertTrue(closure.declares_closure('R3042: 修个 bug', ['tasks_round/任务完成/测试隐藏桌面强制执行·任务完成.md']))


if __name__ == '__main__':
    unittest.main()

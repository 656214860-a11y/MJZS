"""合并轮一条命令：状态页抬头与结果文件的纯函数部分。"""
import os
import subprocess
import sys
import tempfile
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


def _git(root, *args):
    env = dict(os.environ, GIT_AUTHOR_NAME='t', GIT_AUTHOR_EMAIL='t@t',
               GIT_COMMITTER_NAME='t', GIT_COMMITTER_EMAIL='t@t')
    done = subprocess.run(['git', *args], cwd=root, env=env,
                          capture_output=True, text=True, encoding='utf-8')
    assert done.returncode == 0, done.stderr
    return done.stdout.strip()


class MergeInProgressTests(unittest.TestCase):
    """MERGE_HEAD 归属判定：失败清理只能 abort 本分支的合并，不能动别人的现场。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        _git(self.root, 'init', '-q', '-b', 'master')
        (self.root / 'a.txt').write_text('base\n', encoding='utf-8')
        _git(self.root, 'add', '-A')
        _git(self.root, 'commit', '-q', '-m', 'base')
        _git(self.root, 'checkout', '-q', '-b', 'feature')
        (self.root / 'a.txt').write_text('feature\n', encoding='utf-8')
        _git(self.root, 'commit', '-q', '-am', 'feature')
        _git(self.root, 'checkout', '-q', 'master')
        (self.root / 'a.txt').write_text('master\n', encoding='utf-8')
        _git(self.root, 'commit', '-q', '-am', 'master')
        # 制造一个属于 feature 的合并现场（同一文件两边都改 → 冲突 → MERGE_HEAD 存在）
        env = dict(os.environ, GIT_AUTHOR_NAME='t', GIT_AUTHOR_EMAIL='t@t',
                   GIT_COMMITTER_NAME='t', GIT_COMMITTER_EMAIL='t@t')
        done = subprocess.run(['git', 'merge', '--no-commit', '--no-ff', 'feature'],
                              cwd=self.root, env=env, capture_output=True, text=True)
        self.assertNotEqual(done.returncode, 0)
        self.assertTrue(merge_round.merge_in_progress(self.root))

    def test_clean_repo_has_no_merge_in_progress(self):
        repo = Path(self.tmp.name) / 'clean'
        repo.mkdir()
        _git(repo, 'init', '-q', '-b', 'master')
        (repo / 'x').write_text('x', encoding='utf-8')
        _git(repo, 'add', '-A')
        _git(repo, 'commit', '-q', '-m', 'x')
        self.assertFalse(merge_round.merge_in_progress(repo))

    def test_merge_in_progress_and_head_identity(self):
        self.assertTrue(merge_round.merge_in_progress(self.root))
        self.assertTrue(merge_round.merge_head_is('feature', self.root))
        self.assertFalse(merge_round.merge_head_is('master', self.root))

    def test_cleanup_keeps_foreign_merge_and_aborts_own(self):
        # MERGE_HEAD 属于 feature：以 master 身份清理 → 不动现场
        self.assertEqual(merge_round.cleanup_failed_merge('master', self.root), 'foreign')
        self.assertTrue(merge_round.merge_in_progress(self.root))
        # 以 feature 身份清理 → abort，现场还原
        self.assertEqual(merge_round.cleanup_failed_merge('feature', self.root), 'conflict')
        self.assertFalse(merge_round.merge_in_progress(self.root))
        self.assertEqual((self.root / 'a.txt').read_text(encoding='utf-8'), 'master\n')


if __name__ == "__main__":
    unittest.main()

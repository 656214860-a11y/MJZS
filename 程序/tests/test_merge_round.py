"""合并轮一条命令：状态页抬头与结果文件的纯函数部分。"""
import json
import os
import subprocess
import sys
import tempfile
import time
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

    def test_merge_head_age_seconds_reports_age(self):
        age = merge_round.merge_head_age_seconds(self.root)
        self.assertIsNotNone(age)
        self.assertGreaterEqual(age, 0)
        self.assertLess(age, 120)

    def test_merge_head_age_none_without_merge(self):
        repo = Path(self.tmp.name) / 'clean2'
        repo.mkdir()
        _git(repo, 'init', '-q', '-b', 'master')
        (repo / 'x').write_text('x', encoding='utf-8')
        _git(repo, 'add', '-A')
        _git(repo, 'commit', '-q', '-m', 'x')
        self.assertIsNone(merge_round.merge_head_age_seconds(repo))

    def test_cleanup_keeps_foreign_merge_and_aborts_own(self):
        # MERGE_HEAD 属于 feature：以 master 身份清理 → 不动现场
        self.assertEqual(merge_round.cleanup_failed_merge('master', self.root), 'foreign')
        self.assertTrue(merge_round.merge_in_progress(self.root))
        # 以 feature 身份清理 → abort，现场还原
        self.assertEqual(merge_round.cleanup_failed_merge('feature', self.root), 'conflict')
        self.assertFalse(merge_round.merge_in_progress(self.root))
        self.assertEqual((self.root / 'a.txt').read_text(encoding='utf-8'), 'master\n')

    def _write_lane_lock(self, tip, *, stale):
        path = merge_round.merge_lane_lock_path(self.root)
        body = merge_round.lock_lease.payload(4242, branch='feature', tip=tip)
        if stale:
            body['heartbeat_at'] = time.time() - 1000
            body['created_at'] = body['heartbeat_at']
        path.write_text(json.dumps(body), encoding='utf-8')
        return path

    def test_stale_owned_merge_is_aborted(self):
        tip = _git(self.root, 'rev-parse', 'MERGE_HEAD')
        self._write_lane_lock(tip, stale=True)
        self.assertTrue(merge_round.reclaim_dead_owned_merge(self.root))
        self.assertFalse(merge_round.merge_in_progress(self.root))

    def test_live_merge_lane_is_left_alone(self):
        tip = _git(self.root, 'rev-parse', 'MERGE_HEAD')
        self._write_lane_lock(tip, stale=False)
        self.assertFalse(merge_round.reclaim_dead_owned_merge(self.root))
        self.assertTrue(merge_round.merge_in_progress(self.root))

    def test_stale_lock_with_other_tip_is_left_alone(self):
        self._write_lane_lock('0' * 40, stale=True)
        self.assertFalse(merge_round.reclaim_dead_owned_merge(self.root))
        self.assertTrue(merge_round.merge_in_progress(self.root))

    def test_merge_lane_lock_is_exclusive_until_released(self):
        self.assertTrue(merge_round.acquire_merge_lane('feature', 'abc', self.root))
        self.assertFalse(merge_round.acquire_merge_lane('other', 'def', self.root))
        merge_round.release_merge_lane(self.root)
        self.assertTrue(merge_round.acquire_merge_lane('feature', 'abc', self.root))
        merge_round.release_merge_lane(self.root)


class RebaseOntoMasterTests(unittest.TestCase):
    """合入前变基：干净则分支含当前 master；冲突则 abort，主干尖端不动。"""

    def setUp(self):
        self._saved = {key: os.environ.get(key) for key in
                       ("GIT_AUTHOR_NAME", "GIT_AUTHOR_EMAIL", "GIT_COMMITTER_NAME", "GIT_COMMITTER_EMAIL")}
        os.environ["GIT_AUTHOR_NAME"] = "t"
        os.environ["GIT_AUTHOR_EMAIL"] = "t@t"
        os.environ["GIT_COMMITTER_NAME"] = "t"
        os.environ["GIT_COMMITTER_EMAIL"] = "t@t"
        self.addCleanup(self._restore_env)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "repo"
        self.root.mkdir()
        _git(self.root, "init", "-q", "-b", "master")
        (self.root / "a.txt").write_text("base\n", encoding="utf-8")
        _git(self.root, "add", "a.txt")
        _git(self.root, "commit", "-q", "-m", "base")
        self.lane = Path(self.tmp.name) / "lane"
        _git(self.root, "worktree", "add", "-q", "-b", "feature", str(self.lane))

    def _restore_env(self):
        for key, value in self._saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_clean_rebase_aligns_branch_and_leaves_master(self):
        (self.lane / "b.txt").write_text("lane\n", encoding="utf-8")
        _git(self.lane, "add", "b.txt")
        _git(self.lane, "commit", "-q", "-m", "lane")
        (self.root / "c.txt").write_text("master\n", encoding="utf-8")
        _git(self.root, "add", "c.txt")
        _git(self.root, "commit", "-q", "-m", "master-move")
        before = _git(self.root, "rev-parse", "HEAD")
        self.assertEqual(merge_round.rebase_onto_master("feature", self.root), 0)
        self.assertEqual(_git(self.root, "rev-parse", "HEAD"), before)
        self.assertEqual(_git(self.root, "symbolic-ref", "--short", "HEAD"), "master")
        _git(self.root, "merge-base", "--is-ancestor", "master", "feature")
        self.assertFalse(merge_round.rebase_in_progress(self.lane))

    def test_conflict_aborts_and_leaves_both_tips(self):
        (self.lane / "a.txt").write_text("feature\n", encoding="utf-8")
        _git(self.lane, "commit", "-q", "-am", "feature")
        feature_tip = _git(self.lane, "rev-parse", "HEAD")
        (self.root / "a.txt").write_text("master\n", encoding="utf-8")
        _git(self.root, "commit", "-q", "-am", "master")
        before = _git(self.root, "rev-parse", "HEAD")
        self.assertEqual(merge_round.rebase_onto_master("feature", self.root), merge_round.REBASE_RETURNED)
        self.assertEqual(_git(self.root, "rev-parse", "HEAD"), before)
        self.assertEqual(_git(self.lane, "rev-parse", "HEAD"), feature_tip)
        self.assertEqual(_git(self.root, "symbolic-ref", "--short", "HEAD"), "master")
        self.assertFalse(merge_round.rebase_in_progress(self.lane))

    def test_dirty_lane_is_returned_without_moving_either_tip(self):
        (self.lane / "a.txt").write_text("dirty\n", encoding="utf-8")
        lane_tip = _git(self.lane, "rev-parse", "HEAD")
        (self.root / "c.txt").write_text("master\n", encoding="utf-8")
        _git(self.root, "add", "c.txt")
        _git(self.root, "commit", "-q", "-m", "master-move")
        before = _git(self.root, "rev-parse", "HEAD")
        self.assertEqual(merge_round.rebase_onto_master("feature", self.root), merge_round.REBASE_RETURNED)
        self.assertEqual(_git(self.root, "rev-parse", "HEAD"), before)
        self.assertEqual(_git(self.lane, "rev-parse", "HEAD"), lane_tip)
        self.assertEqual((self.lane / "a.txt").read_text(encoding="utf-8"), "dirty\n")

    def test_unchecked_branch_rebases_in_a_temporary_worktree(self):
        _git(self.root, "branch", "side")
        _git(self.root, "commit", "--allow-empty", "-q", "-m", "master-move")
        before = _git(self.root, "rev-parse", "HEAD")
        self.assertEqual(merge_round.rebase_onto_master("side", self.root), 0)
        self.assertEqual(_git(self.root, "rev-parse", "HEAD"), before)
        self.assertEqual(_git(self.root, "rev-parse", "side"), before)
        self.assertEqual(_git(self.root, "symbolic-ref", "--short", "HEAD"), "master")


if __name__ == "__main__":
    unittest.main()

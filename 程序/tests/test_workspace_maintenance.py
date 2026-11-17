# -*- coding: utf-8 -*-
"""仓库级有界卫生的回归：pycache、超期 .selftmp、已并净工作树三段与挂接形态。"""
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from infra import workspace_maintenance as wm
from skip_reasons import PLATFORM_DIRECTORY_LINK


class WorkspaceMaintenanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.program = self.root / '程序'
        self.program.mkdir()
        self.old_protected = wm.SWEEP_PROTECTED
        wm.SWEEP_PROTECTED = (self.root / '运行环境', self.program / 'private',
                              self.program / 'data', self.root / '.git')

    def tearDown(self):
        wm.SWEEP_PROTECTED = self.old_protected
        self.temp.cleanup()

    def _pycache(self, where, name='mod'):
        cache = where / '__pycache__'
        cache.mkdir(parents=True, exist_ok=True)
        (cache / (name + '.cpython-312.pyc')).write_bytes(b'x' * 64)
        return cache

    def test_pycache_sweep_removes_dirs_and_keeps_sources(self):
        pkg = self.program / 'pkg'
        pkg.mkdir()
        (pkg / 'mod.py').write_text('x=1', encoding='utf-8')
        cache = self._pycache(pkg)
        result = wm.clean_pycache((self.program,))
        self.assertFalse(cache.exists())
        self.assertTrue((pkg / 'mod.py').exists())
        self.assertEqual(result['removed_entries'], 1)
        self.assertGreater(result['removed_bytes'], 0)
        self.assertEqual(result['errors'], 0)

    def test_pycache_skips_protected_roots(self):
        env_cache = self._pycache(self.root / '运行环境' / 'Python' / 'Lib')
        private_cache = self._pycache(self.program / 'private')
        wm.clean_pycache((self.program, self.root))
        self.assertTrue(env_cache.exists())
        self.assertTrue(private_cache.exists())

    def test_pycache_walk_prunes_nested_and_counts_outer_once(self):
        outer = self._pycache(self.program / 'deep')
        inner = outer / 'nested' / '__pycache__'
        inner.mkdir(parents=True)
        (inner / 'a.pyc').write_bytes(b'y')
        found = wm.pycache_directories(self.program)
        self.assertEqual([p for p in found if 'deep' in str(p)], [outer])
        result = wm.clean_pycache((self.program,))
        self.assertEqual(result['removed_entries'], 1)
        self.assertFalse(outer.exists())

    def test_locked_file_removal_not_fatal(self):
        cache = self._pycache(self.program / 'busy')
        with mock.patch.object(Path, 'unlink', side_effect=PermissionError):
            result = wm.clean_pycache((self.program,))
        self.assertGreaterEqual(result['errors'], 1)
        self.assertTrue(cache.exists(), '删不动就留着，下次退出再收')

    def test_pycache_with_non_cache_content_is_preserved(self):
        cache = self._pycache(self.program / 'pkg')
        note = cache / 'important.txt'
        note.write_text('keep', encoding='utf-8')
        result = wm.clean_pycache((self.program,))
        self.assertEqual(note.read_text(encoding='utf-8'), 'keep')
        self.assertTrue((cache / 'mod.cpython-312.pyc').exists())
        self.assertEqual(result['removed_files'], 0)

    def test_pycache_under_user_and_log_directories_is_preserved(self):
        caches = [self._pycache(self.program / name) for name in ('episode', 'writing', '配置', 'logs')]
        wm.clean_pycache((self.program,))
        self.assertTrue(all(p.exists() for p in caches))

    def test_pycache_nested_junction_is_not_traversed_or_removed(self):
        cache = self._pycache(self.program / 'pkg')
        linked = cache / 'linked'
        linked.mkdir()
        with mock.patch.object(Path, 'is_junction', autospec=True, side_effect=lambda p: p == linked):
            result = wm.clean_pycache((self.program,))
        self.assertTrue(linked.exists())
        self.assertTrue((cache / 'mod.cpython-312.pyc').exists())
        self.assertEqual(result['removed_files'], 0)

    def test_tracked_pycache_is_preserved(self):
        cache = self._pycache(self.program / 'pkg')
        (self.root / '.git').mkdir()
        with mock.patch.object(wm, 'run_git', return_value=SimpleNamespace(returncode=0, stdout='程序/pkg/__pycache__/mod.pyc\0')):
            wm.clean_pycache((self.program,))
        self.assertTrue(cache.exists())

    def test_unknown_git_tracking_state_preserves_pycache(self):
        cache = self._pycache(self.program / 'pkg')
        (self.root / '.git').mkdir()
        with mock.patch.object(wm, 'run_git', return_value=None):
            result = wm.clean_pycache((self.program,))
        self.assertTrue(cache.exists())
        self.assertGreater(result['errors'], 0)

    def test_selftemp_age_cutoff_keeps_root_and_recent(self):
        home = self.root / '.selftmp'
        home.mkdir()
        old_dir = home / 'tmpOLDOLD01'
        old_dir.mkdir()
        (old_dir / 'a.txt').write_text('old', encoding='utf-8')
        fresh = time.time() - 30 * 24 * 3600
        os.utime(old_dir, (fresh, fresh))
        recent_dir = home / 'tmpRECENT01'
        recent_dir.mkdir()
        probe = home / 'probe_page_freeze.py'
        probe.write_text('# probe', encoding='utf-8')
        old_file = home / 'tmp_ancient.txt'
        old_file.write_text('x', encoding='utf-8')
        os.utime(old_file, (fresh, fresh))
        result = wm.clean_selftemp(home, now=time.time())
        self.assertFalse(old_dir.exists())
        self.assertFalse(old_file.exists())
        self.assertTrue(recent_dir.exists())
        self.assertTrue(probe.exists())
        self.assertTrue(home.exists())
        self.assertEqual(result['removed_entries'], 2)
        self.assertGreaterEqual(result['kept_recent'], 1)

    def test_selftemp_symlink_entry_skipped(self):
        home = self.root / '.selftmp'
        home.mkdir()
        target = self.root / 'elsewhere'
        target.mkdir()
        (target / 'keep.txt').write_text('keep', encoding='utf-8')
        link = home / 'tmpLINK01'
        try:
            os.symlink(str(target), str(link), target_is_directory=True)
        except OSError:
            self.skipTest(PLATFORM_DIRECTORY_LINK)
        result = wm.clean_selftemp(home, now=time.time())
        self.assertEqual(result['skipped'], 1)
        self.assertEqual(result['removed_entries'], 0)
        self.assertTrue((target / 'keep.txt').exists())

    def test_parse_worktree_list_pure(self):
        text = (
            'worktree D:/repo\n'
            'HEAD 1111111111111111111111111111111111111111\n'
            'branch refs/heads/master\n'
            '\n'
            'worktree "D:/repo/.wt/B1"\n'
            'HEAD 2222222222222222222222222222222222222222\n'
            'branch refs/heads/codex/B1\n'
            'locked\n'
            '\n'
            'worktree D:/repo/.wt/R820\n'
            'HEAD 3333333333333333333333333333333333333333\n'
            'detached\n'
            'prunable: git directory is missing\n'
            '\n')
        entries = wm.parse_worktree_list(text)
        self.assertEqual(len(entries), 3)
        self.assertEqual(entries[0]['branch'], 'refs/heads/master')
        self.assertEqual(entries[1]['path'], Path('D:/repo/.wt/B1'))
        self.assertTrue(entries[1]['locked'])
        self.assertTrue(entries[2]['prunable'])
        self.assertIsNone(entries[2]['branch'])

    def _fake_repo(self):
        repo = self.root / 'repo'
        (repo / '.git').mkdir(parents=True)
        wt = repo / '.wt'
        good = wt / 'ROLD'
        good.mkdir(parents=True)
        (good / 'file.txt').write_text('x', encoding='utf-8')
        stamp = time.time() - 30 * 24 * 3600
        os.utime(good, (stamp, stamp))
        return repo, wt, good

    def _list_run(self, repo, good, *, extra=''):
        listing = (f'worktree {repo}\nHEAD {"a" * 40}\nbranch refs/heads/master\n\n'
                   f'worktree {good}\nHEAD {"b" * 40}\nbranch refs/heads/codex/ROLD\n\n'
                   + extra)
        def run(command, **kwargs):
            return SimpleNamespace(returncode=0, stdout=listing, stderr='')
        return run

    def test_local_worktrees_scope_guard(self):
        repo, _wt, good = self._fake_repo()
        extra = (f'worktree C:/Users/x/.codex/worktrees/y/repo\nHEAD {"c" * 40}\n\n')
        with mock.patch.object(wm, 'tool_path', lambda name, fallback='': 'C:/git.exe'):
            entries = wm.local_worktrees(repo, run=self._list_run(repo, good, extra=extra))
        self.assertEqual([Path(e['path']).name for e in entries], ['ROLD'])

    def test_verdict_matrix(self):
        repo, _wt, good = self._fake_repo()
        entry = {'path': good, 'head': 'b' * 40, 'branch': 'x', 'locked': False, 'prunable': False}
        now = time.time()
        def run(command, **kwargs):
            if 'merge-base' in command:
                return SimpleNamespace(returncode=0, stdout='', stderr='')
            if 'status' in command:
                return SimpleNamespace(returncode=0, stdout='', stderr='')
            return SimpleNamespace(returncode=0, stdout='', stderr='')
        with mock.patch.object(wm, 'tool_path', lambda name, fallback='': 'git'):
            self.assertEqual(wm.worktree_verdict(entry, repo, now=now, run=run), (True, 'merged-and-clean'))
            entry_locked = dict(entry, locked=True)
            self.assertEqual(wm.worktree_verdict(entry_locked, repo, now=now, run=run), (False, 'locked'))
            self.assertEqual(wm.worktree_verdict(entry, repo, now=now, min_age_seconds=3650 * 86400, run=run),
                             (False, 'recent'))
            def run_dirty(command, **kwargs):
                if 'merge-base' in command:
                    return SimpleNamespace(returncode=1, stdout='', stderr='')
                return SimpleNamespace(returncode=0, stdout=' M file.py\n', stderr='')
            self.assertEqual(wm.worktree_verdict(entry, repo, now=now, run=run_dirty), (False, 'unmerged'))
            def run_status_dirty(command, **kwargs):
                if 'merge-base' in command:
                    return SimpleNamespace(returncode=0, stdout='', stderr='')
                return SimpleNamespace(returncode=0, stdout=' M file.py\n', stderr='')
            self.assertEqual(wm.worktree_verdict(entry, repo, now=now, run=run_status_dirty), (False, 'dirty'))
            def run_broken(command, **kwargs):
                raise FileNotFoundError('git 不存在')
            self.assertEqual(wm.worktree_verdict(entry, repo, now=now, run=run_broken), (False, 'unmerged'),
                             'git 异常一律保守保留')

    def test_clean_worktrees_sequence_and_no_force(self):
        repo, _wt, good = self._fake_repo()
        calls = []
        def run(command, **kwargs):
            calls.append(list(command))
            joined = ' '.join(command)
            if 'worktree list' in joined:
                return SimpleNamespace(returncode=0,
                                       stdout=f'worktree {good}\nHEAD {"b" * 40}\nbranch refs/heads/x\n\n',
                                       stderr='')
            if 'worktree remove' in joined:
                return SimpleNamespace(returncode=0, stdout='', stderr='')
            if 'worktree prune' in joined or 'merge-base' in joined:
                return SimpleNamespace(returncode=0, stdout='', stderr='')
            return SimpleNamespace(returncode=0, stdout='', stderr='')
        with mock.patch.object(wm, 'tool_path', lambda name, fallback='': 'git'):
            result = wm.clean_worktrees(repo, now=time.time(), run=run)
        self.assertEqual(result['git'], 'present')
        self.assertEqual([item['name'] for item in result['removed']], ['ROLD'])
        remove_calls = [c for c in calls if 'remove' in c]
        self.assertEqual(len(remove_calls), 1)
        self.assertNotIn('--force', remove_calls[0])
        self.assertTrue(any('worktree' in c and 'prune' in c for c in calls), '移除后收一次 prune')
        self.assertEqual(result['errors'], 0)

    def test_clean_worktrees_refused_removal_kept_not_retried(self):
        repo, _wt, good = self._fake_repo()
        def run(command, **kwargs):
            joined = ' '.join(command)
            if 'worktree list' in joined:
                return SimpleNamespace(returncode=0,
                                       stdout=f'worktree {good}\nHEAD {"b" * 40}\nbranch refs/heads/x\n\n',
                                       stderr='')
            if 'worktree remove' in joined:
                return SimpleNamespace(returncode=255, stdout='', stderr='contains untracked files')
            return SimpleNamespace(returncode=0, stdout='', stderr='')
        with mock.patch.object(wm, 'tool_path', lambda name, fallback='': 'git'):
            result = wm.clean_worktrees(repo, now=time.time(), run=run)
        self.assertEqual(result['removed'], [])
        self.assertEqual(result['kept'], [('ROLD', 'remove-refused')])
        self.assertEqual(result['errors'], 1)

    def test_worktrees_absent_on_non_repo_machine(self):
        plain = self.root / 'installed'
        plain.mkdir()
        with mock.patch.object(wm, 'tool_path', lambda name, fallback='': 'git'):
            result = wm.clean_worktrees(plain, run=lambda command, **kwargs: self.fail('不得调用进程'))
        self.assertEqual(result['git'], 'not-a-repo')
        repo, _wt, _good = self._fake_repo()
        with mock.patch.object(wm, 'tool_path', lambda name, fallback='': None):
            result = wm.clean_worktrees(repo, run=lambda command, **kwargs: self.fail('无 git 不得调用进程'))
        self.assertEqual(result['git'], 'absent')

    def test_linked_worktree_gitfile_is_a_repository(self):
        linked = self.root / 'linked'
        linked.mkdir()
        (linked / '.git').write_text('gitdir: elsewhere', encoding='utf-8')
        with mock.patch.object(wm, 'tool_path', lambda name, fallback='': None):
            result = wm.clean_worktrees(linked,
                                        run=lambda command, **kwargs: self.fail('git 不可用时不得调用'))
        self.assertEqual(result['git'], 'absent')

    def test_maintain_repository_dry_run_changes_nothing(self):
        cache = self._pycache(self.program / 'pkg')
        home = self.root / '.selftmp'
        home.mkdir()
        old_dir = home / 'tmpAAAA1'
        old_dir.mkdir()
        stamp = time.time() - 30 * 24 * 3600
        os.utime(old_dir, (stamp, stamp))
        summary = wm.maintain_repository(program=self.program, dist_root=self.root,
                                         dry_run=True, run=lambda command, **kwargs: SimpleNamespace(returncode=1, stdout='', stderr=''))
        self.assertTrue(cache.exists())
        self.assertTrue(old_dir.exists())
        self.assertTrue(summary['dry_run'])
        self.assertGreater(summary['released_bytes'], 0)
        self.assertEqual(summary['worktrees']['git'], 'not-a-repo', '测试根没有 .git，工作树段整体跳过')
        self.assertFalse((self.program / 'logs' / wm.SWEEP_LOG_NAME).exists(), 'dry-run 不写日志')

    def test_maintain_repository_not_a_repo_skips_git(self):
        summary = wm.maintain_repository(program=self.program, dist_root=self.program,
                                         run=lambda command, **kwargs: self.fail('非主仓不得调用 git'))
        self.assertEqual(summary['worktrees']['git'], 'not-a-repo')
        self.assertEqual(summary['pycache']['removed_entries'], 0)

    def test_summary_log_single_line_and_failure_swallowed(self):
        summary = wm.maintain_repository(program=self.program, dist_root=self.root,
                                         run=lambda command, **kwargs: SimpleNamespace(returncode=1, stdout='', stderr=''))
        wm.append_summary_log(self.program, summary)
        lines = (self.program / 'logs' / wm.SWEEP_LOG_NAME).read_text(encoding='utf-8').splitlines()
        self.assertEqual(len(lines), 1)
        self.assertIn('释放', lines[0])
        broken = self.program / 'logs' / 'not-a-dir-file'
        broken.write_text('x', encoding='utf-8')
        with mock.patch.object(wm, 'SWEEP_LOG_NAME', new='not-a-dir-file/deeper.log'):
            self.assertIsNone(wm.append_summary_log(self.program, summary), '日志不可写不得炸掉退出链')

    def test_launch_cleanup_detached_command(self):
        commands = []
        with mock.patch.object(wm, 'launch_background', lambda command, **kwargs: commands.append(command)):
            wm.launch_cleanup(self.program)
        self.assertEqual(commands, [[sys.executable, str(self.program / 'workspace_maintenance.py'), '--cleanup']])

    def test_main_dry_run_reports_and_returns_zero(self):
        self._pycache(self.program / 'pkg')
        with mock.patch.object(wm, 'PROGRAM', self.program), mock.patch.object(wm, 'DIST_ROOT', self.root):
            exit_code = wm.main(['--dry-run'])
        self.assertEqual(exit_code, 0)
        self.assertTrue((self.program / 'pkg' / '__pycache__').exists(), 'dry-run 仍不落改动')


if __name__ == '__main__':
    unittest.main(verbosity=2)

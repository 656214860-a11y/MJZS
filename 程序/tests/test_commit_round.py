"""commit_round：等锁逻辑只在锁持有进程存活时阻塞；失效锁被回收，超时不吞暂存区。"""
import contextlib
import subprocess
import time
import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

PROGRAM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROGRAM / 'scripts'))
import commit_round  # noqa: E402
import run_selftests  # noqa: E402


class CommitRoundTests(unittest.TestCase):
    def test_explicit_commit_rejects_foreign_index_before_adding_files(self):
        from contextlib import ExitStack
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            repo = Path(tmp)
            program = repo / 'program'
            program.mkdir()
            git = commit_round._git
            def run(*args):
                result = git(*args, cwd=program)
                result.check_returncode()
                return result.stdout
            run('init', '-b', 'codex/test', str(repo))
            run('config', 'user.name', 'test')
            run('config', 'user.email', 'test@example.invalid')
            run('config', 'core.hooksPath', 'unused')
            run('commit', '--allow-empty', '-m', 'base')
            (repo / '其他文件').write_text('foreign', encoding='utf8')
            (program / 'owned').write_text('requested', encoding='utf8')
            run('add', '../其他文件')
            head = run('rev-parse', 'HEAD')
            index = run('write-tree')
            stack.enter_context(patch.object(commit_round, 'PROGRAM', program))
            stack.enter_context(patch.object(commit_round, '_git', side_effect=lambda *a, **kw:
                                             git(*a, cwd=kw.get('cwd', program))))
            for guard in ('attach_codex_worktree', 'check_scope_overlap', 'check_test_move',
                          'check_taskbook_closure', 'attach_evidence', 'common_dir'):
                stack.enter_context(patch.object(commit_round, guard, return_value=0))
            self.assertNotEqual(0, commit_round.main(['-m', 'R1: explicit', 'owned']))
            self.assertEqual(head, run('rev-parse', 'HEAD'))
            self.assertEqual(index, run('write-tree'))
            self.assertEqual(0, commit_round.main(['-m', 'R1: staged']))
            merge_head = repo / '.git' / 'MERGE_HEAD'
            merge_head.write_text(run('rev-parse', 'HEAD'), encoding='ascii')
            self.assertNotEqual(0, commit_round.main(['-m', 'R2: partial merge', 'owned']))
            self.assertEqual('', run('diff', '--cached', '--name-only'))
            merge_head.unlink()
            # Another process stages a file after the last check, before Git takes its lock.
            late = repo / 'late'
            late.write_text('concurrent addition', encoding='utf8')
            original_run = commit_round._run_git
            def stage_during_commit(args, cwd, env=None):
                if args[0] == 'commit':
                    original_run(['add', '--', 'late'], repo).check_returncode()
                return original_run(args, cwd, env)
            with patch.object(commit_round, '_run_git', side_effect=stage_during_commit):
                self.assertEqual(0, commit_round.main(['-m', 'R2: explicit', 'owned']))
            self.assertEqual('late', run('diff', '--cached', '--name-only').strip())
            self.assertEqual('program/owned', run('diff-tree', '--no-commit-id', '--name-only',
                                                 '-r', 'HEAD').strip())

    def test_detached_codex_commit_keeps_index_and_leaves_shared_lock_alone(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            repo = home / "repo"
            repo.mkdir()
            work = home / ".codex" / "worktrees" / "abcd" / "repo"
            git = commit_round._git
            git("init", "-b", "main", cwd=repo).check_returncode()
            git("-c", "user.name=test", "-c", "user.email=test@example.org",
                "commit", "--allow-empty", "-m", "init", cwd=repo).check_returncode()
            git("worktree", "add", "--detach", str(work), cwd=repo).check_returncode()
            lock = self.lock(commit_round.common_dir(repo), os.getpid())
            (work / "change").write_text("staged", encoding="utf-8")
            git("add", "change", cwd=work).check_returncode()
            before = git("rev-parse", "HEAD", cwd=work).stdout
            with patch.object(Path, "home", return_value=home):
                self.assertEqual(commit_round.attach_codex_worktree(work), 0)
                self.assertEqual(commit_round.attach_codex_worktree(work), 0)
            self.assertEqual(git("branch", "--show-current", cwd=work).stdout.strip(), "codex/worktree-abcd")
            self.assertEqual(git("rev-parse", "HEAD", cwd=work).stdout, before)
            self.assertEqual(git("diff", "--cached", "--name-only", cwd=work).stdout.strip(), "change")
            self.assertTrue(lock.exists())

    def lock(self, common, pid):
        path = Path(common) / run_selftests.FULL_SAFE_LOCK_NAME
        path.write_text(json.dumps({'pid': pid, 'round': 1}), encoding='utf-8')
        return path

    def test_no_lock_passes_immediately(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertTrue(commit_round.wait_for_lock(Path(tmp), 0, out=lambda _: None))

    def test_dead_holder_lock_is_reclaimed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.lock(tmp, 2 ** 22 + 12345)
            self.assertTrue(commit_round.wait_for_lock(Path(tmp), 5, poll=0.01, out=lambda _: None))
            self.assertFalse(path.exists())

    def test_live_holder_times_out_and_lock_stays(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.lock(tmp, os.getpid())
            self.assertFalse(commit_round.wait_for_lock(Path(tmp), 0.05, poll=0.01, out=lambda _: None))
            self.assertTrue(path.exists())

    def test_fresh_heartbeat_stays_even_when_the_pid_cannot_be_opened(self):
        import time
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / run_selftests.FULL_SAFE_LOCK_NAME
            path.write_text(json.dumps({
                'pid': 2 ** 22 + 9, 'round': 4, 'token': 'held',
                'heartbeat_at': time.time(), 'started_at': time.time(),
            }), encoding='utf-8')
            self.assertFalse(commit_round.wait_for_lock(Path(tmp), 0.05, poll=0.01, out=lambda _: None))
            self.assertEqual(json.loads(path.read_text(encoding='utf-8'))['token'], 'held')

    def test_silent_heartbeat_is_reclaimed_even_if_the_pid_is_alive(self):
        import time
        with tempfile.TemporaryDirectory() as tmp:
            path = self.lock(tmp, os.getpid())
            path.write_text(json.dumps({
                'pid': os.getpid(), 'round': 4, 'token': 'old',
                'heartbeat_at': time.time() - 300, 'started_at': time.time(),
            }), encoding='utf-8')
            self.assertTrue(commit_round.wait_for_lock(Path(tmp), 1, poll=0.01, out=lambda _: None))
            self.assertFalse(path.exists())

    def test_young_unreadable_lock_is_not_deleted(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / run_selftests.FULL_SAFE_LOCK_NAME
            path.write_text('{', encoding='utf-8')
            self.assertFalse(commit_round.wait_for_lock(Path(tmp), 0.05, poll=0.01, out=lambda _: None))
            self.assertEqual(path.read_text(encoding='utf-8'), '{')

    def test_index_lock_retries_then_stops(self):
        from subprocess import CompletedProcess
        calls = []

        def fake_run(command, **kwargs):
            calls.append(command)
            if len(calls) < 3:
                return CompletedProcess(command, 128, '', "fatal: Unable to create '.git/index.lock': File exists.")
            return CompletedProcess(command, 0, '', '')

        with patch('commit_round.subprocess.run', side_effect=fake_run), \
             patch('commit_round.time.sleep') as slept:
            done = commit_round._git('add', '--', 'a')
        self.assertEqual(done.returncode, 0)
        self.assertEqual([item.args[0] for item in slept.call_args_list], [0.2, 0.4])

    def test_unrelated_git_failure_is_not_retried(self):
        from subprocess import CompletedProcess

        def fake_run(command, **kwargs):
            return CompletedProcess(command, 1, '', 'fatal: pathspec did not match')

        with patch('commit_round.subprocess.run', side_effect=fake_run) as run, \
             patch('commit_round.time.sleep') as slept:
            done = commit_round._git('add', '--', 'missing')
        self.assertEqual(done.returncode, 1)
        self.assertEqual(run.call_count, 1)
        slept.assert_not_called()

    def test_old_round_numbers_skip_evidence_and_new_ones_require_it(self):
        import round_evidence
        self.assertEqual(commit_round.attach_evidence('R1931: 旧轮', [], Path('.')), 0)
        self.assertEqual(commit_round.attach_evidence('WIP: 半成品', [], Path('.')), 0)
        self.assertGreater(round_evidence.EVIDENCE_REQUIRED_FROM, 1931)


    def test_agent_trailer_is_appended_once_and_only_when_named(self):
        self.assertEqual(commit_round.with_agent_trailer('R1: x', ''), 'R1: x')
        once = commit_round.with_agent_trailer('R1: x', 'swe-2')
        self.assertEqual(once, 'R1: x\n\nAgent: swe-2')
        self.assertEqual(commit_round.with_agent_trailer(once, 'swe-2'), once)

    def test_test_move_check_only_runs_for_move_round_messages(self):
        from unittest import mock
        with mock.patch.object(commit_round.test_move_audit, 'audit_staged', return_value=['x：改了断言']) as audit:
            self.assertEqual(commit_round.check_test_move('R1: 普通改动', Path('.')), 0)
            self.assertEqual(commit_round.check_test_move('R1: 补测试搬家守卫', Path('.')), 0)
            audit.assert_not_called()
            self.assertEqual(commit_round.check_test_move('R1: 测试搬家：迁入 tests/', Path('.')), 5)
            audit.assert_called_once()
        with mock.patch.object(commit_round.test_move_audit, 'audit_staged', return_value=[]):
            self.assertEqual(commit_round.check_test_move('R1: 测试搬家', Path('.')), 0)

# 在独立的临时仓库内执行同一提交入口，覆盖强杀、并发与回执丢失。
GIT = ['git', '-c', 'core.quotepath=false']
BASE_MESSAGE = 'R1: 黑盒重试回归'
OWNED = 'owned.txt'
ROUND_HIGH = 2600  # >= round_evidence.EVIDENCE_REQUIRED_FROM，覆盖工具证据链路

_RUNNER_TEMPLATE = r'''import os
import sys
import time
from pathlib import Path

REAL_PROGRAM = Path(__REAL_PROGRAM__)
PROGRAM_DIR = Path(__PROGRAM_DIR__)

sys.path.insert(0, str(REAL_PROGRAM / "scripts"))
import commit_round  # noqa: E402

_real_git = commit_round._git
_real_run_git = commit_round._run_git
_real_common_dir = commit_round.common_dir


def _git(*args, **kw):
    kw["cwd"] = kw.get("cwd", PROGRAM_DIR)
    return _real_git(*args, **kw)


def _common_dir(*args, **kw):
    kw["cwd"] = kw.get("cwd", PROGRAM_DIR)
    return _real_common_dir(*args, **kw)


commit_round.PROGRAM = PROGRAM_DIR
commit_round._git = _git
commit_round.common_dir = _common_dir
# 车道范围门禁依赖 lanes.json 等台账，临时仓库没有；固定放行但保留调用痕迹。
commit_round.check_scope_overlap = lambda root: 0

_evidence_dir = os.environ.get("COMMIT_ROUND_EVIDENCE_DIR")
if _evidence_dir:
    import round_evidence as _round_evidence
    _evidence_root = Path(_evidence_dir)

    # write_evidence/judge/result_header/stamp_result 全部经 evidence_path 取径，
    # 单点覆盖即可把证据读写收进临时目录，保留调用者显式指定的目录。
    def _evidence_path(number, directory=None):
        return Path(directory or _evidence_root) / ("R%d.json" % number)

    _round_evidence.evidence_path = _evidence_path

_spy = os.environ.get("COMMIT_ROUND_SPY")
if _spy:
    for _name in ("attach_evidence", "check_test_move",
                  "check_taskbook_closure", "check_scope_overlap"):
        _fn = getattr(commit_round, _name, None)
        if _fn is not None:
            def _spy_wrap(fn, name):
                def inner(*args, **kw):
                    with open(_spy, "a", encoding="utf-8") as handle:
                        handle.write(name + "\n")
                    return fn(*args, **kw)
                return inner
            setattr(commit_round, _name, _spy_wrap(_fn, _name))

_fault = os.environ.get("COMMIT_ROUND_FAULT", "")


def _run_git(args, cwd, env=None):
    if args and args[0] == "commit":
        if _fault == "kill_before_commit":
            os._exit(137)
        if _fault == "kill_after_commit":
            done = _real_run_git(args, cwd, env)
            os._exit(0 if done.returncode == 0 else 1)
        if _fault.startswith("wait:"):
            marker = _fault[len("wait:"):]
            with open(marker + ".reached", "w", encoding="utf-8") as handle:
                handle.write("waiting")
            deadline = time.time() + 120
            while not os.path.exists(marker):
                if time.time() > deadline:
                    os._exit(3)
                time.sleep(0.05)
    return _real_run_git(args, cwd, env)


commit_round._run_git = _run_git

if __name__ == "__main__":
    sys.exit(commit_round.main(sys.argv[1:]))
'''


def git(cwd, *args, input_text=None):
    return subprocess.run(GIT + list(args), cwd=str(cwd), input=input_text,
                          capture_output=True, text=True, encoding='utf-8',
                          errors='replace')


class _Repo:
    """一次用例的隔离现场：repo 是 git 工作树根，program 是 commit_round.PROGRAM。"""

    def __init__(self, base):
        self.base = base
        self.repo = base / 'repo'
        self.program = self.repo / 'program'
        self.runner = base / 'commit_runner.py'
        self.base_sha = ''

    def head(self):
        return git(self.repo, 'rev-parse', 'HEAD').stdout.strip()

    def rev_count(self):
        return int(git(self.repo, 'rev-list', '--count', 'HEAD').stdout.strip())

    def staged_names(self):
        out = git(self.repo, 'diff', '--cached', '--name-only').stdout
        return {line for line in out.splitlines() if line}

    def round_commits(self, message):
        out = git(self.repo, 'log', '--format=%H %s', self.base_sha + '..HEAD').stdout
        return [line.split(' ', 1)[0] for line in out.splitlines()
                if line.split(' ', 1)[-1].startswith(message.split(':', 1)[0] + ':')]


@contextlib.contextmanager
def fixture():
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        fx = _Repo(base)
        fx.program.mkdir(parents=True)
        (base / 'nohooks').mkdir()
        git(fx.repo, 'init', '-b', 'master').check_returncode()
        for key, value in (('user.name', 'commit-retry-test'),
                           ('user.email', 'crt@example.invalid'),
                           ('core.hooksPath', str(base / 'nohooks')),
                           ('commit.gpgsign', 'false')):
            git(fx.repo, 'config', key, value).check_returncode()
        git(fx.repo, 'commit', '--allow-empty', '-m', 'base').check_returncode()
        git(fx.repo, 'switch', '-c', 'codex/test').check_returncode()
        fx.base_sha = fx.head()
        runner = (_RUNNER_TEMPLATE
                  .replace('__REAL_PROGRAM__', json.dumps(str(PROGRAM)))
                  .replace('__PROGRAM_DIR__', json.dumps(str(fx.program))))
        fx.runner.write_text(runner, encoding='utf-8')
        yield fx


def run_commit(fx, args, *, fault=None, spy=None, evidence_dir=None,
               timeout=180, popen=False):
    env = dict(os.environ)
    env['COMMIT_ROUND_FAULT'] = fault or ''
    env.pop('COMMIT_ROUND_SPY', None)
    env.pop('COMMIT_ROUND_EVIDENCE_DIR', None)
    if spy is not None:
        env['COMMIT_ROUND_SPY'] = str(spy)
    if evidence_dir is not None:
        env['COMMIT_ROUND_EVIDENCE_DIR'] = str(evidence_dir)
    cmd = [sys.executable, '-B', str(fx.runner), *[str(a) for a in args]]
    if popen:
        return subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                env=env, text=True, encoding='utf-8',
                                errors='replace')
    return subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8',
                          errors='replace', env=env, timeout=timeout)


def write_owned(fx, text='owned-v1'):
    (fx.program / OWNED).write_text(text, encoding='utf-8')


def explicit_args(message=BASE_MESSAGE):
    return ['-m', message, OWNED]


class CommitRetryTests(unittest.TestCase):
    """黑盒契约：只看退出码、stdout 与临时仓库的 git 状态，不看实现内部。"""

    # ---------- 显式隔离与无路径兼容 ----------

    def test_explicit_paths_reject_unrelated_staged_file(self):
        with fixture() as fx:
            write_owned(fx)
            (fx.repo / 'foreign.txt').write_text('foreign', encoding='utf-8')
            git(fx.repo, 'add', 'foreign.txt').check_returncode()
            head = fx.head()
            proc = run_commit(fx, explicit_args())
            self.assertNotEqual(proc.returncode, 0)
            self.assertEqual(fx.head(), head)
            self.assertIn('foreign.txt', fx.staged_names())
            self.assertEqual(fx.round_commits('R1'), [])

    def test_no_path_commit_still_takes_whole_index(self):
        with fixture() as fx:
            write_owned(fx)
            (fx.repo / 'foreign.txt').write_text('foreign', encoding='utf-8')
            git(fx.repo, 'add', 'foreign.txt', 'program/' + OWNED).check_returncode()
            head = fx.head()
            proc = run_commit(fx, ['-m', BASE_MESSAGE])
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertNotEqual(fx.head(), head)
            names = git(fx.repo, 'show', '--name-only', '--format=', 'HEAD').stdout
            self.assertIn('program/' + OWNED, names)
            self.assertIn('foreign.txt', names)
            self.assertEqual(fx.staged_names(), set())

    def test_no_path_commit_with_nothing_staged_fails(self):
        with fixture() as fx:
            head = fx.head()
            proc = run_commit(fx, ['-m', BASE_MESSAGE])
            self.assertNotEqual(proc.returncode, 0)
            self.assertEqual(fx.head(), head)

    def test_merge_state_no_path_commit_keeps_merge_parents(self):
        with fixture() as fx:
            (fx.program / 'a.txt').write_text('a', encoding='utf-8')
            git(fx.repo, 'add', 'program/a.txt').check_returncode()
            git(fx.repo, 'commit', '-m', 'lane-a').check_returncode()
            git(fx.repo, 'switch', '-c', 'side', fx.base_sha).check_returncode()
            fx.program.mkdir(exist_ok=True)
            (fx.program / 'b.txt').write_text('b', encoding='utf-8')
            git(fx.repo, 'add', 'program/b.txt').check_returncode()
            git(fx.repo, 'commit', '-m', 'lane-b').check_returncode()
            side_sha = fx.head()
            git(fx.repo, 'switch', 'codex/test').check_returncode()
            merge = git(fx.repo, 'merge', '--no-commit', '--no-ff', 'side')
            self.assertEqual(merge.returncode, 0, merge.stderr)
            self.assertTrue((fx.repo / '.git' / 'MERGE_HEAD').exists())
            proc = run_commit(fx, ['-m', 'R2: 合并 side'])
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(git(fx.repo, 'rev-parse', 'HEAD^2').stdout.strip(), side_sha)
            names = git(fx.repo, 'diff', '--name-only', 'HEAD^1', 'HEAD').stdout
            self.assertIn('program/b.txt', names)

    # ---------- 进程中断后接续 ----------

    def test_killed_attempt_resumes_and_reruns_gates(self):
        with fixture() as fx:
            write_owned(fx)
            spy = fx.base / 'spy.log'
            killed = run_commit(fx, explicit_args(), fault='kill_before_commit', spy=spy)
            self.assertEqual(killed.returncode, 137, killed.stderr)
            self.assertEqual(fx.head(), fx.base_sha)
            proc = run_commit(fx, explicit_args(), spy=spy)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertNotEqual(fx.head(), fx.base_sha)
            names = git(fx.repo, 'show', '--name-only', '--format=', 'HEAD').stdout
            self.assertIn('program/' + OWNED, names)
            self.assertEqual(fx.staged_names(), set())
            calls = spy.read_text(encoding='utf-8').split()
            self.assertGreaterEqual(calls.count('attach_evidence'), 2,
                                    '接续必须重跑验收和门禁')

    def test_different_command_runs_independently_after_retry(self):
        with fixture() as fx:
            write_owned(fx)
            killed = run_commit(fx, explicit_args(), fault='kill_before_commit')
            self.assertEqual(killed.returncode, 137, killed.stderr)
            first = run_commit(fx, explicit_args())
            self.assertEqual(first.returncode, 0, first.stderr)
            (fx.program / 'other.txt').write_text('other', encoding='utf-8')
            proc = run_commit(fx, ['-m', 'R2: 另一条命令', 'other.txt'])
            self.assertEqual(proc.returncode, 0, proc.stderr)
            names = git(fx.repo, 'show', '--name-only', '--format=', 'HEAD').stdout
            self.assertIn('program/other.txt', names)
            self.assertNotIn('program/' + OWNED, names)

    # ---------- 证据与工作区漂移 ----------

    def test_workspace_drift_is_reported_and_scene_preserved(self):
        with fixture() as fx:
            write_owned(fx, 'v1')
            run_commit(fx, explicit_args(), fault='kill_before_commit')
            self.assertEqual(fx.head(), fx.base_sha)
            write_owned(fx, 'v2-drift')
            proc = run_commit(fx, explicit_args())
            self.assertNotEqual(proc.returncode, 0)
            self.assertEqual(fx.head(), fx.base_sha)
            self.assertTrue((proc.stdout + proc.stderr).strip(),
                            '漂移必须列出差异')
            self.assertIn('program/' + OWNED, fx.staged_names())

    def test_staged_content_drift_is_reported_and_preserved(self):
        with fixture() as fx:
            write_owned(fx, 'v1')
            run_commit(fx, explicit_args(), fault='kill_before_commit')
            blob = git(fx.repo, 'hash-object', '-w', '--stdin',
                       input_text='injected').stdout.strip()
            git(fx.repo, 'update-index', '--cacheinfo',
                '100644,%s,program/%s' % (blob, OWNED)).check_returncode()
            proc = run_commit(fx, explicit_args())
            self.assertNotEqual(proc.returncode, 0)
            self.assertEqual(fx.head(), fx.base_sha)
            listed = git(fx.repo, 'ls-files', '-s', 'program/' + OWNED).stdout
            self.assertIn(blob, listed, '他人注入的暂存内容必须保留，不得重置')

    def test_foreign_stage_during_retry_is_not_absorbed(self):
        with fixture() as fx:
            write_owned(fx)
            run_commit(fx, explicit_args(), fault='kill_before_commit')
            (fx.repo / 'foreign.txt').write_text('foreign', encoding='utf-8')
            git(fx.repo, 'add', 'foreign.txt').check_returncode()
            proc = run_commit(fx, explicit_args())
            self.assertNotEqual(proc.returncode, 0)
            self.assertEqual(fx.head(), fx.base_sha)
            self.assertIn('foreign.txt', fx.staged_names())

    def test_tool_generated_evidence_drift_is_refused(self):
        with fixture() as fx:
            evidence_dir = fx.program / 'tasks_round' / 'evidence'
            result = fx.program / 'tasks_round' / ('tasks_round_%d_result.md' % ROUND_HIGH)
            result.parent.mkdir(parents=True)
            result.write_text('# R%d 证据漂移用例\n' % ROUND_HIGH, encoding='utf-8')
            write_owned(fx)
            args = ['-m', 'R%d: %s' % (ROUND_HIGH, '证据漂移'), OWNED,
                    'tasks_round/tasks_round_%d_result.md' % ROUND_HIGH]
            killed = run_commit(fx, args, fault='kill_before_commit',
                                evidence_dir=evidence_dir)
            self.assertEqual(killed.returncode, 137, killed.stderr)
            evidence = evidence_dir / ('R%d.json' % ROUND_HIGH)
            self.assertTrue(evidence.is_file(), '门禁必须先生成工具证据')
            evidence.write_text('{"round": %d, "tampered": true}\n' % ROUND_HIGH,
                                encoding='utf-8')
            proc = run_commit(fx, args, evidence_dir=evidence_dir)
            self.assertNotEqual(proc.returncode, 0)
            self.assertEqual(fx.head(), fx.base_sha)
            self.assertIn('tampered', evidence.read_text(encoding='utf-8'),
                          '被改动的证据必须原样保留，不得回写覆盖')

    # ---------- 回执丢失 ----------

    def test_lost_receipt_returns_original_commit_after_head_moves(self):
        with fixture() as fx:
            write_owned(fx)
            run_commit(fx, explicit_args(), fault='kill_after_commit')
            original = fx.head()
            self.assertNotEqual(original, fx.base_sha, '前置条件：提交必须已落地')
            (fx.repo / 'wip.txt').write_text('wip', encoding='utf-8')
            git(fx.repo, 'add', 'wip.txt').check_returncode()
            git(fx.repo, 'commit', '-m', 'wip 后续提交').check_returncode()
            moved = fx.head()
            count = fx.rev_count()
            proc = run_commit(fx, explicit_args())
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn(original[:7], proc.stdout,
                          '必须返回原提交号而不是新提交')
            self.assertEqual(fx.rev_count(), count, '不得重复提交')
            self.assertEqual(fx.head(), moved, 'HEAD 向前移动后不得改写')

    def test_decoy_commit_with_same_round_makes_retry_refuse(self):
        with fixture() as fx:
            write_owned(fx, 'v1')
            run_commit(fx, explicit_args(), fault='kill_after_commit')
            original = fx.head()
            git(fx.repo, 'reset', '--soft', 'HEAD^').check_returncode()
            write_owned(fx, 'decoy')
            git(fx.repo, 'add', 'program/' + OWNED).check_returncode()
            git(fx.repo, 'commit', '-m', BASE_MESSAGE).check_returncode()
            decoy = fx.head()
            self.assertNotEqual(decoy, original)
            write_owned(fx, 'v1')
            git(fx.repo, 'add', 'program/' + OWNED).check_returncode()
            count = fx.rev_count()
            proc = run_commit(fx, explicit_args())
            self.assertNotEqual(proc.returncode, 0,
                                '历史里只有同轮次不同变更树的诱饵提交时必须拒绝')
            self.assertEqual(fx.rev_count(), count)
            self.assertEqual(fx.head(), decoy)

    def test_soft_reset_resume_recommits_cleanly(self):
        with fixture() as fx:
            write_owned(fx)
            run_commit(fx, explicit_args(), fault='kill_after_commit')
            git(fx.repo, 'reset', '--soft', 'HEAD^').check_returncode()
            self.assertEqual(fx.head(), fx.base_sha)
            proc = run_commit(fx, explicit_args())
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(fx.rev_count(), 2, 'base + 恰好一次重提')
            content = git(fx.repo, 'show', 'HEAD:program/' + OWNED).stdout
            self.assertEqual(content, 'owned-v1')

    # ---------- 并发 ----------

    def test_concurrent_executor_does_not_double_commit(self):
        with fixture() as fx:
            write_owned(fx)
            marker = fx.base / 'release.marker'
            first = run_commit(fx, explicit_args(),
                               fault='wait:' + str(marker), popen=True)
            try:
                reached = marker.with_name(marker.name + '.reached')
                deadline = time.time() + 60
                while not reached.exists():
                    self.assertIsNone(first.poll(), '执行者 A 意外退出')
                    self.assertLess(time.time(), deadline, 'A 未到达提交点')
                    time.sleep(0.1)
                second = run_commit(fx, explicit_args(), popen=True)
                try:
                    # 先给 B 进入竞争窗口，再放行 A；无论实现是拒绝、等待还是
                    # 各自提交，最终都必须收敛成恰好一个同轮次提交。
                    time.sleep(8)
                    marker.write_text('go', encoding='utf-8')
                    second.communicate(timeout=180)
                finally:
                    if second.poll() is None:
                        second.kill()
                        second.communicate()
                rc_b = second.returncode
                first.communicate(timeout=60)
                rc_a = first.returncode
            finally:
                if first.poll() is None:
                    first.kill()
                    first.communicate()
                    if not marker.exists():
                        marker.write_text('go', encoding='utf-8')
            self.assertTrue(rc_a == 0 or rc_b == 0,
                            '两个执行者中至少一个应成功（A=%s B=%s）' % (rc_a, rc_b))
            commits = fx.round_commits('R1')
            self.assertEqual(len(commits), 1, '并发重试不得产生第二个同轮次提交')
            content = git(fx.repo, 'show', commits[0] + ':program/' + OWNED).stdout
            self.assertEqual(content, 'owned-v1')


if __name__ == '__main__':
    unittest.main()

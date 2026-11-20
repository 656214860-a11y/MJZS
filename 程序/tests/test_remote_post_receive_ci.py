# -*- coding: utf-8 -*-
"""远端 post-receive CI：ref 过滤、检出克隆、技能包检出、步骤执行、状态落盘、GIT_* 清洗。"""
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

PROGRAM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROGRAM))
sys.path.insert(0, str(PROGRAM / 'scripts'))
spec = importlib.util.spec_from_file_location(
    'remote_post_receive_ci', PROGRAM / '维护记录' / '基准脚本' / 'remote_post_receive_ci.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
import local_ci  # noqa: E402


def _git(repo: Path, *args) -> None:
    done = subprocess.run(['git', '-C', str(repo), *args], capture_output=True, text=True)
    if done.returncode != 0:
        raise AssertionError('git %s 失败：%s' % (args, done.stderr.strip()))


def _init_repo(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    _git(path, 'init', '-q')
    _git(path, 'config', 'user.email', 't@example.com')
    _git(path, 'config', 'user.name', 't')
    (path / 'a.txt').write_text('hello', encoding='utf-8')
    _git(path, 'add', 'a.txt')
    _git(path, 'commit', '-qm', 'init')


class CiRefTests(unittest.TestCase):
    def test_master_main_codex_accepted(self):
        for ref in ('refs/heads/master', 'refs/heads/main', 'refs/heads/codex/wip-R1',
                    'refs/heads/codex/t1-ci'):
            self.assertTrue(mod.ci_ref(ref), ref)

    def test_other_refs_rejected(self):
        for ref in ('refs/heads/feature-x', 'refs/heads/release/1.0',
                    'refs/tags/v1', 'refs/heads/codexx/a'):
            self.assertFalse(mod.ci_ref(ref), ref)


class RefSlugTests(unittest.TestCase):
    def test_slug(self):
        self.assertEqual(mod.ref_slug('refs/heads/master'), 'master')
        self.assertEqual(mod.ref_slug('refs/heads/codex/wip-R2907'), 'codex-wip-R2907')


class CleanEnvTests(unittest.TestCase):
    def test_git_vars_stripped(self):
        with mock.patch.dict(os.environ, {'GIT_DIR': '/x.git', 'GIT_WORK_TREE': '/x',
                                          'HOME': '/home/u', 'PATH': '/bin'}):
            env = mod._clean_env()
        self.assertNotIn('GIT_DIR', env)
        self.assertNotIn('GIT_WORK_TREE', env)
        self.assertEqual(env['HOME'], '/home/u')
        self.assertEqual(env['DRAMA_SUPPRESS_MODAL'], '1')

    def test_extra_merged(self):
        env = mod._clean_env({'PYTHONPATH': '/a'})
        self.assertEqual(env['PYTHONPATH'], '/a')


class CheckoutRefTests(unittest.TestCase):
    def test_clone_and_checkout(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            src = root / 'src'
            _init_repo(src)
            bare = root / 'bare.git'
            _git(src, 'clone', '--bare', '-q', str(src), str(bare))
            workdir = root / 'work' / 'master'
            self.assertIsNone(mod.checkout_ref(str(bare), 'HEAD', workdir))
            self.assertTrue((workdir / '.git').exists())
            self.assertTrue((workdir / 'a.txt').is_file())

    def test_bad_sha_reported(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            src = root / 'src'
            _init_repo(src)
            bare = root / 'bare.git'
            _git(src, 'clone', '--bare', '-q', str(src), str(bare))
            problem = mod.checkout_ref(str(bare), 'f' * 40, root / 'w')
            self.assertIn('checkout', problem)


class ProvisionTests(unittest.TestCase):
    def test_missing_registry_is_noop(self):
        with tempfile.TemporaryDirectory() as folder:
            program = Path(folder)
            self.assertEqual(mod.provision_packages(program), [])

    def test_history_backfilled(self):
        with tempfile.TemporaryDirectory() as folder:
            program = Path(folder)
            (program / '维护记录').mkdir()
            mod.provision_ignored_inputs(program)
            self.assertEqual(json.loads((program / '维护记录' / '基准历史.json')
                                        .read_text(encoding='utf-8')), [])
            # 已存在不覆盖
            (program / '维护记录' / '基准历史.json').write_text('[{"x":1}]', encoding='utf-8')
            mod.provision_ignored_inputs(program)
            self.assertEqual(json.loads((program / '维护记录' / '基准历史.json')
                                        .read_text(encoding='utf-8')), [{'x': 1}])

    def test_arch_targets_exclude_platform_boundary(self):
        with tempfile.TemporaryDirectory() as folder:
            program = Path(folder)
            arch = program / 'tests' / 'architecture'
            arch.mkdir(parents=True)
            for name in ('test_a.py', 'test_b.py', 'test_rule_guard_map.py',
                         'test_skill_package_pins.py', 'test_source_text_contracts.py',
                         'test_service_return_contract.py', 'test_unification_ratchet.py',
                         '_scan.py', 'notes.txt'):
                (arch / name).write_text('', encoding='utf-8')
            targets = mod.arch_targets(program)
            self.assertIn('tests.architecture.test_a', targets)
            self.assertIn('tests.architecture.test_b', targets)
            self.assertNotIn('tests.architecture.test_rule_guard_map', targets)
            self.assertNotIn('tests.architecture.test_skill_package_pins', targets)
            self.assertIn(
                'tests.architecture.test_source_text_contracts.SelftestRunnerContracts', targets)
            self.assertIn(
                'tests.architecture.test_unification_ratchet.UnificationRatchetTests'
                '.test_l2_formal_publish_debt_is_a_nonincreasing_subset', targets)
            self.assertNotIn(
                'tests.architecture.test_unification_ratchet.UnificationRatchetTests'
                '.test_bare_json_load_debt_is_a_nonincreasing_subset', targets)
            self.assertEqual(len(targets), 2 + 1 + 7 + 3)  # a,b + source_text + service 7 + unification 3


class RunStepTests(unittest.TestCase):
    def test_writes_log_and_returns_code(self):
        program = Path(tempfile.mkdtemp())
        log_path = program / 'ci.log'
        with log_path.open('w', encoding='utf-8') as log:
            fake = mock.Mock(returncode=0)
            with mock.patch.object(mod.subprocess, 'run', return_value=fake) as run:
                code, seconds = mod.run_step('静态门禁', ['python3', '-V'], program, log)
        self.assertEqual(code, 0)
        self.assertGreaterEqual(seconds, 0)
        env = run.call_args.kwargs['env']
        self.assertIn(str(program), env['PYTHONPATH'])
        self.assertNotIn('GIT_DIR', env)
        self.assertIn('静态门禁', log_path.read_text(encoding='utf-8'))

    def test_timeout_recorded(self):
        program = Path(tempfile.mkdtemp())
        with (program / 'ci.log').open('w', encoding='utf-8') as log:
            with mock.patch.object(mod.subprocess, 'run',
                                   side_effect=mod.subprocess.TimeoutExpired('x', 1)):
                code, _ = mod.run_step('架构门禁', ['python3'], program, log)
        self.assertIsInstance(code, str)
        self.assertIn('timeout', code)


class RunCiTests(unittest.TestCase):
    def _env(self, folder):
        work = Path(folder) / 'work'
        results = Path(folder) / 'results'
        return mock.patch.multiple(mod, CI_WORK_ROOT=work, CI_RESULT_DIR=results), work, results

    def test_checkout_failure_marks_error(self):
        with tempfile.TemporaryDirectory() as folder:
            patcher, _work, results = self._env(folder)
            with patcher, mock.patch.object(mod, 'checkout_ref',
                                            return_value='clone 失败'):
                status = mod.run_ci('/repo.git', 'refs/heads/master', 'abc123')
            self.assertFalse(status['ok'])
            self.assertEqual(status['error'], 'clone 失败')
            self.assertTrue((results / 'last_ci_status.json').is_file())
            payload = json.loads((results / 'master.status.json').read_text(encoding='utf-8'))
            self.assertEqual(payload['ref'], 'refs/heads/master')

    def test_green_run_records_steps(self):
        with tempfile.TemporaryDirectory() as folder:
            patcher, work, results = self._env(folder)

            def fake_checkout(git_dir, sha, workdir):
                program = workdir / '程序'
                program.mkdir(parents=True)
                (program / 'tests' / 'architecture').mkdir(parents=True)
                (program / 'tests' / 'architecture' / 'test_x.py').write_text('', encoding='utf-8')
                return None

            with patcher, \
                 mock.patch.object(mod, 'checkout_ref', side_effect=fake_checkout), \
                 mock.patch.object(mod, 'provision_packages', return_value=[]), \
                 mock.patch.object(mod, 'provision_ignored_inputs'), \
                 mock.patch.object(mod, 'run_step', side_effect=[(0, 1.0), (0, 2.0)]):
                status = mod.run_ci('/repo.git', 'refs/heads/master', 'abc123')
            self.assertTrue(status['ok'])
            self.assertEqual(len(status['steps']), 2)
            logs = list(results.glob('*.log'))
            self.assertEqual(len(logs), 1)
            self.assertIn('ref=refs/heads/master', logs[0].read_text(encoding='utf-8'))

    def test_first_step_failure_stops(self):
        with tempfile.TemporaryDirectory() as folder:
            patcher, _work, _results = self._env(folder)

            def fake_checkout(git_dir, sha, workdir):
                (workdir / '程序').mkdir(parents=True)
                return None

            with patcher, \
                 mock.patch.object(mod, 'checkout_ref', side_effect=fake_checkout), \
                 mock.patch.object(mod, 'provision_packages', return_value=[]), \
                 mock.patch.object(mod, 'provision_ignored_inputs'), \
                 mock.patch.object(mod, 'run_step', return_value=(1, 0.5)) as step:
                status = mod.run_ci('/repo.git', 'refs/heads/codex/x', 'abc')
            self.assertFalse(status['ok'])
            self.assertEqual(step.call_count, 1)
            self.assertEqual(len(status['steps']), 1)


class StaticGateListTests(unittest.TestCase):
    """R2-G2：本机与远端两份静态门禁清单保持一致；文案规则测试在清单里。"""

    def test_local_and_remote_static_gate_tests_are_identical(self):
        self.assertEqual(tuple(local_ci.STATIC_GATE_TESTS), tuple(mod.STATIC_GATE_TESTS))

    def test_copy_rules_is_in_static_gate(self):
        self.assertIn('tests.test_copy_rules', local_ci.STATIC_GATE_TESTS)


class MainTests(unittest.TestCase):
    def test_only_ci_refs_trigger(self):
        updates = [
            '0' * 40 + ' ' + 'a' * 40 + ' refs/heads/master\n',
            '0' * 40 + ' ' + 'b' * 40 + ' refs/heads/feature\n',
            '0' * 40 + ' ' + '0' * 40 + ' refs/heads/codex/dead\n',
            '0' * 40 + ' ' + 'c' * 40 + ' refs/heads/codex/live\n',
        ]
        stdin = io.StringIO(''.join(updates))
        with mock.patch('sys.stdin', stdin), \
             mock.patch.object(mod, 'run_ci', return_value={'ok': True, 'seconds': 0.1,
                                                            'log': '/tmp/x.log'}) as ci, \
             mock.patch.object(mod, '_locked') as locked:
            locked.return_value.__enter__ = lambda s: s
            locked.return_value.__exit__ = lambda s, *a: False
            rc = mod.main()
        self.assertEqual(rc, 0)
        refs = [call.args[1] for call in ci.call_args_list]
        self.assertEqual(refs, ['refs/heads/master', 'refs/heads/codex/live'])


if __name__ == '__main__':
    unittest.main()

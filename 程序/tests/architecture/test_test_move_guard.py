"""测试搬家轮守卫（规则 16）：搬家只许移动测试文件和修 import，改逻辑、断言或增删测试一律不通过。"""
from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.architecture._scan import ROOT

SPEC = importlib.util.spec_from_file_location('test_move_audit_for_tests', ROOT / 'scripts' / 'test_move_audit.py')
AUDIT = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = AUDIT
SPEC.loader.exec_module(AUDIT)

ORIGINAL = 'import unittest\nfrom pet import thing\n\n\nclass T(unittest.TestCase):\n    def test_a(self):\n        self.assertEqual(thing(1), 2)\n'


def git(root, *args):
    env = dict(os.environ, GIT_AUTHOR_NAME='t', GIT_AUTHOR_EMAIL='t@t', GIT_COMMITTER_NAME='t', GIT_COMMITTER_EMAIL='t@t')
    done = subprocess.run(['git', *args], cwd=root, env=env, capture_output=True, text=True, encoding='utf-8')
    assert done.returncode == 0, done.stderr
    return done.stdout.strip()


class TestMoveGuardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        git(self.root, 'init', '-q', '-b', 'master')
        self.write('程序/test_old.py', ORIGINAL)
        git(self.root, 'add', '-A')
        git(self.root, 'commit', '-q', '-m', 'base')

    def write(self, name, text):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')

    def staged_problems(self):
        git(self.root, 'add', '-A')
        return AUDIT.audit_staged(self.root)

    def test_pure_move_passes(self):
        (self.root / '程序' / 'tests').mkdir()
        git(self.root, 'mv', '程序/test_old.py', '程序/tests/test_old.py')
        self.assertEqual(self.staged_problems(), [])

    def test_move_with_only_import_changes_passes(self):
        (self.root / '程序' / 'tests').mkdir()
        git(self.root, 'mv', '程序/test_old.py', '程序/tests/test_old.py')
        self.write('程序/tests/test_old.py', ORIGINAL.replace('from pet import thing', 'from pet.core import thing'))
        self.assertEqual(self.staged_problems(), [])

    def test_changed_assertion_is_rejected(self):
        (self.root / '程序' / 'tests').mkdir()
        git(self.root, 'mv', '程序/test_old.py', '程序/tests/test_old.py')
        self.write('程序/tests/test_old.py', ORIGINAL.replace('thing(1), 2', 'thing(1), 3'))
        problems = self.staged_problems()
        self.assertEqual(len(problems), 1)
        self.assertIn('除 import 外', problems[0])

    def test_deleted_assertion_is_rejected_even_without_a_move(self):
        self.write('程序/test_old.py', ORIGINAL.replace('        self.assertEqual(thing(1), 2)\n', '        pass\n'))
        self.assertEqual(len(self.staged_problems()), 1)

    def test_adding_or_deleting_test_files_is_rejected(self):
        (self.root / '程序' / 'tests').mkdir()
        self.write('程序/tests/test_new.py', ORIGINAL)
        self.assertIn('新增', self.staged_problems()[0])
        git(self.root, 'reset', '-q')
        (self.root / '程序' / 'tests' / 'test_new.py').unlink()
        (self.root / '程序' / 'test_old.py').unlink()
        self.assertIn('删除', self.staged_problems()[0])

    def test_only_a_subject_that_starts_with_the_marker_is_a_move_round(self):
        self.assertTrue(AUDIT.is_move_round('R12: 测试搬家：迁入 tests/'))
        self.assertTrue(AUDIT.is_move_round('R12-FAIL: 测试搬家'))
        self.assertFalse(AUDIT.is_move_round('R12: 补测试搬家守卫'))
        self.assertFalse(AUDIT.is_move_round('R12: 普通改动\n\n正文提到测试搬家'))

    def test_helper_scripts_named_test_are_not_test_files(self):
        self.assertFalse(AUDIT.is_test_path('程序/scripts/test_move_audit.py'))
        self.assertTrue(AUDIT.is_test_path('程序/tests/test_a.py'))
        self.assertTrue(AUDIT.is_test_path('程序/test_legacy.py'))

    def test_non_test_files_are_not_audited(self):
        self.write('程序/a.py', 'x = 1\n')
        self.assertEqual(self.staged_problems(), [])

    def test_audit_commit_matches_the_staged_verdict(self):
        self.write('程序/test_old.py', ORIGINAL.replace('thing(1), 2', 'thing(1), 3'))
        git(self.root, 'add', '-A')
        git(self.root, 'commit', '-q', '-m', 'R1: 测试搬家')
        sha = git(self.root, 'rev-parse', 'HEAD')
        self.assertEqual(len(AUDIT.audit_commit(self.root, sha)), 1)

    def test_every_real_move_round_commit_in_history_passes(self):
        _code, rows = AUDIT._git(ROOT.parent, 'log', '--grep=' + AUDIT.MARKER, '--format=%H %s', '--no-merges')
        shas = [row.split(' ', 1)[0] for row in rows.splitlines() if AUDIT.is_move_round(row.split(' ', 1)[-1])]
        for sha in shas:
            with self.subTest(sha=sha[:10]):
                self.assertEqual(AUDIT.audit_commit(ROOT.parent, sha), [])


if __name__ == '__main__':
    unittest.main()

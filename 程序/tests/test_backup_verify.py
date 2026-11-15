# -*- coding: utf-8 -*-
"""scripts/backup_verify.py：bundle 逐份 verify、目录缺失/为空判负、坏包检出。"""
import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

PROGRAM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROGRAM))
spec = importlib.util.spec_from_file_location('backup_verify', PROGRAM / 'scripts' / 'backup_verify.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def _git(repo: Path, *args) -> None:
    done = subprocess.run(['git', '-C', str(repo), *args], capture_output=True, text=True)
    if done.returncode != 0:
        raise AssertionError('git %s 失败：%s' % (args, done.stderr.strip()))


def _make_bundle(directory: Path, name: str = 'manju-2026-01-01.bundle') -> Path:
    """在临时仓库里造一个真实 bundle，返回其路径。"""
    repo = directory / ('src-' + name.removesuffix('.bundle'))
    repo.mkdir()
    _git(repo, 'init', '-q')
    _git(repo, 'config', 'user.email', 't@example.com')
    _git(repo, 'config', 'user.name', 't')
    (repo / 'a.txt').write_text('hello', encoding='utf-8')
    _git(repo, 'add', 'a.txt')
    _git(repo, 'commit', '-qm', 'init')
    bundle = directory / name
    _git(repo, 'bundle', 'create', str(bundle), '--all')
    return bundle


class VerifyBundleTests(unittest.TestCase):
    def test_real_bundle_passes(self):
        with tempfile.TemporaryDirectory() as folder:
            bundle = _make_bundle(Path(folder))
            ok, _detail = mod.verify_bundle(bundle)
            self.assertTrue(ok)

    def test_corrupt_bundle_fails(self):
        with tempfile.TemporaryDirectory() as folder:
            bad = Path(folder) / 'bad.bundle'
            bad.write_bytes(b'not a bundle')
            ok, _detail = mod.verify_bundle(bad)
            self.assertFalse(ok)

    def test_git_missing_returns_failure(self):
        with tempfile.TemporaryDirectory() as folder:
            bundle = _make_bundle(Path(folder))
            with mock.patch.object(mod.subprocess, 'run', side_effect=OSError('no git')):
                ok, detail = mod.verify_bundle(bundle)
            self.assertFalse(ok)
            self.assertIn('git', detail)


class MainTests(unittest.TestCase):
    def test_missing_directory_returns_2(self):
        self.assertEqual(mod.main([str(Path(tempfile.gettempdir()) / '不存在的目录xyz')]), 2)

    def test_empty_directory_returns_1(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertEqual(mod.main([folder]), 1)

    def test_all_good_returns_0(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            _make_bundle(directory, 'manju-2026-01-01.bundle')
            _make_bundle(directory, 'manju-2026-01-08.bundle')
            self.assertEqual(mod.main([str(directory)]), 0)

    def test_one_bad_returns_1(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            _make_bundle(directory, 'manju-2026-01-01.bundle')
            (directory / 'manju-2026-01-08.bundle').write_bytes(b'corrupt')
            self.assertEqual(mod.main([str(directory)]), 1)

    def test_env_var_directory(self):
        with tempfile.TemporaryDirectory() as folder:
            _make_bundle(Path(folder))
            with mock.patch.dict('os.environ', {'MANJU_BUNDLE_DIR': folder}):
                self.assertEqual(mod.main([]), 0)

    def test_guess_repo_finds_sibling_bare(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            backups = root / 'backups'
            backups.mkdir()
            (root / 'manju-assistant.git').mkdir()
            self.assertEqual(mod.guess_repo(backups), str(root / 'manju-assistant.git'))
            self.assertIsNone(mod.guess_repo(root))


if __name__ == '__main__':
    unittest.main()

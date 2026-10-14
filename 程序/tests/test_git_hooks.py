"""协作 Git hooks 的安装与核心拒绝规则。"""
from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PROGRAM = Path(__file__).resolve().parent.parent
SCRIPTS = PROGRAM / "维护记录" / "基准脚本"
HOOKS = SCRIPTS / "hooks"
INSTALLER = SCRIPTS / "install_git_hooks.py"
# Windows 用 Git for Windows 自带的 sh；其他平台用 PATH 上的 sh，用例不再只能在 Windows 跑。
_WINDOWS_SH = Path(r"C:\Program Files\Git\bin\sh.exe")
SH = _WINDOWS_SH if _WINDOWS_SH.exists() else Path(shutil.which("sh") or _WINDOWS_SH)
spec = importlib.util.spec_from_file_location("install_git_hooks_for_tests", INSTALLER)
install_git_hooks = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = install_git_hooks
spec.loader.exec_module(install_git_hooks)


class GitHookTests(unittest.TestCase):
    def test_precommit_blocks_full_safe_lock_even_without_staged_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            subprocess.run(["git", "init", "--quiet"], cwd=root, check=True)
            lock = root / '.git' / 'full-safe-selftest.lock'
            lock.write_text('{"pid": 123}', encoding='utf-8')
            self.assertNotEqual(self.run_hook(HOOKS / 'pre-commit', cwd=root).returncode, 0)
            lock.unlink()
            self.assertEqual(self.run_hook(HOOKS / 'pre-commit', cwd=root).returncode, 0)

    def run_hook(self, hook: Path, *args: str, cwd: Path | None = None, env: dict | None = None):
        return subprocess.run([str(SH), str(hook), *args], cwd=cwd, text=True,
                              capture_output=True, env=env, check=False)

    def test_installer_copies_executable_hooks(self):
        with tempfile.TemporaryDirectory() as temporary:
            installed = install_git_hooks.install(Path(temporary))
            self.assertEqual([path.name for path in installed], ["commit-msg", "pre-commit"])
            self.assertTrue(all(path.exists() for path in installed))

    def test_installer_writes_lf_even_from_crlf_sources(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "source"
            source.mkdir()
            for name in install_git_hooks.HOOKS:
                (source / name).write_bytes(b"#!/bin/sh\r\ncase x in\r\n  x) ;;\r\nesac\r\n")
            original = install_git_hooks.SOURCE
            install_git_hooks.SOURCE = source
            try:
                installed = install_git_hooks.install(Path(temporary) / "common")
            finally:
                install_git_hooks.SOURCE = original
            for path in installed:
                self.assertNotIn(b"\r\n", path.read_bytes())

    def test_commit_message_requires_round_prefix(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            subprocess.run(["git", "init", "--quiet"], cwd=root, check=True)
            counter = root / ".git" / "round-counter.json"
            counter.write_text('{"last_claimed": 871}\n', encoding="utf-8")
            message = root / "message"
            message.write_text("update files\n", encoding="utf-8")
            self.assertNotEqual(self.run_hook(HOOKS / "commit-msg", str(message), cwd=root).returncode, 0)
            message.write_text("R871: enforce hooks\n", encoding="utf-8")
            self.assertEqual(self.run_hook(HOOKS / "commit-msg", str(message), cwd=root).returncode, 0)
            message.write_text("R871-FAIL: record blocker\n", encoding="utf-8")
            self.assertEqual(self.run_hook(HOOKS / "commit-msg", str(message), cwd=root).returncode, 0)

    def test_commit_message_rejects_stale_or_nonancestor_round(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            subprocess.run(["git", "init", "--quiet"], cwd=root, check=True)
            subprocess.run(["git", "-c", "user.name=Hook Test", "-c", "user.email=hook@example.invalid",
                            "commit", "--allow-empty", "-m", "seed"], cwd=root, check=True)
            message = root / "message"
            counter = root / ".git" / "round-counter.json"
            counter.write_text('{"last_claimed": 872}\n', encoding="utf-8")
            message.write_text("R871: stale\n", encoding="utf-8")
            stale = self.run_hook(HOOKS / "commit-msg", str(message), cwd=root)
            self.assertNotEqual(stale.returncode, 0)
            self.assertIn("R871 不等于中央已领取轮次 R872", stale.stderr)
            subprocess.run(["git", "checkout", "-q", "-b", "other"], cwd=root, check=True)
            subprocess.run(["git", "-c", "user.name=Hook Test", "-c", "user.email=hook@example.invalid",
                            "commit", "--allow-empty", "-m", "R872: already used"], cwd=root, check=True)
            subprocess.run(["git", "checkout", "-q", "master"], cwd=root, check=True)
            message.write_text("R872-FAIL: duplicate\n", encoding="utf-8")
            duplicate = self.run_hook(HOOKS / "commit-msg", str(message), cwd=root)
            self.assertNotEqual(duplicate.returncode, 0)
            self.assertIn("非祖先分支使用", duplicate.stderr)

    def test_precommit_requires_explicit_allowlist_for_program_code(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            subprocess.run(["git", "init", "--quiet"], cwd=root, check=True)
            path = root / "程序" / "module.py"
            path.parent.mkdir()
            path.write_text("x = 1\n", encoding="utf-8")
            subprocess.run(["git", "add", "程序/module.py"], cwd=root, check=True)
            rejected = self.run_hook(HOOKS / "pre-commit", cwd=root)
            self.assertNotEqual(rejected.returncode, 0)
            environment = os.environ | {"CODEX_STAGE_ALLOWLIST": "程序/module.py"}
            self.assertEqual(self.run_hook(HOOKS / "pre-commit", cwd=root, env=environment).returncode, 0)

    def test_precommit_blocks_project_status_off_master(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            subprocess.run(["git", "init", "--quiet"], cwd=root, check=True)
            subprocess.run(["git", "checkout", "-q", "-b", "topic"], cwd=root, check=True)
            path = root / "程序" / "project_status.md"
            path.parent.mkdir()
            path.write_text("status\n", encoding="utf-8")
            subprocess.run(["git", "add", "程序/project_status.md"], cwd=root, check=True)
            self.assertNotEqual(self.run_hook(HOOKS / "pre-commit", cwd=root).returncode, 0)


if __name__ == "__main__":
    unittest.main()

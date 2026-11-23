"""A15：随附解释器与 FFmpeg 二进制必须共同进入来源/许可证/摘要锁。"""
import contextlib
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import tools_lock


class ToolsLockTests(unittest.TestCase):
    def test_build_covers_all_bundled_executables_with_supply_chain_fields(self):
        entries = tools_lock.build()['tools']
        self.assertEqual(set(entries), {
            '运行环境/Python/python.exe',
            '运行环境/ffmpeg/bin/ffmpeg.exe',
            '运行环境/ffmpeg/bin/ffprobe.exe',
        })
        for name, entry in entries.items():
            with self.subTest(name=name):
                self.assertRegex(entry['sha256'], r'^[0-9a-f]{64}$')
                self.assertGreater(entry['bytes'], 0)
                self.assertTrue(entry['version'])
                self.assertTrue(entry['source'].startswith('https://'))
                self.assertTrue(entry['license'])


class BundleVerifyTests(unittest.TestCase):
    """随包齐全检查：ffmpeg/ffprobe 存在且 sha256 与锁一致，ffmpeg/LICENSE 存在（REL-01）。"""

    FFMPEG = '运行环境/ffmpeg/bin/ffmpeg.exe'
    FFPROBE = '运行环境/ffmpeg/bin/ffprobe.exe'
    LICENSE = '运行环境/ffmpeg/LICENSE'
    FIX = '从备份拷回或重新下载后运行 tools_lock.py --check'

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.lock = {'tools': {}}

    def place(self, name, data):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def register(self, name, data):
        self.place(name, data)
        self.lock['tools'][name] = {'sha256': hashlib.sha256(data).hexdigest()}

    def complete_bundle(self):
        self.register(self.FFMPEG, b'ffmpeg-bytes')
        self.register(self.FFPROBE, b'ffprobe-bytes')
        self.place(self.LICENSE, b'GPL-3.0')

    def resolver(self, name):
        return self.root / name

    def problems(self):
        return tools_lock.bundle_problems(self.lock, resolver=self.resolver)

    def run_cli(self, write_lock=True):
        lock_path = self.root / 'external_tools.lock.json'
        if write_lock:
            lock_path.write_text(json.dumps(self.lock), encoding='utf-8')
        err = io.StringIO()
        with patch.object(tools_lock, 'LOCK', lock_path), \
                patch.object(tools_lock, '_resolve', self.resolver), \
                contextlib.redirect_stderr(err):
            status = tools_lock.main(['--verify-bundle'])
        return status, err.getvalue(), lock_path

    def test_complete_bundle_has_no_problems(self):
        self.complete_bundle()
        self.assertEqual(self.problems(), [])

    def test_missing_executable_reports_item_and_expected_path(self):
        self.complete_bundle()
        (self.root / self.FFPROBE).unlink()
        problems = self.problems()
        self.assertEqual(len(problems), 1)
        self.assertIn(self.FFPROBE, problems[0])
        self.assertIn(str(self.root / self.FFPROBE), problems[0])

    def test_sha256_mismatch_reports_item_and_expected_path(self):
        self.complete_bundle()
        self.place(self.FFMPEG, b'tampered')
        problems = self.problems()
        self.assertEqual(len(problems), 1)
        self.assertIn(self.FFMPEG, problems[0])
        self.assertIn('sha256', problems[0])
        self.assertIn(str(self.root / self.FFMPEG), problems[0])

    def test_missing_license_reports_item_and_expected_path(self):
        self.complete_bundle()
        (self.root / self.LICENSE).unlink()
        problems = self.problems()
        self.assertEqual(len(problems), 1)
        self.assertIn(self.LICENSE, problems[0])
        self.assertIn(str(self.root / self.LICENSE), problems[0])

    def test_verify_bundle_complete_exits_zero(self):
        self.complete_bundle()
        status, err, _ = self.run_cli()
        self.assertEqual(status, 0)
        self.assertEqual(err, '')

    def test_verify_bundle_failure_is_actionable(self):
        self.complete_bundle()
        (self.root / self.LICENSE).unlink()
        status, err, _ = self.run_cli()
        self.assertEqual(status, 1)
        self.assertIn(self.LICENSE, err)
        self.assertIn(str(self.root / self.LICENSE), err)
        self.assertIn(self.FIX, err)

    def test_verify_bundle_missing_lock_fails_without_creating_it(self):
        status, err, lock_path = self.run_cli(write_lock=False)
        self.assertEqual(status, 1)
        self.assertIn(self.FIX, err)
        self.assertFalse(lock_path.is_file())


if __name__ == '__main__':
    unittest.main()

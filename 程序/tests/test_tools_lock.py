"""A15：随附解释器与 FFmpeg 二进制必须共同进入来源/许可证/摘要锁。"""
import unittest

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


if __name__ == '__main__':
    unittest.main()

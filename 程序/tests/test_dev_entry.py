"""scripts/dev.py 只是调度表：每个子命令指向的脚本必须真实存在，未知子命令返回 2。"""
import sys
import unittest
from pathlib import Path

PROGRAM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROGRAM / 'scripts'))
import dev  # noqa: E402


class DevEntryTests(unittest.TestCase):
    def test_every_command_target_exists(self):
        for name, (target, note) in dev.COMMANDS.items():
            self.assertTrue((PROGRAM / target[0]).is_file(), f'{name} -> {target[0]}')
            self.assertTrue(note)

    def test_unknown_command_is_rejected_and_listing_is_ok(self):
        self.assertEqual(dev.main(['nope']), 2)
        self.assertEqual(dev.main([]), 0)

    def test_claude_md_documents_the_entry(self):
        text = (PROGRAM.parent / 'CLAUDE.md').read_text(encoding='utf-8')
        self.assertIn(r'scripts\dev.py', text)


if __name__ == '__main__':
    unittest.main()

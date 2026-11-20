"""版本号唯一来源 app_metadata.VERSION；更新记录必须有同名小节，启动日志带版本与提交号。"""
import re
import unittest
from pathlib import Path

import infra.app_logging as app_logging
from contract import app_metadata

PROGRAM = Path(__file__).resolve().parents[1]


class VersionRecordTests(unittest.TestCase):
    def test_changelog_has_section_for_current_version(self):
        text = (PROGRAM / 'CHANGELOG.md').read_text(encoding='utf-8')
        self.assertRegex(text, r'(?m)^## ' + re.escape(app_metadata.VERSION) + r'\s*$')

    def test_build_commit_is_short_hash_or_empty(self):
        value = app_logging.build_commit()
        self.assertRegex(value, r'^(?:[0-9a-f]{10})?$')

    def test_startup_line_carries_version_and_commit(self):
        source = Path(app_logging.__file__).read_text(encoding='utf-8')
        self.assertIn('VERSION', source)
        self.assertIn('build_commit()', source)


if __name__ == '__main__':
    unittest.main()

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

    def test_release_checklist_points_at_changelog(self):
        """REL-02：检查单里的版本记录文件是 CHANGELOG.md，不是已撤销的 更新记录.md。"""
        text = (PROGRAM / 'docs' / 'process' / '发布检查单.md').read_text(encoding='utf-8')
        self.assertNotIn('更新记录.md', text)
        self.assertIn('CHANGELOG.md', text)

    def test_release_checklist_starts_with_release_gate(self):
        """REL-02：检查单第一节改为先运行 dev.py release-gate。"""
        text = (PROGRAM / 'docs' / 'process' / '发布检查单.md').read_text(encoding='utf-8')
        section = text.split('## 1.', 1)[1].split('## 2.', 1)[0]
        self.assertIn('release-gate', section)

    def test_release_checklist_installer_claim_matches_repo(self):
        """REL-02：仓库根有 reorganize_install.py，检查单不得声称仓库里没有。"""
        text = (PROGRAM / 'docs' / 'process' / '发布检查单.md').read_text(encoding='utf-8')
        self.assertNotIn('没有 `install_release.py` 与 `reorganize_install.py`', text)
        self.assertTrue((PROGRAM.parent / 'reorganize_install.py').is_file(),
                        'reorganize_install.py 在仓库根')

    def test_version_format_is_v_major_minor(self):
        """REL-02：VERSION 形如 V<主>.<次>，门禁按 VERSION = '…' 口径解析。"""
        self.assertRegex(app_metadata.VERSION, r'^V\d+\.\d+$')

    def test_readme_version_tokens_match_metadata(self):
        """REL-02：README 里的 V主.次 字样必须与 VERSION 一致（门禁版本项同口径）。"""
        text = (PROGRAM / 'README.md').read_text(encoding='utf-8')
        self.assertEqual(set(re.findall(r'V\d+\.\d+', text)), {app_metadata.VERSION})

    def test_install_info_json_is_not_tracked(self):
        """REL-02：安装信息.json 是安装残留、不入库，门禁将其排除在版本比对外（R1460）。"""
        gitignore = (PROGRAM.parent / '.gitignore').read_text(encoding='utf-8')
        self.assertIn('安装信息.json', gitignore)


if __name__ == '__main__':
    unittest.main()

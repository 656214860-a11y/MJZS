"""分发清单必须完整覆盖开发目录，且构建出的副本能用自带解释器导入主入口。"""
import sys
import unittest
from pathlib import Path

PROGRAM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROGRAM / 'scripts'))
import distribution_build  # noqa: E402
import distribution_selfcheck  # noqa: E402


class DistributionSelfCheckTests(unittest.TestCase):
    def test_manifest_covers_every_file(self):
        undecided = distribution_build.plan(distribution_build.ROOT)['undecided']
        self.assertEqual(undecided, [], '新增文件必须在 distribution_manifest.md 里声明保留或排除')

    def test_git_pointer_file_of_a_worktree_is_always_excluded(self):
        # 干净检出（.wt/ci）里 .git 是文件而非目录，曾导致后台全量红。
        self.assertIn('.git', distribution_build.ALWAYS_EXCLUDE)
        self.assertTrue(distribution_build.pattern_regex('.git').match('.git'))

    def test_built_copy_imports_entry_modules(self):
        self.assertEqual(distribution_selfcheck.run(), [])


if __name__ == '__main__':
    unittest.main()

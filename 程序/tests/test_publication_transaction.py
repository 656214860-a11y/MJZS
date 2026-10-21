"""发布事务：提交之后的目录清理失败，不能让调用方把已落盘的成果当成发布失败（R1777 审计）。"""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from agent import core, publication


class CommitCleanupTests(unittest.TestCase):
    @staticmethod
    def _transaction_dirs(root):
        return [item for item in root.iterdir() if item.is_dir()]

    def test_cleanup_failure_after_commit_is_not_a_publish_failure(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / 'tx'
            target = Path(folder) / 'result.json'
            target.write_text('old', encoding='utf-8')
            staged = Path(folder) / 'result.json.tmp'
            real_discard = publication._discard
            calls = []

            def flaky_discard(path):
                calls.append(path)
                if len(calls) == 1:
                    raise OSError('file in use')
                return real_discard(path)

            with mock.patch.object(publication, 'ROOT', root), \
                 mock.patch.object(publication, '_discard', side_effect=flaky_discard):
                with publication.transaction():
                    staged.write_text('new', encoding='utf-8')
                    core.replace(staged, target)  # 提交后清理失败，上面不应抛
                self.assertEqual(target.read_text(encoding='utf-8'), 'new')
                self.assertEqual(len(self._transaction_dirs(root)), 1, '残留的已提交目录等下次访问清理')
                with publication.access():
                    pass
                self.assertEqual(self._transaction_dirs(root), [])
                self.assertEqual(target.read_text(encoding='utf-8'), 'new', '已提交成果不被回滚')


if __name__ == '__main__':
    unittest.main()

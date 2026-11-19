"""R2192：成果发布事务少等落盘，回滚保证不变。

覆盖一份文件的事务原先要等 5 次 fsync：开事务写空日志、正文临时文件、复制旧版本、登记后
重写日志、提交写 committed（本机 D 盘同一时段实测约 115–144 ms）。现在待回滚日志推迟到第一次
登记才写；同卷的旧版本用硬链接保住（替换只改目录项，旧内容留在链接上），建不了链接（跨卷、
FAT）才复制并落盘；提交改成删掉日志。同卷单文件 2 次（约 44 ms），跨卷覆盖旧文件 3 次，空事务 0 次。
"""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from agent import core, publication


class PublicationFsyncBudgetTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.target = self.root / 'result.json'
        patcher = mock.patch.object(publication, 'ROOT', self.root / 'tx')
        patcher.start()
        self.addCleanup(patcher.stop)

    def _fsyncs(self, action):
        with mock.patch('os.fsync', wraps=os.fsync) as fsync:
            action()
        return fsync.call_count

    def _publish(self, text):
        with publication.transaction():
            core.save_text(self.target, text)

    def _leftovers(self):
        return [item for item in publication.ROOT.iterdir() if item.is_dir()]

    def test_replacing_existing_file_waits_for_body_and_journal_only(self):
        core.save_text(self.target, 'v1')
        self.assertEqual(self._fsyncs(lambda: self._publish('v2')), 2)
        self.assertEqual(self.target.read_text(encoding='utf-8'), 'v2')
        self.assertEqual(self._leftovers(), [])

    def test_new_file_waits_for_body_and_journal_only(self):
        self.assertEqual(self._fsyncs(lambda: self._publish('v1')), 2)
        self.assertEqual(self.target.read_text(encoding='utf-8'), 'v1')
        self.assertEqual(self._leftovers(), [])

    def test_empty_transaction_does_not_wait_for_disk(self):
        def empty():
            with publication.transaction():
                pass
        self.assertEqual(self._fsyncs(empty), 0)
        self.assertEqual(self._leftovers(), [])

    def test_old_version_is_kept_as_hard_link_and_restored_on_failure(self):
        core.save_text(self.target, 'v1')
        original = os.stat(self.target).st_ino
        backups = []
        with self.assertRaisesRegex(RuntimeError, 'index failed'):
            with publication.transaction():
                core.save_text(self.target, 'v2')
                folder, = self._leftovers()
                backups.append(os.stat(folder / '0').st_ino)
                raise RuntimeError('index failed')
        self.assertEqual(backups, [original], '同卷的旧版本应是硬链接，不整份复制')
        self.assertEqual(self.target.read_text(encoding='utf-8'), 'v1')
        self.assertEqual(self._leftovers(), [])

    def test_link_failure_falls_back_to_flushed_copy(self):
        core.save_text(self.target, 'v1')
        cross_volume = OSError(17, '系统无法将文件移到不同的磁盘驱动器。')
        with mock.patch('os.link', side_effect=cross_volume):
            with self.assertRaisesRegex(RuntimeError, 'index failed'):
                with publication.transaction():
                    core.save_text(self.target, 'v2')
                    raise RuntimeError('index failed')
            self.assertEqual(self.target.read_text(encoding='utf-8'), 'v1')
            self.assertEqual(self._fsyncs(lambda: self._publish('v3')), 3)
        self.assertEqual(self.target.read_text(encoding='utf-8'), 'v3')
        self.assertEqual(self._leftovers(), [])

    def test_journal_lists_each_target_before_it_is_replaced(self):
        core.save_text(self.target, 'v1')
        index = self.root / 'index.json'
        seen = []
        real = core._replace_locked

        def checked(source, target):
            folder, = self._leftovers()
            journal = json.loads((folder / 'journal.json').read_text(encoding='utf-8'))
            seen.append((Path(target).name, [Path(entry['target']).name for entry in journal['entries']]))
            real(source, target)

        with mock.patch.object(core, '_replace_locked', checked):
            with publication.transaction():
                core.save_text(self.target, 'v2')
                core.save_text(index, 'v2')
        self.assertEqual(seen, [('result.json', ['result.json']),
                                ('index.json', ['result.json', 'index.json'])])

    def test_legacy_journal_preserves_unverifiable_target_and_backup(self):
        for state in ('committed', 'rolled_back', 'pending'):
            with self.subTest(state=state):
                core.save_text(self.target, 'new')
                folder = publication.ROOT / ('b' * 32)
                folder.mkdir(parents=True)
                (folder / '0').write_text('old', encoding='utf-8')
                (folder / 'journal.json').write_text(json.dumps({'version': 1, 'state': state, 'entries': [
                    {'target': str(self.target.resolve()), 'backup': '0', 'existed': True}]}), encoding='utf-8')
                if state == 'pending':
                    with self.assertRaisesRegex(RuntimeError, '旧版.*保留备份'):
                        publication.recover_pending()
                    self.assertEqual((folder / '0').read_text(encoding='utf-8'), 'old')
                    self.assertEqual(self._leftovers(), [folder])
                else:
                    publication.recover_pending()
                    self.assertEqual(self._leftovers(), [])
                self.assertEqual(self.target.read_text(encoding='utf-8'), 'new')


if __name__ == '__main__':
    unittest.main()

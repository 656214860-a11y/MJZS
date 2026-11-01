"""R2192：后台排队与执行记录不再等落盘；断电留下的坏文件改名留存后重建。

``outputs/desktop-task-queue.json`` 与 ``desktop-task-history.json`` 只记本机后台任务。界面线程上
每次提交、收尾、入队、领取原先都要等 4–5 次 fsync（本机 D 盘每项约 120–175 ms），现在只加锁并原子
替换：进程崩溃后读到的仍是完整的旧版或新版，断电则可能读出全零或半份。读不出 JSON 时把原文件
改名为 ``<名>.corrupt``，按空记录继续，不让一份坏文件挡住所有后台操作；读得出但版本或结构不对
（新版程序写的、被手改）照旧报错，不覆盖。
"""
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import desktop_automation_service as service
from agent import core, publication

DAMAGED = (b'\0' * 512, b'{"version": 1, "tasks": [{"id": "a' + b'\0' * 64, b'', b'\xff\xfe\x00garbage')


class BackgroundRecordRebuildTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        patcher = mock.patch.object(publication, 'ROOT', self.root / 'tx')
        patcher.start()
        self.addCleanup(patcher.stop)

    def _queue(self):
        return service.PersistentBackgroundTaskQueue(self.root / 'queue.json', handlers={'test': lambda p: p})

    def _history(self):
        return service.BackgroundTaskLifecycle(self.root / 'history.json')

    def test_queue_round_trip_never_waits_for_disk(self):
        queue = self._queue()
        with mock.patch('os.fsync', wraps=os.fsync) as fsync:
            queue.enqueue_descriptor('test', {}, label='first')
            second = queue.enqueue_descriptor('test', {}, label='second')
            queue.pop()['fn']()
            self.assertTrue(queue.cancel(second))
            queue.enqueue(lambda: 'live', label='live')
            self.assertEqual(queue.pop()['fn'](), 'live')
            queue.enqueue_descriptor('test', {}, label='dropped')
            queue.clear()
        self.assertEqual(fsync.call_count, 0)
        reopened = self._queue()
        self.assertEqual(reopened.labels(), [])
        self.assertEqual(reopened.unresolved(), [])
        self.assertEqual({row['label']: row['state'] for row in core.read(self.root / 'queue.json')['tasks']},
                         {'first': 'completed', 'second': 'cancelled', 'dropped': 'cancelled'})

    def test_task_submit_and_finish_never_wait_for_disk(self):
        history = self._history()
        with mock.patch('os.fsync', wraps=os.fsync) as fsync:
            history.submit(1, label='盘点')
            history.finish(1, succeeded=True)
            history.submit(2, label='在途')
        self.assertEqual(fsync.call_count, 0)
        self.assertEqual([row['ticket'] for row in self._history().unresolved_records()], [2])

    def test_unreadable_queue_file_is_set_aside_and_rebuilt(self):
        path = self.root / 'queue.json'
        for content in DAMAGED:
            with self.subTest(content=content[:12]):
                path.write_bytes(content)
                self.assertEqual(self._queue().labels(), [])
                self.assertEqual(path.with_name('queue.json.corrupt').read_bytes(), content)
                self._queue().enqueue_descriptor('test', {}, label='after')
                self.assertEqual(self._queue().labels(), ['after'])
                path.unlink()

    def test_unreadable_history_file_is_set_aside_and_rebuilt(self):
        path = self.root / 'history.json'
        path.write_bytes(b'\0' * 512)
        self.assertEqual(self._history().unresolved_records(), [])
        self.assertEqual(path.with_name('history.json.corrupt').read_bytes(), b'\0' * 512)
        path.write_bytes(b'\0' * 512)
        self._history().submit(7, label='盘点')
        self.assertEqual([row['ticket'] for row in self._history().unresolved_records()], [7])

    def test_rebuild_continues_when_damaged_file_cannot_be_renamed(self):
        path = self.root / 'queue.json'
        path.write_bytes(b'\0' * 512)
        with mock.patch.object(core, 'replace', side_effect=PermissionError(13, '拒绝访问')):
            self.assertEqual(self._queue().labels(), [])
        self.assertFalse(path.with_name('queue.json.corrupt').exists())
        self._queue().enqueue_descriptor('test', {}, label='after')
        self.assertEqual(self._queue().labels(), ['after'])

    def test_readable_record_of_unknown_version_is_never_overwritten(self):
        cases = (('queue.json', lambda: self._queue().enqueue_descriptor('test', {}), '排队记录损坏'),
                 ('history.json', lambda: self._history().submit(1), '后台执行记录损坏'))
        for name, action, message in cases:
            with self.subTest(name=name):
                path = self.root / name
                path.write_text('{"version": 2, "tasks": []}', encoding='utf-8')
                with self.assertRaisesRegex(ValueError, message):
                    action()
                self.assertEqual(path.read_text(encoding='utf-8'), '{"version": 2, "tasks": []}')
                self.assertFalse(path.with_name(name + '.corrupt').exists())


if __name__ == '__main__':
    unittest.main()

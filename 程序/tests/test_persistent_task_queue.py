"""Durable desktop queue order and unknown-submit recovery."""
import tempfile
import subprocess
import sys
import unittest
from pathlib import Path

import desktop_automation_service as service


class PersistentQueueTests(unittest.TestCase):
    def test_storage_descriptor_executes_after_reopening_without_current_desktop(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)/'project'
            root.mkdir()
            source = root/'source.txt'
            source.write_text('retained', encoding='utf-8')
            path = Path(directory)/'queue.json'
            handlers = {'storage_inspect': service.inspect_project_storage}
            queue = service.PersistentBackgroundTaskQueue(path, handlers=handlers)
            queue.enqueue_descriptor('storage_inspect', {'root':str(root)})
            restored = service.PersistentBackgroundTaskQueue(path, handlers=handlers)
            result = restored.pop()['fn']()
            self.assertIn(str(root), result)
            self.assertIn('存储盘点（只读）', result)
            self.assertEqual(source.read_text(encoding='utf-8'), 'retained')
            self.assertEqual(restored.unresolved(), [])

    def test_invalid_arguments_do_not_poison_queue_and_clear_keeps_claims(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'queue.json'
            queue = service.PersistentBackgroundTaskQueue(path, handlers={'test':lambda p:p})
            with self.assertRaises(ValueError):
                queue.enqueue(lambda:None, priority='bad')
            for expiry in ('tomorrow', float('nan'), float('inf')):
                with self.assertRaises(ValueError):
                    queue.enqueue_descriptor('test', {}, expires_at=expiry)
            self.assertEqual(queue.labels(), [])
            claimed = queue.enqueue_descriptor('test', {}, label='claimed')
            queue.pop()
            queue.enqueue_descriptor('test', {}, label='pending')
            queue.clear()
            recovered = service.PersistentBackgroundTaskQueue(path, handlers={'test':lambda p:p})
            self.assertEqual(recovered.labels(), [])
            self.assertEqual([row['id'] for row in recovered.unresolved()], [claimed])

    def test_hard_process_exit_keeps_unclaimed_work_and_quarantines_claim(self):
        script = '''
import os,sys
from desktop_automation_service import PersistentBackgroundTaskQueue
q=PersistentBackgroundTaskQueue(sys.argv[1],handlers={'test':lambda p:p})
q.enqueue_descriptor('test',{},label='pending')
q.enqueue_descriptor('test',{},label='unknown',priority=5)
q.pop()
os._exit(77)
'''
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'queue.json'
            process=subprocess.run([sys.executable,'-B','-c',script,str(path)],
                cwd=Path(__file__).resolve().parents[1],capture_output=True,timeout=15)
            self.assertEqual(process.returncode,77,process.stderr)
            recovered=service.PersistentBackgroundTaskQueue(path,handlers={'test':lambda p:p})
            self.assertEqual(recovered.labels(),['pending'])
            self.assertEqual([r['label'] for r in recovered.unresolved()],['unknown'])

    def test_restart_preserves_priority_and_does_not_replay_claimed_work(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'queue.json'
            calls = []
            handlers = {'test': lambda payload: calls.append(payload['id'])}
            first = service.PersistentBackgroundTaskQueue(path, handlers=handlers)
            first.enqueue_descriptor('test', {'id':'low'}, label='low', priority=0)
            first.enqueue_descriptor('test', {'id':'high'}, label='high', priority=5)
            second = service.PersistentBackgroundTaskQueue(path, handlers=handlers)
            item = second.pop()
            self.assertEqual(item['label'], 'high')
            # A crash after the durable claim may have submitted a paid request.
            third = service.PersistentBackgroundTaskQueue(path, handlers=handlers)
            remaining = third.pop()
            self.assertEqual(remaining['label'], 'low')
            remaining['fn']()
            self.assertIsNone(third.pop())
            self.assertEqual(calls, ['low'])
            self.assertEqual(third.unresolved()[0]['label'], 'high')

    def test_aging_expiry_cancel_and_ephemeral_callbacks(self):
        with tempfile.TemporaryDirectory() as directory:
            now = [100.0]
            queue = service.PersistentBackgroundTaskQueue(Path(directory)/'queue.json',
                handlers={'test':lambda p:p}, clock=lambda:now[0], aging_seconds=10)
            queue.enqueue_descriptor('test', {'id':'old'}, label='old')
            cancelled = queue.enqueue_descriptor('test', {}, label='cancel')
            self.assertTrue(queue.cancel(cancelled))
            queue.enqueue_descriptor('test', {}, label='expired', expires_at=105)
            now[0] = 200
            queue.enqueue(lambda: 'ephemeral', label='urgent', priority=5)
            item = queue.pop()
            self.assertEqual(item['label'], 'old')
            item['fn']()
            self.assertEqual(queue.pop()['fn'](), 'ephemeral')
            self.assertIsNone(queue.pop())

    def test_second_instance_cannot_claim_same_descriptor(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'queue.json'
            a=service.PersistentBackgroundTaskQueue(path, handlers={'test':lambda p:p})
            b=service.PersistentBackgroundTaskQueue(path, handlers={'test':lambda p:p})
            a.enqueue_descriptor('test', {}, label='once')
            item=a.pop()
            self.assertIsNone(b.pop())
            item['fn']()
            self.assertEqual(b.unresolved(), [])

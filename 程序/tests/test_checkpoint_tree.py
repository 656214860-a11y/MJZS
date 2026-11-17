# -*- coding: utf-8 -*-
"""会话 checkpoint 树（R3132）：append-only、parent 链、fork 不覆盖、剪枝、存引用。

运行：python tests/test_checkpoint_tree.py
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from domain.checkpoint_tree import CheckpointStore


class CheckpointStoreTests(unittest.TestCase):
    def setUp(self):
        self.store = CheckpointStore()

    def test_create_and_get(self):
        self.store.create('t1', 'c1', state={'step': 1}, artifact_refs=['a.png'])
        row = self.store.get('c1')
        self.assertEqual(row['state'], {'step': 1})
        self.assertEqual(row['artifact_refs'], ['a.png'])
        self.assertEqual(self.store.current('t1'), 'c1')

    def test_append_only_rejects_duplicate_id(self):
        self.store.create('t1', 'c1')
        with self.assertRaises(ValueError):
            self.store.create('t1', 'c1')

    def test_parent_chain_and_history_order(self):
        self.store.create('t1', 'c1')
        self.store.create('t1', 'c2', parent_id='c1')
        self.store.create('t1', 'c3', parent_id='c2')
        self.assertEqual([row['id'] for row in self.store.history('t1')], ['c1', 'c2', 'c3'])
        self.assertEqual([row['id'] for row in self.store.children('c1')], ['c2'])

    def test_fork_does_not_overwrite_original(self):
        self.store.create('t1', 'c1')
        self.store.create('t1', 'c2', parent_id='c1')
        self.store.create('t1', 'c3', parent_id='c2')
        self.store.fork('t1', 'c2', 'b1')
        self.assertEqual(self.store.get('c3')['parent_id'], 'c2', '原链不得被覆盖')
        self.assertEqual(self.store.get('b1')['parent_id'], 'c2', '新分支挂在旧节点上')
        self.assertEqual(len(self.store.history('t1')), 4)

    def test_set_current_switches_between_branches(self):
        self.store.create('t1', 'c1')
        self.store.create('t1', 'c2', parent_id='c1')
        self.store.set_current('t1', 'c1')
        self.assertEqual(self.store.current('t1'), 'c1')
        self.store.set_current('t1', 'c2')
        self.assertEqual(self.store.current('t1'), 'c2')

    def test_prune_keeps_newest_and_reparents_roots(self):
        for index in range(10):
            self.store.create('t1', 'c%d' % index,
                              parent_id=('c%d' % (index - 1)) if index else '')
        removed = self.store.prune('t1', keep=3)
        self.assertEqual(removed, 7)
        remaining = [row['id'] for row in self.store.history('t1')]
        self.assertEqual(remaining, ['c7', 'c8', 'c9'])
        self.assertEqual(self.store.get('c7')['parent_id'], '', '被剪父节点改挂根')


if __name__ == '__main__':
    unittest.main()

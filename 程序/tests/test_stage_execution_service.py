# -*- coding: utf-8 -*-
"""阶段成果发布编排器的无 Tk 回归。"""
import tempfile
import unittest
import subprocess
import sys
from pathlib import Path

from stage_execution_service import publish_stage_bundle, publish_stage_bytes, publish_stage_text


class StagePublicationTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.target = Path(self.folder.name) / '成果.md'

    def tearDown(self):
        self.folder.cleanup()

    def test_restart_after_process_death_restores_the_entire_bundle(self):
        from agent.core import read, save
        root = Path(self.folder.name)
        first, second = root / 'first.json', root / 'second.json'
        save(first, {'version': 'old-first'})
        save(second, {'version': 'old-second'})
        script = '''
import os, sys
from pathlib import Path
from agent import core
from stage_execution_service import publish_stage_bundle
root = Path(sys.argv[1])
original = core.replace
def die_after_first(source, target):
    original(source, target)
    if Path(target).name == 'first.json':
        os._exit(77)
core.replace = die_after_first
publish_stage_bundle({root/'first.json': b'{"version":"new-first"}',
                      root/'second.json': b'{"version":"new-second"}'},
                     lambda rows: True, lambda: None)
'''
        result = subprocess.run([sys.executable, '-B', '-c', script, str(root)],
                                cwd=Path(__file__).resolve().parents[1],
                                capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 77, result.stderr.decode(errors='replace'))
        self.assertEqual(read(first), {'version': 'old-first'})
        self.assertEqual(read(second), {'version': 'old-second'})

    def test_validated_publish_updates_index_after_atomic_file(self):
        calls = []

        def update_index(target):
            calls.append(target.read_text(encoding='utf-8'))

        result = publish_stage_text(self.target, '有效成果', lambda text: text == '有效成果', update_index)
        self.assertEqual(result, self.target)
        self.assertEqual(self.target.read_text(encoding='utf-8'), '有效成果')
        self.assertEqual(calls, ['有效成果'])

    def test_validation_failure_creates_no_file_or_index(self):
        calls = []
        with self.assertRaisesRegex(ValueError, '校验未通过'):
            publish_stage_text(self.target, '不合格', lambda _text: False,
                               lambda _target: calls.append('index'))
        self.assertFalse(self.target.exists())
        self.assertEqual(calls, [])

    def test_index_failure_restores_previous_artifact_and_raises(self):
        self.target.write_text('旧成果', encoding='utf-8')
        with self.assertRaisesRegex(RuntimeError, 'index failed'):
            publish_stage_text(self.target, '新成果', lambda _text: True,
                               lambda _target: (_ for _ in ()).throw(RuntimeError('index failed')))
        self.assertEqual(self.target.read_text(encoding='utf-8'), '旧成果')

    def test_binary_publish_updates_index_after_atomic_file(self):
        target = Path(self.folder.name) / '成果.bin'
        calls = []

        result = publish_stage_bytes(
            target, b'new-media', lambda raw: raw.startswith(b'new'),
            lambda path: calls.append(path.read_bytes()))

        self.assertEqual(result, target)
        self.assertEqual(target.read_bytes(), b'new-media')
        self.assertEqual(calls, [b'new-media'])

    def test_binary_index_failure_restores_previous_artifact_and_raises(self):
        target = Path(self.folder.name) / '成果.bin'
        target.write_bytes(b'old-media')
        with self.assertRaisesRegex(RuntimeError, 'index failed'):
            publish_stage_bytes(
                target, b'new-media', lambda _raw: True,
                lambda _path: (_ for _ in ()).throw(RuntimeError('index failed')))
        self.assertEqual(target.read_bytes(), b'old-media')

    def test_bundle_publishes_all_artifacts_before_index_update(self):
        with tempfile.TemporaryDirectory() as folder:
            first = Path(folder) / 'first.bin'
            second = Path(folder) / 'second.bin'
            indexed = []
            result = publish_stage_bundle(
                {first: b'first', second: b'second'}, lambda _items: True,
                lambda: indexed.append((first.read_bytes(), second.read_bytes())))
            self.assertEqual(result, (first, second))
            self.assertEqual(indexed, [(b'first', b'second')])

    def test_bundle_index_failure_restores_every_previous_artifact(self):
        with tempfile.TemporaryDirectory() as folder:
            first = Path(folder) / 'first.bin'; first.write_bytes(b'old-first')
            second = Path(folder) / 'second.bin'
            with self.assertRaisesRegex(RuntimeError, 'index failed'):
                publish_stage_bundle(
                    {first: b'new-first', second: b'new-second'}, lambda _items: True,
                    lambda: (_ for _ in ()).throw(RuntimeError('index failed')))
            self.assertEqual(first.read_bytes(), b'old-first')
            self.assertFalse(second.exists())

"""正式发布保留原事务，并在成功后增量同步已有文件索引。"""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from agent import core, publication
from contract.project_context import ProjectContext
import file_index
from orchestrator import stage_publication


class StageFileIndexPublicationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.ctx = ProjectContext.snapshot(self.root, lambda stage: self.root / stage)
        self.transaction_root = patch.object(publication, 'ROOT', self.root / 'transactions')
        self.transaction_root.start()
        self.addCleanup(self.transaction_root.stop)

    def seed_index(self, root=None):
        file_index.rebuild(root or self.root)

    def indexed(self, root=None):
        return {item['path'] for item in file_index.read(root or self.root)['files']}

    def test_text_bytes_and_bundle_visible_immediately_with_context(self):
        self.seed_index()
        text = self.root / '剧本' / 'story.md'
        binary = self.root / '音频' / 'voice.wav'
        bundle = {self.root / '分镜' / 'shots.json': b'{}',
                  self.root / '分镜' / 'notes.md': b'notes'}
        text_updater, bytes_updater, bundle_updater = Mock(), Mock(), Mock()
        stage_publication.publish_stage_text(text, 'story', bool, text_updater, context=self.ctx)
        self.assertIn(text.relative_to(self.root).as_posix(), self.indexed())
        stage_publication.publish_stage_bytes(binary, b'wave', bool, bytes_updater, context=self.ctx)
        self.assertIn(binary.relative_to(self.root).as_posix(), self.indexed())
        stage_publication.publish_stage_bundle(bundle, bool, bundle_updater, context=self.ctx)
        self.assertTrue({p.relative_to(self.root).as_posix() for p in bundle} <= self.indexed())
        text_updater.assert_called_once_with(text)
        bytes_updater.assert_called_once_with(binary)
        bundle_updater.assert_called_once_with()

    def test_existing_callers_infer_roots_and_group_bundle(self):
        roots = [self.root / 'one', self.root / 'two']
        for root in roots:
            root.mkdir()
            self.seed_index(root)
        text, binary = roots[0] / 'story.md', roots[0] / 'voice.wav'
        stage_publication.publish_stage_text(text, 'story', bool, lambda _: None)
        stage_publication.publish_stage_bytes(binary, b'wave', bool, lambda _: None)
        bundle = {roots[0] / 'one.md': b'one', roots[1] / 'two.md': b'two'}
        stage_publication.publish_stage_bundle(bundle, bool, lambda: None)
        self.assertTrue({'story.md', 'voice.wav', 'one.md'} <= self.indexed(roots[0]))
        self.assertIn('two.md', self.indexed(roots[1]))

    def test_save_failure_leaves_no_false_index(self):
        self.seed_index()
        updater = Mock()
        with patch.object(core, 'save_text', side_effect=OSError('save failed')):
            with self.assertRaisesRegex(OSError, 'save failed'):
                stage_publication.publish_stage_text(self.root / 'new.md', 'new', bool, updater,
                                                     context=self.ctx)
        updater.assert_not_called()
        self.assertNotIn('new.md', self.indexed())
        self.assertFalse((self.root / 'new.md').exists())

    def test_bundle_save_failure_rolls_back_without_indexing_partial_outputs(self):
        self.seed_index()
        first, second = self.root / 'first.md', self.root / 'second.md'
        save_bytes = core.save_bytes

        def fail_second(path, data):
            if path == second:
                raise OSError('second save failed')
            save_bytes(path, data)

        updater = Mock()
        with patch.object(core, 'save_bytes', side_effect=fail_second):
            with self.assertRaisesRegex(OSError, 'second save failed'):
                stage_publication.publish_stage_bundle({first: b'first', second: b'second'},
                                                        bool, updater, context=self.ctx)
        updater.assert_not_called()
        self.assertFalse(first.exists())
        self.assertFalse(second.exists())
        self.assertFalse({'first.md', 'second.md'} & self.indexed())

    def test_caller_updater_failure_keeps_original_rollback(self):
        self.seed_index()
        target = self.root / 'old.md'
        core.save_text(target, 'old')
        with patch.object(file_index, 'update') as update:
            with self.assertRaisesRegex(RuntimeError, 'caller failed'):
                stage_publication.publish_stage_text(target, 'new', bool,
                    Mock(side_effect=RuntimeError('caller failed')), context=self.ctx)
        self.assertEqual(target.read_text(encoding='utf-8'), 'old')
        update.assert_not_called()

    def test_file_index_failure_logs_without_rolling_back_artifact(self):
        self.seed_index()
        target = self.root / 'new.md'
        updater = Mock()
        with patch.object(file_index, 'update', side_effect=OSError('index failed')):
            with self.assertLogs(stage_publication.__name__, level='WARNING'):
                result = stage_publication.publish_stage_text(target, 'new', bool, updater,
                                                               context=self.ctx)
        self.assertEqual(result, target)
        self.assertEqual(target.read_text(encoding='utf-8'), 'new')
        updater.assert_called_once_with(target)

    def test_missing_or_invalid_cache_never_rebuilds(self):
        for existing in (False, True):
            with self.subTest(existing=existing):
                if existing:
                    path = file_index.index_path(self.root)
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text('{broken', encoding='utf-8')
                with patch.object(file_index, 'rebuild', side_effect=AssertionError('full scan')):
                    with patch.object(file_index, 'update') as update:
                        stage_publication.publish_stage_text(self.root / 'new.md', 'new', bool,
                                                             lambda _: None, context=self.ctx)
                        stage_publication.publish_stage_bytes(self.root / 'new.bin', b'new', bool,
                                                              lambda _: None)
                update.assert_not_called()

    def test_context_rejects_outside_path_before_publication(self):
        target = self.root.parent / (self.root.name + '-outside.md')
        with patch.object(core, 'save_text') as save:
            with self.assertRaises(ValueError):
                stage_publication.publish_stage_text(target, 'new', bool, lambda _: None,
                                                     context=self.ctx)
        save.assert_not_called()
        self.assertFalse(target.exists())

    def test_index_read_failure_logs_without_changing_publish_result(self):
        self.seed_index()
        target = self.root / 'read-failure.md'
        with patch.object(file_index, 'read', side_effect=OSError('private-path-secret')):
            with self.assertLogs(stage_publication.__name__, level='WARNING') as logs:
                result = stage_publication.publish_stage_text(target, 'new', bool,
                                                             lambda _: None, context=self.ctx)
        self.assertEqual(result, target)
        self.assertEqual(target.read_text(encoding='utf-8'), 'new')
        self.assertNotIn('private-path-secret', '\n'.join(logs.output))

    def test_index_file_is_not_passed_back_to_index_update(self):
        self.seed_index()
        path = file_index.index_path(self.root)
        data = path.read_bytes()
        with patch.object(file_index, 'update', wraps=file_index.update) as update:
            stage_publication.publish_stage_bytes(path, data, bool, lambda _: None,
                                                  context=self.ctx)
        update.assert_not_called()
        self.assertNotIn(path.relative_to(self.root).as_posix(), self.indexed())


if __name__ == '__main__':
    unittest.main()

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import keyframe_lifecycle_service
from agent.core import read, save
from tests.image_fixtures import png
from stage_execution_service import (
    delete_stage_keyframe, replace_stage_keyframe, restore_stage_keyframe,
)


class KeyframeLifecycleServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.image = self.base / 'frames/SH001.png'
        self.image.parent.mkdir()
        self.image.write_bytes(b'png')
        self.source = self.base / 'episode.json'
        self.episode = {'shots': [{'id': 'SH001', 'frame': 'frames/SH001.png'}]}
        save(self.source, self.episode)
        decoder = patch('domain.keyframe_evidence.tool_path', return_value='fixture-ffmpeg')
        process = patch('domain.keyframe_evidence.run_process',
                        return_value=SimpleNamespace(returncode=0, stderr='', stdout=''))
        decoder.start(); process.start()
        self.addCleanup(decoder.stop); self.addCleanup(process.stop)

    def test_recycles_frame_then_marks_episode(self):
        result = delete_stage_keyframe(self.base, self.source, self.episode, self.episode['shots'][0])
        self.assertTrue(result.ok)
        self.assertEqual(result.data, self.image)
        self.assertFalse(self.image.exists())
        self.assertTrue(read(self.source)['shots'][0]['frame_deleted'])

    def test_failed_episode_save_restores_frame_and_old_state(self):
        with patch('stage_execution_service.publish_keyframe_episode', side_effect=OSError('磁盘不可用')):
            result = delete_stage_keyframe(
                self.base, self.source, self.episode, self.episode['shots'][0])
        self.assertFalse(result.ok)
        self.assertIn('稍后重试', result.reason)
        self.assertTrue(self.image.is_file())
        self.assertNotIn('frame_deleted', self.episode['shots'][0])

    def test_restores_recycled_frame_then_clears_deleted_state(self):
        shot = self.episode['shots'][0]
        deleted = delete_stage_keyframe(self.base, self.source, self.episode, shot)
        self.assertTrue(deleted.ok, (deleted.reason, deleted.data))
        restored = restore_stage_keyframe(self.base, self.source, self.episode, shot)
        self.assertTrue(restored.ok, (restored.reason, restored.data))
        self.assertTrue(self.image.is_file())
        self.assertNotIn('frame_deleted', read(self.source)['shots'][0])

    def test_restore_while_committed_backup_is_open(self):
        from contextlib import ExitStack
        from agent import publication

        with patch.object(publication, 'ROOT', self.base / 'transactions'):
            shot = self.episode['shots'][0]
            deleted = delete_stage_keyframe(self.base, self.source, self.episode, shot)
            self.assertTrue(deleted.ok, (deleted.reason, deleted.data))
            unrelated = self.base / 'other.json'
            save(unrelated, {'version': 1})
            with ExitStack() as reader:
                with publication.transaction():
                    save(unrelated, {'version': 2})
                    journal, = publication.ROOT.glob('*/journal.json')
                    backup = journal.parent / '0'
                    reader.enter_context(backup.open('rb'))
                self.assertFalse(journal.exists())
                self.assertTrue(backup.exists())
                restored = restore_stage_keyframe(self.base, self.source, self.episode, shot)
                self.assertTrue(restored.ok, (restored.reason, restored.data))
                self.assertEqual(self.image.read_bytes(), b'png')
                self.assertNotIn('frame_deleted', read(self.source)['shots'][0])
            publication.recover_pending()
            self.assertFalse(backup.parent.exists())
            self.assertEqual(read(unrelated), {'version': 2})

    def test_restore_uses_exact_deleted_version_and_nested_original_name(self):
        from infra.storage_maintenance import recycle_paths
        shot = self.episode['shots'][0]
        shot['frame'] = 'frames/nested/custom.PNG'
        original = self.base / shot['frame']
        original.parent.mkdir()
        original.write_bytes(b'first')
        self.assertTrue(delete_stage_keyframe(self.base, self.source, self.episode, shot).ok)
        original.write_bytes(b'another')
        recycle_paths(self.base, (original,), '其他删除')
        with patch('stage_execution_service.publish_keyframe_episode', side_effect=OSError()):
            self.assertFalse(restore_stage_keyframe(self.base, self.source, self.episode, shot).ok)
        self.assertFalse(original.exists())
        self.assertTrue(restore_stage_keyframe(self.base, self.source, self.episode, shot).ok)
        self.assertEqual(original.read_bytes(), b'first')
        self.assertEqual(read(self.source)['shots'][0]['frame'], 'frames/nested/custom.PNG')

    def test_legacy_restore_without_original_file_never_publishes_success(self):
        shot = self.episode['shots'][0]
        shot.update(frame='frames/missing.png', frame_deleted=True)
        save(self.source, self.episode)
        before = self.source.read_bytes()
        with patch('stage_execution_service.publish_keyframe_episode') as publish:
            self.assertFalse(restore_stage_keyframe(self.base, self.source, self.episode, shot).ok)
            publish.assert_not_called()
        self.assertEqual(self.source.read_bytes(), before)

    def test_failed_restore_save_recycles_frame_and_keeps_deleted_state(self):
        shot = self.episode['shots'][0]
        self.assertTrue(delete_stage_keyframe(self.base, self.source, self.episode, shot).ok)
        with patch('stage_execution_service.publish_keyframe_episode', side_effect=OSError('磁盘不可用')):
            result = restore_stage_keyframe(self.base, self.source, self.episode, shot)
        self.assertFalse(result.ok)
        self.assertFalse(self.image.exists())
        self.assertTrue(self.episode['shots'][0]['frame_deleted'])

    def test_replaces_frame_and_recycles_previous_version(self):
        result = replace_stage_keyframe(
            self.base, self.source, self.episode, self.episode['shots'][0], png())
        self.assertTrue(result.ok)
        self.assertEqual(self.image.read_bytes(), png())
        recycle = self.base / '工作流任务/回收站'
        self.assertTrue(any(path.name == 'SH001.png' for path in recycle.rglob('*') if path.is_file()))

    def test_failed_replace_save_restores_previous_frame_and_state(self):
        previous = self.image.read_bytes()
        with patch('stage_execution_service.publish_keyframe_episode', side_effect=OSError('磁盘不可用')):
            result = replace_stage_keyframe(
                self.base, self.source, self.episode, self.episode['shots'][0], png())
        self.assertFalse(result.ok)
        self.assertEqual(self.image.read_bytes(), previous)
        self.assertNotIn('frame_deleted', self.episode['shots'][0])

    def test_replace_uses_injected_publisher_and_recovers_old_frame_on_index_failure(self):
        shot = self.episode['shots'][0]
        with patch('stage_execution_service.publish_keyframe_episode', side_effect=OSError('索引失败')):
            result = replace_stage_keyframe(
                self.base, self.source, self.episode, shot, png())
        self.assertFalse(result.ok)

        self.assertEqual(self.image.read_bytes(), b'png')
        self.assertEqual(shot.get('frame'), 'frames/SH001.png')

    def test_l2_requires_l3_publishers(self):
        shot = self.episode['shots'][0]
        with self.assertRaisesRegex(TypeError, 'L3'):
            keyframe_lifecycle_service.delete_keyframe(self.base, self.source, self.episode, shot)
        with self.assertRaisesRegex(TypeError, 'L3'):
            keyframe_lifecycle_service.replace_keyframe(
                self.base, self.source, self.episode, shot, png())

    def test_invalid_user_input_returns_user_error(self):
        result = delete_stage_keyframe(
            self.base, self.source, self.episode, {'id': 'invalid', 'frame': 'frames/SH001.png'})
        self.assertFalse(result.ok)
        self.assertTrue(result.recoverable)
        self.assertIn('镜头编号', result.reason)

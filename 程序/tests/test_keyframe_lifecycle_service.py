import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import keyframe_lifecycle_service
from agent.core import read, save
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
        self.assertTrue(delete_stage_keyframe(self.base, self.source, self.episode, shot).ok)
        self.assertTrue(restore_stage_keyframe(self.base, self.source, self.episode, shot).ok)
        self.assertTrue(self.image.is_file())
        self.assertNotIn('frame_deleted', read(self.source)['shots'][0])

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
            self.base, self.source, self.episode, self.episode['shots'][0], b'\x89PNG\r\n\x1a\nnew')
        self.assertTrue(result.ok)
        self.assertEqual(self.image.read_bytes(), b'\x89PNG\r\n\x1a\nnew')
        recycle = self.base / '工作流任务/回收站'
        self.assertTrue(any(path.name == 'SH001.png' for path in recycle.rglob('*') if path.is_file()))

    def test_failed_replace_save_restores_previous_frame_and_state(self):
        previous = self.image.read_bytes()
        with patch('stage_execution_service.publish_keyframe_episode', side_effect=OSError('磁盘不可用')):
            result = replace_stage_keyframe(
                self.base, self.source, self.episode, self.episode['shots'][0], b'\x89PNG\r\n\x1a\nnew')
        self.assertFalse(result.ok)
        self.assertEqual(self.image.read_bytes(), previous)
        self.assertNotIn('frame_deleted', self.episode['shots'][0])

    def test_replace_uses_injected_publisher_and_recovers_old_frame_on_index_failure(self):
        shot = self.episode['shots'][0]
        with patch('stage_execution_service.publish_keyframe_episode', side_effect=OSError('索引失败')):
            result = replace_stage_keyframe(
                self.base, self.source, self.episode, shot, b'\x89PNG\r\n\x1a\nnew')
        self.assertFalse(result.ok)

        self.assertEqual(self.image.read_bytes(), b'png')
        self.assertEqual(shot.get('frame'), 'frames/SH001.png')

    def test_l2_requires_l3_publishers(self):
        shot = self.episode['shots'][0]
        with self.assertRaisesRegex(TypeError, 'L3'):
            keyframe_lifecycle_service.delete_keyframe(self.base, self.source, self.episode, shot)
        with self.assertRaisesRegex(TypeError, 'L3'):
            keyframe_lifecycle_service.replace_keyframe(
                self.base, self.source, self.episode, shot, b'\x89PNG\r\n\x1a\nnew')

    def test_invalid_user_input_returns_user_error(self):
        result = delete_stage_keyframe(
            self.base, self.source, self.episode, {'id': 'invalid', 'frame': 'frames/SH001.png'})
        self.assertFalse(result.ok)
        self.assertTrue(result.recoverable)
        self.assertIn('镜头编号', result.reason)

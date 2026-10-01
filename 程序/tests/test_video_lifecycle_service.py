import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import video_lifecycle_service
from agent.core import read, save


class VideoLifecycleServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.source = Path(self.temp.name) / 'episode.json'
        save(self.source, {'shots': [{'id': 'SH001'}, {'id': 'SH002'}]})

    def test_marks_only_the_selected_shot_after_settlement(self):
        episode = video_lifecycle_service.mark_video_deleted(
            self.source, 'SH002', [{'state': 'downloaded'}])
        self.assertFalse(episode['shots'][0].get('video_deleted'))
        self.assertTrue(episode['shots'][1]['video_deleted'])
        self.assertTrue(read(self.source)['shots'][1]['video_deleted'])

    def test_uncertain_job_refuses_to_change_the_episode(self):
        with self.assertRaisesRegex(ValueError, '未完成'):
            video_lifecycle_service.mark_video_deleted(self.source, 'SH001', [{'state': 'running'}])
        self.assertFalse(read(self.source)['shots'][0].get('video_deleted'))

    def test_failed_publish_restores_the_in_memory_record(self):
        with patch.object(video_lifecycle_service, 'save', side_effect=OSError('磁盘不可用')):
            with self.assertRaisesRegex(OSError, '磁盘不可用'):
                video_lifecycle_service.mark_video_deleted(self.source, 'SH001', [])
        self.assertFalse(read(self.source)['shots'][0].get('video_deleted'))

    def test_saves_cloud_asset_and_audio_options_without_submitting(self):
        episode = video_lifecycle_service.save_video_options(
            self.source, 'SH001', ['CHAR_001'], False, False)
        shot = episode['shots'][0]
        self.assertEqual(shot['upload_asset_ids'], ['CHAR_001'])
        self.assertTrue(shot['upload_assets'])
        self.assertFalse(shot['generate_audio'])
        self.assertEqual(shot['checkbox_defaults_version'], 1)

    def test_saves_local_options_with_the_local_field_only(self):
        episode = video_lifecycle_service.save_video_options(
            self.source, 'SH001', ['CHAR_001'], True, True)
        shot = episode['shots'][0]
        self.assertEqual(shot['local_asset_ids'], ['CHAR_001'])
        self.assertTrue(shot['generate_audio'])
        self.assertNotIn('upload_asset_ids', shot)

    def test_failed_options_publish_restores_the_record(self):
        with patch.object(video_lifecycle_service, 'save', side_effect=OSError('磁盘不可用')):
            with self.assertRaisesRegex(OSError, '磁盘不可用'):
                video_lifecycle_service.save_video_options(
                    self.source, 'SH001', ['CHAR_001'], False, False)
        self.assertNotIn('upload_asset_ids', read(self.source)['shots'][0])

    def test_saves_white_model_upload_choice_without_uploading_media(self):
        episode = video_lifecycle_service.save_white_model_upload(self.source, 'SH002', True)
        self.assertFalse(episode['shots'][0].get('upload_white_model'))
        self.assertTrue(episode['shots'][1]['upload_white_model'])
        self.assertTrue(read(self.source)['shots'][1]['upload_white_model'])

    def test_failed_white_model_choice_publish_restores_the_record(self):
        with patch.object(video_lifecycle_service, 'save', side_effect=OSError('磁盘不可用')):
            with self.assertRaisesRegex(OSError, '磁盘不可用'):
                video_lifecycle_service.save_white_model_upload(self.source, 'SH001', True)
        self.assertNotIn('upload_white_model', read(self.source)['shots'][0])

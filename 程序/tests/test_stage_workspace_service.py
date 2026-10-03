# -*- coding: utf-8 -*-
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from service_contract import SystemError

import project_stages
from stage_workspace_service import (ensure_audio_workspace, ensure_delivery_workspace,
                                     ensure_editing_workspace, ensure_storyboard_workspace)


class StageWorkspaceServiceTests(unittest.TestCase):
    def test_all_entrypoints_return_system_error_on_mkdir_failure(self):
        for service in (ensure_audio_workspace, ensure_storyboard_workspace,
                        ensure_editing_workspace, ensure_delivery_workspace):
            with self.subTest(service=service.__name__):
                with patch.object(Path, 'mkdir', side_effect=OSError('private detail')):
                    with self.assertLogs('stage_workspace_service', level='ERROR'):
                        result = service('project')
                self.assertIsInstance(result, SystemError)
                self.assertIsNone(result.data)
                self.assertNotIn('private detail', result.reason)

    def test_programming_errors_propagate(self):
        with patch.object(Path, 'mkdir', side_effect=TypeError('bug')):
            with self.assertRaisesRegex(TypeError, 'bug'):
                ensure_audio_workspace('project')

    def test_storyboard_workspace_creates_only_storyboard_directory(self):
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp) / '项目'
            result = ensure_storyboard_workspace(project)
            self.assertTrue(result.ok)
            storyboard_dir = result.data
            self.assertEqual(project_stages.storyboard(project), storyboard_dir)
            self.assertTrue(storyboard_dir.is_dir())
            self.assertFalse(project_stages.assets(project).exists())

    def test_audio_workspace_creates_only_audio_and_subtitle_directories(self):
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp) / '项目'
            result = ensure_audio_workspace(project)
            self.assertTrue(result.ok)
            audio_dir, subtitle_dir = result.data
            self.assertEqual((project_stages.audio(project), project_stages.subtitles(project)),
                             (audio_dir, subtitle_dir))
            self.assertTrue(audio_dir.is_dir())
            self.assertTrue(subtitle_dir.is_dir())
            self.assertFalse(project_stages.editing(project).exists())

    def test_editing_workspace_creates_only_editing_directory(self):
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp) / '项目'
            result = ensure_editing_workspace(project)
            self.assertTrue(result.ok)
            editing_dir, = result.data
            self.assertEqual(project_stages.editing(project), editing_dir)
            self.assertTrue(editing_dir.is_dir())
            self.assertFalse(project_stages.delivery(project).exists())

    def test_delivery_workspace_creates_delivery_and_export_directories(self):
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp) / '项目'
            result = ensure_delivery_workspace(project)
            self.assertTrue(result.ok)
            delivery_dir, export_dir = result.data
            self.assertEqual((project_stages.delivery(project), project_stages.exports(project)),
                             (delivery_dir, export_dir))
            self.assertTrue(delivery_dir.is_dir())
            self.assertTrue(export_dir.is_dir())

# -*- coding: utf-8 -*-
import tempfile
import unittest
from pathlib import Path

import project_stages
from stage_workspace_service import (ensure_audio_workspace, ensure_delivery_workspace,
                                     ensure_editing_workspace, ensure_storyboard_workspace)


class StageWorkspaceServiceTests(unittest.TestCase):
    def test_storyboard_workspace_creates_only_storyboard_directory(self):
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp) / '项目'
            storyboard_dir = ensure_storyboard_workspace(project)
            self.assertEqual(project_stages.storyboard(project), storyboard_dir)
            self.assertTrue(storyboard_dir.is_dir())
            self.assertFalse(project_stages.assets(project).exists())

    def test_audio_workspace_creates_only_audio_and_subtitle_directories(self):
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp) / '项目'
            audio_dir, subtitle_dir = ensure_audio_workspace(project)
            self.assertEqual((project_stages.audio(project), project_stages.subtitles(project)),
                             (audio_dir, subtitle_dir))
            self.assertTrue(audio_dir.is_dir())
            self.assertTrue(subtitle_dir.is_dir())
            self.assertFalse(project_stages.editing(project).exists())

    def test_editing_workspace_creates_only_editing_directory(self):
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp) / '项目'
            editing_dir, = ensure_editing_workspace(project)
            self.assertEqual(project_stages.editing(project), editing_dir)
            self.assertTrue(editing_dir.is_dir())
            self.assertFalse(project_stages.delivery(project).exists())

    def test_delivery_workspace_creates_delivery_and_export_directories(self):
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp) / '项目'
            delivery_dir, export_dir = ensure_delivery_workspace(project)
            self.assertEqual((project_stages.delivery(project), project_stages.exports(project)),
                             (delivery_dir, export_dir))
            self.assertTrue(delivery_dir.is_dir())
            self.assertTrue(export_dir.is_dir())

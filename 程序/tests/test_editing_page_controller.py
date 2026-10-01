from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from editing_page_controller import EditingPageController


class _Studio:
    def __init__(self, state, result='MASTER.mp4'):
        self.episode = {'shots': [{'id': 'SH001'}, {'id': 'SH002'}]}
        self._state = state
        self.result = result
        self.calls = []

    def state(self):
        return self._state

    def assemble(self, **kwargs):
        self.calls.append(kwargs)
        kwargs['report']['skipped'] = ['SH002']
        return self.result


class EditingPageControllerTests(unittest.TestCase):
    def test_has_downloaded_video_requires_an_existing_registered_file(self):
        with tempfile.TemporaryDirectory() as folder:
            project = Path(folder)
            studio = _Studio({'shots': {'SH001': [{'file': 'data/SH001.mp4'}], 'SH002': []}})
            controller = EditingPageController(project, studio)
            self.assertFalse(controller.has_downloaded_video())
            clip = project / 'data' / 'SH001.mp4'
            clip.parent.mkdir()
            clip.write_bytes(b'video')
            self.assertTrue(controller.has_downloaded_video())

    def test_assemble_preserves_skip_report_for_page_status(self):
        with tempfile.TemporaryDirectory() as folder:
            studio = _Studio({'shots': {'SH001': [], 'SH002': []}}, result='out/MASTER.mp4')
            controller = EditingPageController(folder, studio)
            self.assertEqual(controller.assemble(), 'out/MASTER.mp4')
            self.assertEqual(studio.calls, [{'skip_unready': True, 'report': controller.assemble_report}])
            self.assertEqual(controller.assembled_message('out/MASTER.mp4'),
                             '已跳过 1 个未就绪镜头：SH002；成片：out/MASTER.mp4')

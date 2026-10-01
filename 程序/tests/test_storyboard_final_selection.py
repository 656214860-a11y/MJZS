import tempfile
import unittest
from pathlib import Path

from agent.core import read, save
from storyboard_selection import remember_final_view


class StoryboardFinalSelectionTests(unittest.TestCase):
    def setUp(self):
        self.project = Path(tempfile.mkdtemp())
        self.source = self.project / '06分镜定稿' / 'EP001.json'
        self.source.parent.mkdir()
        self.source.write_text('{}', encoding='utf-8')
        save(self.project / 'ui_settings.json', {'frame_json': '03初步分镜/episode.json', 'auto_final': True})

    def test_remember_final_view_preserves_other_project_preferences(self):
        self.assertEqual(remember_final_view(self.project, self.source), self.source.resolve())
        prefs = read(self.project / 'ui_settings.json')
        self.assertEqual(prefs['final_storyboard_json'], '06分镜定稿/EP001.json')
        self.assertEqual(prefs['frame_json'], '03初步分镜/episode.json')
        self.assertTrue(prefs['auto_final'])

    def test_remember_final_view_rejects_external_path(self):
        with self.assertRaisesRegex(ValueError, '不在当前项目内'):
            remember_final_view(self.project, self.project.parent / 'outside.json')

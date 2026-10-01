import tempfile
import unittest
from pathlib import Path

from agent.core import read, save
from storyboard_final_controller import FinalStoryboardController


class FinalStoryboardControllerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name)
        self.path = self.project / '06分镜定稿' / '分镜' / 'EP001.json'
        self.path.parent.mkdir(parents=True)
        save(self.path, {'episode_id': 'EP001', 'shots': [{'id': 'S01'}, {'id': 'S02'}]})
        self.controller = FinalStoryboardController(self.project)

    def test_choose_persists_view_and_tracks_preview_navigation(self):
        preview, note = self.controller.choose(self.path)
        self.assertEqual(preview.path, self.path.resolve())
        self.assertIn('已选：06分镜定稿/分镜/EP001.json', note)
        self.assertEqual(self.controller.shot_ids, ('S01', 'S02'))
        self.assertEqual(self.controller.select_shot('S02'), 'S02')
        self.assertEqual(self.controller.selected_shot, 'S02')
        self.assertEqual(read(self.project / 'ui_settings.json')['final_storyboard_json'],
                         '06分镜定稿/分镜/EP001.json')

    def test_save_edited_validates_before_atomic_persistence(self):
        self.controller.load(self.path)
        with self.assertRaisesRegex(ValueError, '合法 JSON'):
            self.controller.save_edited('{')
        self.assertEqual(read(self.path)['episode_id'], 'EP001')
        preview = self.controller.save_edited('{"episode_id":"EP001","shots":[{"id":"S03"}]}')
        self.assertEqual(preview.data['shots'][0]['id'], 'S03')
        self.assertEqual(self.controller.shot_ids, ('S03',))

    def test_apply_preview_accepts_background_result_without_re_reading(self):
        worker = FinalStoryboardController(self.project)
        preview = worker.load(self.path)
        accepted = self.controller.apply_preview(preview)
        self.assertIs(accepted, preview)
        self.assertEqual(self.controller.active_path(), self.path.resolve())
        self.assertEqual(self.controller.shot_ids, ('S01', 'S02'))

    def test_choose_can_persist_before_a_background_load(self):
        preview, note = self.controller.choose(self.path, load=False)
        self.assertIsNone(preview)
        self.assertIn('正在加载预览', note)
        self.assertEqual(read(self.project / 'ui_settings.json')['final_storyboard_json'],
                         '06分镜定稿/分镜/EP001.json')

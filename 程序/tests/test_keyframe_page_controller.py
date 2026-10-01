import tempfile
import unittest
from pathlib import Path

from keyframe_page_controller import KeyframePageController


class KeyframePageControllerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.first = self.root / 'first.json'
        self.second = self.root / 'second.json'
        self.base_one = self.root / 'one'; self.base_one.mkdir()
        self.base_two = self.root / 'two'; self.base_two.mkdir()
        (self.base_one / 'a.png').write_bytes(b'image')
        self.a = {'id': 'S01', 'frame': 'a.png'}
        self.b = {'id': 'S02', 'frame': 'missing.png'}
        self.controller = KeyframePageController(
            self.first, {'shots': [self.a]}, self.base_one,
            [('S01', self.a, self.first, self.base_one, {'shots': [self.a]}),
             ('S02', self.b, self.second, self.base_two, {'shots': [self.b]})],
        )

    def tearDown(self):
        self.temp.cleanup()

    def test_rows_preserve_owners_and_safe_frame_paths(self):
        self.assertTrue(self.controller.merged)
        self.assertEqual(self.controller.iid_of(self.b), 'S02')
        self.assertTrue(self.controller.frame_exists(self.a))
        with self.assertRaisesRegex(ValueError, '首帧不存在'):
            self.controller.frame_path(self.b)

    def test_pick_batch_prefers_selected_storyboard_and_reports_remaining(self):
        source, ids, remaining = self.controller.pick_batch(['S01', 'S02'], ('S02',))
        self.assertEqual(source, self.second.resolve())
        self.assertEqual(ids, ['S02'])
        self.assertEqual(remaining, 1)

    def test_unknown_selection_falls_back_to_sorted_source(self):
        source, ids, remaining = self.controller.pick_batch(['S01'], ('missing',))
        self.assertEqual(source, self.first.resolve())
        self.assertEqual(ids, ['S01'])
        self.assertEqual(remaining, 0)

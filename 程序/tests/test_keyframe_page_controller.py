import tempfile
import unittest
from pathlib import Path

from orchestrator.keyframe_page_controller import KeyframePageController


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

    def _many_rows(self, count):
        shots = [{'id': f'SH{i:03d}', 'title': f'镜头{i}', 'duration': 3, 'frame': f'frames/SH{i:03d}.png'}
                 for i in range(1, count + 1)]
        episode = {'shots': shots}
        return episode, [(shot['id'], shot, self.first, self.base_one, episode) for shot in shots]

    def test_pagination_caps_page_size_at_100_and_navigates_pages(self):
        episode, rows = self._many_rows(235)
        controller = KeyframePageController(self.first, episode, self.base_one, rows, page_size=250)
        self.assertEqual(controller.page_size, 100)
        self.assertEqual(controller.total_rows, 235)
        self.assertEqual(controller.total_pages, 3)
        self.assertEqual(controller.current_page, 1)
        page1 = controller.page_ids()
        self.assertEqual(len(page1), 100)
        self.assertEqual((page1[0], page1[-1]), ('SH001', 'SH100'))

        self.assertEqual(controller.next_page(), 2)
        page2 = controller.page_ids()
        self.assertEqual(len(page2), 100)
        self.assertEqual((page2[0], page2[-1]), ('SH101', 'SH200'))

        self.assertEqual(controller.last_page(), 3)
        page3 = controller.page_ids()
        self.assertEqual(len(page3), 35)
        self.assertEqual((page3[0], page3[-1]), ('SH201', 'SH235'))

        self.assertEqual(controller.prev_page(), 2)
        self.assertEqual(controller.first_page(), 1)
        self.assertEqual(controller.set_page(99), 3)
        self.assertEqual(controller.set_page(0), 1)

    def test_cross_page_selection_preserves_shot_ids_across_page_switches(self):
        episode, rows = self._many_rows(235)
        controller = KeyframePageController(self.first, episode, self.base_one, rows)
        controller.sync_page_selection(('SH005', 'SH012'))
        self.assertEqual(controller.selected_shot_ids, {'SH005', 'SH012'})

        controller.next_page()
        self.assertEqual(controller.selected_on_page(), [])
        self.assertEqual(controller.selected_shot_ids, {'SH005', 'SH012'})

        controller.sync_page_selection(('SH105',))
        self.assertEqual(controller.selected_shot_ids, {'SH005', 'SH012', 'SH105'})

        controller.prev_page()
        self.assertEqual(controller.selected_on_page(), ['SH005', 'SH012'])
        controller.sync_page_selection(('SH005',))
        self.assertEqual(controller.selected_shot_ids, {'SH005', 'SH105'})

        controller.replace_rows([row for row in rows if row[0] != 'SH105'])
        self.assertEqual(controller.selected_shot_ids, {'SH005'})

    def test_select_current_page_only_selects_visible_page_and_jump_to_shot(self):
        episode, rows = self._many_rows(235)
        controller = KeyframePageController(self.first, episode, self.base_one, rows)
        controller.sync_page_selection(('SH005',))
        controller.next_page()
        selected = controller.select_current_page()
        self.assertEqual(len(selected), 100)
        self.assertEqual((selected[0], selected[-1]), ('SH101', 'SH200'))
        self.assertEqual(controller.selected_shot_ids, set(selected))
        self.assertNotIn('SH005', controller.selected_shot_ids)
        self.assertNotIn('SH201', controller.selected_shot_ids)

        jumped = controller.jump_to_shot('SH220')
        self.assertEqual(jumped, 'SH220')
        self.assertEqual(controller.current_page, 3)
        self.assertIsNone(controller.jump_to_shot('SH999'))

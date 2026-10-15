from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from storyboard_page_controller import StoryboardPageController


class StoryboardPageControllerTests(unittest.TestCase):
    def test_refresh_reconciles_selection_and_control_states_without_tk(self):
        with tempfile.TemporaryDirectory() as folder:
            project = Path(folder)
            script = project / 'EP001.md'
            board = project / 'EP001.json'
            script.write_text('剧本', encoding='utf-8')
            board.write_text('{}', encoding='utf-8')
            with patch('storyboard_page_controller.selected_many', return_value=[]), \
                 patch('storyboard_page_controller.remember_many') as remember, \
                 patch('storyboard_page_controller.catalog_snapshot', return_value={
                     kind: [{'path': script if kind == 'script' else board, 'title': 'x',
                             'created': 1, 'done': kind == 'script'}]
                     for kind in ('script', 'storyboard')}), \
                 patch('storyboard_page_controller.produced_scripts', return_value={script}), \
                 patch('storyboard_page_controller.adopted', return_value={board}):
                controller = StoryboardPageController(project)
                catalogs = controller.apply_catalogs(controller.refresh_catalogs())
                self.assertEqual(catalogs['script'][0]['path'], script)
                self.assertEqual(controller.selection('script'), [])
                states = controller.control_states([script], [board])
                self.assertFalse(states['agent'])
                self.assertFalse(states['delete_script'])
                self.assertFalse(states['delete_storyboard'])
                self.assertGreaterEqual(remember.call_count, 2)

    def test_recycle_plan_and_execution_stay_behind_controller(self):
        with tempfile.TemporaryDirectory() as folder:
            project = Path(folder)
            board = project / 'EP001.json'
            board.write_text('{}', encoding='utf-8')
            with patch('storyboard_page_controller.selected_many', return_value=[]), \
                 patch('storyboard_page_controller.adopted', return_value=set()), \
                 patch('storyboard_page_controller.recycle_plan', return_value=[board]) as plan, \
                 patch('storyboard_page_controller.recycle_files', return_value=project / '回收站') as recycle:
                controller = StoryboardPageController(project)
                sources, targets = controller.recycle_targets('storyboard', [board])
                self.assertEqual((sources, targets), ([board], [board]))
                self.assertEqual(controller.recycle('storyboard', [board]), project / '回收站')
                self.assertEqual(plan.call_count, 2)
                recycle.assert_called_once_with(project, 'storyboard', [board])

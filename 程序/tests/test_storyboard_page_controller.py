from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import patch

from orchestrator import storyboard_selection
from orchestrator.storyboard_page_controller import StoryboardPageController


class StoryboardPageControllerTests(unittest.TestCase):
    def test_refresh_reconciles_selection_and_control_states_without_tk(self):
        with tempfile.TemporaryDirectory() as folder:
            project = Path(folder)
            script = project / 'EP001.md'
            board = project / 'EP001.json'
            script.write_text('剧本', encoding='utf-8')
            board.write_text('{}', encoding='utf-8')
            with patch('orchestrator.storyboard_page_controller.selected_many', return_value=[]), \
                 patch('orchestrator.storyboard_page_controller.remember_many') as remember, \
                 patch('orchestrator.storyboard_page_controller.catalog_snapshot', return_value={
                     kind: [{'path': script if kind == 'script' else board, 'title': 'x',
                             'created': 1, 'done': kind == 'script'}]
                     for kind in ('script', 'storyboard')}), \
                 patch('orchestrator.storyboard_page_controller.produced_scripts', return_value={script}), \
                 patch('orchestrator.storyboard_page_controller.adopted', return_value={board}):
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
            with patch('orchestrator.storyboard_page_controller.selected_many', return_value=[]), \
                 patch('orchestrator.storyboard_page_controller.adopted', return_value=set()), \
                 patch('orchestrator.storyboard_page_controller.recycle_plan', return_value=[board]) as plan, \
                 patch('orchestrator.storyboard_page_controller.recycle_files', return_value=project / '回收站') as recycle:
                controller = StoryboardPageController(project)
                sources, targets = controller.recycle_targets('storyboard', [board])
                self.assertEqual((sources, targets), ([board], [board]))
                self.assertEqual(controller.recycle('storyboard', [board]), project / '回收站')
                self.assertEqual(plan.call_count, 2)
                recycle.assert_called_once_with(project, 'storyboard', [board])

    def test_refresh_after_selected_board_is_deleted_drops_it_instead_of_failing(self):
        """删除已勾选的分镜后刷新：不因读已删文件时间报 WinError 2，表格与勾选都不再保留它。"""
        with tempfile.TemporaryDirectory() as folder:
            project = Path(folder).resolve()
            kept = project / 'EP002.json'
            gone = project / 'EP001.json'
            kept.write_text('{}', encoding='utf-8')
            gone.write_text('{}', encoding='utf-8')
            with patch('orchestrator.storyboard_page_controller.selected_many', return_value=[]), \
                 patch('orchestrator.storyboard_page_controller.remember_many'), \
                 patch('orchestrator.storyboard_page_controller.produced_scripts', return_value=set()), \
                 patch('orchestrator.storyboard_page_controller.adopted', return_value=set()):
                controller = StoryboardPageController(project)
                controller.choose('storyboard', [gone, kept])
                gone.unlink()
                catalogs = controller.apply_catalogs({
                    'script': [],
                    'storyboard': [{'path': kept, 'title': 'EP002', 'created': 1, 'done': False}],
                })
                self.assertEqual([entry['path'] for entry in catalogs['storyboard']], [kept])
                self.assertEqual(controller.selection('storyboard'), [kept])

    def test_a_vanished_project_folder_is_not_recreated_by_the_page_scan(self):
        with tempfile.TemporaryDirectory() as folder:
            gone = Path(folder) / '项目' / '已移走'
            controller = StoryboardPageController(gone)
            with self.assertRaises(ValueError) as caught:
                controller.apply_catalogs({'script': [], 'storyboard': [], 'completed_scripts': []})
            self.assertIn('项目目录不存在或已被移动', str(caught.exception))
            self.assertFalse(gone.exists())
            self.assertFalse(gone.parent.exists())

    def test_remembering_a_selection_never_recreates_the_project_folder(self):
        with tempfile.TemporaryDirectory() as folder:
            gone = Path(folder) / '项目' / '已移走'
            for kind in ('script', 'storyboard'):
                with self.subTest(kind=kind), self.assertRaises(ValueError) as caught:
                    storyboard_selection.remember_many(gone, kind, [])
                self.assertIn('项目目录不存在或已被移动', str(caught.exception))
            self.assertFalse(gone.exists())

    def test_remembering_a_selection_still_works_in_an_existing_project(self):
        with tempfile.TemporaryDirectory() as folder:
            project = Path(folder)
            storyboard_selection.remember_many(project, 'script', [])
            path = project / 'ui_settings.json'
            self.assertTrue(path.is_file())
            self.assertEqual(json.loads(path.read_text(encoding='utf-8'))['storyboard_scripts'], [])


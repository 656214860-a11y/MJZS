"""Complete storyboard catalogs reuse one scan and one source lookup per kind."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import infra.file_cache as file_cache
import storyboard_catalog_service as service
import stage_execution_service as stages
from orchestrator.storyboard_page_controller import StoryboardPageController


class StoryboardCatalogSnapshotTests(unittest.TestCase):
    def make_project(self, folder):
        project = Path(folder).resolve()
        script = project / '01剧本准备' / 'EP001_正式剧本.md'
        board = project / '03初步分镜' / 'EP001_分镜.json'
        script.parent.mkdir()
        script.write_text('# 第一集\n\n正式剧本', encoding='utf-8')
        board.parent.mkdir()
        board.write_text(json.dumps({
            'episode_id': 'EP001', 'title': '第一集',
            'source_script': script.relative_to(project).as_posix(),
            'shots': [{'id': 'SH001', 'duration': 5}],
        }, ensure_ascii=False), encoding='utf-8')
        return project, script, board

    def test_controller_refresh_discovers_each_kind_once(self):
        with tempfile.TemporaryDirectory() as folder:
            project, _script, _board = self.make_project(folder)
            controller = StoryboardPageController(project)
            with patch.object(service, 'discover_files', wraps=service.discover_files) as discover:
                controller.refresh_catalogs()
            suffixes = [call.args[1] for call in discover.call_args_list]
            self.assertEqual(suffixes.count({'.json'}), 1)
            self.assertEqual(len(suffixes), 2)

    def test_snapshot_preserves_catalogs_and_previews_without_rereading_boards(self):
        with tempfile.TemporaryDirectory() as folder:
            project, script, board = self.make_project(folder)
            expected = {kind: stages.storyboard_catalog(project, kind)
                        for kind in ('script', 'storyboard')}
            previews = {entry['path']: service.content_preview(entry['path'])
                        for entries in expected.values() for entry in entries}
            with patch.object(file_cache, 'read_json', wraps=file_cache.read_json) as read_json:
                actual = stages.storyboard_catalog_snapshot(project)
            for kind in ('script', 'storyboard'):
                self.assertEqual([{key: value for key, value in entry.items() if key != 'preview'}
                                  for entry in actual[kind]], expected[kind])
                self.assertEqual([entry['preview'] for entry in actual[kind]],
                                 [previews[entry['path']] for entry in expected[kind]])
            self.assertEqual(actual['completed_scripts'], {script})
            board_reads = [call for call in read_json.call_args_list if Path(call.args[0]) == board]
            self.assertEqual(len(board_reads), 1)

    def test_apply_snapshot_uses_completed_paths_without_io_or_re_resolving(self):
        with tempfile.TemporaryDirectory() as folder:
            project, script, board = self.make_project(folder)
            controller = StoryboardPageController(project)
            catalogs = {'script': [{'path': script, 'title': 'script', 'done': False}],
                        'storyboard': [{'path': board, 'title': 'board', 'done': False}],
                        'completed_scripts': {project / 'EP002.md'}}
            with patch('orchestrator.storyboard_page_controller.produced_scripts',
                       side_effect=AssertionError('Snapshot already contains completed scripts')), \
                 patch('orchestrator.storyboard_page_controller.remember_many'), \
                 patch('orchestrator.storyboard_page_controller.adopted', return_value=set()), \
                 patch.object(Path, 'resolve', side_effect=AssertionError('Paths are already resolved')):
                result = controller.apply_catalogs(catalogs)
            self.assertEqual(result['script'], catalogs['script'])
            self.assertEqual(controller.selection('script'), [script])
            self.assertEqual(controller.completed_scripts, catalogs['completed_scripts'])

    def test_snapshot_keeps_preview_fallback_for_nontext_episode_id(self):
        with tempfile.TemporaryDirectory() as folder:
            project, _script, board = self.make_project(folder)
            data = json.loads(board.read_text(encoding='utf-8'))
            data['episode_id'] = 7
            board.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
            snapshot = stages.storyboard_catalog_snapshot(project)
            self.assertEqual(snapshot['storyboard'][0]['preview'], board.stem)
            self.assertEqual(snapshot['storyboard'][0]['preview'], service.content_preview(board))

    def test_apply_snapshot_path_matching_is_linear_in_catalog_size(self):
        with tempfile.TemporaryDirectory() as folder:
            project = Path(folder).resolve()
            controller = StoryboardPageController(project)
            paths = [project / ('EP%03d.md' % number) for number in range(120)]
            catalogs = {'script': [{'path': path, 'title': path.stem, 'done': False}
                                   for path in paths],
                        'storyboard': [], 'completed_scripts': set()}
            comparisons = []
            original_eq = Path.__eq__

            def compare(left, right):
                comparisons.append(None)
                return original_eq(left, right)

            with patch('orchestrator.storyboard_page_controller.remember_many'), \
                 patch('orchestrator.storyboard_page_controller.adopted', return_value=set()), \
                 patch.object(Path, '__eq__', compare):
                controller.apply_catalogs(catalogs)
            self.assertLessEqual(len(comparisons), len(paths) * 3)
            self.assertEqual(controller.selection('script'), paths)

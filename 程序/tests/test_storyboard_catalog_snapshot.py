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


class StructureScriptCatalogTests(unittest.TestCase):
    """REQ-S03-07：初步分镜页的剧本清单列出每份可见的结构剧本。"""

    def make_project(self, folder):
        project = Path(folder).resolve() / '项目'
        source = project / '01剧本准备' / '项目剧本' / '项目_自然剧本_Google_20261114.md'
        source.parent.mkdir(parents=True)
        source.write_text('第 1 集\n场景 1：夜，旧书店内\n林小满：把旧怀表交给我。\n', encoding='utf-8')
        target = project / '02剧本结构' / '结构剧本'
        target.mkdir(parents=True)
        return project, source, target

    def episode(self, project, source, target, number):
        path = target / ('项目_结构剧本_第%02d集_20261122.md' % number)
        path.write_text('# 第%d集：雨夜来客\n\n> 结构化剧本 · 第 %d 集\n> 来源：`%s`\n\n## 四、分场结构\n'
                        % (number, number, source.relative_to(project).as_posix()), encoding='utf-8')
        return path

    def listed(self, project):
        return [entry['path'] for entry in stages.storyboard_catalog(project, 'script')]

    def test_model_written_episode_script_is_listed(self):
        """模型按集写的结构剧本（版式不是本地规则那一种）在初步分镜页能选到。"""
        with tempfile.TemporaryDirectory() as folder:
            project, source, target = self.make_project(folder)
            episode = self.episode(project, source, target, 1)
            self.assertEqual(self.listed(project), [episode])

    def test_every_visible_structure_script_is_listed_not_only_the_newest(self):
        """按集各写一份时每一集都列出，按集号排序。"""
        with tempfile.TemporaryDirectory() as folder:
            project, source, target = self.make_project(folder)
            episodes = [self.episode(project, source, target, number) for number in (1, 2)]
            self.assertEqual(self.listed(project), episodes)

    def test_structure_script_whose_source_is_gone_stays_hidden(self):
        """来源原稿已不在的旧结构稿不列出（REQ-S02-21），可见的那份照常列出。"""
        with tempfile.TemporaryDirectory() as folder:
            project, source, target = self.make_project(folder)
            episode = self.episode(project, source, target, 1)
            orphan = target / '项目_结构剧本_正稿_20261021.md'
            orphan.write_text('# 结构化剧本\n\n> 来源：`01剧本准备/项目剧本/项目_自然剧本_Anthropic_20261014.md`\n\n'
                              '## 角色档案\n\n## 分场剧本\n', encoding='utf-8')
            self.assertEqual(self.listed(project), [episode])

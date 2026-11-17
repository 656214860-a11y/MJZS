"""P2：分镜启动计划可脱离 Tk/Agent 直接验证。"""
import tempfile
import unittest
from pathlib import Path

from orchestrator.storyboard_plan_service import build_work_plan
from storyboard_catalog_service import discover_files, document_dir, file_snapshot, has_synced_assets, working_dir
from stage_execution_service import project_context


class StoryboardPlanServiceTests(unittest.TestCase):
    def test_plan_deduplicates_and_classifies_production_and_adoption(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            script_a, script_b, board_a, board_b = (root / name for name in ('a.md', 'b.md', 'a.json', 'b.json'))
            result = build_work_plan([script_a, script_a, script_b], [board_a, board_b], [script_a], [board_a])
        self.assertEqual(result['scripts'], [script_a.resolve(), script_b.resolve()])
        self.assertEqual(result['todo'], [script_b.resolve()])
        self.assertEqual(result['revise'], [board_b.resolve()])

    def test_catalog_discovery_excludes_empty_internal_and_link_escape_files(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / 'project'; root.mkdir()
            keep = root / '分镜文档' / 'EP001.json'; keep.parent.mkdir()
            keep.write_text('{"shots":[1]}', encoding='utf-8')
            (root / '分镜文档' / 'empty.json').write_text('', encoding='utf-8')
            internal = root / '历史版本' / 'old.json'; internal.parent.mkdir(); internal.write_text('{}', encoding='utf-8')
            rows = list(discover_files([root], {'.json'}, {'历史版本'}))
            self.assertEqual([(item[0].name, item[1]) for item in rows], [('EP001.json', keep.resolve())])

    def test_synced_asset_predicate_uses_the_storyboard_sibling_registry(self):
        with tempfile.TemporaryDirectory() as temp:
            board = Path(temp) / '分镜' / 'episode.json'; board.parent.mkdir()
            board.write_text('{}', encoding='utf-8')
            self.assertFalse(has_synced_assets(board))
            (board.parent / 'assets.json').write_text('{}', encoding='utf-8')
            self.assertTrue(has_synced_assets(board))

    def test_file_snapshot_ignores_empty_and_internal_documents(self):
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            from contract.project_stages import storyboard
            board = storyboard(project) / 'EP001.json'; board.parent.mkdir(parents=True)
            board.write_text('{}', encoding='utf-8')
            (board.parent / 'empty.json').write_text('', encoding='utf-8')
            ignored = board.parent / '历史版本' / 'old.json'; ignored.parent.mkdir(); ignored.write_text('{}', encoding='utf-8')
            rows = file_snapshot(project_context(project))
            self.assertEqual(len(rows), 1)
            self.assertEqual(Path(rows[0][0]), board)

    def test_storyboard_workspace_paths_are_headless_stage_derivations(self):
        project = Path('D:/project')
        self.assertEqual(working_dir(project_context(project)), Path('D:/project/03初步分镜/分镜拆分'))
        self.assertEqual(document_dir(project_context(project)), Path('D:/project/03初步分镜/分镜文档'))

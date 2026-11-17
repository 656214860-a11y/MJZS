# -*- coding: utf-8 -*-
"""性能轮 PERFSB2：prune_invalid_adoptions 惰性扫描剧本目录。

改动前，prune_invalid_adoptions 对每个已采用分镜都调 catalog('script') 做一轮完整
剧本扫描，而该调用没传 completed，又经 produced_scripts 再扫一遍分镜目录——N 个已采用
分镜即约 2N 次整库扫描。本测试用计数器断言：
- 空采用列表、或所有板都在来源比对前返回：0 次扫描（与改前一致）；
- N 个板都到达来源比对（N=1／2／10）：_catalog 与 discover_files 各 1 次。
且 prune 仍会把来源失效的板摘掉、返回值与基线一致。
"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

BASELINE_REV = '39b3c7f6'  # 改动前（R1746）的 storyboard_selection.py 作对照基线
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
os.chdir(HERE)

import infra.file_cache as file_cache
import storyboard_catalog_service
import storyboard_selection
from agent.core import save
from project_context_factory import project_context
from contract.stage_path_service import write_dir


def _shot(sid='SH001', duration=5):
    return {'id': sid, 'title': '镜头', 'duration': duration, 'characters': [],
            'location': 'LOC_001', 'props': [], 'frame': 'frames/%s.png' % sid,
            'video_prompt': '景别机位、动作起止与对白', 'dialogue': []}


def _board(episode_id='EP001'):
    return {'episode_id': episode_id, 'title': '测试集', 'duration': 5,
            'shots': [_shot()]}


def _working(root):
    folder = write_dir(root, 'storyboard')
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def _script(root, name):
    path = write_dir(root, 'script') / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('# 第一集\n\n正式剧本\n', encoding='utf-8')
    return path


def _adopted_fixture(project, count, invalid_indexes=()):
    """造 count 个已采用分镜；invalid_indexes 里的板其来源剧本被删除（来源失效）。"""
    project = Path(project)
    folder = _working(project)
    boards = []
    invalid = []
    for index in range(count):
        script = _script(project, 'EP%03d_正式剧本.md' % index)
        board = folder / ('EP%03d_分镜.json' % index)
        data = _board('EP%03d' % index)
        data['source_script'] = script.relative_to(project).as_posix()
        save(board, data)
        if index in invalid_indexes:
            script.unlink()
            invalid.append(board)
        boards.append(board)
    save(project / 'ui_settings.json', {
        'adopted_storyboards': [b.relative_to(project).as_posix() for b in boards],
        'frame_json': boards[-1].relative_to(project).as_posix() if boards else '',
    })
    file_cache.clear()
    return boards, invalid


def _early_return_fixture(project):
    """所有已采用板都在来源比对前提前返回（空采用列表另测）。

    EP000／EP001 是损坏 JSON → 读 JSON 处返回（旧版 paths 只回退默认源，
    非默认源路径不会跳过）；EP002／EP003 是空来源／无来源历史 JSON → 来源检查处返回。
    """
    project = Path(project)
    folder = _working(project)
    boards = []
    for index, content in enumerate(('bad', 'bad')):
        script = _script(project, 'EP%03d_正式剧本.md' % index)
        board = folder / ('EP%03d_分镜.json' % index)
        data = _board('EP%03d' % index)
        data['source_script'] = script.relative_to(project).as_posix()
        save(board, data)
        if content == 'bad':
            # 损坏 JSON：在读 JSON 处返回。
            board.write_text(content, encoding='utf-8')
        boards.append(board)
    adopted = [b.relative_to(project).as_posix() for b in boards]
    # 无来源／空来源历史 JSON：在来源比对前返回。所有引用都失效，旧版 paths 不会退回默认源。
    for data in ({'episode_id': 'EP002', 'title': '无来源', 'shots': [_shot()]},
                 {'episode_id': 'EP003', 'title': '空来源', 'shots': [_shot()],
                  'source_script': ''}):
        data['source_script'] = ''
        board = folder / ('%s_分镜.json' % data['episode_id'])
        save(board, data)
        boards.append(board)
        adopted.append(board.relative_to(project).as_posix())
    save(project / 'ui_settings.json', {'adopted_storyboards': adopted,
                                       'frame_json': adopted[-1]})
    file_cache.clear()
    return boards


def _late_comparison_fixture(project):
    """仅一块板到达来源比对、其余提前返回；目录还有一块来源失效的孤儿板。"""
    project = Path(project)
    folder = _working(project)
    boards = []
    for index, reaches in enumerate((False, False, False, True)):
        script = _script(project, 'EP%03d_正式剧本.md' % index)
        board = folder / ('EP%03d_分镜.json' % index)
        data = _board('EP%03d' % index)
        data['source_script'] = script.relative_to(project).as_posix()
        save(board, data)
        if not reaches:
            script.unlink()
            board.write_text('not json', encoding='utf-8')
        boards.append(board)
    for episode_id in ('EP004', 'EP005'):
        board = folder / ('%s_分镜.json' % episode_id)
        save(board, {'episode_id': episode_id, 'title': '历史板',
                     'shots': [_shot()], 'source_script': ''})
        boards.insert(-1, board)
    orphan = folder / 'EP006_孤儿分镜.json'
    orphan_script = _script(project, 'EP006_正式剧本.md')
    save(orphan, {'episode_id': 'EP006', 'title': '孤儿板', 'shots': [_shot()],
                  'source_script': orphan_script.relative_to(project).as_posix()})
    orphan_script.unlink()
    save(project / 'ui_settings.json', {
        'adopted_storyboards': [b.relative_to(project).as_posix() for b in boards],
        'frame_json': boards[0].relative_to(project).as_posix(),
    })
    file_cache.clear()
    return boards, orphan

class StoryboardCatalogScanCountTests(unittest.TestCase):
    def setUp(self):
        file_cache.clear()

    def _count_with_fetcher(self, project):
        """计数 _catalog/discover_files，并直接记录 available 取数器的调用次数。"""
        real_error = storyboard_selection.source_script_error
        fetches = []

        def counted_error(current, board, available=None):
            if callable(available):
                def fetch():
                    fetches.append(1)
                    return available()
                available = fetch
            return real_error(current, board, available=available)

        with patch.object(storyboard_selection, 'source_script_error', counted_error), \
             patch.object(storyboard_catalog_service, '_catalog',
                          wraps=storyboard_catalog_service._catalog) as catalog_mock, \
             patch.object(storyboard_catalog_service, 'discover_files',
                          wraps=storyboard_catalog_service.discover_files) as discover_mock:
            removed = storyboard_selection.prune_invalid_adoptions(project)
        return (catalog_mock.call_count, discover_mock.call_count, len(fetches)), removed

    def _count(self, project):
        with patch.object(storyboard_catalog_service, '_catalog',
                          wraps=storyboard_catalog_service._catalog) as catalog_mock, \
             patch.object(storyboard_catalog_service, 'discover_files',
                          wraps=storyboard_catalog_service.discover_files) as discover_mock:
            removed = storyboard_selection.prune_invalid_adoptions(project)
        return (catalog_mock.call_count, discover_mock.call_count), removed

    def test_prune_empty_adoptions_scans_nothing(self):
        """空采用列表：_catalog、discover_files 与取数器都不调用（PERFSB2 口径，0 次）。

        改动前 HEAD 也是 0 次（循环不进入）；PERFSB 初版在循环外无条件预取，变成了 1 次，
        这里按“需要才扫”的要求从 1 收回 0。
        """
        with tempfile.TemporaryDirectory() as td:
            project = Path(td)
            _adopted_fixture(project, 0)
            (catalog_count, discover_count, fetches), removed = self._count_with_fetcher(project)
        self.assertEqual((catalog_count, discover_count), (0, 0),
                         '空采用列表不应扫描剧本目录，实际 %s' % ((catalog_count, discover_count),))
        self.assertEqual(fetches, 0, '空采用列表连预取器都不应调用')
        self.assertEqual(removed, ())

    def test_prune_scans_zero_unless_a_board_reaches_comparison(self):
        """只有最后一块到达来源比对：_catalog 与 discover_files 各只调用 1 次。"""
        with tempfile.TemporaryDirectory() as td:
            project = Path(td)
            boards, orphan = _late_comparison_fixture(project)
            (catalog_count, discover_count), removed = self._count(project)
        self.assertEqual((catalog_count, discover_count), (1, 1))
        self.assertEqual(removed, tuple(str(board.resolve()) for board in boards[:3]))
        self.assertNotIn(str(orphan.resolve()), removed, '未被采用的板不属于采用列表')

    def test_prune_scans_nothing_when_all_boards_return_early(self):
        """所有板都在来源比对前提前返回：_catalog、discover_files 与取数器都不调用。"""
        with tempfile.TemporaryDirectory() as td:
            project = Path(td)
            boards = _early_return_fixture(project)
            (catalog_count, discover_count, fetches), removed = self._count_with_fetcher(project)
        self.assertEqual((catalog_count, discover_count), (0, 0),
                         '提前返回的板不应触发扫描，实际 %s' % ((catalog_count, discover_count),))
        self.assertEqual(fetches, 0, '提前返回的板连预取器都不应调用')
        # 与改前一致：两份损坏 JSON 被摘；两份空来源历史板保持可采用。
        self.assertEqual(removed, tuple(str(board.resolve()) for board in boards[:2]))

    def test_early_return_removed_values_match_head(self):
        """提前返回场景的摘除结果与改前 R1746 逐项一致（不只比扫描次数）。"""
        import subprocess
        with tempfile.TemporaryDirectory() as td:
            project = Path(td) / '项目'
            _early_return_fixture(project)
            # prune 会改写项目偏好，基线对照须用另一份同构夹具，不能复用已被改写的项目。
            project_baseline = Path(td) / '项目基线'
            _early_return_fixture(project_baseline)
            current = storyboard_selection.prune_invalid_adoptions(project)
            baseline = Path(td) / 'lane'
            baseline.mkdir()
            source = subprocess.run(['git', 'show', BASELINE_REV + ':程序/storyboard_selection.py'],
                                    cwd=HERE, capture_output=True, text=True, check=True).stdout
            (baseline / 'storyboard_selection.py').write_text(source, encoding='utf-8')
            code = (
                "import sys; from pathlib import Path\n"
                "sys.path[:0]=[sys.argv[1], sys.argv[2], sys.argv[3]]\n"
                "import storyboard_selection as s\n"
                "from pathlib import Path\n"
                "removed = s.prune_invalid_adoptions(sys.argv[4])\n"
                "import json; print(json.dumps(list(removed), ensure_ascii=False))\n"
            )
            output = subprocess.run([sys.executable, '-B', '-X', 'utf8', '-c', code,
                                     str(baseline), os.path.dirname(HERE),
                                     os.path.dirname(os.path.dirname(HERE)),
                                     str(project_baseline)],
                                    capture_output=True, text=True, encoding='utf-8',
                                    cwd=str(baseline))
        self.assertEqual(output.returncode, 0, output.stderr[-500:])
        baseline_removed = [str(p).replace(str(project_baseline.resolve()), str(project.resolve()))
                            for p in json.loads(output.stdout.strip())]
        self.assertEqual(list(current), baseline_removed)

    def test_prune_early_return_counts_match_baseline_no_scan(self):
        """对照改前 R1746 实现（复制到临时目录）：提前返回场景改前也 0 次扫描。"""
        import subprocess
        with tempfile.TemporaryDirectory() as td:
            project = Path(td) / '项目'
            _early_return_fixture(project)
            baseline = Path(td) / 'lane'
            baseline.mkdir()
            source = subprocess.run(['git', 'show', BASELINE_REV + ':程序/storyboard_selection.py'],
                                    cwd=HERE, capture_output=True, text=True, check=True).stdout
            (baseline / 'storyboard_selection.py').write_text(source, encoding='utf-8')
            code = (
                "import sys; from pathlib import Path; from unittest.mock import patch\n"
                "sys.path[:0]=[sys.argv[1], sys.argv[2], sys.argv[3]]\n"
                "import storyboard_selection as s, storyboard_catalog_service as c\n"
                "with patch.object(c,'_catalog',wraps=c._catalog) as cm, \\\n"
                "     patch.object(c,'discover_files',wraps=c.discover_files) as dm:\n"
                "    s.prune_invalid_adoptions(sys.argv[4])\n"
                "    print('COUNT', cm.call_count, dm.call_count)\n"
            )
            output = subprocess.run([sys.executable, '-B', '-c', code,
                                     str(baseline), os.path.dirname(HERE),
                                     os.path.dirname(os.path.dirname(HERE)),
                                     str(project)],
                                    capture_output=True, text=True, cwd=str(baseline))
        self.assertEqual(output.returncode, 0, output.stderr[-500:])
        self.assertIn('COUNT 0 0', output.stdout)

    def test_prune_scan_count_is_one_for_one_two_ten_comparisons(self):
        """1／2／10 个板都到达来源比对时，_catalog 与 discover_files 各只调用 1 次。"""
        counts = {}
        invalid_by_count = {}
        for count, invalid_indexes in ((1, (0,)), (2, (0, 1)), (10, (5,))):
            with tempfile.TemporaryDirectory() as td:
                project = Path(td)
                _boards, invalid = _adopted_fixture(project, count, invalid_indexes)
                counts[count], removed = self._count(project)
                invalid_by_count[count] = (removed, invalid)

        catalog_counts = [counts[count][0] for count in (1, 2, 10)]
        discover_counts = [counts[count][1] for count in (1, 2, 10)]
        self.assertEqual(catalog_counts, [1, 1, 1],
                         '_catalog 调用次数应恒为 1，实际 %s' % catalog_counts)
        self.assertEqual(discover_counts, [1, 1, 1],
                         'discover_files 调用次数应恒为 1，实际 %s' % discover_counts)
        for count in (1, 2, 10):
            removed, invalid = invalid_by_count[count]
            self.assertEqual(removed, tuple(str(board.resolve()) for board in invalid))

    def test_prune_still_removes_invalid_source_board(self):
        """1 个来源失效板：prune 返回值与基线一致，仍把它摘掉、保留 JSON 文件。"""
        with tempfile.TemporaryDirectory() as td:
            project = Path(td)
            boards, invalid = _adopted_fixture(project, 1, (0,))
            removed = storyboard_selection.prune_invalid_adoptions(project)
            self.assertEqual(removed, (str(invalid[0].resolve()),))
            self.assertTrue(invalid[0].is_file(), '来源失效只取消采用，不删分镜文件')
            self.assertEqual(storyboard_selection.adopted(project), [])

    def test_catalog_script_paths_unchanged_when_completed_passed(self):
        """catalog('script') 传 completed 与否，返回的剧本路径集合逐项一致（优化不改输出）。"""
        with tempfile.TemporaryDirectory() as td:
            project = Path(td)
            _boards, _invalid = _adopted_fixture(project, 1, ())
            context = project_context(project)
            full = storyboard_catalog_service.catalog(context, 'script')
            partial = storyboard_catalog_service.catalog(context, 'script', completed=set())
            self.assertEqual([entry['path'] for entry in full],
                             [entry['path'] for entry in partial])
            self.assertTrue(full, '夹具应至少发现一份可用剧本')

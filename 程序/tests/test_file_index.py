# -*- coding: utf-8 -*-
"""R3093（任务书 P0）：项目文件索引的读写、筛选与一致性标记。

覆盖：全量重建写盘并落 DES §3.1 字段；阶段／类型由路径推导；清单引用过的文件标
「已发布」、清单里有但磁盘没有的标 ``missing``；增量更新支持新增与删除；索引缺失或
损坏时自动重建；筛选四条件可组合。
"""
import json
import os
import subprocess
import tempfile
import threading
import unittest
from unittest import mock
from pathlib import Path

import infra.file_index as file_index
from contract import file_naming, stage_layout
from contract.file_index_contract import (INDEX_VERSION, ORIGIN_SYSTEM, ORIGIN_USER, STATUS_ARCHIVED,
                                          STATUS_DRAFT, STATUS_PUBLISHED, FileRow)
from contract.infra_errors import ConfigError


def _write(path, content='x'):
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, bytes):
        path.write_bytes(content)
    else:
        path.write_text(content, encoding='utf-8')
    return path


class FileIndexTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix='file-index-')
        self.root = Path(self.temp.name) / '测试项目'
        self.root.mkdir()
        _write(self.root / '01剧本准备' / 'docs' / '测试项目_剧本_初稿_20261117.md')
        _write(self.root / '01剧本准备' / 'docs' / '角色设定.md')
        _write(self.root / '05资产管理' / 'assets' / 'CHAR_001.png', b'\x89PNG')
        _write(self.root / '11配音与字幕' / '音频' / 'S01.wav', b'RIFF')
        _write(self.root / '10视频生成' / 'assets' / 'EP001_SH001.mp4', b'\x00\x00')

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_rebuild_writes_index_file(self) -> None:
        payload = file_index.rebuild(self.root)
        self.assertEqual(payload['schema_version'], INDEX_VERSION)
        self.assertEqual(payload['project'], '测试项目')
        self.assertTrue(file_index.index_path(self.root).is_file())
        written = json.loads(file_index.index_path(self.root).read_text(encoding='utf-8'))
        self.assertEqual(written['files'], payload['files'])

    def test_rows_carry_stage_and_kind(self) -> None:
        file_index.rebuild(self.root)
        found = {row.path: row for row in file_index.rows(self.root)}
        script = found['01剧本准备/docs/测试项目_剧本_初稿_20261117.md']
        self.assertEqual((script.stage, script.kind), ('script', '剧本'))
        # 契约变更：01剧本准备下的设定/大纲/角色卡与输入附件统一归为「参考」类型，自然剧本仍为「剧本」。
        self.assertEqual(found['01剧本准备/docs/角色设定.md'].kind, '参考')
        self.assertEqual(found['05资产管理/assets/CHAR_001.png'].kind, '资产')
        self.assertEqual(found['11配音与字幕/音频/S01.wav'].kind, '音频')
        self.assertEqual(found['10视频生成/assets/EP001_SH001.mp4'].kind, '视频')

    def test_task_attachment_is_reference_once(self) -> None:
        """原文与转换稿不能按扩展名拆进「其他」和「报告」。"""
        paths = (
            '01剧本准备/输入/项目_原始附件_人物_20261127.xlsx',
            '01剧本准备/输入/项目_附件文本_人物_20261127.md',
            '02剧本结构/任务附件/说明.md',
        )
        self.assertEqual([file_index.kind_of(path) for path in paths], ['参考', '参考', '参考'])
        self.assertEqual(file_index.kind_of('02剧本结构/结构剧本/正稿.md'), '报告')

    def test_size_and_mtime_come_from_disk(self) -> None:
        file_index.rebuild(self.root)
        row = {item.path: item for item in file_index.rows(self.root)}['05资产管理/assets/CHAR_001.png']
        self.assertEqual(row.size, 4)
        self.assertGreater(row.mtime, 0)

    def test_order_and_title_parsed_from_name(self) -> None:
        file_index.rebuild(self.root)
        row = {item.path: item for item in file_index.rows(self.root)}['10视频生成/assets/EP001_SH001.mp4']
        self.assertEqual(row.order, 1)
        self.assertIn('EP001', row.title)

    def test_everything_starts_as_draft(self) -> None:
        file_index.rebuild(self.root)
        self.assertTrue(all(row.status == STATUS_DRAFT for row in file_index.rows(self.root)))

    # 有意更新 status 契约：清单必须 complete 且 reviewed=True，原发布断言保持。
    def test_manifest_marks_file_published(self) -> None:
        _write(self.root / '05资产管理' / '成果确认' / 'abc.json',
               json.dumps({'status': 'complete', 'reviewed': True,
                           'outputs': [{'path': '05资产管理/assets/CHAR_001.png'}]}, ensure_ascii=False))
        file_index.rebuild(self.root)
        row = {item.path: item for item in file_index.rows(self.root)}['05资产管理/assets/CHAR_001.png']
        self.assertEqual(row.status, STATUS_PUBLISHED)

    def test_manifest_path_absent_on_disk_is_marked_missing(self) -> None:
        _write(self.root / '05资产管理' / '成果确认' / 'abc.json',
               json.dumps({'status': 'complete', 'reviewed': True,
                           'outputs': [{'path': '05资产管理/assets/不存在.png'}]}, ensure_ascii=False))
        file_index.rebuild(self.root)
        found = {item.path: item for item in file_index.rows(self.root)}
        missing = found['05资产管理/assets/不存在.png']
        self.assertTrue(missing.missing)
        self.assertEqual(missing.status, STATUS_PUBLISHED)
        self.assertEqual(file_index.summary(self.root)['missing'], 1)

    def test_delivery_manifest_counts_as_published(self) -> None:
        _write(self.root / '13质检交付' / '导出成片' / 'delivery_manifest.json',
               json.dumps({'status': 'complete', 'reviewed': True,
                           'files': [{'path': '10视频生成/assets/EP001_SH001.mp4'}]}, ensure_ascii=False))
        file_index.rebuild(self.root)
        row = {item.path: item for item in file_index.rows(self.root)}['10视频生成/assets/EP001_SH001.mp4']
        self.assertEqual(row.status, STATUS_PUBLISHED)

    def test_archive_files_are_archived(self) -> None:
        _write(self.root / stage_layout.ARCHIVE / 'episode' / '旧镜头.mp4', b'\x00')
        file_index.rebuild(self.root)
        row = {item.path: item for item in file_index.rows(self.root)}['_archive/episode/旧镜头.mp4']
        self.assertEqual(row.status, STATUS_ARCHIVED)
        self.assertEqual(row.stage, '')

    def test_workflow_dir_is_not_indexed(self) -> None:
        _write(self.root / '工作流任务' / '回收站' / '批次' / '恢复位置.json', '{}')
        file_index.rebuild(self.root)
        self.assertFalse([row for row in file_index.rows(self.root) if '工作流任务' in row.path])

    def test_search_filters_combine(self) -> None:
        file_index.rebuild(self.root)
        self.assertEqual(len(file_index.search(self.root, stage='assets')), 1)
        self.assertEqual(len(file_index.search(self.root, kind='剧本')), 1)
        self.assertEqual(len(file_index.search(self.root, kind='资产', name='char')), 1)
        self.assertEqual(file_index.search(self.root, kind='剧本', stage='assets'), [])

    def test_kinds_lists_present_kinds_in_contract_order(self) -> None:
        file_index.rebuild(self.root)
        # 契约变更：「参考」排在工作流类型首位。
        self.assertEqual(file_index.kinds(self.root), ['参考', '剧本', '资产', '音频', '视频'])

    def test_update_adds_and_removes(self) -> None:
        file_index.rebuild(self.root)
        added = _write(self.root / '01剧本准备' / 'docs' / '新增.md')
        file_index.update(self.root, [added])
        self.assertIn('01剧本准备/docs/新增.md', [row.path for row in file_index.rows(self.root)])
        file_index.update(self.root, [added], removed=True)
        self.assertNotIn('01剧本准备/docs/新增.md', [row.path for row in file_index.rows(self.root)])

    def test_update_drops_row_when_file_already_gone(self) -> None:
        file_index.rebuild(self.root)
        gone = self.root / '01剧本准备' / 'docs' / '新增.md'
        _write(gone)
        file_index.update(self.root, [gone])
        gone.unlink()
        file_index.update(self.root, [gone])
        self.assertNotIn('01剧本准备/docs/新增.md', [row.path for row in file_index.rows(self.root)])

    def test_update_rebuilds_when_index_missing(self) -> None:
        payload = file_index.update(self.root, [])
        self.assertEqual(payload['schema_version'], INDEX_VERSION)
        self.assertTrue(file_index.rows(self.root))

    def test_ensure_rebuilds_when_index_is_broken(self) -> None:
        file_index.rebuild(self.root)
        file_index.index_path(self.root).write_text('{坏掉的 JSON', encoding='utf-8')
        self.assertIsNone(file_index.read(self.root))
        self.assertTrue(file_index.rows(self.root))

    def test_ensure_rebuilds_on_version_mismatch(self) -> None:
        file_index.rebuild(self.root)
        path = file_index.index_path(self.root)
        data = json.loads(path.read_text(encoding='utf-8'))
        data['schema_version'] = INDEX_VERSION + 1
        path.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
        self.assertIsNone(file_index.read(self.root))
        self.assertEqual(file_index.ensure(self.root)['schema_version'], INDEX_VERSION)

    def test_rebuild_is_idempotent(self) -> None:
        first = file_index.rebuild(self.root, now=0)
        second = file_index.rebuild(self.root, now=0)
        self.assertEqual(first['files'], second['files'])

    def test_index_path_lives_under_workflow_dir(self) -> None:
        expected = stage_layout.workflow_dir(self.root, '文件索引', 'index.json')
        self.assertEqual(file_index.index_path(self.root), expected)

    def test_index_outside_project_is_rejected(self) -> None:
        file_index.rebuild(self.root)
        with self.assertRaises(ValueError):
            file_index.update(self.root, [Path(self.temp.name) / '外面.txt'])


class FileIndexIntegrityTests(unittest.TestCase):
    def test_root_and_custom_files_are_included_but_secrets_and_runtime_are_not(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            wanted = ['用户笔记.md', '自建素材/封面.png', 'writing/结构剧本/剧本.md',
                      'writing/初稿.md', '09视频生成/assets/旧片.mp4']
            excluded = ['skill_config.json', 'config.json', 'projects.json', '.env', '.env.local',
                        '用户密钥.pem', 'api_key.txt', '配置/用户资料.json', 'private/token.txt',
                        'logs/task.txt', 'data/cache.json', '.cache/a.png',
                        '01剧本准备/logs/run.txt', '工作流任务/文件索引/index.json']
            for name in wanted + excluded:
                _write(root / name)
            table = {row['path']: row for row in file_index.build(root)['files']}
            self.assertEqual(set(table), set(wanted))
            self.assertEqual(table['writing/结构剧本/剧本.md']['stage'], 'script_structure')
            self.assertEqual(table['writing/初稿.md']['stage'], 'script')
            self.assertEqual(table['09视频生成/assets/旧片.mp4']['stage'], 'video')
            self.assertEqual(table['writing/初稿.md']['kind'], '剧本')

    def test_invalid_update_is_rejected_before_missing_index_can_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'project'
            root.mkdir()
            with self.assertRaises(ValueError):
                file_index.update(root, [Path(tmp) / 'outside.txt'])
            self.assertFalse(file_index.index_path(root).exists())

    def test_search_applies_status_and_path_keyword_without_changing_cache(self):
        from agent.core import save
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / '05资产管理/assets/CHAR_008.png'
            path.parent.mkdir(parents=True)
            path.write_bytes(b'image')
            receipt = root / '05资产管理/成果确认/check.json'
            save(receipt, {'status': 'complete', 'reviewed': True,
                           'outputs': [{'path': path.relative_to(root).as_posix()}]})
            file_index.rebuild(root)
            self.assertEqual([row.path for row in file_index.search(root, status='已发布', name='CHAR_008')],
                             [path.relative_to(root).as_posix()])
            self.assertEqual(file_index.search(root, status='已归档'), [])
            self.assertEqual(file_index.search(root, name='不存在的关键字'), [])
            self.assertEqual(file_index.search(root, stage='video'), [])
            self.assertTrue(file_index.read(root))

    def test_untrusted_cache_rejects_duplicate_and_invalid_metadata(self):
        from agent.core import save
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / '01剧本准备/docs/样例.md'
            path.parent.mkdir(parents=True)
            path.write_text('内容', encoding='utf-8')
            payload = file_index.rebuild(root)
            original = payload['files'][0]
            for field, value in (('size', -1), ('mtime', float('inf')), ('missing', 'yes'),
                                 ('status', '伪造确认'), ('origin', '未经登记'), ('order', True)):
                with self.subTest(field=field):
                    row = dict(original, **{field: value})
                    save(file_index.index_path(root), dict(payload, files=[row]))
                    self.assertIsNone(file_index.read(root))
            save(file_index.index_path(root), dict(payload, files=[original, original]))
            self.assertIsNone(file_index.read(root))

    def test_malformed_cached_rows_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for bad in [None, {'path': '../secret'}, {'path': 'a', 'size': 'big'},
                        {'path': 'a', 'order': []}, {'path': 'a', 'missing': 'yes'},
                        {'path': 'a', 'mtime': float('nan')}, {'path': 'a', 'kind': []}]:
                payload = {'schema_version': INDEX_VERSION, 'files': [bad]}
                _write(file_index.index_path(root), json.dumps(payload))
                self.assertIsNone(file_index.read(root), repr(bad))

    def test_cached_reads_refresh_stat_without_walk_or_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = _write(root / '01剧本准备/docs/a.md', 'a')
            file_index.rebuild(root)
            _write(path, 'changed')
            with mock.patch.object(file_index, '_walk', side_effect=AssertionError('full scan')):
                self.assertEqual(file_index.rows(root)[0].size, 7)
                path.unlink()
                self.assertTrue(file_index.rows(root)[0].missing)
                self.assertEqual(file_index.summary(root)['missing'], 1)

    def test_only_reviewed_complete_safe_manifest_paths_are_published(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            confirm = root / '01剧本准备/成果确认'
            _write(confirm / 'unsafe.json', json.dumps({'status': 'complete', 'reviewed': True,
                   'outputs': [{'path': '../escape.mp4'}, {'path': str(root / 'absolute.mp4')},
                               {'path': 'private/key.txt'}, {'path': '01剧本准备/docs/missing.md'}]}))
            _write(confirm / 'unreviewed.json', json.dumps({'status': 'complete',
                   'outputs': [{'path': '01剧本准备/docs/unreviewed.md'}]}))
            _write(confirm / 'draft.json', json.dumps({'status': 'draft', 'reviewed': True,
                   'outputs': [{'path': '01剧本准备/docs/draft.md'}]}))
            self.assertEqual(file_index.published_paths(root), {'01剧本准备/docs/missing.md'})
            rows = file_index.build(root)['files']
            self.assertEqual([r['path'] for r in rows if r['missing']], ['01剧本准备/docs/missing.md'])

    def test_concurrent_updates_do_not_overwrite_each_other(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            file_index.rebuild(root)
            a = _write(root / 'a.md')
            b = _write(root / 'b.md')
            original = file_index.read
            first_read, second_started, release = threading.Event(), threading.Event(), threading.Event()
            errors = []
            def delayed_read(project):
                data = original(project)
                if threading.current_thread().name == 'first':
                    first_read.set()
                    release.wait(3)
                return data
            def run(path):
                try:
                    if path == b:
                        second_started.set()
                    file_index.update(root, [path])
                except Exception as exc:
                    errors.append(exc)
            with mock.patch.object(file_index, 'read', side_effect=delayed_read):
                first = threading.Thread(target=run, args=(a,), name='first')
                second = threading.Thread(target=run, args=(b,), name='second')
                first.start()
                self.assertTrue(first_read.wait(3))
                second.start()
                self.assertTrue(second_started.wait(3))
                second.join(.1)
                release.set()
                first.join(3)
                second.join(3)
            self.assertFalse(first.is_alive() or second.is_alive())
            self.assertEqual(errors, [])
            self.assertEqual({r.path for r in file_index.rows(root)}, {'a.md', 'b.md'})

    def test_large_file_metadata_remains_valid_without_32bit_truncation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = {'schema_version': INDEX_VERSION,
                       'files': [FileRow(path='large.mp4', size=2 ** 33, mtime=1).to_dict()]}
            _write(file_index.index_path(root), json.dumps(payload))
            self.assertEqual(file_index.read(root)['files'][0]['size'], 2 ** 33)

    def test_index_destination_cannot_escape_through_workflow_junction(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'project'
            outside = Path(tmp) / 'outside'
            root.mkdir()
            outside.mkdir()
            destination = file_index.index_path(root)
            original = Path.resolve
            def redirected(path, *args, **kwargs):
                return outside / 'index.json' if path == destination else original(path, *args, **kwargs)
            with mock.patch.object(Path, 'resolve', redirected):
                with self.assertRaises(ValueError):
                    file_index.rebuild(root)
            self.assertEqual(list(outside.iterdir()), [])

    def test_junction_and_file_links_cannot_escape_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'project'
            outside = Path(tmp) / 'outside'
            root.mkdir()
            _write(outside / 'secret.txt')
            junction = root / 'linked'
            if os.name == 'nt':
                result = subprocess.run(['cmd', '/c', 'mklink', '/J', str(junction), str(outside)],
                                        capture_output=True, check=False)
                self.assertEqual(result.returncode, 0, result.stderr)
            else:
                junction.symlink_to(outside, target_is_directory=True)
            try:
                self.assertEqual(file_index.build(root)['files'], [])
                with self.assertRaises(ValueError):
                    file_index.update(root, [junction / 'secret.txt'])
            finally:
                if os.name == 'nt':
                    junction.rmdir()
                else:
                    junction.unlink()
            # Exercise a file link independently of Windows symlink privileges.
            linked = _write(root / 'linked.txt')
            original = Path.resolve
            def redirected(path, *args, **kwargs):
                return outside / 'secret.txt' if path == linked else original(path, *args, **kwargs)
            with mock.patch.object(Path, 'resolve', redirected):
                self.assertEqual(file_index.build(root)['files'], [])


class FileRowTests(unittest.TestCase):
    def test_round_trip(self) -> None:
        row = FileRow(path='01剧本准备/docs/a.md', stage='script', kind='剧本', status=STATUS_PUBLISHED,
                      size=3, mtime=1.5, order=2, title='a', missing=True)
        self.assertEqual(FileRow.from_dict(row.to_dict()), row)

    def test_from_dict_tolerates_missing_and_extra_keys(self) -> None:
        row = FileRow.from_dict({'path': 'a', 'unknown': 1})
        self.assertEqual(row.path, 'a')
        self.assertEqual(row.kind, '其他')
        self.assertEqual(row.status, STATUS_DRAFT)
        self.assertFalse(row.missing)

    def test_sort_key_orders_by_stage_then_kind_then_order(self) -> None:
        rows = [FileRow(path='b', stage='assets', kind='资产', order=2),
                FileRow(path='a', stage='script', kind='剧本', order=9),
                FileRow(path='c', stage='assets', kind='资产', order=1)]
        self.assertEqual([row.path for row in sorted(rows, key=lambda item: item.sort_key())],
                         ['c', 'b', 'a'])


class FileIndexDiscoverTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='file-index-discover-')
        self.root = Path(self.temp.name) / '测试项目'
        self.root.mkdir()
        _write(self.root / '01剧本准备' / 'docs' / 'a.md', 'a')
        _write(self.root / '05资产管理' / 'assets' / 'b.png', b'\x89PNG')
        file_index.rebuild(self.root)

    def tearDown(self):
        self.temp.cleanup()

    def test_discover_finds_external_file(self):
        _write(self.root / '01剧本准备' / 'docs' / '外部新增.md', '新')
        self.assertEqual(file_index.discover(self.root), 1)
        paths = [row.path for row in file_index.rows(self.root)]
        self.assertIn('01剧本准备/docs/外部新增.md', paths)
        with mock.patch('agent.core.save') as save:
            self.assertEqual(file_index.discover(self.root), 0)
        save.assert_not_called()

    def test_discover_stage_limits_scope(self):
        _write(self.root / '01剧本准备' / 'docs' / '新剧本.md', 'x')
        _write(self.root / '05资产管理' / 'assets' / '新资产.png', b'\x89PNG')
        self.assertEqual(file_index.discover(self.root, stage='script'), 1)
        paths = [row.path for row in file_index.rows(self.root)]
        self.assertIn('01剧本准备/docs/新剧本.md', paths)
        self.assertNotIn('05资产管理/assets/新资产.png', paths)
        self.assertEqual(file_index.discover(self.root), 1)
        paths = [row.path for row in file_index.rows(self.root)]
        self.assertIn('05资产管理/assets/新资产.png', paths)

    def test_discover_no_cache_returns_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'nocache'
            root.mkdir()
            _write(root / '01剧本准备' / 'docs' / 'a.md', 'a')
            self.assertFalse(file_index.index_path(root).exists())
            self.assertEqual(file_index.discover(root), 0)
            self.assertFalse(file_index.index_path(root).exists())

    def test_discover_skips_excluded(self):
        _write(self.root / '01剧本准备' / 'logs' / 'run.log', 'log')
        skip_dir = sorted(file_index.SKIP_DIRS)[0]
        hidden = '01剧本准备/%s/hidden.md' % skip_dir
        _write(self.root / '01剧本准备' / skip_dir / 'hidden.md', 'x')
        self.assertEqual(file_index.discover(self.root), 0)
        paths = [row.path for row in file_index.rows(self.root)]
        self.assertNotIn('01剧本准备/logs/run.log', paths)
        self.assertNotIn(hidden, paths)

    def test_discover_multiple_stages(self):
        _write(self.root / '01剧本准备' / 'docs' / '新剧本.md', 'x')
        _write(self.root / '05资产管理' / 'assets' / '新资产.png', b'\x89PNG')
        self.assertEqual(file_index.discover(self.root), 2)
        self.assertEqual(file_index.discover(self.root), 0)

    def test_is_functional_suffixes(self):
        self.assertTrue(file_index.is_functional('x.json'))
        self.assertTrue(file_index.is_functional('x.JSONL'))
        self.assertFalse(file_index.is_functional('x.md'))
        self.assertFalse(file_index.is_functional('x.png'))
        self.assertFalse(file_index.is_functional('x.mp4'))
        self.assertFalse(file_index.is_functional('x.srt'))

    def test_discover_concurrent_registration_returns_zero(self):
        """候选收齐到加锁写回之间另一写入者抢先登记：返回 0、行只出现一次。"""
        _write(self.root / '01剧本准备' / 'docs' / '抢先登记.md', 'x')
        original = file_index._collect_discover_candidates

        def interleaved(root, stages, published, origins, now, existing):
            candidates = original(root, stages, published, origins, now, existing)
            file_index.rebuild(root)
            return candidates

        with mock.patch.object(file_index, '_collect_discover_candidates',
                               side_effect=interleaved):
            self.assertEqual(file_index.discover(self.root), 0)
        paths = [row.path for row in file_index.rows(self.root)]
        self.assertEqual(paths.count('01剧本准备/docs/抢先登记.md'), 1)

    def test_discover_index_deleted_before_lock_returns_zero(self):
        """加锁前索引被删：返回 0 且索引文件不被重建。"""
        _write(self.root / '01剧本准备' / 'docs' / '新增.md', 'x')
        original = file_index._collect_discover_candidates

        def interleaved(root, stages, published, origins, now, existing):
            candidates = original(root, stages, published, origins, now, existing)
            file_index.index_path(root).unlink()
            return candidates

        with mock.patch.object(file_index, '_collect_discover_candidates',
                               side_effect=interleaved):
            self.assertEqual(file_index.discover(self.root), 0)
        self.assertFalse(file_index.index_path(self.root).exists())

    def test_discover_published_paths_failure_returns_zero(self):
        """统计发布路径抛 OSError：discover 吞掉返回 0，索引内容不变。"""
        before = file_index.index_path(self.root).read_bytes()
        with mock.patch.object(file_index, 'published_paths', side_effect=OSError('x')):
            self.assertEqual(file_index.discover(self.root), 0)
        self.assertEqual(file_index.index_path(self.root).read_bytes(), before)

    def test_discover_stage_read_dirs_failure_skips_only_that_stage(self):
        """某阶段目录读取抛错只跳过该阶段，其余阶段的新文件照常收。"""
        _write(self.root / '01剧本准备' / 'docs' / '新剧本.md', 'x')
        _write(self.root / '05资产管理' / 'assets' / '新资产.png', b'\x89PNG')
        original = file_index.read_dirs
        calls = []

        def flaky(project, stage, today=None):
            if stage == 'assets':
                calls.append(stage)
                # 第一次 assets 调用来自 published_paths，放行；候选收集那次才抛错。
                if len(calls) > 1:
                    raise ValueError('模拟阶段目录读取失败')
            return original(project, stage, today=today)

        with mock.patch.object(file_index, 'read_dirs', side_effect=flaky):
            self.assertEqual(file_index.discover(self.root), 1)
        paths = [row.path for row in file_index.rows(self.root)]
        self.assertIn('01剧本准备/docs/新剧本.md', paths)
        self.assertNotIn('05资产管理/assets/新资产.png', paths)

    def test_discover_skips_files_that_fail_row_build(self):
        """_row_for 抛错或返回 None 的候选被跳过，其余文件照常收。"""
        _write(self.root / '01剧本准备' / 'docs' / '新1.md', 'x')
        _write(self.root / '01剧本准备' / 'docs' / '新2.md', 'x')
        _write(self.root / '01剧本准备' / 'docs' / '新3.md', 'x')
        original = file_index._row_for

        def flaky(project, relative_path, published, now=None, origins=None):
            if str(relative_path).endswith('新1.md'):
                raise OSError('模拟 stat 失败')
            if str(relative_path).endswith('新2.md'):
                return None
            return original(project, relative_path, published, now=now, origins=origins)

        with mock.patch.object(file_index, '_row_for', side_effect=flaky):
            self.assertEqual(file_index.discover(self.root), 1)
        paths = [row.path for row in file_index.rows(self.root)]
        self.assertIn('01剧本准备/docs/新3.md', paths)
        self.assertNotIn('01剧本准备/docs/新1.md', paths)
        self.assertNotIn('01剧本准备/docs/新2.md', paths)

    def test_discover_skips_candidate_when_relative_fails(self):
        """项目相对化抛错的候选被跳过，同目录其他新文件照常收。"""
        _write(self.root / '01剧本准备' / 'docs' / '跳过.md', 'x')
        _write(self.root / '01剧本准备' / 'docs' / '保留.md', 'x')
        original = file_index._relative

        def flaky(project, path):
            if str(path).endswith('跳过.md'):
                raise ValueError('模拟越界')
            return original(project, path)

        with mock.patch.object(file_index, '_relative', side_effect=flaky):
            self.assertEqual(file_index.discover(self.root), 1)
        paths = [row.path for row in file_index.rows(self.root)]
        self.assertIn('01剧本准备/docs/保留.md', paths)
        self.assertNotIn('01剧本准备/docs/跳过.md', paths)

    def test_discover_walk_interruption_keeps_other_dirs(self):
        """某目录遍历中途抛错：已产出的候选保留，其他目录新文件照收。"""
        script_dir = Path(file_index.read_dirs(self.root, 'script')[0])
        first = script_dir / 'docs' / '先出现.md'
        _write(first, 'x')
        _write(self.root / '05资产管理' / 'assets' / '新资产.png', b'\x89PNG')
        original = file_index._walk

        def flaky(folder):
            if Path(folder) == script_dir:
                yield first
                raise OSError('模拟遍历中断')
            yield from original(folder)

        with mock.patch.object(file_index, '_walk', side_effect=flaky):
            self.assertEqual(file_index.discover(self.root), 2)
        paths = [row.path for row in file_index.rows(self.root)]
        self.assertIn('01剧本准备/docs/先出现.md', paths)
        self.assertIn('05资产管理/assets/新资产.png', paths)


class FileIndexBranchTests(unittest.TestCase):
    """来源、手动类型、定稿台账与全局库：两条结果都要走到。"""

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix='file-index-branch-')
        self.root = Path(self.temp.name) / '测试项目'
        self.root.mkdir()
        _write(self.root / '01剧本准备' / 'docs' / '测试项目_剧本_初稿_20261117.md')
        _write(self.root / '01剧本准备' / 'docs' / '角色设定.md')
        _write(self.root / '05资产管理' / 'assets' / 'CHAR_001.png', b'\x89PNG')
        _write(self.root / '11配音与字幕' / '音频' / 'S01.wav', b'RIFF')
        _write(self.root / '10视频生成' / 'assets' / 'EP001_SH001.mp4', b'\x00\x00')
        self.script = '01剧本准备/docs/测试项目_剧本_初稿_20261117.md'
        self.setting = '01剧本准备/docs/角色设定.md'
        self.image = '05资产管理/assets/CHAR_001.png'

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_listeners_survive_bad_callbacks_and_resolve_failure(self) -> None:
        calls = []

        def ok(project):
            calls.append(project)

        def bad(project):
            raise RuntimeError('监听失败')

        self.assertIsNone(file_index.subscribe_changes(None))
        self.assertIs(file_index.subscribe_changes(ok), ok)
        file_index.subscribe_changes(ok)
        file_index.subscribe_changes(bad)
        try:
            self.assertEqual(file_index._project_key(self.root),
                             os.path.normcase(str(self.root.resolve())))
            with mock.patch.object(Path, 'resolve', side_effect=OSError('模拟路径失败')):
                self.assertEqual(file_index._project_key('D:/不存在'), os.path.normcase('D:/不存在'))
            file_index.rebuild(self.root)
            self.assertTrue(calls)
        finally:
            file_index.unsubscribe_changes(ok)
            file_index.unsubscribe_changes(bad)
            file_index.unsubscribe_changes(ok)
            file_index.unsubscribe_changes(lambda project: None)

    def test_origin_and_kind_keep_user_fact_and_manual_override(self) -> None:
        with self.assertRaises(ValueError):
            file_index.record_origin(self.root, [], '不明来源')
        for bad in ('../越界.md', 'a\x00b.md', 'foo:bar.md', str(self.root) + '\\bad:name\\a.md'):
            with self.assertRaises(ValueError):
                file_index.record_origin(self.root, [bad], ORIGIN_USER)
        batch = ['01剧本准备/docs/缺失.md', '01剧本准备/docs', self.setting,
                 str((self.root / self.script).resolve())]
        file_index.record_origin(self.root, batch, ORIGIN_USER)
        file_index.record_origin(self.root, [self.setting], ORIGIN_USER)
        file_index.record_origin(self.root, [self.setting], ORIGIN_SYSTEM)
        file_index.record_origin(self.root, [self.image], ORIGIN_SYSTEM)
        origins = file_index._read_origins(self.root)
        self.assertEqual(origins[self.setting], ORIGIN_USER)
        self.assertEqual(origins[self.script], ORIGIN_USER)
        self.assertEqual(origins[self.image], ORIGIN_SYSTEM)
        with self.assertRaises(ConfigError):
            file_index.record_kind(self.root, [self.setting], '不是类型')
        file_index.record_kind(self.root, [self.setting, self.image], '报告')
        file_index.rebuild(self.root)
        file_index.record_kind(self.root, [self.setting, self.image], '分镜')
        file_index.record_kind(self.root, [self.setting], '分镜')
        found = {row.path: row for row in file_index.rows(self.root)}
        self.assertEqual(found[self.setting].kind, '分镜')
        self.assertEqual(found[self.setting].origin, ORIGIN_USER)
        file_index.record_kind(self.root, [self.setting, self.image], '')
        file_index.record_kind(self.root, [self.setting], None)
        found = {row.path: row for row in file_index.rows(self.root)}
        self.assertEqual(found[self.setting].kind, '参考')
        self.assertIsNone(file_index._row_for(self.root, '01剧本准备/docs', set()))
        target = file_index.origin_path(self.root)
        target.write_text('{', encoding='utf-8')
        self.assertEqual(file_index._read_meta(self.root), ({}, {}))
        target.write_text('[]', encoding='utf-8')
        self.assertEqual(file_index._read_meta(self.root), ({}, {}))
        target.write_text(json.dumps({'schema_version': 9}), encoding='utf-8')
        self.assertEqual(file_index._read_meta(self.root), ({}, {}))
        target.write_text(json.dumps({'schema_version': 1, 'origins': ['不是字典'], 'kinds': '不是字典'}),
                          encoding='utf-8')
        self.assertEqual(file_index._read_meta(self.root), ({}, {}))
        target.write_text(json.dumps({
            'schema_version': 1,
            'origins': {
                self.setting: ORIGIN_USER,
                '01剧本准备/docs/坏来源.md': '不是来源',
                '01剧本准备/docs/不是字符串.md': 1,
                '../越界.md': ORIGIN_SYSTEM,
            },
            'kinds': {
                self.image: '报告',
                '05资产管理/assets/坏类型.png': '不是类型',
                '../越界.md': '剧本',
            },
        }, ensure_ascii=False), encoding='utf-8')
        origins, kinds = file_index._read_meta(self.root)
        self.assertEqual(origins, {self.setting: ORIGIN_USER})
        self.assertEqual(kinds, {self.image: '报告'})
        data = file_index.read(self.root)
        for item in data['files']:
            if item['path'] == self.image:
                item['kind'] = '资产'
        applied = file_index._apply_origins(self.root, data, origins={self.setting: ORIGIN_USER},
                                            kinds={self.setting: '报告'})
        by_path = {item['path']: item for item in applied['files']}
        self.assertEqual(by_path[self.setting]['kind'], '报告')
        self.assertEqual(by_path[self.setting]['origin'], ORIGIN_USER)
        self.assertEqual(by_path[self.image]['kind'], '资产')
        loaded = file_index._apply_origins(self.root, data)
        self.assertTrue(loaded['files'])

    def test_kind_of_uses_stage_duty_before_suffix(self) -> None:
        samples = {
            '01剧本准备/skills/说明.md': '其他',
            '01剧本准备/logs/run.txt': '日志',
            '01剧本准备/项目设定/世界观.md': '参考',
            '01剧本准备/项目剧本/正稿.md': '剧本',
            '01剧本准备/docs/海报.png': '资产',
            '05资产管理/参考图/a.png': '参考',
            '_shared/reference_images/a.png': '参考',
            '03初步分镜/docs/镜头.md': '分镜',
            '03初步分镜/assets/说明.txt': '报告',
            '05资产管理/docs/人物.md': '设定',
            '05资产管理/assets/说明.md': '报告',
        }
        self.assertEqual({path: file_index.kind_of(path) for path in samples}, samples)

    def test_confirmed_and_manifest_paths_skip_unsafe_entries(self) -> None:
        folder = self.root / '01剧本准备'
        _write(folder / 'preparation_state.json', json.dumps({
            'documents': [
                {'confirmed': True, 'path': 'docs/已确认.md'},
                {'confirmed': False, 'path': 'docs/未确认.md'},
                {'confirmed': True, 'path': 5},
                {'confirmed': True, 'path': '../../越界.md'},
                '坏文档',
                {'confirmed': True},
            ],
            'revision': {'documents': [{'confirmed': True, 'path': 'docs/修订.md'}]},
        }, ensure_ascii=False))
        _write(folder / 'natural_script_selection.json', json.dumps(
            {'path': '01剧本准备/docs/已确认.md'}, ensure_ascii=False))
        found = file_index._confirmed_docs_in(self.root, folder)
        self.assertEqual(found, {'01剧本准备/docs/已确认.md', '01剧本准备/docs/修订.md'})
        self.assertEqual(file_index._confirmed_docs_in(self.root, self.root / '05资产管理'), set())
        odd = self.root / '02剧本结构'
        _write(odd / 'preparation_state.json', '[]')
        _write(odd / 'natural_script_selection.json', json.dumps({'path': '   '}))
        self.assertEqual(file_index._confirmed_docs_in(self.root, odd), set())
        broken = self.root / '03初步分镜'
        _write(broken / 'preparation_state.json', '{')
        _write(broken / 'natural_script_selection.json', '{')
        self.assertEqual(file_index._confirmed_docs_in(self.root, broken), set())
        _write(self.root / '10视频生成' / 'preparation_state.json', json.dumps({
            'documents': [{'confirmed': True, 'path': 'docs/无修订.md'}],
            'revision': ['不是字典'],
        }, ensure_ascii=False))
        self.assertEqual(file_index._confirmed_docs_in(self.root, self.root / '10视频生成'),
                         {'10视频生成/docs/无修订.md'})
        _write(self.root / '05资产管理' / '成果确认' / '坏.json', '{')
        _write(self.root / '05资产管理' / '成果确认' / '备注.json', json.dumps(
            {'status': 'draft', 'reviewed': False, 'outputs': []}, ensure_ascii=False))
        _write(folder / '成果确认' / 'delivery_manifest.json', json.dumps({
            'status': 'complete', 'reviewed': True,
            'files': [{'path': '10视频生成/assets/EP001_SH001.mp4'}, {'path': '../越界.mp4'}, '坏'],
        }, ensure_ascii=False))
        published = file_index.published_paths(self.root)
        self.assertIn('10视频生成/assets/EP001_SH001.mp4', published)
        self.assertIn('01剧本准备/docs/已确认.md', published)

    def test_discover_drops_stale_rows_and_ignores_unknown_paths(self) -> None:
        published = {self.script}
        items = [
            '不是字典',
            {'path': 3},
            {'path': self.script},
            {'missing': True, 'path': self.setting},
            {'path': '01剧本准备/docs/不存在.md'},
            {'path': '01剧本准备/docs/炸.md'},
            {'path': self.image},
        ]
        original = Path.is_file

        def flaky(path):
            if Path(path).name == '炸.md':
                raise OSError('模拟文件状态失败')
            return original(path)

        with mock.patch.object(Path, 'is_file', flaky):
            stale = file_index._collect_removed_paths(
                self.root, items, ['script', 'assets'], published)
        self.assertCountEqual(stale, ['01剧本准备/docs/不存在.md', '01剧本准备/docs/炸.md'])
        file_index.rebuild(self.root)
        (self.root / self.setting).unlink()
        self.assertGreaterEqual(file_index.discover(self.root), 1)
        self.assertNotIn(self.setting, [row.path for row in file_index.rows(self.root)])
        with mock.patch.object(file_index, '_collect_removed_paths', return_value=['不在索引里.md']):
            self.assertEqual(file_index.discover(self.root), 0)

    def test_global_library_round_trip_rejects_blank_and_broken_index(self) -> None:
        library = Path(self.temp.name) / '素材库'
        program = Path(self.temp.name) / '假程序'
        missing = self.root / '没有这个库'
        self.assertIsNone(file_index.read_global_dir(program))
        self.assertEqual(file_index.build_global(missing)['files'], [])
        self.assertEqual(file_index.rebuild_global(missing)['files'], [])
        self.assertEqual(file_index.global_rows(missing), [])
        self.assertIsNone(file_index.read_global(library))
        _write(program / '配置' / '素材库.json', '[]')
        self.assertIsNone(file_index.read_global_dir(program))
        _write(program / '配置' / '素材库.json', json.dumps({'library_dir': '  '}))
        self.assertIsNone(file_index.read_global_dir(program))
        with self.assertRaises(ValueError):
            file_index.save_global_dir('   ', program)
        _write(library / '封面.png', b'png')
        _write(library / '备注.txt', '文字')
        self.assertTrue(file_index.build_global(library)['files'])
        written = file_index.save_global_dir(library, program)
        self.assertTrue(written.is_file())
        self.assertEqual(file_index.read_global_dir(program), Path(library))
        self.assertTrue(file_index.rebuild_global(library)['files'])
        again = [item['path'] for item in file_index.build_global(library)['files']]
        self.assertIn('封面.png', again)
        self.assertNotIn('index.json', again)
        self.assertIsNotNone(file_index.read_global(library))
        file_index.global_index_path(library).write_text('{', encoding='utf-8')
        self.assertIsNone(file_index.read_global(library))
        file_index.rebuild_global(library)
        self.assertTrue(file_index.search_global(library, kind='资产', name='封面'))
        self.assertEqual(file_index.search_global(library, kind='音频'), [])
        self.assertEqual(file_index.search_global(library, name='不存在的关键字'), [])
        self.assertGreaterEqual(len(file_index.search_global(library)), 2)


if __name__ == '__main__':
    unittest.main()

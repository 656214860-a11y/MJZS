# -*- coding: utf-8 -*-
"""R3093（任务书 P0）：项目文件索引的读写、筛选与一致性标记。

覆盖：全量重建写盘并落 DES §3.1 字段；阶段／类型由路径推导；清单引用过的文件标
「已发布」、清单里有但磁盘没有的标 ``missing``；增量更新支持新增与删除；索引缺失或
损坏时自动重建；筛选四条件可组合。
"""
import json
import tempfile
import unittest
from pathlib import Path

import infra.file_index as file_index
from contract import file_naming, stage_layout
from contract.file_index_contract import (INDEX_VERSION, STATUS_ARCHIVED, STATUS_DRAFT, STATUS_PUBLISHED,
                                          FileRow)


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
        self.assertEqual(found['01剧本准备/docs/角色设定.md'].kind, '设定')
        self.assertEqual(found['05资产管理/assets/CHAR_001.png'].kind, '资产')
        self.assertEqual(found['11配音与字幕/音频/S01.wav'].kind, '音频')
        self.assertEqual(found['10视频生成/assets/EP001_SH001.mp4'].kind, '视频')

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

    def test_manifest_marks_file_published(self) -> None:
        _write(self.root / '05资产管理' / '成果确认' / 'abc.json',
               json.dumps({'outputs': [{'path': '05资产管理/assets/CHAR_001.png'}]}, ensure_ascii=False))
        file_index.rebuild(self.root)
        row = {item.path: item for item in file_index.rows(self.root)}['05资产管理/assets/CHAR_001.png']
        self.assertEqual(row.status, STATUS_PUBLISHED)

    def test_manifest_path_absent_on_disk_is_marked_missing(self) -> None:
        _write(self.root / '05资产管理' / '成果确认' / 'abc.json',
               json.dumps({'outputs': [{'path': '05资产管理/assets/不存在.png'}]}, ensure_ascii=False))
        file_index.rebuild(self.root)
        found = {item.path: item for item in file_index.rows(self.root)}
        missing = found['05资产管理/assets/不存在.png']
        self.assertTrue(missing.missing)
        self.assertEqual(missing.status, STATUS_PUBLISHED)
        self.assertEqual(file_index.summary(self.root)['missing'], 1)

    def test_delivery_manifest_counts_as_published(self) -> None:
        _write(self.root / '13质检交付' / '导出成片' / 'delivery_manifest.json',
               json.dumps({'files': [{'path': '10视频生成/assets/EP001_SH001.mp4'}]}, ensure_ascii=False))
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
        self.assertEqual(file_index.kinds(self.root), ['剧本', '设定', '资产', '音频', '视频'])

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


if __name__ == '__main__':
    unittest.main()

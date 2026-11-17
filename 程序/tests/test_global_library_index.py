# -*- coding: utf-8 -*-
"""R3123（任务书 P3，Q11）：全局素材库索引。

覆盖：库内文件按「库相对 posix」入索引、类型由后缀推导、索引自身不入表；重建落盘后
可读回；按类型与关键字筛选；整库换目录不需要改写索引里的路径。
"""
import json
import tempfile
import unittest
from pathlib import Path

import infra.file_index as file_index


def _library(tmp):
    root = Path(tmp) / '漫剧助手素材库'
    (root / '角色').mkdir(parents=True)
    (root / '场景').mkdir(parents=True)
    (root / '角色' / 'CHAR_001.png').write_bytes(b'\x89PNG')
    (root / '角色' / '角色设定.md').write_text('# 设定', encoding='utf-8')
    (root / '场景' / 'LOC_001.png').write_bytes(b'\x89PNG')
    (root / '旁白.wav').write_bytes(b'RIFF')
    return root


class GlobalLibraryIndexTests(unittest.TestCase):
    def test_paths_are_library_relative(self):
        with tempfile.TemporaryDirectory() as tmp:
            library = _library(tmp)
            rows = [row.path for row in file_index.global_rows(library)]
            self.assertIn('角色/CHAR_001.png', rows)
            self.assertTrue(all(not Path(row).is_absolute() for row in rows), rows)

    def test_kind_comes_from_suffix(self):
        with tempfile.TemporaryDirectory() as tmp:
            library = _library(tmp)
            found = {row.path: row.kind for row in file_index.global_rows(library)}
            self.assertEqual(found['角色/CHAR_001.png'], '资产')
            self.assertEqual(found['旁白.wav'], '音频')
            self.assertEqual(found['角色/角色设定.md'], '报告')

    def test_index_file_is_not_listed(self):
        with tempfile.TemporaryDirectory() as tmp:
            library = _library(tmp)
            file_index.rebuild_global(library)
            self.assertTrue(file_index.global_index_path(library).is_file())
            rows = [row.path for row in file_index.global_rows(library)]
            self.assertNotIn(file_index.GLOBAL_INDEX_NAME, rows)

    def test_rebuild_then_read_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            library = _library(tmp)
            payload = file_index.rebuild_global(library, now=0)
            written = json.loads(file_index.global_index_path(library).read_text(encoding='utf-8'))
            self.assertEqual(written['files'], payload['files'])
            self.assertEqual(file_index.read_global(library)['schema_version'], file_index.INDEX_VERSION)

    def test_search_filters_kind_and_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            library = _library(tmp)
            self.assertEqual(sorted(row.path for row in file_index.search_global(library, kind='资产')),
                             sorted(['角色/CHAR_001.png', '场景/LOC_001.png']))
            self.assertEqual([row.path for row in file_index.search_global(library, name='LOC_001')],
                             ['场景/LOC_001.png'])

    def test_moving_the_library_does_not_need_rewriting(self):
        with tempfile.TemporaryDirectory() as tmp:
            library = _library(tmp)
            file_index.rebuild_global(library)
            moved = Path(tmp) / '新位置素材库'
            library.rename(moved)
            rows = [row.path for row in file_index.global_rows(moved)]
            self.assertIn('角色/CHAR_001.png', rows)

    def test_corrupt_index_is_rebuilt(self):
        with tempfile.TemporaryDirectory() as tmp:
            library = _library(tmp)
            file_index.rebuild_global(library)
            file_index.global_index_path(library).write_text('{坏', encoding='utf-8')
            self.assertIsNone(file_index.read_global(library))
            self.assertTrue(file_index.global_rows(library))

    def test_missing_library_yields_empty_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(file_index.global_rows(Path(tmp) / '不存在'), [])


if __name__ == '__main__':
    unittest.main()

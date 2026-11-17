# -*- coding: utf-8 -*-
"""R3165（任务书 P3，Q11 收尾）：全局库与项目之间的复制动作。

覆盖：引用＝复制进项目 `_shared/全局素材库/` 并登记来源、不移动源；添加＝复制进全局库、
重名加序号、不移动源；越界文件拒绝；来源登记可累积。
"""
import json
import tempfile
import unittest
from pathlib import Path

import contract.stage_layout as stage_layout
from domain import global_library_service as service


def _library(tmp):
    library = Path(tmp) / '素材库'
    (library / '角色').mkdir(parents=True)
    (library / '角色' / 'CHAR_001.png').write_bytes(b'\x89PNG')
    return library


def _project(tmp):
    project = Path(tmp) / '项目'
    (project / '01剧本准备' / 'docs').mkdir(parents=True)
    (project / '01剧本准备' / 'docs' / '脚本.md').write_text('正文', encoding='utf-8')
    return project


class CopyToProjectTests(unittest.TestCase):
    def test_copies_into_shared_and_records_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            library = _library(tmp)
            project = _project(tmp)
            target = service.copy_to_project(library, '角色/CHAR_001.png', project)
            self.assertTrue(target.is_file())
            shared = stage_layout.shared_paths(project)['root']
            self.assertTrue(target.resolve().is_relative_to(shared))
            manifest = shared / service.SHARED_SUB / service.SOURCE_MANIFEST
            data = json.loads(manifest.read_text(encoding='utf-8'))
            self.assertEqual(data['entries'][0]['path'], '角色/CHAR_001.png')
            # 源文件仍在全局库，不移动。
            self.assertTrue((library / '角色' / 'CHAR_001.png').is_file())

    def test_rejects_out_of_library_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            library = _library(tmp)
            project = _project(tmp)
            with self.assertRaises(ValueError):
                service.copy_to_project(library, '../外面.txt', project)

    def test_duplicate_import_overwrites_the_same_entry(self):
        with tempfile.TemporaryDirectory() as tmp:
            library = _library(tmp)
            project = _project(tmp)
            service.copy_to_project(library, '角色/CHAR_001.png', project)
            service.copy_to_project(library, '角色/CHAR_001.png', project)
            manifest = stage_layout.shared_paths(project)['root'] / service.SHARED_SUB / service.SOURCE_MANIFEST
            data = json.loads(manifest.read_text(encoding='utf-8'))
            self.assertEqual(len(data['entries']), 1)


class CopyToLibraryTests(unittest.TestCase):
    def test_copies_into_library_and_keeps_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            library = _library(tmp)
            project = _project(tmp)
            target = service.copy_to_library(project, '01剧本准备/docs/脚本.md', library)
            self.assertTrue(target.is_file())
            self.assertTrue(target.resolve().is_relative_to(library))
            # 源文件仍在项目，不移动。
            self.assertTrue((project / '01剧本准备' / 'docs' / '脚本.md').is_file())

    def test_name_collision_gets_a_numbered_suffix(self):
        with tempfile.TemporaryDirectory() as tmp:
            library = _library(tmp)
            # 冲突发生在保留相对结构的实际目标位置。
            (library / '01剧本准备' / 'docs' / '脚本.md').parent.mkdir(parents=True)
            (library / '01剧本准备' / 'docs' / '脚本.md').write_text('已有', encoding='utf-8')
            project = _project(tmp)
            target = service.copy_to_library(project, '01剧本准备/docs/脚本.md', library)
            self.assertEqual(target.name, '脚本(2).md')

    def test_rejects_out_of_project_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            library = _library(tmp)
            project = _project(tmp)
            with self.assertRaises(ValueError):
                service.copy_to_library(project, '../外面.txt', library)


if __name__ == '__main__':
    unittest.main()

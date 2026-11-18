# -*- coding: utf-8 -*-
"""R3165（任务书 P3，Q11 收尾）：全局库与项目之间的复制动作。

覆盖：引用＝复制进项目 `_shared/全局素材库/` 并登记来源、不移动源；添加＝复制进全局库、
重名加序号、不移动源；越界文件拒绝；来源登记可累积。
"""
import json
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest import mock

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


class CopySafetyTests(unittest.TestCase):
    def test_rejects_absolute_and_parent_components_even_when_inside_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            library, project = _library(tmp), _project(tmp)
            cases = ((service.copy_to_project, library, project, '角色/CHAR_001.png'),
                     (service.copy_to_library, project, library, '01剧本准备/docs/脚本.md'))
            for copy, source_root, destination, relative in cases:
                for invalid in (str(source_root / relative), './' + relative,
                                'unused/../' + relative, '..\\' + relative,
                                'C:relative.txt', '\\\\server\\share\\file.txt'):
                    with self.subTest(copy=copy.__name__, path=invalid):
                        with self.assertRaises(ValueError):
                            copy(source_root, invalid, destination)

    def test_project_duplicate_preserves_user_edit_and_relative_structure(self):
        with tempfile.TemporaryDirectory() as tmp:
            library, project = _library(tmp), _project(tmp)
            first = service.copy_to_project(library, '角色/CHAR_001.png', project)
            first.write_bytes(b'user edit')
            second = service.copy_to_project(library, '角色/CHAR_001.png', project)
            self.assertEqual(first.read_bytes(), b'user edit')
            self.assertEqual(second.parent, first.parent)
            self.assertEqual(second.name, 'CHAR_001(2).png')
            self.assertEqual(second.read_bytes(), b'\x89PNG')

    def test_target_junction_escape_rejected_in_both_directions(self):
        with tempfile.TemporaryDirectory() as tmp:
            library, project = _library(tmp), _project(tmp)
            outside = Path(tmp) / 'outside'
            outside.mkdir()
            shared = stage_layout.shared_paths(project)['root'] / service.SHARED_SUB
            shared.mkdir(parents=True)
            for copy, source_root, destination, relative, link in (
                    (service.copy_to_project, library, project, '角色/CHAR_001.png', shared / '角色'),
                    (service.copy_to_library, project, library, '01剧本准备/docs/脚本.md', library / '01剧本准备')):
                with self.subTest(copy=copy.__name__):
                    # Windows junctions need no developer-mode symlink privilege.
                    import subprocess
                    subprocess.run(['cmd', '/c', 'mklink', '/J', str(link), str(outside)],
                                   check=True, capture_output=True)
                    try:
                        with self.assertRaises(ValueError):
                            copy(source_root, relative, destination)
                        self.assertEqual(list(outside.iterdir()), [])
                    finally:
                        link.rmdir()

    def test_manifest_symlink_or_junction_ancestor_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            library, project = _library(tmp), _project(tmp)
            shared = stage_layout.shared_paths(project)['root']
            outside = Path(tmp) / 'outside'
            outside.mkdir()
            import subprocess
            subprocess.run(['cmd', '/c', 'mklink', '/J', str(shared), str(outside)],
                           check=True, capture_output=True)
            try:
                with self.assertRaises(ValueError):
                    service.copy_to_project(library, '角色/CHAR_001.png', project)
                self.assertEqual(list(outside.iterdir()), [])
            finally:
                shared.rmdir()

    def test_manifest_failure_recycles_only_new_copy_and_preserves_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            library, project = _library(tmp), _project(tmp)
            old = stage_layout.shared_paths(project)['root'] / service.SHARED_SUB / '角色/CHAR_001.png'
            old.parent.mkdir(parents=True)
            old.write_bytes(b'user edit')
            def fail_save(path, text):
                raise OSError('injected manifest failure')
            with mock.patch('storage_maintenance.recycle_paths', wraps=__import__('storage_maintenance').recycle_paths) as recycle:
                with self.assertRaisesRegex(OSError, 'injected manifest failure'):
                    service.copy_to_project(library, '角色/CHAR_001.png', project, saver=fail_save)
                self.assertEqual(recycle.call_count, 1)
                self.assertEqual(recycle.call_args.args[1], [old.with_name('CHAR_001(2).png')])
            self.assertEqual(old.read_bytes(), b'user edit')
            self.assertFalse(old.with_name('CHAR_001(2).png').exists())
            self.assertEqual((library / '角色/CHAR_001.png').read_bytes(), b'\x89PNG')

    def test_atomic_collision_after_candidate_selection_retries_without_overwrite(self):
        from agent.core import copy_file_new
        with tempfile.TemporaryDirectory() as tmp:
            library, project = _library(tmp), _project(tmp)
            for copy, source_root, destination, relative in (
                    (service.copy_to_project, library, project, '角色/CHAR_001.png'),
                    (service.copy_to_library, project, library, '01剧本准备/docs/脚本.md')):
                collided = []
                def race(path, source, validate):
                    if not collided:
                        path.write_bytes(b'concurrent user edit')
                        collided.append(path)
                    return copy_file_new(path, source, validate)
                with mock.patch.object(service, 'copy_file_new', side_effect=race):
                    result = copy(source_root, relative, destination)
                self.assertNotEqual(result, collided[0])
                self.assertEqual(collided[0].read_bytes(), b'concurrent user edit')
                self.assertEqual(result.read_bytes(), (source_root / relative).read_bytes())

    def test_failed_registration_never_recycles_modified_copy(self):
        with tempfile.TemporaryDirectory() as tmp:
            library, project = _library(tmp), _project(tmp)
            target = stage_layout.shared_paths(project)['root'] / service.SHARED_SUB / '角色/CHAR_001.png'
            def edit_then_fail(path, text):
                target.write_bytes(b'new user edit')
                raise OSError('registration failed')
            with mock.patch('storage_maintenance.recycle_paths') as recycle:
                with self.assertRaisesRegex(OSError, 'registration failed'):
                    service.copy_to_project(library, '角色/CHAR_001.png', project, saver=edit_then_fail)
                recycle.assert_not_called()
            self.assertEqual(target.read_bytes(), b'new user edit')

    def test_library_index_failure_recycles_only_new_copy(self):
        with tempfile.TemporaryDirectory() as tmp:
            library, project = _library(tmp), _project(tmp)
            with mock.patch.object(service.file_index, 'rebuild_global', side_effect=OSError('index failed')):
                with self.assertRaisesRegex(OSError, 'index failed'):
                    service.copy_to_library(project, '01剧本准备/docs/脚本.md', library)
            self.assertFalse((library / '01剧本准备/docs/脚本.md').exists())
            self.assertEqual((project / '01剧本准备/docs/脚本.md').read_text(encoding='utf-8'), '正文')

    def test_source_junction_escape_rejected_in_both_directions(self):
        with tempfile.TemporaryDirectory() as tmp:
            library, project = _library(tmp), _project(tmp)
            outside = Path(tmp) / 'outside'
            outside.mkdir()
            (outside / 'file.txt').write_text('outside', encoding='utf-8')
            import subprocess
            for copy, root, destination in ((service.copy_to_project, library, project),
                                             (service.copy_to_library, project, library)):
                link = root / 'linked'
                subprocess.run(['cmd', '/c', 'mklink', '/J', str(link), str(outside)],
                               check=True, capture_output=True)
                try:
                    with self.assertRaises(ValueError):
                        copy(root, 'linked/file.txt', destination)
                    self.assertEqual((outside / 'file.txt').read_text(encoding='utf-8'), 'outside')
                finally:
                    link.rmdir()

    def test_manifest_link_is_rejected_before_creating_copy(self):
        with tempfile.TemporaryDirectory() as tmp:
            library, project = _library(tmp), _project(tmp)
            root = stage_layout.shared_paths(project)['root'] / service.SHARED_SUB
            root.mkdir(parents=True)
            manifest = root / service.SOURCE_MANIFEST
            # Exercise the file-symlink guard without requiring Windows symlink privilege.
            original = Path.is_symlink
            with mock.patch.object(Path, 'is_symlink', autospec=True,
                                   side_effect=lambda p: p == manifest or original(p)):
                with self.assertRaises(ValueError):
                    service.copy_to_project(library, '角色/CHAR_001.png', project)
            self.assertFalse((root / '角色/CHAR_001.png').exists())

    def test_concurrent_collisions_never_overwrite_in_both_directions(self):
        with tempfile.TemporaryDirectory() as tmp:
            library, project = _library(tmp), _project(tmp)
            for copy, source_root, destination, relative in (
                    (service.copy_to_project, library, project, '角色/CHAR_001.png'),
                    (service.copy_to_library, project, library, '01剧本准备/docs/脚本.md')):
                barrier = threading.Barrier(4)
                def run(_):
                    barrier.wait(timeout=10)
                    return copy(source_root, relative, destination)
                with ThreadPoolExecutor(max_workers=4) as pool:
                    paths = list(pool.map(run, range(4)))
                with self.subTest(copy=copy.__name__):
                    self.assertEqual(len(set(paths)), 4)
                    self.assertTrue(all(p.read_bytes() == (source_root / relative).read_bytes() for p in paths))
                    self.assertTrue(all(p.parent == destination.joinpath(*relative.split('/')[:-1])
                                        if copy is service.copy_to_library else
                                        p.parent == stage_layout.shared_paths(project)['root'] / service.SHARED_SUB / '角色'
                                        for p in paths))

    def test_copy_to_project_rollback_and_recycle_failures_are_logged_not_masking(self):
        """R3310：事务回滚与副本回收各自失败都只记日志，调用方原异常照常抛出。"""
        with tempfile.TemporaryDirectory() as tmp:
            library, project = _library(tmp), _project(tmp)

            def fail_save(path, text):
                raise OSError('injected manifest failure')

            with mock.patch.object(service.unit_of_work, 'rollback',
                                   side_effect=RuntimeError('journal rollback failed')), \
                 mock.patch.object(service, '_rollback',
                                   side_effect=OSError('recycle failed')), \
                 self.assertLogs('swallowed', level='WARNING') as logs:
                with self.assertRaisesRegex(OSError, 'injected manifest failure'):
                    service.copy_to_project(library, '角色/CHAR_001.png', project, saver=fail_save)
            self.assertTrue(any('rollback' in line for line in logs.output))
            self.assertTrue(any('recycle' in line for line in logs.output))

    def test_copy_to_library_rollback_and_recycle_failures_are_logged_not_masking(self):
        """R3310：事务回滚与副本回收各自失败都只记日志，调用方原异常照常抛出。"""
        with tempfile.TemporaryDirectory() as tmp:
            library, project = _library(tmp), _project(tmp)
            with mock.patch.object(service.file_index, 'rebuild_global',
                                   side_effect=OSError('index failed')), \
                 mock.patch.object(service.unit_of_work, 'rollback',
                                   side_effect=RuntimeError('journal rollback failed')), \
                 mock.patch.object(service, '_rollback',
                                   side_effect=OSError('recycle failed')), \
                 self.assertLogs('swallowed', level='WARNING') as logs:
                with self.assertRaisesRegex(OSError, 'index failed'):
                    service.copy_to_library(project, '01剧本准备/docs/脚本.md', library)
            self.assertTrue(any('rollback' in line for line in logs.output))
            self.assertTrue(any('recycle' in line for line in logs.output))


if __name__ == '__main__':
    unittest.main()

# -*- coding: utf-8 -*-
"""REL-06B：用户级项目 zip 备份导出与校验导入还原。"""
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import tkinter as tk

from contract import app_metadata
from contract.service_contract import success
from desktop_project_pages import ProjectPagesMixin, ProjectPageServices
from domain import project_archive
from projects import Projects
from stage_execution_service import project_registry_gateway, unwrap_project_result
from ui_widgets import ContextMenu


def _service(td):
    app = Path(td) / '程序'
    app.mkdir()
    (app / 'config.json').write_text(json.dumps(
        {'downloads_root': str(Path(td) / '库')}, ensure_ascii=False), encoding='utf-8')
    (app / 'projects.json').write_text(json.dumps(
        {'active': None, 'projects': []}, ensure_ascii=False), encoding='utf-8')
    return Projects(app, gateway=project_registry_gateway(), migrate_legacy=False)


def _project(td, name='甲'):
    service = _service(td)
    result = service.create(name)
    assert result.ok, result.reason
    return service, Path(result.data)


def _rezip(source, target, mutate):
    """按条目重打包 zip；``mutate(arcname, bytes)`` 返回替换内容（None 原样）。"""
    with zipfile.ZipFile(source) as src, zipfile.ZipFile(target, 'w') as out:
        for info in src.infolist():
            data = src.read(info.filename)
            changed = mutate(info.filename, data)
            out.writestr(info, data if changed is None else changed)


class ProjectArchiveTests(unittest.TestCase):
    def test_archive_format_marker(self):
        self.assertEqual(project_archive.ARCHIVE_FORMAT, 'manju-project-archive/1')

    def test_export_inspect_import_round_trip_preserves_bytes_and_mtime(self):
        with tempfile.TemporaryDirectory() as td:
            service, project = _project(td)
            payload = project / '01剧本准备' / '故事.md'
            payload.parent.mkdir(parents=True, exist_ok=True)
            payload.write_text('# 故事\n第一幕\n', encoding='utf-8')
            os.utime(payload, (1700000000.5, 1700000000.5))
            archive = project_archive.export_project(service, project, dest_dir=Path(td) / 'out')
            manifest = project_archive.inspect_archive(archive)
            self.assertEqual(manifest['format'], project_archive.ARCHIVE_FORMAT)
            self.assertEqual(manifest['app_version'], app_metadata.VERSION)
            self.assertEqual(manifest['file_count'], len(manifest['files']))
            self.assertEqual(manifest['original_root'], str(project))
            rows = {row['path']: row for row in manifest['files']}
            self.assertIn('config.json', rows)
            self.assertIn('01剧本准备/故事.md', rows)
            self.assertEqual(rows['01剧本准备/故事.md']['size'],
                             (project / '01剧本准备' / '故事.md').stat().st_size)
            self.assertGreater(rows['config.json']['size'], 0)
            result = service.import_archive(archive)
            self.assertTrue(result.ok, result.reason)
            dst = Path(result.data)
            self.assertNotEqual(dst, project)
            restored = dst / '01剧本准备' / '故事.md'
            self.assertEqual(restored.read_text(encoding='utf-8'), '# 故事\n第一幕\n')
            self.assertEqual(hashlib.sha256(restored.read_bytes()).hexdigest(),
                             rows['01剧本准备/故事.md']['sha256'])
            self.assertAlmostEqual(restored.stat().st_mtime, 1700000000.5, delta=0.01)
            self.assertIn(str(dst), [item['path'] for item in service.info['projects']])
            original = json.loads((project / 'config.json').read_text(encoding='utf-8'))
            imported = json.loads((dst / 'config.json').read_text(encoding='utf-8'))
            self.assertEqual(original['project_id'], imported['project_id'],
                             '导入副本保留原项目身份，不与源项目互踩')

    def test_import_rewrites_live_paths_to_new_root(self):
        with tempfile.TemporaryDirectory() as td:
            service, project = _project(td)
            archive = project_archive.export_project(service, project, dest_dir=Path(td) / 'out')
            result = service.import_archive(archive)
            self.assertTrue(result.ok, result.reason)
            dst = Path(result.data)
            cfg = json.loads((dst / 'config.json').read_text(encoding='utf-8'))
            self.assertTrue(str(cfg['episode_dir']).startswith(str(dst)), cfg['episode_dir'])
            self.assertTrue(str(cfg['episode_file']).startswith(str(dst)), cfg['episode_file'])
            self.assertFalse(str(cfg['episode_dir']).startswith(str(project) + os.sep),
                             cfg['episode_dir'])

    def test_import_twice_lands_on_serial_suffix(self):
        with tempfile.TemporaryDirectory() as td:
            service, project = _project(td)
            archive = project_archive.export_project(service, project, dest_dir=Path(td) / 'out')
            first = service.import_archive(archive)
            second = service.import_archive(archive)
            self.assertTrue(first.ok and second.ok, (first.reason, second.reason))
            dst1, dst2 = Path(first.data), Path(second.data)
            self.assertNotEqual(dst1, dst2)
            self.assertRegex(dst1.name, r'_\d{8}_2$')
            self.assertRegex(dst2.name, r'_\d{8}_3$')
            paths = [item['path'] for item in service.info['projects']]
            self.assertIn(str(dst1), paths)
            self.assertIn(str(dst2), paths)

    def test_tampered_archive_fails_verification_and_leaves_no_residue(self):
        with tempfile.TemporaryDirectory() as td:
            service, project = _project(td)
            (project / 'note.txt').write_text('original', encoding='utf-8')
            archive = project_archive.export_project(service, project, dest_dir=Path(td) / 'out')
            tampered = Path(td) / 'tampered.zip'
            _rezip(archive, tampered, lambda name, data:
                   b'tampered' if name == 'project/note.txt' else None)
            before = [item['path'] for item in service.info['projects']]
            with self.assertRaisesRegex(ValueError, '备份包校验失败'):
                service.import_archive(tampered)
            self.assertEqual([item['path'] for item in service.info['projects']], before)
            self.assertFalse(list(service.base.glob('._import_*')), '失败必须无解包残留')

    def test_extract_refuses_existing_dest_dir(self):
        with tempfile.TemporaryDirectory() as td:
            service, project = _project(td)
            archive = project_archive.export_project(service, project, dest_dir=Path(td) / 'out')
            dest = Path(td) / 'existing'
            dest.mkdir()
            marker = dest / 'keep.txt'
            marker.write_text('keep', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, '目标目录已存在，拒绝覆盖'):
                project_archive.extract_archive(archive, dest)
            self.assertEqual(marker.read_text(encoding='utf-8'), 'keep', '既有目录一个字节都不能动')

    def test_newer_format_major_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            service, project = _project(td)
            archive = project_archive.export_project(service, project, dest_dir=Path(td) / 'out')
            newer = Path(td) / 'newer.zip'

            def bump(name, data):
                if name != 'manifest.json':
                    return None
                manifest = json.loads(data)
                manifest['format'] = 'manju-project-archive/99'
                return json.dumps(manifest, ensure_ascii=False).encode('utf-8')

            _rezip(archive, newer, bump)
            with self.assertRaisesRegex(ValueError, '格式版本'):
                project_archive.inspect_archive(newer)
            with self.assertRaisesRegex(ValueError, '格式版本'):
                project_archive.extract_archive(newer, Path(td) / 'unpack')
            self.assertFalse((Path(td) / 'unpack').exists(), '版本过新拒绝时必须无残留')

    def test_manifest_with_traversal_paths_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            service, project = _project(td)
            archive = project_archive.export_project(service, project, dest_dir=Path(td) / 'out')
            evil = Path(td) / 'evil.zip'

            def poison(name, data):
                if name != 'manifest.json':
                    return None
                manifest = json.loads(data)
                manifest['files'][0]['path'] = '../evil.txt'
                return json.dumps(manifest, ensure_ascii=False).encode('utf-8')

            _rezip(archive, evil, poison)
            with self.assertRaises(ValueError):
                project_archive.extract_archive(evil, Path(td) / 'unpack')
            self.assertFalse((Path(td) / 'unpack').exists(), '拒绝穿越时必须无残留')

    def test_secret_fields_are_redacted_and_recorded(self):
        with tempfile.TemporaryDirectory() as td:
            service, project = _project(td)
            cfg = json.loads((project / 'config.json').read_text(encoding='utf-8'))
            cfg['api_key'] = 'AK-SECRET-123'
            cfg['nested'] = {'access_token': 'tok-456', 'keep': 'visible'}
            (project / 'config.json').write_text(
                json.dumps(cfg, ensure_ascii=False), encoding='utf-8')
            cloud = project / 'cloud_video' / 'job1'
            cloud.mkdir(parents=True)
            (cloud / 'config.json').write_text(
                json.dumps({'password': 'pw'}), encoding='utf-8')
            (project / 'projects.json').write_text(
                json.dumps({'projects': [{'path': 'x', 'session_secret': 's'}]}), encoding='utf-8')
            archive = project_archive.export_project(service, project, dest_dir=Path(td) / 'out')
            manifest = project_archive.inspect_archive(archive)
            self.assertEqual(
                sorted(set(row.split('#')[0] for row in manifest['redacted'])),
                ['cloud_video/job1/config.json', 'config.json', 'projects.json'])
            with zipfile.ZipFile(archive) as zf:
                packed = json.loads(zf.read('project/config.json'))
                packed_cloud = json.loads(zf.read('project/cloud_video/job1/config.json'))
                packed_reg = json.loads(zf.read('project/projects.json'))
            self.assertEqual(packed['api_key'], '<已移除>')
            self.assertEqual(packed['nested']['access_token'], '<已移除>')
            self.assertEqual(packed['nested']['keep'], 'visible')
            self.assertEqual(packed_cloud['password'], '<已移除>')
            self.assertEqual(packed_reg['projects'][0]['session_secret'], '<已移除>')

    def test_junction_locks_and_cache_dirs_are_skipped(self):
        with tempfile.TemporaryDirectory() as td:
            service, project = _project(td)
            outside = Path(td) / 'outside'
            outside.mkdir()
            (outside / 'secret.txt').write_text('x', encoding='utf-8')
            link = project / 'linked'
            made = False
            try:
                result = subprocess.run(['cmd', '/c', 'mklink', '/J', str(link), str(outside)],
                                        capture_output=True, timeout=10)
                made = result.returncode == 0 and link.is_dir()
            except (OSError, subprocess.SubprocessError):
                made = False
            if not made:
                try:
                    link.symlink_to(outside, target_is_directory=True)
                    made = True
                except OSError:
                    self.fail('本机无法创建目录链接')
            def _drop_link():
                try:
                    if link.is_junction() or link.is_symlink():
                        link.rmdir()
                except OSError:
                    pass

            self.addCleanup(_drop_link)
            (project / 'operation.lock').write_text('lock', encoding='utf-8')
            cache = project / '__pycache__'
            cache.mkdir()
            (cache / 'x.pyc').write_bytes(b'pyc')
            thumbs = project / '.thumbs'
            thumbs.mkdir()
            (thumbs / 't.png').write_bytes(b'png')
            archive = project_archive.export_project(service, project, dest_dir=Path(td) / 'out')
            manifest = project_archive.inspect_archive(archive)
            names = [row['path'] for row in manifest['files']]
            self.assertNotIn('linked/secret.txt', names)
            self.assertNotIn('operation.lock', names)
            self.assertFalse(any('__pycache__' in n for n in names))
            self.assertFalse(any(n.startswith('.thumbs') for n in names))
            self.assertTrue(manifest['notes'], '跳过与排除项必须留痕')
            self.assertTrue((outside / 'secret.txt').is_file(), '链接目标内容不得被打包触碰')

    def test_registry_write_failure_moves_project_back_and_keeps_unpack_dir(self):
        with tempfile.TemporaryDirectory() as td:
            service, project = _project(td)
            archive = project_archive.export_project(service, project, dest_dir=Path(td) / 'out')
            real = service._publish_json

            def locked(path, data, *args, **kwargs):
                if Path(path) == service.registry:
                    raise OSError('locked')
                return real(path, data, *args, **kwargs)

            service._publish_json = locked
            result = service.import_archive(archive)
            self.assertFalse(result.ok)
            self.assertIn('已解包到', result.reason)
            leftovers = list(service.base.glob('._import_*'))
            self.assertEqual(len(leftovers), 1, '登记写失败时解包目录必须保留可恢复')
            self.assertTrue((leftovers[0] / 'config.json').is_file())
            registered = json.loads(service.registry.read_text(encoding='utf-8'))
            self.assertEqual(len(registered['projects']), 1, '登记失败不得改写注册表')
            self.assertEqual(len(service.info['projects']), 1)


class ProjectArchiveUiTests(unittest.TestCase):
    """隐藏桌面用例：项目首页右键菜单两项与处理函数。"""

    def _tk_root(self):
        root = tk.Tk()
        root.withdraw()
        return root

    def _stub(self, root, captured):
        stub = SimpleNamespace()
        stub.win = root
        stub.video_sessions = {}
        stub.worker = False
        stub.status = SimpleNamespace(set=mock.Mock())
        stub.reload = mock.Mock()
        stub.safe = lambda fn: fn()
        stub.async_ = lambda fn, done=None, **kw: captured.__setitem__('job', (fn, done))
        stub.file_dialog = SimpleNamespace(
            directory=lambda **kw: captured['dest_dir'],
            open_file=lambda **kw: captured['zip_path'])
        stub.projects = SimpleNamespace(
            base=Path('D:/lib'), info={'projects': []},
            import_archive=mock.Mock(return_value=success('D:/lib/甲_20260101')))
        stub._project_result_data = unwrap_project_result
        stub._session_busy = lambda v: ProjectPagesMixin._session_busy(stub, v)
        return stub

    def test_menu_lists_export_import_before_delete_and_handlers_work(self):
        root = self._tk_root()
        captured = {'dest_dir': 'D:/dest', 'zip_path': 'D:/dest/甲.zip'}
        menus = []

        def _context_menu(owner):
            menu = ContextMenu(owner)
            # 隐藏桌面上 tk_popup 会真弹并卡住事件循环：打桩弹出时机，菜单本体照常构建。
            menu.menu.tk_popup = lambda *a, **k: None
            menus.append(menu)
            return menu

        try:
            stub = self._stub(root, captured)
            stub.project_page_services = ProjectPageServices(
                open_path=mock.Mock(),
                context_menu=_context_menu,
                confirm=mock.Mock(return_value=True))
            item = {'name': '甲', 'path': 'D:/x/甲_20260101', 'status': 'making'}
            event = SimpleNamespace(x_root=10, y_root=10)
            ProjectPagesMixin._project_item_menu(stub, item, event)
            menu = menus[0]
            count = (menu.menu.index('end') or 0) + 1
            labels = [menu.menu.entrycget(i, 'label') if menu.menu.type(i) == 'command' else None
                      for i in range(count)]
            self.assertLess(labels.index('导出项目…'), labels.index('删除项目及全部素材…'))
            self.assertLess(labels.index('导入备份包…'), labels.index('删除项目及全部素材…'))

            ProjectPagesMixin.export_project_archive(stub, item)
            fn, done = captured['job']
            manifest = {'format': project_archive.ARCHIVE_FORMAT, 'name': '甲',
                        'redacted': ['config.json#api_key', 'config.json#nested.access_token',
                                     'projects.json#session_secret']}
            with mock.patch('domain.project_archive.export_project',
                            return_value=Path('D:/dest/甲.zip')) as export, \
                    mock.patch('domain.project_archive.inspect_archive',
                               return_value=manifest):
                result = fn()
            export.assert_called_once_with(stub.projects, Path(item['path']),
                                           dest_dir=Path('D:/dest'))
            self.assertEqual(result, (Path('D:/dest/甲.zip'), manifest))
            done(result)
            stub.status.set.assert_called_with(
                '已导出项目备份：D:\\dest\\甲.zip，其中 2 个配置文件的密钥已移除')
            done((Path('D:/dest/甲.zip'), {'redacted': []}))
            stub.status.set.assert_called_with('已导出项目备份：D:\\dest\\甲.zip')

            with mock.patch('domain.project_archive.inspect_archive',
                            return_value={'format': project_archive.ARCHIVE_FORMAT,
                                          'name': '甲'}) as inspect:
                ProjectPagesMixin.import_project_archive(stub)
            inspect.assert_called_once_with('D:/dest/甲.zip')
            stub.project_page_services.confirm.assert_called_once_with(
                stub.win, '导入备份包', '将把备份包还原为新项目 甲，不会改动任何现有项目')
            fn, done = captured['job']
            fn()
            stub.projects.import_archive.assert_called_once_with('D:/dest/甲.zip')
            done('D:/lib/甲_20260101')
            stub.reload.assert_called_once()
            stub.status.set.assert_called_with('已导入项目：D:/lib/甲_20260101')

            session = SimpleNamespace(
                root=Path(item['path']), busy=True, optimizer_busy=False,
                studio=SimpleNamespace(state=lambda: {'shots': {}}))
            stub.video_sessions = {'k': session}
            with self.assertRaisesRegex(ValueError, '仍有视频或提示词任务'):
                ProjectPagesMixin.export_project_archive(stub, item)
        finally:
            root.destroy()

    def test_import_cancel_or_invalid_zip_starts_no_job(self):
        root = self._tk_root()
        captured = {'zip_path': 'D:/dest/甲.zip'}
        try:
            stub = self._stub(root, captured)
            stub.project_page_services = ProjectPageServices(
                open_path=mock.Mock(), context_menu=mock.Mock(),
                confirm=mock.Mock(return_value=False))
            with mock.patch('domain.project_archive.inspect_archive',
                            return_value={'format': project_archive.ARCHIVE_FORMAT,
                                          'name': '甲'}):
                self.assertIsNone(ProjectPagesMixin.import_project_archive(stub))
            stub.project_page_services.confirm.assert_called_once()
            self.assertNotIn('job', captured, '用户取消确认后不得派发导入任务')
            with mock.patch('domain.project_archive.inspect_archive',
                            side_effect=ValueError('不是漫剧项目备份包（format 不符）：甲.zip')):
                with self.assertRaisesRegex(ValueError, '不是漫剧项目备份包'):
                    ProjectPagesMixin.import_project_archive(stub)
            self.assertNotIn('job', captured, '非备份包必须在确认前就被 inspect 拒绝')
            stub.project_page_services.confirm.assert_called_once()
        finally:
            root.destroy()


if __name__ == '__main__':
    unittest.main()

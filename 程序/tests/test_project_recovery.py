# -*- coding: utf-8 -*-
"""O40：项目删除／登记写失败／索引重建与回收恢复边界。"""
import inspect
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

import desktop
from projects import Projects
from stage_execution_service import project_registry_gateway
from infra.storage_maintenance import recycle_base, restore_recycle_batch


def dump(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')


def make_service(folder, name='故事_20261001'):
    app = Path(folder) / '程序'
    base = Path(folder) / '库' / '项目'
    project = base / name
    base.mkdir(parents=True)
    dump(app / 'config.json', {'downloads_root': str(Path(folder) / '库')})
    dump(project / 'config.json', {'episode_dir': str(project / '03初步分镜' / '分镜拆分')})
    (project / '03初步分镜' / '分镜拆分').mkdir(parents=True)
    dump(app / 'projects.json', {'active': str(project), 'projects': [
        {'name': '故事', 'path': str(project), 'created_at': 1, 'status': 'making'}]})
    return Projects(app, gateway=project_registry_gateway()), base, project


def read_registry(service):
    return json.loads(service.registry.read_text(encoding='utf-8'))


class ProjectRecoveryTests(unittest.TestCase):
    def test_recycle_succeeds_but_registry_write_fails_stays_recoverable(self):
        with tempfile.TemporaryDirectory() as td:
            service, base, project = make_service(td)
            gateway = project_registry_gateway()
            original = gateway['publish_json']
            def failing(path, data):
                if str(path) == str(service.registry):
                    raise PermissionError('locked')
                return original(path, data)
            gateway['publish_json'] = failing
            service.gateway = gateway; service._require_gateway()
            result = service.delete(str(project))
            self.assertFalse(result.ok)
            self.assertIn('回收站', result.reason)
            self.assertIn('重建项目索引', result.reason)
            # 项目内容确实进了项目库回收站，且能从回收站完整恢复。
            self.assertFalse(project.exists())
            batches = [b for b in recycle_base(base).iterdir() if b.is_dir()]
            self.assertEqual(len(batches), 1)
            self.assertEqual([str(x) for x in restore_recycle_batch(base, batches[0])], [str(project)])
            # 内存与磁盘登记都回退到删除前事实：界面不能显示成“已删除”。
            self.assertEqual([x['path'] for x in service.info['projects']], [str(project)])
            self.assertEqual([x['path'] for x in read_registry(service)['projects']], [str(project)])

    def test_rebuild_registry_drops_phantom_and_registers_new_directory(self):
        with tempfile.TemporaryDirectory() as td:
            service, base, project = make_service(td)
            ghost = base / '已失效_20261001'
            service.info['projects'].append({'name': '已失效', 'path': str(ghost), 'created_at': 2})
            newcomer = base / '新来的_20261002'
            (newcomer / '01剧本准备').mkdir(parents=True)
            outcome = service.rebuild_registry().data
            self.assertEqual(outcome['dropped'], [str(ghost)])
            self.assertIn(str(newcomer), outcome['added'])
            self.assertEqual(outcome['kept'], [str(project)])
            paths = [x['path'] for x in service.info['projects']]
            self.assertNotIn(str(ghost), paths)
            self.assertIn(str(newcomer), paths)
            self.assertEqual([x['path'] for x in read_registry(service)['projects']], paths)

    def test_rebuild_registry_is_idempotent_when_registry_matches_disk(self):
        with tempfile.TemporaryDirectory() as td:
            service, base, project = make_service(td)
            outcome = service.rebuild_registry().data
            self.assertFalse(outcome['changed'])
            self.assertEqual(outcome['dropped'], [])
            self.assertEqual(outcome['added'], [])

    def test_clear_registration_never_touches_disk(self):
        with tempfile.TemporaryDirectory() as td:
            service, base, project = make_service(td)
            with self.assertRaisesRegex(ValueError, '仍存在'):
                service.clear_missing_registration(str(project))
            self.assertTrue(project.is_dir())
            moved = base / '搬走了_20261001'
            project.rename(moved)
            self.assertTrue(service.clear_missing_registration(str(project)).ok)
            self.assertEqual([x['path'] for x in service.info['projects']], [])
            self.assertTrue(moved.is_dir(), '只清登记绝不动磁盘上的项目目录')

    def test_restore_into_occupied_name_keeps_batch_and_retries(self):
        with tempfile.TemporaryDirectory() as td:
            service, base, project = make_service(td)
            self.assertTrue(service.delete(str(project)).ok)
            batch = next(b for b in recycle_base(base).iterdir() if b.is_dir())
            recycled = next(x for x in batch.iterdir() if x.is_dir())
            (project / '01剧本准备').mkdir(parents=True)  # 同名新目录占了原位置
            with self.assertRaises(ValueError):
                restore_recycle_batch(base, batch)
            self.assertTrue(recycled.is_dir(), '目标被占用时恢复必须零移动，内容仍留在回收站')
            project.rename(base / '占用者_20261001')
            self.assertEqual([str(x) for x in restore_recycle_batch(base, batch)], [str(project)])
            self.assertTrue(project.is_dir())


class PermanentClearIsSeparateTests(unittest.TestCase):
    def test_project_layer_never_permanently_removes(self):
        source = Path(inspect.getfile(Projects)).read_text(encoding='utf-8')
        self.assertIn('recycle_paths', source)
        self.assertNotIn('rmtree', source)
        self.assertNotIn('unlink()', source)


class DesktopRebuildIndexTests(unittest.TestCase):
    def test_rebuild_reports_counts_and_refreshes(self):
        with tempfile.TemporaryDirectory() as td:
            service, base, project = make_service(td)
            ghost = base / '失效_20261001'
            service.info['projects'].append({'name': '失效', 'path': str(ghost), 'created_at': 2})
            app = MagicMock()
            app.projects = service
            app._project_home_tree = None
            app._project_result_data = lambda r: desktop.Desktop._project_result_data(app, r)
            outcome = desktop.Desktop.rebuild_project_index(app)
            self.assertEqual(outcome['dropped'], [str(ghost)])
            app.reload.assert_called_once()
            self.assertIn('重建项目索引', app.status.set.call_args.args[0])


class EmptyShellRegistrationTests(unittest.TestCase):
    """目录还在但没有 config.json 的登记：清除只动登记，重建索引不误留。"""

    def test_clear_missing_registration_keeps_shell_files_and_still_rejects_openable(self):
        with tempfile.TemporaryDirectory() as td:
            service, base, project = make_service(td)
            shell = base / '空壳_20261001'
            shell.mkdir()
            (shell / 'ui_settings.json').write_text('{}', encoding='utf-8')
            service.info['projects'].append({'name': '空壳', 'path': str(shell), 'created_at': 2})
            before = sorted(str(p.relative_to(shell)) for p in shell.rglob('*'))
            outcome = service.clear_missing_registration(str(shell))
            self.assertTrue(outcome.ok)
            self.assertEqual([x['path'] for x in service.info['projects']], [str(project)])
            self.assertEqual(sorted(str(p.relative_to(shell)) for p in shell.rglob('*')), before,
                             '只清登记绝不动失效登记目录里的文件')
            self.assertTrue(shell.is_dir())
            with self.assertRaisesRegex(ValueError, '仍存在'):
                service.clear_missing_registration(str(project))
            self.assertTrue((project / 'config.json').is_file())
            self.assertEqual([x['path'] for x in service.info['projects']], [str(project)])

    def test_rebuild_registry_drops_pure_shell_and_keeps_partial_project(self):
        with tempfile.TemporaryDirectory() as td:
            service, base, project = make_service(td)
            shell = base / '空壳_20261001'
            shell.mkdir()
            partial = base / '残缺_20261002'
            (partial / '01剧本准备').mkdir(parents=True)
            service.info['projects'].append({'name': '空壳', 'path': str(shell),
                                             'created_at': 2, 'status': 'making'})
            service.info['projects'].append({'name': '残缺', 'path': str(partial),
                                             'created_at': 3, 'status': 'completed'})
            outcome = service.rebuild_registry().data
            self.assertIn(str(shell), outcome['dropped'], '纯空壳登记要进 dropped')
            self.assertIn(str(partial), outcome['kept'], '有阶段目录的残缺项目保持登记')
            self.assertIn(str(project), outcome['kept'])
            paths = [x['path'] for x in service.info['projects']]
            self.assertNotIn(str(shell), paths)
            self.assertEqual(paths, [str(project), str(partial)])
            kept = next(x for x in service.info['projects'] if x['path'] == str(partial))
            self.assertEqual(kept.get('status'), 'completed', '保持登记不丢状态')
            self.assertEqual(sorted(str(p.relative_to(shell)) for p in shell.rglob('*')), [],
                             '重建索引不动空壳目录')


if __name__ == '__main__':
    unittest.main()

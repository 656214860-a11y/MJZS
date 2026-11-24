# -*- coding: utf-8 -*-
"""O40：项目删除／登记写失败／索引重建与回收恢复边界；REL-06 并入 config.json 读坏回退与版本登记。"""
import inspect
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

import desktop
import engine
from infra import project_settings
from contract import artifact_schema
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


class CorruptConfigFallbackTests(unittest.TestCase):
    """REL-06：config.json 读坏回退最近的 .bak 并提示；无 .bak 报可操作错误且不新建文件。"""

    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.addCleanup(self.td.cleanup)
        self.project = Path(self.td.name) / '项目'
        self.project.mkdir()
        self.config = self.project / 'config.json'

    def listing(self):
        return sorted(p.name for p in self.project.iterdir())

    def test_corrupt_config_falls_back_to_recent_bak_with_notice(self):
        backup_data = {'episode_dir': 'episode', 'custom_key': '用户自己的值'}
        dump(self.project / 'config.json.bak', backup_data)
        self.config.write_text('{"episode_dir":', encoding='utf-8')
        with self.assertLogs('engine', level='WARNING') as caught:
            cfg = engine.read_project_config(self.project)
        self.assertEqual(cfg, backup_data, '回退必须给出备份里的用户值')
        self.assertTrue(any('回退' in line or '备份' in line for line in caught.output),
                        '回退必须留下用户可查的提示：' + repr(caught.output))
        self.assertEqual(self.config.read_text(encoding='utf-8'), '{"episode_dir":',
                         '坏文件原样留在盘上，不被顺手改写')

    def test_corrupt_config_without_bak_reports_actionable_error_and_creates_nothing(self):
        self.config.write_text('{坏配置', encoding='utf-8')
        with self.assertRaises(ValueError) as caught:
            engine.read_project_config(self.project)
        message = str(caught.exception)
        self.assertIn('config.json 无法读取', message)
        self.assertNotIn('没有项目配置文件', message)
        self.assertIn('config.json.bak', message, '无备份时报错要点出备份文件名，用户才知道去哪找')
        self.assertIn('请', message, '无备份时报错必须可操作（检查编码／重新查找项目）')
        self.assertEqual(self.listing(), ['config.json'],
                         '读坏报错不得在目录里新建文件，更不静默建空配置')

    def test_corrupt_config_with_also_corrupt_bak_reports_both_unreadable(self):
        self.config.write_text('{坏配置', encoding='utf-8')
        (self.project / 'config.json.bak').write_text('{也坏', encoding='utf-8')
        with self.assertRaises(ValueError) as caught:
            engine.read_project_config(self.project)
        message = str(caught.exception)
        self.assertIn('config.json 无法读取', message)
        self.assertIn('config.json.bak', message)
        self.assertTrue('备份' in message and ('读不出' in message or '损坏' in message or '也' in message),
                        '备份也读坏时要明说两份都不可用：' + message)

    def test_healthy_config_refreshes_bak_snapshot(self):
        data = {'episode_dir': 'episode', 'custom_key': '最近一次好内容'}
        dump(self.config, data)
        engine.read_project_config(self.project)
        backup = self.project / 'config.json.bak'
        self.assertTrue(backup.is_file(), '成功读取后应刷新最近的 .bak 快照')
        self.assertEqual(backup.read_bytes(), self.config.read_bytes())

    def test_bak_from_last_good_read_wins(self):
        # 好配置读过一遍留下 .bak；之后 config 损坏，下一趟读回退到那份快照。
        dump(self.config, {'episode_dir': 'episode', 'custom_key': '第一版'})
        engine.read_project_config(self.project)
        self.config.write_text('{后来被改坏', encoding='utf-8')
        cfg = engine.read_project_config(self.project)
        self.assertEqual(cfg, {'episode_dir': 'episode', 'custom_key': '第一版'})


class ProjectConfigVersionTests(unittest.TestCase):
    """REL-06：config.json／skill_config.json 登记版本——容忍缺版本、拒绝未来版本、写回补版本号。"""

    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.addCleanup(self.td.cleanup)
        self.project = Path(self.td.name) / '项目'
        self.project.mkdir()

    def test_project_config_and_skill_config_are_registered(self):
        for kind in ('project_config', 'skill_config'):
            with self.subTest(kind=kind):
                item = artifact_schema.spec(kind)
                self.assertIsInstance(item['version'], int)
                self.assertEqual(artifact_schema.classify(kind, {'x': 1}), 'missing')
                self.assertEqual(artifact_schema.classify(kind, {'schema_version': item['version']}),
                                 'current')
                self.assertEqual(artifact_schema.classify(kind, {'schema_version': item['version'] + 1}),
                                 'future')

    def test_old_config_without_version_is_tolerated_and_next_write_stamps(self):
        # 老项目 config.json 没有版本字段：照常读、用户值原样，写回时补 schema_version。
        dump(self.project / 'config.json', {'episode_dir': '旧的指针目录', 'custom_key': '用户值'})
        studio = engine.Studio.__new__(engine.Studio)
        studio.root = self.project
        studio.episode_path = self.project / 'episode' / 'episode.json'
        studio.cfg = engine.read_project_config(self.project)
        self.assertTrue(studio.remember_episode(), '指针不一致时 remember_episode 应写回')
        saved = json.loads((self.project / 'config.json').read_text(encoding='utf-8'))
        self.assertEqual(saved['schema_version'],
                         artifact_schema.spec('project_config')['version'])
        self.assertEqual(saved['custom_key'], '用户值', '迁移只加键、不删用户数据')
        self.assertEqual(saved['episode_dir'], str(studio.episode_path.parent))

    def test_future_version_config_is_rejected_without_touching_file(self):
        target = artifact_schema.spec('project_config')['version'] + 1
        original = json.dumps({'episode_dir': 'episode', 'schema_version': target},
                              ensure_ascii=False)
        (self.project / 'config.json').write_text(original, encoding='utf-8')
        with self.assertRaises(ValueError) as caught:
            engine.read_project_config(self.project)
        self.assertIn('版本', str(caught.exception))
        self.assertEqual((self.project / 'config.json').read_text(encoding='utf-8'), original,
                         '拒绝未来版本不得改写原文件')


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

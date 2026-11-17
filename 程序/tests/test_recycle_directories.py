"""整目录恢复只在临时项目库验证，不触碰真实项目。"""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from projects import Projects
from orchestrator.recycle_recovery_controller import RecycleRecoveryController
from domain.recycle_recovery_service import list_batches, restore_batch
from contract.service_contract import SystemError
from stage_execution_service import project_registry_gateway
from infra.storage_maintenance import recycle_paths, restore_recycle_batch


class RecycleDirectoryTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name) / '库'
        self.root.mkdir()

    def recycle(self, *paths):
        records = recycle_paths(self.root, paths, '目录回归', now=1700000000)
        batch = self.root / Path(records[0]['recycle_path']).parts[0] / '回收站'
        return records, next(batch.iterdir())

    def test_directory_and_empty_directory_are_visible_and_restored(self):
        project = self.root / '故事'; empty = self.root / '空项目'
        (project / '01剧本准备').mkdir(parents=True); empty.mkdir()
        script = project / '01剧本准备' / '剧本.md'
        script.write_text('原始剧本', encoding='utf-8')
        self.recycle(project, empty)
        record = list_batches(self.root)[0]
        self.assertEqual({item['source'] for item in record['items']}, {'故事', '空项目'})
        result = restore_batch(record)
        self.assertTrue(result.ok, result.reason)
        self.assertEqual(set(result.data), {project, empty})
        self.assertEqual(script.read_text(encoding='utf-8'), '原始剧本')
        self.assertEqual(list(empty.iterdir()), [])
        self.assertEqual(list_batches(self.root)[0]['items'], [])

    def test_directory_conflict_is_zero_move(self):
        first = self.root / '甲'; second = self.root / '乙'
        first.mkdir(); second.mkdir()
        records, batch = self.recycle(first, second)
        second.mkdir()
        with self.assertRaises(ValueError):
            restore_recycle_batch(self.root, batch)
        self.assertFalse(first.exists())
        self.assertTrue(all((self.root / row['recycle_path']).is_dir() for row in records))

    def test_directory_rename_failure_rolls_back_previous_directory(self):
        first = self.root / '甲'; second = self.root / '乙'
        first.mkdir(); second.mkdir()
        records, batch = self.recycle(first, second)
        rename = Path.rename
        def fail_second(path, target):
            if path == self.root / records[1]['recycle_path']:
                raise OSError('test failure')
            return rename(path, target)
        with patch.object(Path, 'rename', fail_second):
            with self.assertRaisesRegex(ValueError, '已回滚'):
                restore_recycle_batch(self.root, batch)
        self.assertFalse(first.exists()); self.assertFalse(second.exists())
        self.assertTrue(all((self.root / row['recycle_path']).is_dir() for row in records))

    def test_edited_directory_manifest_cannot_escape_or_overlap(self):
        project = self.root / '故事'; (project / '子目录').mkdir(parents=True)
        records, batch = self.recycle(project)
        manifest = batch / '恢复位置.json'
        for rows in ([dict(records[0], source='../外部')],
                     [records[0], dict(records[0])],
                     [records[0], {'source': '另一目录',
                                   'recycle_path': records[0]['recycle_path'] + '/子目录'}]):
            with self.subTest(rows=rows):
                manifest.write_text(json.dumps({'items': rows}), encoding='utf-8')
                with self.assertRaises(ValueError):
                    restore_recycle_batch(self.root, batch)
                self.assertTrue((self.root / records[0]['recycle_path']).is_dir())
                self.assertFalse(project.exists())

    def test_link_nodes_and_ancestors_are_rejected_before_resolution(self):
        project = self.root / '故事'; project.mkdir()
        records, batch = self.recycle(project)
        source = self.root / records[0]['recycle_path']
        for method in ('is_symlink', 'is_junction'):
            original = getattr(Path, method)
            for linked in (source, batch, project):
                with self.subTest(method=method, linked=linked), patch.object(
                        Path, method, lambda path: path == linked or original(path)):
                    with self.assertRaises(ValueError):
                        restore_recycle_batch(self.root, batch)
                    self.assertTrue(source.is_dir())

    def make_projects(self):
        app = self.root / '程序'; app.mkdir()
        (app / 'config.json').write_text(json.dumps({'downloads_root': str(self.root / '下载')}), encoding='utf-8')
        (app / 'projects.json').write_text('{"projects": [], "active": null}', encoding='utf-8')
        return Projects(app, gateway=project_registry_gateway(), migrate_legacy=False)

    def test_deleted_project_restores_and_registers_exact_restored_path(self):
        projects = self.make_projects()
        project = projects.base / '故事_20261007'; project.mkdir()
        projects.info = {'projects': [{'name': '故事', 'path': str(project), 'created_at': 1}],
                         'active': str(project)}
        self.assertTrue(projects.delete(str(project)).ok)
        controller = RecycleRecoveryController(None, projects.base,
                                               register_restored=projects.register_restored_projects)
        record = controller.list_batches()[0]
        restored = controller.restore_batch(record)
        self.assertEqual(restored, [project])
        self.assertEqual([item['path'] for item in projects.info['projects']], [str(project)])
        self.assertEqual(projects.info['active'], str(project))
        self.assertTrue(projects.register_restored_projects(restored).ok)
        self.assertEqual(len(projects.info['projects']), 1)

    def test_registry_failure_reports_disk_restore_without_claiming_rollback(self):
        project = self.root / '故事'; project.mkdir(); self.recycle(project)
        controller = RecycleRecoveryController(None, self.root,
                                               register_restored=lambda paths: SystemError('登记失败'))
        with self.assertRaisesRegex(ValueError, '内容已恢复.*登记失败'):
            controller.restore_batch(controller.list_batches()[0])
        self.assertTrue(project.is_dir())

    def test_registration_failure_keeps_in_memory_registry_unchanged(self):
        projects = self.make_projects(); project = projects.base / '故事'; project.mkdir()
        before = dict(projects.info)
        with patch.object(projects, '_publish_json', side_effect=OSError('disk')):
            with self.assertLogs('projects', level='ERROR'):
                result = projects.register_restored_projects([project])
        self.assertFalse(result.ok)
        self.assertEqual(projects.info, before)

    def test_project_internal_directory_does_not_register_as_project(self):
        project = self.root / '内部素材'; project.mkdir(); self.recycle(project)
        def unexpected(paths):
            self.fail('项目内恢复不得登记为独立项目')
        controller = RecycleRecoveryController(self.root, self.root / '其他库',
                                               register_restored=unexpected)
        self.assertEqual(controller.restore_batch(controller.list_batches()[0]), [project])

    def test_existing_registration_is_preserved_and_outside_directory_rejected(self):
        projects = self.make_projects(); project = projects.base / '故事'; project.mkdir()
        existing = {'name': '用户名称', 'path': str(project), 'created_at': 1, 'status': 'completed'}
        projects.info = {'projects': [existing], 'active': str(project)}
        self.assertTrue(projects.register_restored_projects([project]).ok)
        self.assertEqual(projects.info['projects'], [existing])
        with self.assertRaises(ValueError):
            projects.register_restored_projects([self.root])
        self.assertEqual(projects.info['projects'], [existing])

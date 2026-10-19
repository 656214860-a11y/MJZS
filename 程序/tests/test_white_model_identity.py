# -*- coding: utf-8 -*-
"""REQ-S09-32（O07）：白模工作目录的项目身份、集维度与旧目录迁移。

隔离要求：位置不同的同名项目、同一项目两集复用 S001、项目改名／移动，都不能落到同一目录；
旧布局成果保持只读可用，迁移可重复、不覆盖、失败原样回滚。
"""
import json
import os
import shutil
import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.chdir(HERE)

import white_model_service
from projects import Projects
from stage_execution_service import (project_context, project_registry_gateway,
                                     white_model_shot_directory)


def _episode(path, episode_id, shot_ids):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({'episode_id': episode_id, 'title': episode_id,
                                'shots': [{'id': sid} for sid in shot_ids]}, ensure_ascii=False),
                    encoding='utf-8')
    return path


def _project(root, project_id=None, episode_ids=('EP001',), shots=('SH001', 'SH002')):
    """搭一个最小项目：config.json（可选身份）＋一或多集分镜，不碰真实白模工作区。"""
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    story = root / '03初步分镜' / '分镜拆分'
    episodes = {episode_id: _episode(story / (episode_id + '_分镜.json'), episode_id, shots)
                for episode_id in episode_ids}
    config = {'episode_dir': str(root / '03初步分镜'),
              'episode_file': str(episodes[episode_ids[0]])}
    if project_id:
        config['project_id'] = project_id
    (root / 'config.json').write_text(json.dumps(config, ensure_ascii=False), encoding='utf-8')
    return root, episodes


class IdentityDirectoryTests(unittest.TestCase):
    def setUp(self):
        self.space = tempfile.TemporaryDirectory()
        self.addCleanup(self.space.cleanup)
        self.space_path = Path(self.space.name)
        for cache in (white_model_service._BASE_CACHE, white_model_service._DIR_CACHE):
            cache.clear()
            self.addCleanup(cache.clear)

    def target(self, *parts):
        return self.space_path.joinpath(*parts).resolve()

    def test_same_named_projects_keep_separate_directories(self):
        left, _ = _project(self.space_path / 'a' / '同名项目', project_id='pid-left')
        right, _ = _project(self.space_path / 'b' / '同名项目', project_id='pid-right')
        left_dir = white_model_shot_directory(left, 'SH001', workspace_path=self.space_path)
        right_dir = white_model_shot_directory(right, 'SH001', workspace_path=self.space_path)
        self.assertNotEqual(left_dir.resolve(), right_dir.resolve())
        self.assertEqual(left_dir.resolve(), self.target('pid-left', 'EP001', 'SH001'))
        self.assertEqual(right_dir.resolve(), self.target('pid-right', 'EP001', 'SH001'))

    def test_same_shot_id_in_two_episodes_keeps_separate_directories(self):
        project, episodes = _project(self.space_path / 'p', project_id='pid',
                                     episode_ids=('EP001', 'EP002'))
        first = white_model_shot_directory(project, 'SH001', workspace_path=self.space_path,
                                           source=episodes['EP001'])
        second = white_model_shot_directory(project, 'SH001', workspace_path=self.space_path,
                                            source=episodes['EP002'])
        self.assertNotEqual(first, second)
        self.assertEqual(first.parent.name, 'EP001')
        self.assertEqual(second.parent.name, 'EP002')

    def test_shot_id_episode_prefix_wins_without_a_source(self):
        project, _ = _project(self.space_path / 'p', project_id='pid')
        folder = white_model_shot_directory(project, 'EP007_SH003', workspace_path=self.space_path)
        self.assertEqual(folder.parent.name, 'EP007')

    def test_rename_and_move_keep_the_same_directory(self):
        project, _ = _project(self.space_path / 'before' / '项目', project_id='pid')
        before = white_model_shot_directory(project, 'SH001', workspace_path=self.space_path)
        moved = self.space_path / 'after' / '改名后的项目'
        moved.parent.mkdir(parents=True)
        shutil.move(str(project), str(moved))
        self.assertEqual(white_model_shot_directory(moved, 'SH001', workspace_path=self.space_path), before)

    def test_project_without_identity_keeps_legacy_layout_readable(self):
        project, _ = _project(self.space_path / 'p')
        legacy = self.space_path / 'p' / 'SH001'
        legacy.mkdir(parents=True)
        (legacy / '预演记录.json').write_text(json.dumps({'preview': 'old.mp4'}, ensure_ascii=False),
                                             encoding='utf-8')
        root = white_model_shot_directory(project, 'SH001', workspace_path=self.space_path)
        self.assertEqual(root.resolve(), legacy.resolve())
        self.assertEqual(white_model_service.read_record(root)['preview'], 'old.mp4')


class LegacyMigrationTests(unittest.TestCase):
    def setUp(self):
        self.space = tempfile.TemporaryDirectory()
        self.addCleanup(self.space.cleanup)
        self.space_path = Path(self.space.name)
        for cache in (white_model_service._BASE_CACHE, white_model_service._DIR_CACHE):
            cache.clear()
            self.addCleanup(cache.clear)

    def legacy(self, name, sid):
        return self.space_path / name / sid

    def build(self, shots=('SH001', 'SH002')):
        project, episodes = _project(self.space_path / 'case' / 'p')
        for sid in shots:
            folder = self.legacy(project.name, sid)
            folder.mkdir(parents=True)
            (folder / '预演记录.json').write_text(
                json.dumps({'preview': sid + '.mp4'}, ensure_ascii=False), encoding='utf-8')
        (project / 'ui_settings.json').write_text(
            json.dumps({'adopted_storyboards': [str(episodes['EP001'])]}, ensure_ascii=False),
            encoding='utf-8')
        return project

    def migrate(self, project):
        return white_model_service.migrate_legacy_directories(
            project_context(project), publish=_publish, workspace_path=self.space_path)

    def test_migration_moves_legacy_directories_and_records_source_version(self):
        project = self.build()
        result = self.migrate(project)
        identity = result['project_id']
        self.assertEqual(sorted(result['moved']), ['SH001', 'SH002'])
        for sid in ('SH001', 'SH002'):
            self.assertTrue((self.space_path / identity / 'EP001' / sid / '预演记录.json').is_file())
            self.assertFalse(self.legacy(project.name, sid).exists())
        manifest = json.loads(Path(result['manifest']).read_text(encoding='utf-8'))
        self.assertEqual(manifest['status'], 'completed')
        self.assertEqual(manifest['items'][0]['episode_id'], 'EP001')
        self.assertEqual(manifest['items'][0]['source_version']['episode_id'], 'EP001')
        self.assertTrue(Path(manifest['items'][0]['source_version']['storyboard']).is_file())
        self.assertEqual(white_model_shot_directory(project, 'SH001', workspace_path=self.space_path),
                         (self.space_path / identity / 'EP001' / 'SH001').resolve())

    def test_migration_is_repeatable_and_never_moves_twice(self):
        project = self.build()
        first = self.migrate(project)
        second = self.migrate(project)
        self.assertEqual(second['moved'], [])
        self.assertEqual(second['project_id'], first['project_id'])
        self.assertIsNone(second['manifest'])
        self.assertTrue((self.space_path / first['project_id'] / 'EP001' / 'SH001').is_dir())

    def test_existing_target_is_skipped_not_overwritten(self):
        project = self.build(shots=('SH001',))
        fixed = uuid.UUID(int=7)
        target = self.space_path / fixed.hex / 'EP001' / 'SH001'
        target.mkdir(parents=True)
        (target / '预演记录.json').write_text(json.dumps({'preview': 'new.mp4'}, ensure_ascii=False),
                                             encoding='utf-8')
        with patch('white_model_service.uuid.uuid4', return_value=fixed):
            result = self.migrate(project)
        self.assertEqual(result['moved'], [])
        self.assertEqual(result['skipped'][0]['sid'], 'SH001')
        self.assertEqual(json.loads((target / '预演记录.json').read_text(encoding='utf-8'))['preview'], 'new.mp4')
        self.assertTrue(self.legacy(project.name, 'SH001').is_dir())

    def test_failed_move_rolls_back_and_leaves_identity_unset(self):
        project = self.build()
        real_move = shutil.move
        calls = []

        def flaky(source, target):
            calls.append(source)
            if len(calls) == 2:
                raise OSError('locked')
            return real_move(source, target)

        with patch('white_model_service.shutil.move', side_effect=flaky):
            with self.assertRaises(OSError):
                self.migrate(project)
        for sid in ('SH001', 'SH002'):
            self.assertTrue((self.legacy(project.name, sid) / '预演记录.json').is_file())
        self.assertNotIn('project_id', json.loads((project / 'config.json').read_text(encoding='utf-8')))
        self.assertEqual(white_model_shot_directory(project, 'SH001', workspace_path=self.space_path),
                         self.legacy(project.name, 'SH001').resolve())

    def test_unmapped_legacy_directory_aborts_before_touching_anything(self):
        project = self.build(shots=('SH001', 'SH999'))
        with self.assertRaisesRegex(ValueError, '找不到对应采用分镜'):
            self.migrate(project)
        for sid in ('SH001', 'SH999'):
            self.assertTrue((self.legacy(project.name, sid) / '预演记录.json').is_file())
        self.assertNotIn('project_id', json.loads((project / 'config.json').read_text(encoding='utf-8')))

    def test_broken_config_blocks_migration_without_losing_any_directory(self):
        project = self.build(shots=('SH001',))
        (project / 'config.json').write_text('{ 坏配置', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, '项目配置无法读取'):
            self.migrate(project)
        self.assertTrue((self.legacy(project.name, 'SH001') / '预演记录.json').is_file())
        self.assertEqual((project / 'config.json').read_text(encoding='utf-8'), '{ 坏配置')


class CreatedProjectIdentityTests(unittest.TestCase):
    def test_created_project_gets_its_own_identity_directory(self):
        with tempfile.TemporaryDirectory() as td:
            app = Path(td) / '程序'
            app.mkdir()
            (app / 'config.json').write_text(
                json.dumps({'downloads_root': str(Path(td) / '库')}, ensure_ascii=False), encoding='utf-8')
            (app / 'projects.json').write_text(
                json.dumps({'active': None, 'projects': []}, ensure_ascii=False), encoding='utf-8')
            service = Projects(app, gateway=project_registry_gateway(), migrate_legacy=False)
            project = Path(service.create('测试项目').data)
            config = json.loads((project / 'config.json').read_text(encoding='utf-8'))
            space = Path(td) / '白模'
            folder = white_model_shot_directory(project, 'SH001', workspace_path=space)
            self.assertTrue(config.get('project_id'))
            self.assertEqual(folder.parent.parent.name, config['project_id'])
            self.assertEqual(folder.parent.name, 'EP001')
            self.assertEqual(folder.name, 'SH001')


def _publish(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')


if __name__ == '__main__':
    unittest.main()

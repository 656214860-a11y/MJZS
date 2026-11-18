# -*- coding: utf-8 -*-
"""R3310 轮 6：``infra.unit_of_work`` 接入 7 处写路径的回滚完整性回归。

每个用例模拟「第二步写入失败或 ``BaseException`` 取消」，断言先前写入全部恢复；
改前只在 ``except Exception`` 内回滚（或完全没有回滚）的路径在取消下保持半成品，
因此这些用例改前红、改后绿。
"""
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import asset_batch_service
from domain import global_library_service as gls
import idea_chat
import local_video_settings_service
import video_prompt_publication
import white_model_service
from agent.core import read, save, save_bytes, save_text
from contract.service_contract import SystemError
from contract.stage_layout import shared_paths
from contract.stage_path_service import write_dir
from projects import Projects
from stage_execution_service import (asset_batch_gateway, asset_detail_gateway,
                                     idea_chat_gateway, local_video_settings_gateway,
                                     project_context, project_registry_gateway,
                                     video_prompt_gateway)


class _Cancelled(BaseException):
    """模拟 ``asyncio.Cancelled``／``KeyboardInterrupt`` 一类非 ``Exception`` 中断。"""


class AssetBatchTransactionTests(unittest.TestCase):
    """asset_batch_service 两处：改名单与导入图片。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)

    def _rename_fixture(self):
        plan = self.base / 'assets/资产清单/assets.json'
        plan.parent.mkdir(parents=True)
        registry = self.base / 'assets.json'
        save(plan, {'CHAR_001': {'name': '旧名', 'aliases': []}})
        save(registry, {'CHAR_001': {'name': '旧名'}})
        return plan, registry

    def test_rename_asset_cancel_restores_plan_and_registry(self):
        plan, registry = self._rename_fixture()
        before_plan, before_registry = plan.read_bytes(), registry.read_bytes()
        real_publish = asset_batch_gateway()['publish_json']

        def flaky(path, value):
            real_publish(path, value)
            if Path(path) == registry:
                raise _Cancelled('第二写被取消')

        gateway = asset_batch_gateway()
        gateway['publish_json'] = flaky
        with self.assertRaises(_Cancelled):
            asset_batch_service.rename_asset(self.base, 'CHAR_001', '旧名', '新名', gateway=gateway)
        self.assertEqual(plan.read_bytes(), before_plan)
        self.assertEqual(registry.read_bytes(), before_registry)

    def test_import_asset_image_cancel_restores_image_and_registry(self):
        base = self.base / 'asset-base'
        base.mkdir()
        project = self.base / 'project'
        project.mkdir()
        source = self.base / 'incoming.png'
        source.write_bytes(b'new image')
        registry_file = base / 'assets.json'
        save(registry_file, {'CHAR_001': {'name': '旧角色'}})
        dest = base / 'assets/characters/CHAR_001.png'
        dest.parent.mkdir(parents=True)
        dest.write_bytes(b'old image')
        before_registry = registry_file.read_bytes()

        gateway = asset_batch_gateway()
        real_publish = gateway['publish_json']

        def flaky(path, value):
            real_publish(path, value)
            raise _Cancelled('登记发布被取消')

        gateway['publish_json'] = flaky
        with self.assertRaises(_Cancelled):
            asset_batch_service.import_asset_image(
                base, project, 'CHAR_001', source,
                {'CHAR_001': {'name': '角色', 'description': '主角'}}, gateway=gateway)
        self.assertEqual(dest.read_bytes(), b'old image')
        self.assertEqual(registry_file.read_bytes(), before_registry)
        self.assertTrue(source.is_file())


class AssetDetailTransactionTests(unittest.TestCase):
    def test_bind_cancel_restores_image_and_index(self):
        with tempfile.TemporaryDirectory() as raw:
            project = Path(raw) / 'project'
            base = project / '05资产管理'
            index = base / 'assets/资产清单/assets.json'
            save(project / 'config.json', {'episode_dir': '05资产管理'})
            save(index, {'CHAR_001': {'name': '小满'}})
            source = project / 'source.png'
            source.write_bytes(b'png-data')
            dest = base / 'assets/正典板/CHAR_001_front.png'
            dest.parent.mkdir(parents=True)
            dest.write_bytes(b'old-image')
            before_index = index.read_bytes()
            with patch('asset_detail_service.update_fields', side_effect=_Cancelled('索引写被取消')):
                with self.assertRaises(_Cancelled):
                    from asset_detail_service import bind_canonical_view
                    bind_canonical_view(project, base, 'CHAR_001', 'front', source,
                                        gateway=asset_detail_gateway())
            self.assertEqual(dest.read_bytes(), b'old-image')
            self.assertEqual(index.read_bytes(), before_index)


class LocalVideoTransactionTests(unittest.TestCase):
    def test_save_cancel_removes_new_workflow_and_restores_config(self):
        with tempfile.TemporaryDirectory() as raw:
            project = Path(raw) / 'project'
            project.mkdir()
            config = project / 'config.json'
            save(config, {'video_backend': 'wan'})
            source = project / 'chosen.json'
            save_text(source, '{"1": {}}')
            first = local_video_settings_service.save_local_video_settings(
                project_context(project), read(config), {'workflow': str(source)},
                gateway=local_video_settings_gateway())
            before_config = config.read_bytes()
            source.write_text('{"2": {}}', encoding='utf-8')
            gateway = local_video_settings_gateway()
            real_publish = gateway['publish_json']

            def flaky(path, value):
                real_publish(path, value)
                raise _Cancelled('配置发布被取消')

            gateway['publish_json'] = flaky
            with self.assertRaises(_Cancelled):
                local_video_settings_service.save_local_video_settings(
                    project_context(project), read(config), {'workflow': str(source)}, gateway=gateway)
            self.assertEqual(config.read_bytes(), before_config)
            # 新工作流按内容哈希命名：取消后只应留下第一份，第二份不得留盘。
            workflows = sorted((project / 'workflows').glob('video_*.json'))
            self.assertEqual(len(workflows), 1)
            self.assertEqual(workflows[0].read_bytes(),
                             Path(first['local_video']['workflow']).read_bytes())


class WhiteModelTransactionTests(unittest.TestCase):
    """white_model_service 三处：项目副本同步、媒体导入、旧目录迁移。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.space = Path(self.tmp.name) / 'space'
        self.space.mkdir()
        for cache in (white_model_service._BASE_CACHE, white_model_service._DIR_CACHE,
                      white_model_service._WORKSPACE_CACHE):
            cache.clear()
            self.addCleanup(cache.clear)

    def _project(self, root, shots=('SH001', 'SH002')):
        root = Path(root)
        root.mkdir(parents=True, exist_ok=True)
        story = root / '03初步分镜' / '分镜拆分'
        episode = story / 'EP001_分镜.json'
        episode.parent.mkdir(parents=True, exist_ok=True)
        episode.write_text(json.dumps({'episode_id': 'EP001', 'title': 'EP001',
                                       'shots': [{'id': sid} for sid in shots]}, ensure_ascii=False),
                           encoding='utf-8')
        (root / 'config.json').write_text(json.dumps(
            {'episode_dir': str(root / '03初步分镜'), 'episode_file': str(episode)},
            ensure_ascii=False), encoding='utf-8')
        return root, episode

    @staticmethod
    def _publish(path, data):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')

    def test_sync_project_copy_cancel_restores_target_and_index(self):
        project, episode = self._project(self.space / 'case' / 'p')
        (project / 'config.json').write_text(json.dumps(
            {'project_id': 'pid-sync', 'episode_dir': str(project / '03初步分镜'),
             'episode_file': str(episode)}, ensure_ascii=False), encoding='utf-8')
        context = project_context(project)
        # sync_project_copy 内部不传 workspace_path，走 workspace()；与 shot_directory 对齐。
        with patch.object(white_model_service, 'workspace', lambda: self.space):
            shot = white_model_service.shot_directory(context, 'SH001', source=episode)
            shot.mkdir(parents=True)
            preview = shot / 'prev.mp4'
            preview.write_bytes(b'video-bytes')
            white_model_service.write_record(shot, {'shot_id': 'SH001', 'preview': str(preview)},
                                             publish=save)
            white_model_service.record_evidence(shot, 'SH001', episode, publish=save)
            index_path = white_model_service.project_index_path(context, write=True)

            def flaky(path, data):
                save(path, data)
                raise _Cancelled('索引发布被取消')

            with self.assertRaises(_Cancelled):
                white_model_service.sync_project_copy(context, 'SH001', episode, publish=flaky)
        target = write_dir(project, 'previs') / 'assets' / 'SH001' / 'prev.mp4'
        self.assertFalse(target.exists())
        self.assertFalse(index_path.exists())

    def test_import_previs_media_cancel_restores_record_and_removes_media(self):
        root = self.space / 'shot'
        root.mkdir()
        record_path = root / '预演记录.json'
        save_text(record_path, json.dumps({'shot_id': 'SH001', 'preview': 'old.mp4'}, ensure_ascii=False))
        before_record = record_path.read_bytes()
        source = self.space / 'incoming.mp4'
        source.write_bytes(b'media-bytes')

        def flaky(path, data):
            save(path, data)
            raise _Cancelled('记录发布被取消')

        with self.assertRaises(_Cancelled):
            white_model_service.import_previs_media(root, 'SH001', source, publish=flaky)
        self.assertEqual(record_path.read_bytes(), before_record)
        self.assertEqual(list(root.glob('SH001_白模预演*')), [])

    def test_migrate_cancel_moves_completed_directories_back(self):
        project, episode = self._project(self.space / 'case' / 'p')
        for sid in ('SH001', 'SH002'):
            folder = self.space / project.name / sid
            folder.mkdir(parents=True)
            (folder / '预演记录.json').write_text(
                json.dumps({'preview': sid + '.mp4'}, ensure_ascii=False), encoding='utf-8')
        (project / 'ui_settings.json').write_text(
            json.dumps({'adopted_storyboards': [str(episode)]}, ensure_ascii=False), encoding='utf-8')
        real_move = shutil.move
        calls = []

        def flaky(source, target):
            calls.append(source)
            if len(calls) == 2:
                raise _Cancelled('第二次搬迁被取消')
            return real_move(source, target)

        with patch('white_model_service.shutil.move', side_effect=flaky):
            with self.assertRaises(_Cancelled):
                white_model_service.migrate_legacy_directories(
                    project_context(project), publish=self._publish,
                    workspace_path=self.space)
        for sid in ('SH001', 'SH002'):
            self.assertTrue((self.space / project.name / sid / '预演记录.json').is_file())
        self.assertNotIn('project_id', json.loads((project / 'config.json').read_text(encoding='utf-8')))

    def test_migrate_move_back_failure_is_logged_not_silent(self):
        project, episode = self._project(self.space / 'case' / 'p')
        for sid in ('SH001', 'SH002'):
            folder = self.space / project.name / sid
            folder.mkdir(parents=True)
            (folder / '预演记录.json').write_text('{}', encoding='utf-8')
        (project / 'ui_settings.json').write_text(
            json.dumps({'adopted_storyboards': [str(episode)]}, ensure_ascii=False), encoding='utf-8')
        real_move = shutil.move
        calls = []

        def flaky(source, target):
            calls.append(source)
            if len(calls) >= 2:
                raise OSError('locked')
            return real_move(source, target)

        with patch('white_model_service.shutil.move', side_effect=flaky):
            with self.assertLogs('swallowed', level='WARNING') as logs:
                with self.assertRaises(OSError):
                    white_model_service.migrate_legacy_directories(
                        project_context(project), publish=self._publish,
                        workspace_path=self.space)
        self.assertTrue(any('move_back' in line or 'rollback' in line for line in logs.output))


class VideoPromptTransactionTests(unittest.TestCase):
    def test_stage_import_rollback_failure_preserves_original_error(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            (root / 'episode.json').write_text(json.dumps({'shots': [{'id': 'SH001'}]}),
                                               encoding='utf-8')
            studio = SimpleNamespace(episode_path=root / 'episode.json', media_dir=root,
                                     shot_folder=lambda sid: root / 'shots' / sid)
            target = root / 'video_prompts' / 'SH001.json'
            target.parent.mkdir(parents=True)
            save(target, {'video_prompt': '旧草稿'})
            before = target.read_bytes()
            gateway = video_prompt_gateway()
            gateway['publish_json'] = Mock(side_effect=OSError('写入失败'))
            gateway['restore_bytes'] = Mock(side_effect=ValueError('回滚也失败'))
            result = video_prompt_publication.stage_import(studio, 'SH001', '导入提示词',
                                                           gateway=gateway)
            self.assertIsInstance(result, SystemError)
            self.assertEqual(target.read_bytes(), before)
            self.assertFalse((root / 'video_prompts' / '历史版本').exists())


class IdeaChatTransactionTests(unittest.TestCase):
    def test_receive_brief_cancel_restores_raw_append(self):
        with tempfile.TemporaryDirectory() as raw:
            context = project_context(raw)
            gateway = idea_chat_gateway()

            def flaky(path, value):
                raise _Cancelled('完整简报发布被取消')

            gateway['publish_json'] = flaky
            text = ('故事梗概：夜班照相馆收到一张会显影未来的旧底片。\n'
                    '主要角色：少年摄影师林默\n题材类型：都市悬疑\n篇幅：24集\n交付形态：markdown')
            with self.assertRaises(_Cancelled):
                idea_chat.receive_brief(context, text, gateway=gateway)
            raw_path = idea_chat.brief_raw_path(context)
            self.assertFalse(raw_path.exists())
            self.assertFalse(idea_chat.brief_complete_path(context).exists())


class ProjectsTransactionTests(unittest.TestCase):
    def test_write_transaction_cancel_restores_all_files(self):
        with tempfile.TemporaryDirectory() as raw:
            app = Path(raw) / '程序'
            app.mkdir()
            library = Path(raw) / '库'
            (app / 'config.json').write_text(
                json.dumps({'downloads_root': str(library)}, ensure_ascii=False), encoding='utf-8')
            (app / 'projects.json').write_text(
                json.dumps({'active': None, 'projects': []}, ensure_ascii=False), encoding='utf-8')
            service = Projects(app, gateway=project_registry_gateway(), migrate_legacy=False)
            first = library / '项目' / 'a.json'
            second = library / '项目' / 'b.json'
            save_text(first, 'before-a')
            save_text(second, 'before-b')
            before_a, before_b = first.read_bytes(), second.read_bytes()
            gateway = project_registry_gateway()
            real_publish = gateway['publish_bytes']
            calls = []

            def flaky(path, data):
                calls.append(Path(path))
                real_publish(path, data)
                if Path(path) == second:
                    raise _Cancelled('第二个登记写被取消')

            gateway['publish_bytes'] = flaky
            service.gateway = gateway
            service._require_gateway()
            with self.assertRaises(_Cancelled):
                service._write_transaction([(first, b'after-a'), (second, b'after-b')])
            self.assertEqual(first.read_bytes(), before_a)
            self.assertEqual(second.read_bytes(), before_b)


class GlobalLibraryTransactionTests(unittest.TestCase):
    def _library(self, tmp):
        library = Path(tmp) / '素材库'
        (library / '角色').mkdir(parents=True)
        (library / '角色' / 'CHAR_001.png').write_bytes(b'\x89PNG')
        return library

    def _project(self, tmp):
        project = Path(tmp) / '项目'
        (project / '01剧本准备' / 'docs').mkdir(parents=True)
        (project / '01剧本准备' / 'docs' / '脚本.md').write_text('正文', encoding='utf-8')
        return project

    def test_copy_to_project_cancel_rolls_back_copy_manifest_and_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            library, project = self._library(tmp), self._project(tmp)

            def flaky(path, text):
                save_text(path, text)
                raise _Cancelled('来源登记被取消')

            with self.assertRaises(_Cancelled):
                gls.copy_to_project(library, '角色/CHAR_001.png', project, saver=flaky)
            shared = shared_paths(project)['root'] / gls.SHARED_SUB
            self.assertEqual(list(shared.glob('角色/*')), [])
            self.assertFalse((shared / gls.SOURCE_MANIFEST).exists())
            self.assertTrue((library / '角色' / 'CHAR_001.png').is_file())

    def test_copy_to_library_cancel_rolls_back_copy_and_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            library, project = self._library(tmp), self._project(tmp)
            with patch.object(gls.file_index, 'rebuild_global',
                              side_effect=_Cancelled('全局索引重建被取消')):
                with self.assertRaises(_Cancelled):
                    gls.copy_to_library(project, '01剧本准备/docs/脚本.md', library)
            self.assertFalse((library / '01剧本准备/docs/脚本.md').exists())
            self.assertTrue((project / '01剧本准备/docs/脚本.md').is_file())


if __name__ == '__main__':
    unittest.main()

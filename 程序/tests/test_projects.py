# -*- coding: utf-8 -*-
"""项目登记服务的 L3 网关注入边界。"""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import file_cache

from projects import Projects
from stage_execution_service import project_registry_gateway


class ProjectsGatewayTests(unittest.TestCase):
    def test_practice_sample_creates_isolated_ten_shot_project_without_generation(self):
        from contract.episode_contract import validate_episode
        sample = Path(__file__).resolve().parents[1] / '说明' / '示例' / '雨夜修伞'
        episode = json.loads((sample / 'episode.json').read_text(encoding='utf-8'))
        assets = json.loads((sample / 'assets.json').read_text(encoding='utf-8'))
        originals = {name: (sample / name).read_bytes() for name in ('episode.json', 'assets.json')}
        checked = validate_episode(episode, sample, assets)
        self.assertEqual((checked['shot_count'], checked['total_seconds']), (10, 60))
        with tempfile.TemporaryDirectory() as td:
            app = Path(td) / 'app'; app.mkdir()
            (app / 'config.json').write_text(json.dumps({'downloads_root': str(Path(td) / '库')}), encoding='utf-8')
            service = Projects(app, gateway=project_registry_gateway(), migrate_legacy=False)
            result = service.create('练习', sample / 'episode.json')
            self.assertTrue(result.ok, result.reason)
            cfg = json.loads((Path(result.data) / 'config.json').read_text(encoding='utf-8'))
            imported = json.loads(Path(cfg['episode_file']).read_text(encoding='utf-8'))
            self.assertEqual(imported, episode)
            self.assertFalse(cfg['live_enabled'])
            # R3162 M2：新建项目默认云端后端；已有项目的显式取值不受影响。
            self.assertEqual(cfg['video_backend'], 'cloud')
            self.assertNotIn('ffmpeg', cfg)
            self.assertNotIn('ffprobe', cfg)
            from contract.project_stages import assets as asset_dir
            first = Path(result.data)
            imported_assets = asset_dir(first) / 'assets.json'
            self.assertEqual(json.loads(imported_assets.read_text(encoding='utf-8')), assets)
            second_result = service.create('练习', sample / 'episode.json')
            self.assertTrue(second_result.ok, second_result.reason)
            second = Path(second_result.data)
            other_cfg = json.loads((second / 'config.json').read_text(encoding='utf-8'))
            self.assertNotEqual(first, second)
            self.assertNotEqual(cfg['project_id'], other_cfg['project_id'])
            # 编辑练习副本不会污染同名第二份项目或内置教学素材。
            changed_episode = dict(imported, title='我的改稿')
            Path(cfg['episode_file']).write_text(json.dumps(changed_episode), encoding='utf-8')
            imported_assets.write_text('{}', encoding='utf-8')
            self.assertEqual(json.loads(Path(other_cfg['episode_file']).read_text(encoding='utf-8')), episode)
            self.assertEqual(json.loads((asset_dir(second) / 'assets.json').read_text(encoding='utf-8')), assets)
            for name, original in originals.items():
                self.assertEqual((sample / name).read_bytes(), original)
            for root in (first, second):
                self.assertFalse(list(root.rglob('成果确认/*.json')))
                self.assertFalse([p for p in root.rglob('*') if p.suffix.lower() in {'.png', '.mp4', '.wav'}])

    def test_projects_rejects_uninjected_storage_gateway(self):
        with tempfile.TemporaryDirectory() as td:
            app=Path(td) / '程序'
            app.mkdir()
            (app / 'config.json').write_text(
                json.dumps({'downloads_root': str(Path(td) / '库')}, ensure_ascii=False),
                encoding='utf-8',
            )
            (app / 'projects.json').write_text(
                json.dumps({'active': None, 'projects': []}, ensure_ascii=False),
                encoding='utf-8',
            )
            with self.assertRaisesRegex(TypeError, 'L3 注入'):
                Projects(app)

    def test_deferred_legacy_migration_does_not_scan_until_worker_runs(self):
        with tempfile.TemporaryDirectory() as td:
            app=Path(td) / '程序'; old=app / 'episode'
            old.mkdir(parents=True)
            (app / 'config.json').write_text(json.dumps({
                'downloads_root': str(Path(td) / '库'), 'episode_dir': str(old),
            },ensure_ascii=False),encoding='utf-8')
            (old / 'episode.json').write_text(json.dumps({'title':'旧故事'},ensure_ascii=False),encoding='utf-8')
            with patch.object(Path,'rglob',side_effect=AssertionError('首帧不得递归扫描')):
                service=Projects(app,gateway=project_registry_gateway(),migrate_legacy=False)
            self.assertTrue(service.legacy_migration_pending)
            self.assertFalse((app/'projects.json').exists())
            self.assertTrue(service.migrate().ok)
            self.assertFalse(service.legacy_migration_pending)
            self.assertEqual(service.info['projects'][0]['name'],'旧故事')

    def test_empty_registry_gets_required_keys_without_losing_future_fields(self):
        with tempfile.TemporaryDirectory() as td:
            app=Path(td) / '程序'; app.mkdir()
            (app / 'config.json').write_text(json.dumps({
                'downloads_root':str(Path(td) / '库'),
            },ensure_ascii=False),encoding='utf-8')
            (app / 'projects.json').write_text('{}',encoding='utf-8')
            service=Projects(app,gateway=project_registry_gateway(),migrate_legacy=False)
            self.assertEqual(service.info,{'active':None,'projects':[]})

    def test_refresh_empty_registry_gets_required_keys(self):
        with tempfile.TemporaryDirectory() as td:
            app=Path(td) / '程序'; app.mkdir()
            (app / 'config.json').write_text(json.dumps({
                'downloads_root':str(Path(td) / '库'),
            },ensure_ascii=False),encoding='utf-8')
            registry=app / 'projects.json'
            registry.write_text(json.dumps({'active':None,'projects':[]}),encoding='utf-8')
            service=Projects(app,gateway=project_registry_gateway(),migrate_legacy=False)
            registry.write_text('{}',encoding='utf-8')
            self.assertEqual(service.refresh_registry(),{'active':None,'projects':[]})

    def test_create_maps_storage_failure_to_controlled_result(self):
        with tempfile.TemporaryDirectory() as td:
            app=Path(td) / '程序'; app.mkdir()
            (app / 'config.json').write_text(json.dumps({
                'downloads_root':str(Path(td) / '库'),
            },ensure_ascii=False),encoding='utf-8')
            (app / 'projects.json').write_text(json.dumps({'active':None,'projects':[]}),encoding='utf-8')
            gateway=project_registry_gateway()
            gateway['publish_json']=lambda *_args: (_ for _ in ()).throw(PermissionError('locked'))
            result=Projects(app,gateway=gateway,migrate_legacy=False).create('测试项目')
            self.assertFalse(result.ok)
            self.assertIn('项目登记未能保存',result.reason)

    def test_legacy_migration_hashes_through_the_file_cache_layer(self):
        """P2-7／R1651：迁移校验的哈希必须走 file_cache 缓存层，不再直连 agent.core.file_hash。"""
        with tempfile.TemporaryDirectory() as td:
            app=Path(td) / '程序'; old=app / 'episode'
            old.mkdir(parents=True)
            (app / 'config.json').write_text(json.dumps({
                'downloads_root':str(Path(td) / '库'), 'episode_dir':str(old),
            },ensure_ascii=False),encoding='utf-8')
            (old / 'episode.json').write_text(json.dumps({'title':'旧故事'},ensure_ascii=False),encoding='utf-8')
            (app / 'data').mkdir()
            (app / 'data' / 'sample.bin').write_bytes(b'migration-payload')
            service=Projects(app,gateway=project_registry_gateway(),migrate_legacy=False)
            real=file_cache.file_digest
            with patch('projects.file_digest',side_effect=real) as digest:
                self.assertTrue(service.migrate().ok)
            self.assertGreaterEqual(digest.call_count,2,
                                    '迁移校验未经 file_cache.file_digest（源与目标各一次）')

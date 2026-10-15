# -*- coding: utf-8 -*-
"""项目登记服务的 L3 网关注入边界。"""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from projects import Projects
from stage_execution_service import project_registry_gateway


class ProjectsGatewayTests(unittest.TestCase):
    def test_practice_sample_creates_isolated_ten_shot_project_without_generation(self):
        from episode_contract import validate_episode
        sample = Path(__file__).resolve().parents[1] / '说明' / '示例' / '雨夜修伞'
        episode = json.loads((sample / 'episode.json').read_text(encoding='utf-8'))
        assets = json.loads((sample / 'assets.json').read_text(encoding='utf-8'))
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

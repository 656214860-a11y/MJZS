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
            service.migrate()
            self.assertFalse(service.legacy_migration_pending)
            self.assertEqual(service.info['projects'][0]['name'],'旧故事')

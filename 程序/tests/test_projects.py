# -*- coding: utf-8 -*-
"""项目登记服务的 L3 网关注入边界。"""
import json
import tempfile
import unittest
from pathlib import Path

from projects import Projects


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

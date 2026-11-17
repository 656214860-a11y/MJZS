"""JSON 正式路径必须复用缓存读取与原子发布入口。"""
from __future__ import annotations

import unittest
from pathlib import Path

from tests.architecture._layers import LAYERS
from tests.architecture._scan import entity_file, stage_execution_source


ROOT = Path(__file__).resolve().parents[2]


class JsonIoBoundaryTests(unittest.TestCase):
    def test_previs_progress_uses_cache_and_l3_injected_publisher(self):
        """L2 进度轮询不得退回裸读写，正式发布器必须由 L3 注入。"""
        self.assertEqual(LAYERS['previs_progress_service'], 2)
        source = entity_file('previs_progress_service').read_text(encoding='utf-8')
        self.assertIn('from infra.file_cache import read_json', source)
        self.assertIn('data = read_json(path)', source)
        self.assertIn("if not callable(publish_text):", source)
        self.assertIn('publish_text(path, json.dumps(data, ensure_ascii=False))', source)
        self.assertNotIn('from agent.core import', source)
        self.assertNotIn('path.read_text(', source)
        self.assertNotIn('json.dump(', source)

        stage = stage_execution_source()
        facade = entity_file('previs_progress').read_text(encoding='utf-8')
        self.assertIn('def previs_progress_gateway()', stage)
        self.assertIn('def publish_stage_previs_progress(', stage)
        self.assertIn('publish_text=previs_progress_gateway()', stage)
        self.assertIn('publish_stage_previs_progress as publish', facade)

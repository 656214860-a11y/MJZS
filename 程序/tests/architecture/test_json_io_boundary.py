"""JSON 正式路径必须复用缓存读取与原子发布入口。"""
from __future__ import annotations

import unittest
from pathlib import Path

from tests.architecture._layers import LAYERS


ROOT = Path(__file__).resolve().parents[2]


class JsonIoBoundaryTests(unittest.TestCase):
    def test_previs_progress_uses_cache_for_read_and_core_for_write(self):
        """L2 进度轮询不得退回裸 read_text/json.load 或直接落盘。"""
        self.assertEqual(LAYERS['previs_progress_service'], 2)
        source = (ROOT / 'previs_progress_service.py').read_text(encoding='utf-8')
        self.assertIn('from file_cache import read_json', source)
        self.assertIn('from agent.core import save_text', source)
        self.assertIn('data = read_json(path)', source)
        self.assertIn('save_text(path, json.dumps(data, ensure_ascii=False))', source)
        self.assertNotIn('path.read_text(', source)
        self.assertNotIn('json.dump(', source)


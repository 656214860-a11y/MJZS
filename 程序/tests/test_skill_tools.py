# -*- coding: utf-8 -*-
"""SKILL 工具入口的定向回归。"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import line_endings
import skill_tools


class DeliveryManifestTests(unittest.TestCase):
    def test_delivery_manifest_is_valid_json_with_clean_line_endings(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / '交付清单.json'
            result = skill_tools.call('delivery.exportManifest', {
                'project': folder,
                'manifest': target,
                'results': [{'stage': 'delivery', 'ok': True}],
            })
            self.assertEqual(result['manifest'], str(target))
            self.assertEqual(json.loads(target.read_text(encoding='utf-8'))['stage_results'],
                             [{'stage': 'delivery', 'ok': True}])
            self.assertEqual(line_endings.problems(target), [])


if __name__ == '__main__':
    unittest.main()

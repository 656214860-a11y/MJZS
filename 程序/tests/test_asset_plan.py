"""资产清单发布包的失败回滚与落盘复核。"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import asset_plan


class AssetPlanPublicationTests(unittest.TestCase):
    def test_failed_bundle_publication_restores_all_existing_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary) / 'assets' / '资产清单'
            folder.mkdir(parents=True)
            originals = {
                '名称编号对照.json': b'{"old": 1}', 'assets.json': b'{"CHAR_001": {}}',
                '来源.json': b'{"storyboard": "old"}', '导入进度.md': b'# old\n',
            }
            for name, content in originals.items():
                (folder / name).write_bytes(content)
            real_save = asset_plan.save
            calls = 0

            def fail_second_save(path, content):
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise OSError('disk full')
                real_save(path, content)

            with patch.object(asset_plan, 'save', side_effect=fail_second_save):
                with self.assertRaisesRegex(OSError, 'disk full'):
                    asset_plan.publish_plan_bundle(folder, {'CHAR:甲': 'CHAR_001'}, {'CHAR_001': {'name': '甲'}},
                                                  {'storyboard': 'new'}, '# new\n')
            self.assertEqual({name: (folder / name).read_bytes() for name in originals}, originals)

    def test_bundle_publication_writes_and_verifies_all_four_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary) / 'assets' / '资产清单'
            asset_plan.publish_plan_bundle(folder, {'CHAR:甲': 'CHAR_001'}, {'CHAR_001': {'name': '甲'}},
                                          {'storyboard': 'episode.json'}, '# 资产清单\n')
            self.assertEqual(asset_plan.read(folder / 'assets.json'), {'CHAR_001': {'name': '甲'}})
            self.assertEqual((folder / '导入进度.md').read_text(encoding='utf-8'), '# 资产清单\n')

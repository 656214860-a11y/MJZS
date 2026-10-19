"""资产清单发布包的失败回滚与落盘复核。"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import asset_plan


def gateway():
    from agent.core import save, save_bytes, save_text
    from file_cache import remove_temporary_file
    return {'publish_json': save, 'publish_bytes': save_bytes,
            'publish_text': save_text, 'remove_file': remove_temporary_file}


class AssetPlanPublicationTests(unittest.TestCase):
    def test_failed_bundle_publication_restores_all_existing_files(self) -> None:
        """REQ-S05-16：四份发布文件写入失败时整体回滚到发布前的字节。"""
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary) / 'assets' / '资产清单'
            folder.mkdir(parents=True)
            originals = {
                '名称编号对照.json': b'{"old": 1}', 'assets.json': b'{"CHAR_001": {}}',
                '来源.json': b'{"storyboard": "old"}', '导入进度.md': b'# old\n',
            }
            for name, content in originals.items():
                (folder / name).write_bytes(content)
            real_save = gateway()['publish_json']
            calls = 0

            def fail_second_save(path, content):
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise OSError('disk full')
                real_save(path, content)

            failed_gateway = dict(gateway(), publish_json=fail_second_save)
            result = asset_plan.publish_plan_bundle(folder, {'CHAR:甲': 'CHAR_001'}, {'CHAR_001': {'name': '甲'}},
                                                    {'storyboard': 'new'}, '# new\n', gateway=failed_gateway)
            self.assertFalse(result.ok)
            self.assertIn('资产清单未能保存', result.reason)
            self.assertEqual({name: (folder / name).read_bytes() for name in originals}, originals)

    def test_bundle_publication_writes_and_verifies_all_four_files(self) -> None:
        """REQ-S05-16：清单、名称编号对照、来源、导入进度四份文件作为发布包写入并复核。"""
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary) / 'assets' / '资产清单'
            result = asset_plan.publish_plan_bundle(folder, {'CHAR:甲': 'CHAR_001'}, {'CHAR_001': {'name': '甲'}},
                                                    {'storyboard': 'episode.json'}, '# 资产清单\n', gateway=gateway())
            self.assertTrue(result.ok)
            self.assertEqual(asset_plan.read(folder / 'assets.json'), {'CHAR_001': {'name': '甲'}})
            self.assertEqual((folder / '导入进度.md').read_text(encoding='utf-8'), '# 资产清单\n')

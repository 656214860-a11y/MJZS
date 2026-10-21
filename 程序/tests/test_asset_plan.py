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


class AssetPlanRepublishTests(unittest.TestCase):
    """性能：无人值守轮询每个节拍都会重算资产清单；内容没变就不应再落盘（每次 4 个文件 ×fsync×回读）。"""

    ARGS = ({'CHAR:甲': 'CHAR_001'}, {'CHAR_001': {'name': '甲'}}, {'storyboard': 'episode.json'}, '# 资产清单\n')

    def counted_gateway(self):
        counts = {'json': 0, 'text': 0}
        base = gateway()

        def count_json(path, content):
            counts['json'] += 1
            base['publish_json'](path, content)

        def count_text(path, content):
            counts['text'] += 1
            base['publish_text'](path, content)

        return counts, dict(base, publish_json=count_json, publish_text=count_text)

    def test_identical_bundle_is_not_written_again(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary) / 'assets' / '资产清单'
            counts, counted = self.counted_gateway()
            self.assertTrue(asset_plan.publish_plan_bundle(folder, *self.ARGS, gateway=counted).ok)
            self.assertEqual(counts, {'json': 3, 'text': 1}, '首次发布写齐四份')
            stamps = {path.name: path.stat().st_mtime_ns for path in folder.iterdir()}
            self.assertTrue(asset_plan.publish_plan_bundle(folder, *self.ARGS, gateway=counted).ok)
            self.assertEqual(counts, {'json': 3, 'text': 1}, '内容没变：不再写任何文件')
            self.assertEqual({path.name: path.stat().st_mtime_ns for path in folder.iterdir()}, stamps)

    def test_one_changed_file_still_republishes_the_whole_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary) / 'assets' / '资产清单'
            counts, counted = self.counted_gateway()
            asset_plan.publish_plan_bundle(folder, *self.ARGS, gateway=counted)
            mappings, planned, source, progress = self.ARGS
            changed = dict(planned, CHAR_002={'name': '乙'})
            self.assertTrue(asset_plan.publish_plan_bundle(folder, mappings, changed, source, progress, gateway=counted).ok)
            self.assertEqual(counts, {'json': 6, 'text': 2}, '有一份不同：整包重新发布，保持原有的整体回滚语义')
            self.assertEqual(asset_plan.read(folder / 'assets.json'), changed)

    def test_a_partial_or_damaged_bundle_is_rewritten(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary) / 'assets' / '资产清单'
            counts, counted = self.counted_gateway()
            asset_plan.publish_plan_bundle(folder, *self.ARGS, gateway=counted)
            (folder / '来源.json').unlink()
            self.assertTrue(asset_plan.publish_plan_bundle(folder, *self.ARGS, gateway=counted).ok)
            self.assertEqual(counts, {'json': 6, 'text': 2}, '缺一份：补写整包')
            (folder / 'assets.json').write_text('not json', encoding='utf-8')
            self.assertTrue(asset_plan.publish_plan_bundle(folder, *self.ARGS, gateway=counted).ok)
            self.assertEqual(asset_plan.read(folder / 'assets.json'), self.ARGS[1])

# -*- coding: utf-8 -*-
"""存储清理安全自检（路径越界与明确目录范围）。"""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import storage_maintenance as sm


class StorageSafetyTests(unittest.TestCase):
    def test_cleanup_preserves_referenced_history_and_commercial_proof(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / 'project'; history = root / '历史版本'
            history.mkdir(parents=True)
            (root / 'config.json').write_text('{}', encoding='utf-8')
            proof = history / '授权.txt'; proof.write_text('proof', encoding='utf-8')
            (root / 'delivery.commercial.json').write_text(json.dumps({'authorization': {'file': '历史版本/授权.txt'}}), encoding='utf-8')
            with mock.patch.object(sm, 'downloads_root', return_value=Path(td)):
                self.assertEqual(sm.clean_project(root), [])
            self.assertTrue(proof.exists())
            summary = sm.storage_summary(root)
            self.assertGreater(summary['bytes']['protected'], 0)
            self.assertFalse(summary['errors'])

    def test_corrupt_source_manifest_blocks_automatic_cleanup(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / 'project'; history = root / '历史版本'
            history.mkdir(parents=True)
            (root / 'config.json').write_text('{}', encoding='utf-8')
            (history / 'keep.txt').write_text('keep', encoding='utf-8')
            (root / 'assets.json').write_text('{bad', encoding='utf-8')
            with mock.patch.object(sm, 'downloads_root', return_value=Path(td)):
                self.assertEqual(sm.clean_project(root), [])
            self.assertTrue((history / 'keep.txt').exists())
            self.assertTrue(sm.storage_summary(root)['errors'])

    def test_nonfinite_creation_time_cannot_expire(self):
        for created in (float('nan'), float('inf'), float('-inf')):
            with self.subTest(created=created):
                self.assertEqual(sm.version_retention({'state': 'downloaded', 'version': 1, 'created': created}, 'SH001', 2, set(), set(), 1700000000), sm.RETAIN_FRESH)

    def test_adopted_version_file_in_history_is_not_moved(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / 'project'; history = root / '历史版本'
            history.mkdir(parents=True); (root / 'data').mkdir()
            (root / 'config.json').write_text('{}', encoding='utf-8')
            media = history / 'adopted.mp4'; media.write_bytes(b'fixture')
            (root / 'data' / 'state.json').write_text(json.dumps({'shots': {'SH001': [{'version': 1, 'state': 'downloaded', 'review': 'pass', 'file': '历史版本/adopted.mp4'}]}}), encoding='utf-8')
            with mock.patch.object(sm, 'downloads_root', return_value=Path(td)):
                self.assertEqual(sm.clean_project(root), [])
            self.assertTrue(media.exists())

    def test_launch_cleanup_starts_the_detached_cleanup_entry(self):
        """带三秒延后等待的维护只能由独立 --cleanup 进程启动。"""
        with tempfile.TemporaryDirectory() as td:
            program = Path(td)
            commands = []
            with mock.patch.object(sm, 'launch_background',
                                   lambda command, **kwargs: commands.append((command, kwargs))):
                sm.launch_cleanup(program)
        self.assertEqual(commands[0][0], [sys.executable, str(program / 'storage_maintenance.py'), '--cleanup'])
        self.assertIs(commands[0][1]['stdin'], sm.subprocess.DEVNULL)
        self.assertIs(commands[0][1]['stdout'], sm.subprocess.DEVNULL)
        self.assertIs(commands[0][1]['stderr'], sm.subprocess.DEVNULL)

    def test_within(self):
        root = Path(tempfile.mkdtemp())
        self.assertTrue(sm._within(root / "a", root))
        self.assertFalse(sm._within(root.parent / "x", root))

    def test_clean_project_clears_history_keeps_others(self):
        with tempfile.TemporaryDirectory() as td:
            old = sm.downloads_root
            sm.downloads_root = lambda: Path(td)
            try:
                proj = Path(td) / "p"
                (proj / "storyboard" / "历史版本").mkdir(parents=True)
                (proj / "storyboard" / "历史版本" / "old.json").write_text("{}", encoding="utf-8")
                (proj / "storyboard" / "keep").mkdir(parents=True)
                (proj / "storyboard" / "keep" / "x.json").write_text("{}", encoding="utf-8")
                (proj / "config.json").write_text("{}", encoding="utf-8")
                sm.clean_project(proj, now=1_700_000_000)
                self.assertFalse((proj / "storyboard" / "历史版本").exists())
                self.assertTrue((proj / "storyboard" / "keep" / "x.json").is_file())
                self.assertTrue((proj / "config.json").is_file())
                batches = list((proj / "工作流任务" / "回收站").glob("自动维护_*"))
                self.assertEqual(len(batches), 1)
                recycle = batches[0]
                self.assertTrue((recycle / "storyboard" / "历史版本" / "old.json").is_file())
                manifest = json.loads((recycle / "恢复位置.json").read_text(encoding="utf-8"))
                self.assertEqual(manifest["items"][0]["source"], "storyboard/历史版本")
            finally:
                sm.downloads_root = old

    def test_clean_project_ignores_outside_downloads(self):
        with tempfile.TemporaryDirectory() as td:
            old = sm.downloads_root
            sm.downloads_root = lambda: Path(td) / "downloads"
            try:
                outside = Path(td) / "elsewhere" / "p"
                (outside / "历史版本").mkdir(parents=True)
                (outside / "config.json").write_text("{}", encoding="utf-8")
                self.assertEqual(sm.clean_project(outside), [])
                self.assertTrue((outside / "历史版本").exists())
            finally:
                sm.downloads_root = old

    def test_recycle_paths_preserves_source_and_writes_manifest(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); source=root / '01剧本准备' / '剧本.md'
            source.parent.mkdir(parents=True); source.write_text('正文',encoding='utf-8')
            records=sm.recycle_paths(root,[source],'删除项目剧本',now=1_700_000_000)
            self.assertEqual(len(records),1)
            self.assertFalse(source.exists())
            restored=root / records[0]['recycle_path']
            self.assertEqual(restored.read_text(encoding='utf-8'),'正文')
            manifest=restored.parents[1] / '恢复位置.json'
            self.assertEqual(json.loads(manifest.read_text(encoding='utf-8'))['reason'],'删除项目剧本')

    def test_recycle_and_restore_invalidate_both_file_locations(self):
        import file_cache
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); source = root / '01剧本准备' / '剧本.json'
            source.parent.mkdir(parents=True); source.write_text('{"version": 1}', encoding='utf-8')
            file_cache.read_json(source)
            records = sm.recycle_paths(root, [source], '删除项目剧本', now=1_700_000_000)
            recycled_path = root / records[0]['recycle_path']
            self.assertNotIn(file_cache._key(source), file_cache._CACHE)
            file_cache.read_json(recycled_path)
            batch = recycled_path.parents[1]
            sm.restore_recycle_batch(root, batch)
            self.assertNotIn(file_cache._key(recycled_path), file_cache._CACHE)


    def test_clear_generated_workflow_state_only_removes_exact_internal_state(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            workflows = root / "workflows"
            workflows.mkdir()
            state = workflows / "资产续跑台账.json"
            state.write_text("{}", encoding="utf-8")
            other = root / "保留文件.json"
            other.write_text("keep", encoding="utf-8")

            self.assertTrue(sm.clear_generated_workflow_state(
                root, state, "资产续跑台账.json"
            ))
            self.assertFalse(state.exists())
            self.assertFalse(sm.clear_generated_workflow_state(
                root, other, "资产续跑台账.json"
            ))
            self.assertEqual(other.read_text(encoding="utf-8"), "keep")


class DownloadsRootTests(unittest.TestCase):
    def test_reads_config(self):
        with tempfile.TemporaryDirectory() as td:
            old_program = sm.PROGRAM
            sm.PROGRAM = Path(td)
            try:
                (Path(td) / "config.json").write_text(
                    json.dumps({"downloads_root": str(Path(td) / "dl")}), encoding="utf-8"
                )
                self.assertEqual(sm.downloads_root(), Path(td) / "dl" / "项目")
            finally:
                sm.PROGRAM = old_program

    def test_fallback_default(self):
        with tempfile.TemporaryDirectory() as td:
            old_program = sm.PROGRAM
            sm.PROGRAM = Path(td)
            try:
                self.assertEqual(sm.downloads_root(), Path("D:/漫剧下载") / "项目")
            finally:
                sm.PROGRAM = old_program

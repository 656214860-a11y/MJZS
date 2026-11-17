# -*- coding: utf-8 -*-
"""存储清理安全自检（路径越界与明确目录范围）。"""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import infra.storage_maintenance as sm


class StorageSafetyTests(unittest.TestCase):
    def test_retained_version_protects_transitive_sources_but_expired_one_recycles(self):
        from agent.core import save
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / 'project'; root.mkdir()
            save(root / 'config.json', {})
            history = root / '历史版本'; history.mkdir()
            original = history / 'original.png'; original.write_bytes(b'original')
            frame = root / 'frame.png'; frame.write_bytes(b'frame')
            receipt = frame.with_name(frame.name + '.source.json')
            save(receipt, {'source': str(original), 'imported_file': frame.name})
            rows = []
            for number in (1, 2):
                folder = root / 'data' / 'SH001' / f'v{number:03}'
                folder.mkdir(parents=True)
                video = folder / 'video.mp4'; video.write_bytes(b'video')
                save(folder / 'assets_manifest.json', {'first_frame': {'path': str(frame)}})
                rows.append({'version': number, 'created': 1, 'state': 'downloaded',
                             'file': video.relative_to(root).as_posix()})
            save(root / 'data' / 'state.json', {'shots': {'SH001': rows}})
            protected, errors = sm.source_protection(root, 1700000000)
            self.assertFalse(errors)
            self.assertTrue({original, frame, receipt, folder / 'assets_manifest.json'} <= protected)
            self.assertNotIn(root / 'data/SH001/v001/assets_manifest.json', protected)
            with mock.patch.object(sm, 'downloads_root', return_value=Path(td)):
                sm.clean_project(root, 1700000000)
            self.assertTrue(original.exists())
            self.assertTrue(receipt.exists())
            self.assertFalse((root / rows[0]['file']).exists())
            self.assertTrue((root / rows[1]['file']).exists())

    def test_corrupt_retained_source_receipt_blocks_cleanup(self):
        from agent.core import save
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            media = root / 'adopted.mp4'; media.write_bytes(b'video')
            save(root / 'assets.json', {'file': str(media)})
            media.with_name(media.name + '.source.json').write_text('{bad', encoding='utf-8')
            self.assertTrue(sm.source_protection(root)[1])

    def test_policy_version_accounting_and_recoverable_cleanup(self):
        from agent.core import save, file_hash
        from engine import adopted_edit_version
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / 'project'; root.mkdir()
            save(root / 'config.json', {})
            now = 1700000000
            rows = []
            for number, content in ((1, b'old'), (2, b'adopted')):
                path = root / 'data' / 'S01' / f'v{number:03}' / 'video.mp4'
                path.parent.mkdir(parents=True); path.write_bytes(content)
                rows.append({'version': number, 'state': 'downloaded', 'created': now - 10 * 86400,
                             'review': 'pass' if number == 2 else 'reject', 'qc_pass': True,
                             'file': path.relative_to(root).as_posix(), 'sha256': file_hash(path)})
            save(root / 'data' / 'state.json', {'shots': {'S01': rows}})
            save(root / 'storage_policy.json', {'retention_days': 30})
            summary = sm.storage_summary(root, now, adopted_edit_version)
            self.assertFalse(summary['errors'])
            self.assertEqual((summary['adopted_bytes'], summary['other_version_bytes'], summary['recyclable_bytes']), (7, 3, 0))
            with mock.patch.object(sm, 'downloads_root', return_value=Path(td)):
                self.assertEqual(sm.clean_project(root, now), [])
                save(root / 'storage_policy.json', {'retention_days': 7})
                summary = sm.storage_summary(root, now, adopted_edit_version)
                self.assertEqual(summary['recyclable_bytes'], 3)
                self.assertEqual(summary['immediately_released_bytes'], 0)
                self.assertTrue(sm.clean_project(root, now))
            self.assertTrue((root / rows[1]['file']).exists())
            self.assertFalse((root / rows[0]['file']).exists())
            batch = next(sm.recycle_base(root).iterdir())
            sm.restore_recycle_batch(root, batch)
            self.assertEqual((root / rows[0]['file']).read_bytes(), b'old')

    def test_invalid_retention_policy_blocks_cleanup(self):
        from agent.core import save
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / 'project'; history = root / '历史版本'
            history.mkdir(parents=True); (history / 'keep.txt').write_text('keep')
            save(root / 'config.json', {})
            for days in (0, -1, 3651, True, '7', None):
                save(root / 'storage_policy.json', {'retention_days': days})
                with mock.patch.object(sm, 'downloads_root', return_value=Path(td)):
                    self.assertEqual(sm.clean_project(root), [])
                self.assertIsNone(sm.storage_summary(root)['recyclable_bytes'])
                self.assertTrue((history / 'keep.txt').exists())

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
        import infra.file_cache as file_cache
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


class SourceDeclarationErrorTests(unittest.TestCase):
    """读坏或形状不对的来源声明都要报成错误（从而阻断自动清理），不能当作「没有引用」。"""

    def _errors(self, files):
        from agent.core import save
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            for name, data in files.items():
                (root / name).parent.mkdir(parents=True, exist_ok=True)
                if isinstance(data, str):
                    (root / name).write_text(data, encoding='utf-8')
                else:
                    save(root / name, data)
            return sm.source_protection(root, 1700000000)[1]

    def test_each_malformed_declaration_is_reported(self):
        exports = '13质检交付/导出成片/'
        cases = {
            '来源声明不是对象或清单': {'assets.json': 5},
            '生成版本编号无效': {'data/state.json': {'shots': {'S1': [{'version': '1', 'state': 'downloaded'}]}}},
            '成片来源清单缺失': {exports + 'edit_bundle.json': {'manifest': 'none'}},
            '成片来源条目无法确认': {exports + 'edit_bundle.json': {'manifest': [{'version': 1}]}},
            '来源旁证不是对象': {'clip.mp4': 'v', 'clip.mp4.source.json': '[]', 'assets.json': {'file': 'clip.mp4'}},
        }
        for reason, files in cases.items():
            with self.subTest(reason):
                errors = self._errors(files)
                self.assertTrue(any(reason in error for error in errors), errors)

    def test_edit_sources_skip_unreadable_manifests_and_keep_digest_of_unnumbered_rows(self):
        from agent.core import save
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            folder = root / '13质检交付' / '导出成片'
            (folder / 'a').mkdir(parents=True)
            (folder / 'a' / 'edit_bundle.json').write_text('{bad', encoding='utf-8')
            save(folder / 'edit_manifest.json', {'manifest': [{'shot': 'S1', 'version': 'x', 'sha256': 'ab'},
                                                              {'shot': 'S2', 'version': 3}]})
            self.assertEqual(sm.edit_source_versions(root), ({('S2', 3)}, {('S1', 'ab')}))


class StorageSummaryVersionTests(unittest.TestCase):
    def test_cleaned_versions_recycle_ledgers_and_referenced_folders(self):
        from agent.core import save
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / 'project'; root.mkdir()
            now = 1700000000
            rows = []
            for number in (1, 2, 3):
                folder = root / 'data' / 'S1' / f'v{number:03}'
                folder.mkdir(parents=True); (folder / 'video.mp4').write_bytes(b'v' * number)
                rows.append({'version': number, 'state': 'downloaded', 'created': now - 30 * 86400})
            rows[0]['cleaned_at'] = now   # 已清理过的版本不再盘点
            save(root / 'data' / 'state.json', {'shots': {'S1': rows}})
            save(root / 'assets.json', {'file': 'data/S1/v002/video.mp4'})   # 过期旧版仍被资产引用
            stale = sm.recycle_base(root) / 'batch' / 'data'
            stale.mkdir(parents=True)
            save(stale / 'state.json', {'shots': {'S9': [{'version': 1, 'state': 'downloaded', 'created': 0}]}})
            summary = sm.storage_summary(root, now)
            self.assertFalse(summary['errors'])
            self.assertEqual([(v['shot'], v['version'], v['reason'], v['candidate']) for v in summary['versions']],
                             [('S1', 2, '来源或授权资料仍被引用', False), ('S1', 3, sm.RETAIN_REASONS[sm.RETAIN_LATEST], False)])
            self.assertEqual(summary['recyclable_bytes'], 0)


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

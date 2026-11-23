"""Expired generation receipts must preserve recovery and duplicate-submission guards."""
import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from asset_generated_import_service import cleanup_batches


class AssetBatchRetentionTests(unittest.TestCase):
    def record(self, folder, name, data, age=8):
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / name
        path.write_text(json.dumps(data), encoding='utf-8')
        stamp = time.time() - age * 86400
        os.utime(path, (stamp, stamp))
        return path

    def test_repeated_cleanup_preserves_unsettled_receipts_and_guard(self):
        from seedream_api import unsettled
        with tempfile.TemporaryDirectory() as td:
            folder = Path(td)
            originals = {}
            for root in (folder, folder / 'seedream'):
                for state in ('uncertain', 'sending', 'submitting', 'unknown',
                              'queued', 'running', 'completed', 'import_pending'):
                    path = self.record(root, f'seedream_{state}.json',
                                       {'state': state, 'id': 'remote-original'})
                    originals[path] = path.read_bytes()
            for _ in range(3):
                cleanup_batches(folder)
                for path, original in originals.items():
                    self.assertTrue(path.is_file(), path.name)
                    self.assertEqual(path.read_bytes(), original)
                self.assertEqual(unsettled(folder / 'seedream', ['uncertain', 'sending']),
                                 ['uncertain', 'sending'])

    def test_failed_receipt_is_recoverable_and_recent_failure_is_retained(self):
        from infra.storage_maintenance import recycle_base, read_recycle_batch
        with tempfile.TemporaryDirectory() as td:
            folder = Path(td)
            failed = self.record(folder, 'failed.json', {'state': 'failed', 'id': 'remote-old'})
            original = failed.read_bytes()
            recent = self.record(folder, 'recent.json', {'state': 'failed'}, age=1)
            cleanup_batches(folder)
            self.assertFalse(failed.exists())
            self.assertTrue(recent.exists())
            manifests = list(recycle_base(folder).glob('*/恢复位置.json'))
            self.assertEqual(len(manifests), 1)
            rows = read_recycle_batch(folder, manifests[0].parent)['items']
            self.assertEqual([row['source'] for row in rows], ['failed.json'])
            self.assertEqual((folder / rows[0]['recycle_path']).read_bytes(), original)
            cleanup_batches(folder)
            self.assertEqual(read_recycle_batch(folder, manifests[0].parent)['items'], rows)

    def test_restart_queries_original_remote_success_without_resubmitting(self):
        import native_assets
        asset = {'name': '角色', 'image_prompt': '一只猫', '_reference_signature': 'same'}
        with tempfile.TemporaryDirectory() as td:
            project = Path(td)
            base = project / 'episode'
            record = self.record(project / 'workflows/Comfy资产批次', 'original.json',
                                 {'id': 'remote-original', 'state': 'uncertain',
                                  'assets': {'CHAR_001': asset}, 'imported': [],
                                  'request': {'options': {'model': native_assets.LOCAL}}})
            requests = []
            def request(path, *args, **kwargs):
                requests.append(path)
                if path == '/drama/assets/health':
                    return {'options': {'model': native_assets.LOCAL}}
                if path == '/drama/assets/job/remote-original':
                    return {'state': 'completed', 'files': []}
                raise AssertionError('unexpected submission: ' + path)
            with patch('native_apps.wait_comfy'), patch('native_assets.Comfy') as client, \
                    patch('asset_batch_service.image_ready', return_value=False), \
                    patch('asset_prompt_rules.issues', return_value=[]), \
                    patch('asset_reference_images.snapshot', return_value=asset):
                client.return_value.request.side_effect = request
                cleanup_batches(record.parent)
                cleanup_batches(record.parent)
                native_assets.run(project, base, [('CHAR_001', asset)], 'http://127.0.0.1:8189', lambda _: None)
            self.assertEqual(requests, ['/drama/assets/health', '/drama/assets/job/remote-original'])
            self.assertEqual(json.loads(record.read_text(encoding='utf-8'))['state'], 'completed')

    def test_manual_resolution_remains_auditable_after_expiry(self):
        from seedream_api import release, unsettled
        from infra.storage_maintenance import recycle_base
        with tempfile.TemporaryDirectory() as td:
            folder = Path(td)
            record = self.record(folder / 'seedream', 'seedream_CHAR_001.json',
                                 {'state': 'uncertain', 'id': 'remote-old', 'aid': 'CHAR_001'})
            cleanup_batches(folder)
            self.assertEqual(release(record.parent, ['CHAR_001']), ['CHAR_001'])
            self.assertEqual(unsettled(record.parent, ['CHAR_001']), [])
            stamp = time.time() - 8 * 86400
            os.utime(record, (stamp, stamp))
            cleanup_batches(folder)
            archived = list(recycle_base(folder).glob('*/seedream/seedream_CHAR_001.json'))
            self.assertEqual(len(archived), 1)
            data = json.loads(archived[0].read_text(encoding='utf-8'))
            self.assertEqual(data['id'], 'remote-old')
            self.assertEqual(data['state'], 'failed')
            self.assertIn('已在火山控制台核实', data['note'])

    def test_recycle_failure_surfaces_without_falling_back_to_deletion(self):
        with tempfile.TemporaryDirectory() as td:
            folder = Path(td)
            record = self.record(folder, 'failed.json', {'state': 'failed'})
            with patch('storage_maintenance.recycle_paths', side_effect=OSError('disk failure')):
                with self.assertRaisesRegex(OSError, 'disk failure'):
                    cleanup_batches(folder)
            self.assertTrue(record.is_file())

    def test_failed_register_image_removes_autoimport_temp(self):
        import asset_batch_service
        from agent.core import save_bytes
        from asset_context import generated_dir
        from asset_generated_import_service import import_pending_generated, pending_generated_files
        from tests.image_fixtures import png
        with tempfile.TemporaryDirectory() as td:
            project = Path(td) / 'project'
            base = project / 'episode'
            plan = base / 'assets/资产清单/assets.json'
            plan.parent.mkdir(parents=True)
            plan.write_text(json.dumps({'CHAR_001': {'name': '角色', 'image_prompt': 'x'}},
                                       ensure_ascii=False), encoding='utf-8')
            source = generated_dir(base) / 'CHAR_001_seedream_fail.png'
            source.write_bytes(png())
            reports = []
            with patch.object(asset_batch_service, 'register_image', side_effect=OSError('登记失败')):
                done = import_pending_generated(project, base, reports.append,
                                                gateway={'publish_bytes': save_bytes})
            self.assertEqual(done, [])
            self.assertFalse((source.parent / 'CHAR_001_autoimport.png').exists())
            self.assertEqual(len(reports), 1)
            self.assertIn('自动导入未完成', reports[0])
            self.assertEqual([path.name for _folder, path, _aid in pending_generated_files(project, base)],
                             ['CHAR_001_seedream_fail.png'])


if __name__ == '__main__':
    unittest.main()

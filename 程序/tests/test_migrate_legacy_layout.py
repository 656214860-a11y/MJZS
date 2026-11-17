# -*- coding: utf-8 -*-
"""P4 safety regressions. Every fixture is a disposable temporary project."""
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import contract.stage_layout as stage_layout
from agent.core import save, file_hash
from orchestrator import legacy_migration as migration

SOURCE = 'writing/创意_20260101/大纲.md'
TARGET = '01剧本准备/docs/创意_20260101/大纲.md'
FRAME = 'episode/frames/EP001_SH001.png'
NEW_FRAME = '08首帧管理/assets/EP001_SH001.png'


def put(root, relative, content=b'original'):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def project(tmp):
    root = Path(tmp) / '项目'
    put(root, SOURCE, '大纲正文'.encode())
    put(root, FRAME, b'\x89PNG')
    return root


def snapshot(root):
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob('*') if p.is_file()}


def active_snapshot(root):
    return {key: value for key, value in snapshot(root).items()
            if '迁移备份' not in Path(key).parts and '回收站' not in Path(key).parts}


def media_fixture(root, *, source=SOURCE, reviewed=True):
    from stage_completion_service import media_manifest_path
    scope = {'project': str(root), 'source': source,
             'source_sha256': file_hash(root / source), 'episode': 'EP001'}
    path = media_manifest_path(root, 'audio', scope)
    save(path, {'schema': 1, 'stage': 'audio', 'scope': scope,
                'status': 'complete' if reviewed else 'pending_review', 'reviewed': reviewed,
                'outputs': [{'path': FRAME, 'sha256': file_hash(root / FRAME)}]})
    return path, scope


class PlanTests(unittest.TestCase):
    def test_preserves_subtree_and_same_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = project(tmp)
            put(root, 'writing/另一版/大纲.md', b'another')
            ops = {op['source']: op for op in migration.plan(root)}
            self.assertEqual(ops[SOURCE]['target'], TARGET)
            self.assertEqual(ops['writing/另一版/大纲.md']['target'], '01剧本准备/docs/另一版/大纲.md')
            self.assertEqual(ops[FRAME]['target'], NEW_FRAME)

    def test_plan_and_dry_run_are_read_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = project(tmp)
            before = snapshot(root)
            paths = sorted(str(p) for p in root.rglob('*'))
            migration.apply(root, migration.plan(root), dry_run=True)
            self.assertEqual(snapshot(root), before)
            self.assertEqual(sorted(str(p) for p in root.rglob('*')), paths)

    def test_dry_run_avoids_storage_read_gate_side_effects(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = project(tmp)
            save(root / 'ui_settings.json', {'frame_json': FRAME})
            before = snapshot(root)
            with patch('file_cache.read_json', side_effect=AssertionError('write-capable reader')):
                migration.apply(root, migration.plan(root), dry_run=True)
            self.assertEqual(snapshot(root), before)

    def test_existing_different_target_blocks_whole_batch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = project(tmp)
            put(root, TARGET, b'different')
            before = snapshot(root)
            with self.assertRaisesRegex(ValueError, '冲突'):
                migration.plan(root)
            self.assertEqual(snapshot(root), before)

    def test_existing_identical_target_is_skipped_and_source_recycled(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = project(tmp)
            put(root, TARGET, (root / SOURCE).read_bytes())
            ops = migration.plan(root)
            self.assertEqual(next(op for op in ops if op['source'] == SOURCE)['action'], 'skip')
            migration.apply(root, ops)
            self.assertFalse((root / SOURCE).exists())
            self.assertEqual((root / TARGET).read_bytes(), '大纲正文'.encode())

    def test_duplicate_legacy_rows_are_deduplicated(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = project(tmp)
            row = ('00_script', 'writing', '')
            with patch.object(stage_layout, 'LEGACY', (row, row)):
                self.assertEqual(len(migration.plan(root)), 1)

    def test_ambiguous_source_requires_explicit_or_authoritative_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = project(tmp)
            old = 'storyboard/分镜拆分/EP001.json'
            put(root, old, b'{"shots": [1]}')
            with self.assertRaisesRegex(ValueError, '归属不明'):
                migration.plan(root)
            target = '07分镜定稿/output/EP001.json'
            ops = migration.plan(root, {old: target})
            self.assertEqual(next(op['target'] for op in ops if op['source'] == old), target)
            put(root, target, (root / old).read_bytes())
            ops = migration.plan(root)
            self.assertEqual(next(op['target'] for op in ops if op['source'] == old), target)

    def test_multiple_authoritative_targets_still_block(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = project(tmp)
            old = 'storyboard/分镜拆分/a.json'
            put(root, old, b'{}')
            put(root, '03初步分镜/output/a.json', b'{}')
            put(root, '07分镜定稿/output/a.json', b'{}')
            with self.assertRaisesRegex(ValueError, '归属不明'):
                migration.plan(root)

    def test_casefold_target_collision_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = project(tmp)
            put(root, 'episode/audio/A.wav')
            put(root, 'episode/subtitles/a.wav')
            with self.assertRaisesRegex(ValueError, '碰撞'):
                migration.plan(root)

    def test_traversal_and_unknown_alias_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = project(tmp)
            for row in [('00_script', '../escape', ''), ('unknown', 'writing', '')]:
                with self.subTest(row=row), patch.object(stage_layout, 'LEGACY', (row,)):
                    with self.assertRaises(ValueError):
                        migration.plan(root)

    def test_injected_incomplete_and_outside_plans_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = project(tmp)
            ops = migration.plan(root)
            before = snapshot(root)
            with self.assertRaises(ValueError):
                migration.apply(root, ops[:1])
            ops[0]['target'] = '../escape'
            with self.assertRaises(ValueError):
                migration.apply(root, ops)
            self.assertEqual(snapshot(root), before)

    def test_junction_rejected_without_traversal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = project(tmp)
            outside = Path(tmp) / 'outside'
            outside.mkdir()
            put(outside, 'secret.txt', b'private')
            link = root / 'writing' / 'linked'
            if os.name == 'nt':
                result = subprocess.run(['cmd', '/c', 'mklink', '/J', str(link), str(outside)],
                                        capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
            else:
                link.symlink_to(outside, target_is_directory=True)
            before = (outside / 'secret.txt').read_bytes()
            with self.assertRaisesRegex(ValueError, 'symlink/junction'):
                migration.plan(root)
            self.assertEqual((outside / 'secret.txt').read_bytes(), before)


class TransactionTests(unittest.TestCase):
    def test_complete_backup_uuid_report_and_repeat(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = project(tmp)
            put(root, 'unrelated/keep.bin', b'keep')
            put(root, '_archive/history.bin', b'history')
            put(root, '工作流任务/回收站/old.bin', b'trash')
            put(root, '工作流任务/迁移备份/old/old.bin', b'old backup')
            before = active_snapshot(root)
            done, stamp = migration.apply(root, migration.plan(root))
            self.assertEqual(len(stamp.rsplit('_', 1)[1]), 32)
            batch = stage_layout.workflow_dir(root, migration.BACKUP_DIR_NAME, stamp)
            self.assertEqual(snapshot(batch / 'files'), before)
            self.assertTrue((batch / migration.REPORT_NAME).is_file())
            self.assertEqual(json.loads((batch / 'journal.json').read_text(encoding='utf-8'))['state'], 'committed')
            self.assertEqual((root / TARGET).read_bytes(), before[SOURCE])
            self.assertFalse((root / SOURCE).exists())
            self.assertEqual(migration.plan(root), [])
            self.assertEqual(migration.apply(root, []), ([], ''))
            self.assertEqual(len(done), 2)

    def test_rollback_restores_exact_original_bytes_and_is_repeatable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = project(tmp)
            save(root / 'ui_settings.json', {'frame_json': FRAME})
            before = active_snapshot(root)
            _, stamp = migration.apply(root, migration.plan(root))
            migration.rollback(root, stamp)
            self.assertEqual(active_snapshot(root), before)
            migration.rollback(root, stamp)
            self.assertEqual(active_snapshot(root), before)
            migration.apply(root, migration.plan(root))
            self.assertFalse((root / SOURCE).exists())

    def test_publish_failure_rolls_back_and_survives_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = project(tmp)
            save(root / 'ui_settings.json', {'frame_json': FRAME})
            before = active_snapshot(root)
            from agent.core import save_text
            def fail(path, text, *args, **kwargs):
                if Path(path) == root / 'ui_settings.json':
                    raise OSError('injected write failure')
                return save_text(path, text, *args, **kwargs)
            with patch('agent.core.save_text', side_effect=fail):
                with self.assertRaisesRegex(ValueError, '已回滚'):
                    migration.apply(root, migration.plan(root))
            self.assertEqual(active_snapshot(root), before)
            journals = list(root.rglob('journal.json'))
            self.assertEqual(len(journals), 1)
            self.assertEqual(json.loads(journals[0].read_text(encoding='utf-8'))['state'], 'rolled_back')

    def test_recycle_failure_rolls_back_after_writes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = project(tmp)
            before = active_snapshot(root)
            from infra.storage_maintenance import recycle_paths
            calls = []
            def fail_once(*args, **kwargs):
                calls.append(True)
                if len(calls) == 1:
                    raise OSError('recycle failure')
                return recycle_paths(*args, **kwargs)
            with patch('storage_maintenance.recycle_paths', side_effect=fail_once):
                with self.assertRaisesRegex(ValueError, '已回滚'):
                    migration.apply(root, migration.plan(root))
            self.assertEqual(active_snapshot(root), before)

    def test_backup_failure_does_not_modify_originals(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = project(tmp)
            before = active_snapshot(root)
            from agent.core import save_file
            def fail(path, *args, **kwargs):
                if 'files' in Path(path).parts:
                    raise OSError('backup failed')
                return save_file(path, *args, **kwargs)
            with patch('agent.core.save_file', side_effect=fail):
                with self.assertRaises(OSError):
                    migration.apply(root, migration.plan(root))
            self.assertEqual(active_snapshot(root), before)

    def test_interrupted_journal_blocks_apply_and_can_recover(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = project(tmp)
            before = active_snapshot(root)
            def interrupt(*args):
                raise KeyboardInterrupt('process interrupted')
            with patch.object(migration, '_publish', side_effect=interrupt):
                with self.assertRaises(KeyboardInterrupt):
                    migration.apply(root, migration.plan(root))
            journal = next(root.rglob('journal.json'))
            stamp = journal.parent.name
            with self.assertRaisesRegex(ValueError, '未完成事务'):
                migration.apply(root, migration.plan(root))
            migration.rollback(root, stamp)
            self.assertEqual(active_snapshot(root), before)

    def test_rollback_refuses_changed_target_and_corrupt_backup(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = project(tmp)
            _, stamp = migration.apply(root, migration.plan(root))
            put(root, TARGET, b'user changed')
            with self.assertRaisesRegex(ValueError, '回滚冲突'):
                migration.rollback(root, stamp)
            self.assertEqual((root / TARGET).read_bytes(), b'user changed')
            put(root, TARGET, '大纲正文'.encode())
            batch = stage_layout.workflow_dir(root, migration.BACKUP_DIR_NAME, stamp)
            put(batch / 'files', SOURCE, b'corrupt')
            with self.assertRaisesRegex(ValueError, '备份损坏'):
                migration.rollback(root, stamp)


class ReferenceTests(unittest.TestCase):
    def test_scope_outputs_ui_assets_and_confirmation_are_repointed_atomically(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = project(tmp)
            old, scope = media_fixture(root)
            save(root / 'ui_settings.json', {'frame_json': SOURCE, 'adopted_storyboards': [SOURCE]})
            asset = root / '10视频生成/assets/assets_manifest.json'
            save(asset, {'assets': [{'path': str(root / FRAME)}], 'mode': 'local'})
            migration.apply(root, migration.plan(root))
            from stage_completion_service import media_manifest_path
            new = media_manifest_path(root, 'audio', dict(scope, source=TARGET))
            data = json.loads(new.read_text(encoding='utf-8'))
            self.assertFalse(old.exists())
            self.assertEqual(data['scope']['source'], TARGET)
            self.assertEqual(data['scope']['source_sha256'], file_hash(root / TARGET))
            self.assertEqual(data['outputs'][0], {'path': NEW_FRAME, 'sha256': file_hash(root / NEW_FRAME)})
            self.assertTrue(data['reviewed'])
            self.assertEqual(data['status'], 'complete')
            ui = json.loads((root / 'ui_settings.json').read_text(encoding='utf-8'))
            self.assertEqual(ui, {'frame_json': TARGET, 'adopted_storyboards': [TARGET]})
            self.assertEqual(json.loads(asset.read_text(encoding='utf-8'))['assets'][0]['path'], NEW_FRAME)

    def test_media_output_manifest_file_hash_is_recomputed_without_promoting_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = project(tmp)
            save(root / '11配音与字幕/output/voice.json', {'tracks': [{'file': FRAME,
                 'sha256': file_hash(root / FRAME)}]})
            media = root / '11配音与字幕/output/audio_manifest.json'
            save(media, {'files': [{'path': '11配音与字幕/output/voice.json',
                 'sha256': file_hash(root / '11配音与字幕/output/voice.json')}]})
            migration.apply(root, migration.plan(root))
            voice = json.loads((root / '11配音与字幕/output/voice.json').read_text(encoding='utf-8'))
            self.assertEqual(voice['tracks'][0]['file'], NEW_FRAME)
            data = json.loads(media.read_text(encoding='utf-8'))
            self.assertEqual(data['files'][0]['sha256'], file_hash(root / data['files'][0]['path']))
            self.assertNotIn('reviewed', data)

    def test_confirmation_filename_references_are_cascaded(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = project(tmp)
            old, scope = media_fixture(root)
            save(root / 'ui_settings.json', {'manifest_path': old.relative_to(root).as_posix()})
            migration.apply(root, migration.plan(root))
            from stage_completion_service import media_manifest_path
            new = media_manifest_path(root, 'audio', dict(scope, source=TARGET))
            data = json.loads((root / 'ui_settings.json').read_text(encoding='utf-8'))
            self.assertEqual(data['manifest_path'], new.relative_to(root).as_posix())
            self.assertTrue(new.is_file())
            self.assertFalse(old.exists())

    def test_pending_confirmation_is_never_promoted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = project(tmp)
            _, scope = media_fixture(root, reviewed=False)
            migration.apply(root, migration.plan(root))
            from stage_completion_service import media_manifest_path
            data = json.loads(media_manifest_path(root, 'audio', dict(scope, source=TARGET)).read_text(encoding='utf-8'))
            self.assertFalse(data['reviewed'])
            self.assertEqual(data['status'], 'pending_review')

    def test_rewritten_source_hash_updates_and_review_is_invalidated(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = project(tmp)
            source = 'writing/source.json'
            save(root / source, {'shots': [{'image_path': FRAME}]})
            _, scope = media_fixture(root, source=source)
            original_sha = file_hash(root / source)
            migration.apply(root, migration.plan(root))
            target = '01剧本准备/output/source.json'
            from stage_completion_service import media_manifest_path
            data = json.loads(media_manifest_path(root, 'audio', dict(scope, source=target)).read_text(encoding='utf-8'))
            self.assertNotEqual(file_hash(root / target), original_sha)
            self.assertEqual(data['scope']['source_sha256'], file_hash(root / target))
            self.assertFalse(data['reviewed'])
            self.assertEqual(data['status'], 'pending_review')

    def test_stale_confirmation_hash_blocks_instead_of_repairing_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = project(tmp)
            old, _ = media_fixture(root)
            data = json.loads(old.read_text(encoding='utf-8'))
            data['outputs'][0]['sha256'] = 'stale'
            save(old, data)
            before = snapshot(root)
            with self.assertRaisesRegex(ValueError, '指纹不匹配'):
                migration.apply(root, migration.plan(root))
            self.assertEqual(snapshot(root), before)

    def test_unknown_reference_or_malformed_json_blocks_before_backup(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = project(tmp)
            save(root / 'custom.json', {'mystery': FRAME})
            before = snapshot(root)
            with self.assertRaisesRegex(ValueError, '未知引用字段'):
                migration.apply(root, migration.plan(root))
            self.assertEqual(snapshot(root), before)
            put(root, 'custom.json', b'{broken')
            before = snapshot(root)
            with self.assertRaisesRegex(ValueError, 'JSON 无法解析'):
                migration.apply(root, migration.plan(root))
            self.assertEqual(snapshot(root), before)

    def test_external_or_traversal_reference_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = project(tmp)
            for value in ['../outside.png', str(Path(tmp) / 'outside.png')]:
                save(root / 'ui_settings.json', {'frame_json': value})
                before = snapshot(root)
                with self.assertRaises(ValueError):
                    migration.apply(root, migration.plan(root))
                self.assertEqual(snapshot(root), before)

    def test_confirmation_rename_collision_blocks_before_backup(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = project(tmp)
            _, scope = media_fixture(root)
            from stage_completion_service import media_manifest_path
            save(media_manifest_path(root, 'audio', dict(scope, source=TARGET)), {'different': True})
            before = snapshot(root)
            with self.assertRaisesRegex(ValueError, '目标已存在'):
                migration.apply(root, migration.plan(root))
            self.assertEqual(snapshot(root), before)


class CliTests(unittest.TestCase):
    def run_cli(self, *args):
        script = Path(__file__).resolve().parents[1] / 'scripts/migrate_legacy_layout.py'
        return subprocess.run([sys.executable, '-B', str(script), *args],
                              capture_output=True, text=True, encoding='utf-8', errors='replace')

    def test_dry_run_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = project(tmp)
            before = snapshot(root)
            done = self.run_cli('--project', str(root), '--dry-run')
            self.assertEqual(done.returncode, 0, done.stderr)
            self.assertEqual(snapshot(root), before)

    def test_real_run_and_cli_rollback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = project(tmp)
            before = active_snapshot(root)
            done = self.run_cli('--project', str(root))
            self.assertEqual(done.returncode, 0, done.stderr)
            self.assertTrue((root / TARGET).is_file())
            stamp = next(root.rglob('journal.json')).parent.name
            done = self.run_cli('--project', str(root), '--rollback', stamp)
            self.assertEqual(done.returncode, 0, done.stderr)
            self.assertEqual(active_snapshot(root), before)

    def test_conflict_and_malformed_json_fail_nonzero(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = project(tmp)
            put(root, TARGET, b'different')
            done = self.run_cli('--project', str(root))
            self.assertNotEqual(done.returncode, 0)
            self.assertTrue((root / SOURCE).exists())
            put(root, TARGET, (root / SOURCE).read_bytes())
            put(root, 'bad.json', b'bad')
            self.assertNotEqual(self.run_cli('--project', str(root), '--dry-run').returncode, 0)

    def test_missing_project_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            done = self.run_cli('--project', str(Path(tmp) / '不存在'))
            self.assertEqual(done.returncode, 2)


if __name__ == '__main__':
    unittest.main()

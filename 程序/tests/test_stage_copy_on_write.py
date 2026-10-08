"""R1124: historical directories remain byte-for-byte read-only."""
from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import patch

from asset_context import library_dir
from stage_execution_service import prepare_asset_write, prepare_stage_write
from stage_path_service import write_dir


class StageCopyOnWriteTests(unittest.TestCase):
    def test_new_readme_scaffold_does_not_hide_old_assets(self):
        from stage_path_service import existing_dir
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            current = write_dir(root, 'assets')
            current.mkdir()
            (current / 'README.md').write_text('stage contract', encoding='utf-8')
            old = root / '04资产管理'
            old.mkdir()
            (old / 'assets.json').write_text('{}', encoding='utf-8')
            self.assertEqual(existing_dir(root, 'assets'), old)

    def test_legacy_numbered_mutation_paths_are_rebased(self):
        from stage_execution_service import prepare_legacy_stage_path
        from stage_path_service import LEGACY_NUMBERED
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            for stage, name in LEGACY_NUMBERED.items():
                with self.subTest(stage=stage):
                    old = root / name / 'batch/episode.json'
                    old.parent.mkdir(parents=True)
                    old.write_bytes(b'original')
                    current = prepare_legacy_stage_path(old)
                    self.assertEqual(current, write_dir(root, stage) / 'batch/episode.json')
                    current.write_bytes(b'edited')
                    self.assertEqual(old.read_bytes(), b'original')
            ordinary = root / 'custom/episode.json'
            self.assertEqual(prepare_legacy_stage_path(ordinary), ordinary)
            self.assertIsNone(prepare_legacy_stage_path(None))

    def test_asset_edit_gateway_modifies_copy_not_legacy_plan(self):
        from stage_execution_service import update_asset_plan_fields
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            old = root / '04资产管理'
            plan = old / 'assets/资产清单/assets.json'
            plan.parent.mkdir(parents=True)
            original = json.dumps({'CHAR_001': {'name': '旧名'}}, ensure_ascii=False).encode('utf-8')
            plan.write_bytes(original)
            update_asset_plan_fields(root, old, 'CHAR_001', {'name': '新名'})
            current = write_dir(root, 'assets') / plan.relative_to(old)
            self.assertEqual(json.loads(current.read_bytes())['CHAR_001']['name'], '新名')
            self.assertEqual(plan.read_bytes(), original)

    def test_old_continuity_read_new_confirmation_write(self):
        import confirm_gates
        import continuity_ledger
        from agent.core import save
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            old = root / '05连贯性清单/output'
            old.mkdir(parents=True)
            ledger = old / continuity_ledger.LEDGER_NAME
            ledger.write_text('{"version": 1}', encoding='utf-8')
            confirmed = old / confirm_gates.CONFIRM_NAME
            original = '{"confirmed": {"old": {"choice": "yes", "by": "human"}}}'
            confirmed.write_text(original, encoding='utf-8')
            self.assertEqual(continuity_ledger.read(root), {'version': 1})
            self.assertIn('old', confirm_gates.confirmations(root))
            confirm_gates.record(root, 'new', 'yes', publish=save)
            self.assertEqual(confirmed.read_text(encoding='utf-8'), original)
            self.assertEqual(set(confirm_gates.confirmations(root)), {'old', 'new'})

    def test_browse_does_not_copy_then_modify_current_only(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            old = root / '04资产管理'
            old.mkdir()
            (old / 'assets.json').write_bytes(b'{"CHAR_001": {}}')
            self.assertEqual(library_dir(root), old)
            self.assertFalse(write_dir(root, 'assets').exists())
            current = prepare_asset_write(root)
            self.assertEqual(current, write_dir(root, 'assets'))
            self.assertEqual(library_dir(root), current)
            (current / 'assets.json').write_bytes(b'{}')
            self.assertEqual((old / 'assets.json').read_bytes(), b'{"CHAR_001": {}}')
            self.assertEqual(prepare_asset_write(root), current)
            self.assertEqual((current / 'assets.json').read_bytes(), b'{}')

    def test_existing_current_content_wins_and_old_is_unchanged(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            old = root / '04资产管理'
            current = write_dir(root, 'assets')
            old.mkdir(); current.mkdir()
            (old / 'assets.json').write_bytes(b'old')
            (old / 'reference.png').write_bytes(b'image')
            (current / 'assets.json').write_bytes(b'new')
            prepare_stage_write(root, 'assets', source=old)
            self.assertEqual((current / 'assets.json').read_bytes(), b'new')
            self.assertEqual((current / 'reference.png').read_bytes(), b'image')
            self.assertEqual((old / 'assets.json').read_bytes(), b'old')

    def test_copy_failure_does_not_publish_or_touch_old(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            old = root / '04资产管理'
            old.mkdir(); (old / 'assets.json').write_bytes(b'old')
            with patch('shutil.copy2', side_effect=OSError('disk full')):
                with self.assertRaises(OSError):
                    prepare_asset_write(root)
            self.assertFalse(write_dir(root, 'assets').exists())
            self.assertEqual((old / 'assets.json').read_bytes(), b'old')
            self.assertEqual(list(root.glob('.stage-copy-*')), [])

    def test_directory_switch_failure_restores_current(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            old = root / '04资产管理'; old.mkdir()
            (old / 'assets.json').write_bytes(b'old')
            current = write_dir(root, 'assets'); current.mkdir()
            (current / 'note.md').write_bytes(b'keep')
            replace = Path.replace
            def fail_prepared(path, target):
                if path.name == 'prepared':
                    raise OSError('switch failed')
                return replace(path, target)
            with patch.object(Path, 'replace', fail_prepared):
                with self.assertRaises(OSError):
                    prepare_stage_write(root, 'assets', source=old)
            self.assertEqual((current / 'note.md').read_bytes(), b'keep')
            self.assertFalse((current / 'assets.json').exists())
            self.assertEqual((old / 'assets.json').read_bytes(), b'old')

    def test_external_source_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            with self.assertRaises(ValueError):
                prepare_stage_write(root, 'assets', source=root.parent)


if __name__ == '__main__':
    unittest.main()

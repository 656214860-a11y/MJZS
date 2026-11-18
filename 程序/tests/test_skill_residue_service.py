"""残留包通道：隔离目录中验证发现、边界与真实回收恢复。"""
import dataclasses
import tempfile
import unittest
from pathlib import Path

from contract.service_contract import ServiceResult, SystemError, UserError
from infra.file_cache import read_json
from infra.storage_maintenance import recycle_paths, restore_recycle_batch
from orchestrator.skill_project_layer import stage_from_path
from orchestrator.skill_registry import Registry, default_registry
from domain.skill_residue_service import scan_residue, dispose_residue


class SkillResidueTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.program = Path(self.temp.name)
        self.root = self.program / 'skills'
        self.package = self.root / '00全流程SKILL' / 'AIGC创作全流程'
        self.package.mkdir(parents=True)
        (self.package / 'README.md').write_text('总包说明', encoding='utf-8')
        self.normal = self.root / '01剧本准备' / 'normal'
        self.normal.mkdir(parents=True)
        (self.normal / 'SKILL.md').write_text('normal', encoding='utf-8')
        self.kwargs = dict(stage_from_path=stage_from_path, package_source=Registry._package_source)

    def scan(self):
        return scan_residue(self.program, **self.kwargs)

    def dispose(self, name):
        return dispose_residue(self.program, name, publisher=recycle_paths, **self.kwargs)

    def test_scan_packages_separately_and_keep_stage_registry_clean(self):
        other = self.root / 'imagegen'
        other.mkdir()
        (other / 'SKILL.md').write_text('imagegen', encoding='utf-8')
        rows = self.scan()
        self.assertEqual([r['name'] for r in rows], ['AIGC创作全流程', 'imagegen'])
        self.assertTrue(all(r['kind'] == 'package' for r in rows))
        self.assertEqual(rows[0]['path'], str(self.package))
        self.assertEqual(rows[0]['description'], 'README.md')
        self.assertTrue(all('01剧本准备' not in r['path'] for r in rows))
        self.assertNotIn('AIGC创作全流程', [s.name for s in default_registry(self.program).getAll()])

    def test_real_recycle_receipt_and_restore_whole_package(self):
        nested = self.package / 'nested' / 'SKILL.md'
        nested.parent.mkdir()
        nested.write_text('保留内容', encoding='utf-8')
        result = self.dispose('AIGC创作全流程')
        self.assertIsInstance(result, ServiceResult)
        self.assertEqual(set(dataclasses.asdict(result)), {'ok', 'reason', 'recoverable', 'data'})
        self.assertTrue(result.ok, result.reason)
        self.assertFalse(self.package.exists())
        self.assertTrue(self.normal.exists())
        records = result.data['records']
        self.assertEqual(records[0]['status'], 'moved')
        self.assertEqual(Path(records[0]['source']).as_posix(), 'skills/00全流程SKILL/AIGC创作全流程')
        manifests = list(self.program.rglob('恢复位置.json'))
        self.assertEqual(len(manifests), 1)
        receipt = read_json(manifests[0])
        self.assertEqual(receipt['state'], 'committed')
        self.assertEqual(receipt['items'], records)
        self.assertTrue(receipt['reason'])
        restore_recycle_batch(self.program, manifests[0].parent)
        self.assertEqual(nested.read_text(encoding='utf-8'), '保留内容')

    def test_missing_empty_outside_and_stage_targets_are_user_errors(self):
        for name in ('', '不存在', '../outside', str(self.normal), '01剧本准备', '00全流程SKILL'):
            with self.subTest(name=name):
                result = self.dispose(name)
                self.assertIsInstance(result, UserError)
                self.assertFalse(result.ok)
                self.assertEqual(set(dataclasses.asdict(result)), {'ok', 'reason', 'recoverable', 'data'})
                self.assertTrue(self.package.exists())
                self.assertTrue(self.normal.exists())

    def test_size_and_sub_skill_count_do_not_follow_links(self):
        nested = self.package / 'child'
        nested.mkdir()
        (nested / 'SKILL.md').write_bytes(b'abc')
        (nested / 'extra.skill.md').write_bytes(b'xyz')
        linked = self.package / 'linked'
        linked.mkdir()
        (linked / 'SKILL.md').write_bytes(b'ignored')
        from unittest import mock
        original = Path.is_symlink
        with mock.patch.object(Path, 'is_symlink', lambda p: p == linked or original(p)):
            row = self.scan()[0]
        self.assertEqual(row['sub_skill_count'], 2)
        self.assertEqual(row['size'], len('总包说明'.encode('utf-8')) + 6)

    def test_multiple_targets_recycle_and_invalid_selection_is_atomic(self):
        other = self.root / 'imagegen'
        other.mkdir()
        result = self.dispose(['AIGC创作全流程', '不存在'])
        self.assertIsInstance(result, UserError)
        self.assertTrue(self.package.exists())
        result = self.dispose(['AIGC创作全流程', 'imagegen'])
        self.assertTrue(result.ok, result.reason)
        self.assertEqual(len(result.data['records']), 2)
        self.assertFalse(self.package.exists())
        self.assertFalse(other.exists())
        self.assertIsInstance(self.dispose([]), UserError)

    def test_publisher_is_injected_and_receives_only_revalidated_package(self):
        calls = []
        def publish(root, paths, reason):
            calls.append((root, paths, reason))
            return recycle_paths(root, paths, reason)
        result = dispose_residue(self.program, 'AIGC创作全流程', publisher=publish, **self.kwargs)
        self.assertTrue(result.ok)
        self.assertEqual(calls[0][0], self.program.resolve())
        self.assertEqual(calls[0][1], [self.package])

    def test_publisher_errors_return_typed_four_field_results(self):
        from unittest import mock
        for error, kind in ((OSError('占用'), SystemError), (ValueError('拒绝路径'), UserError)):
            result = dispose_residue(self.program, ['AIGC创作全流程'],
                                     publisher=mock.Mock(side_effect=error), **self.kwargs)
            self.assertIsInstance(result, kind)
            self.assertEqual(set(dataclasses.asdict(result)), {'ok', 'reason', 'recoverable', 'data'})
            self.assertTrue(self.package.exists())
        result = dispose_residue(self.program, ['AIGC创作全流程'],
                                 publisher=lambda *args: [], **self.kwargs)
        self.assertIsInstance(result, UserError)

    def test_all_stage_folders_and_empty_root_remain_safe(self):
        from orchestrator.skill_project_layer import STAGE_DIRECTORY_IDS
        for number in STAGE_DIRECTORY_IDS:
            folder = self.root / (number + '阶段')
            folder.mkdir(exist_ok=True)
            (folder / 'SKILL.md').write_text('normal', encoding='utf-8')
        self.assertEqual([row['name'] for row in self.scan()], ['AIGC创作全流程'])
        self.assertEqual(scan_residue(self.program / 'missing', **self.kwargs), [])

    def test_real_junction_cannot_escape_skills_root(self):
        import subprocess
        outside = self.program / 'outside'
        outside.mkdir()
        marker = outside / 'SKILL.md'
        marker.write_text('outside content', encoding='utf-8')
        junction = self.root / 'escape'
        completed = subprocess.run(['cmd', '/c', 'mklink', '/J', str(junction), str(outside)],
                                   capture_output=True, check=False)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.addCleanup(lambda: junction.rmdir() if junction.is_junction() else None)
        self.assertNotIn('escape', [row['name'] for row in self.scan()])
        self.assertIsInstance(self.dispose('escape'), UserError)
        self.assertEqual(marker.read_text(encoding='utf-8'), 'outside content')

    def test_symlink_and_junction_targets_are_not_disposable(self):
        from unittest import mock
        original = Path.is_symlink
        with mock.patch.object(Path, 'is_symlink', lambda p: p == self.package or original(p)):
            self.assertEqual(self.scan(), [])
            self.assertIsInstance(self.dispose('AIGC创作全流程'), UserError)
        with mock.patch.object(Path, 'is_junction', lambda p: p == self.root):
            self.assertEqual(self.scan(), [])
            self.assertIsInstance(self.dispose('AIGC创作全流程'), UserError)
        self.assertTrue(self.package.exists())


if __name__ == '__main__':
    unittest.main()

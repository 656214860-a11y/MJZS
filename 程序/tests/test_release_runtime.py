"""A15：发布解释器只能携带 requirements.txt 的精确闭包。"""
import tempfile
import unittest
from pathlib import Path

from scripts import release_runtime


def write_dist(root: Path, name: str, version: str, module: str):
    site = root / release_runtime.SITE
    info = site / f'{name.replace("-", "_")}-{version}.dist-info'
    package = site / module
    info.mkdir(parents=True)
    package.mkdir(parents=True)
    (package / '__init__.py').write_text('', encoding='utf-8')
    (info / 'METADATA').write_text(
        f'Metadata-Version: 2.1\nName: {name}\nVersion: {version}\n', encoding='utf-8')
    (info / 'RECORD').write_text(
        f'{module}/__init__.py,,\n{info.name}/METADATA,,\n{info.name}/RECORD,,\n',
        encoding='utf-8')


class ReleaseRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.program = self.root / '程序'
        self.program.mkdir()
        self.addCleanup(self.temp.cleanup)

    def test_plan_keeps_locked_distribution_and_prunes_unknown(self):
        (self.program / 'requirements.txt').write_text('requests==2.34.2\n', encoding='utf-8')
        write_dist(self.root, 'requests', '2.34.2', 'requests')
        write_dist(self.root, 'pydantic', '2.14.3', 'pydantic')
        report = release_runtime.plan(self.root, self.program)
        self.assertEqual(report['missing'], [])
        self.assertEqual(report['version_mismatches'], [])
        self.assertEqual(report['removed_distributions'], ['pydantic'])
        self.assertTrue(all('pydantic' in path for path in report['remove_files']))
        self.assertFalse(any('/requests' in path for path in report['remove_files']))

    def test_validate_requires_exact_closed_inventory(self):
        (self.program / 'requirements.txt').write_text('requests==2.34.2\n', encoding='utf-8')
        write_dist(self.root, 'requests', 'wrong', 'requests')
        verdict = release_runtime.validate(self.root, self.program)
        self.assertFalse(verdict['ok'])
        self.assertEqual(verdict['version_mismatches'], ['requests: wrong（预期 2.34.2）'])

    def test_plan_does_not_remove_a_file_owned_by_an_allowed_distribution(self):
        (self.program / 'requirements.txt').write_text('requests==2.34.2\n', encoding='utf-8')
        write_dist(self.root, 'requests', '2.34.2', 'requests')
        write_dist(self.root, 'unknown', '1.0', 'unknown')
        site = self.root / release_runtime.SITE
        shared = 'shared_namespace.py'
        (site / shared).write_text('', encoding='utf-8')
        for record in (site / 'requests-2.34.2.dist-info/RECORD',
                       site / 'unknown-1.0.dist-info/RECORD'):
            record.write_text(record.read_text(encoding='utf-8') + f'{shared},,\n', encoding='utf-8')
        report = release_runtime.plan(self.root, self.program)
        self.assertNotIn((release_runtime.SITE / shared).as_posix(), report['remove_files'])

    def test_plan_rejects_unknown_distribution_without_record(self):
        (self.program / 'requirements.txt').write_text('requests==2.34.2\n', encoding='utf-8')
        write_dist(self.root, 'requests', '2.34.2', 'requests')
        info = self.root / release_runtime.SITE / 'unknown-1.0.dist-info'
        info.mkdir(parents=True)
        (info / 'METADATA').write_text(
            'Metadata-Version: 2.1\nName: unknown\nVersion: 1.0\n', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, '缺少 RECORD'):
            release_runtime.plan(self.root, self.program)

    def test_inventory_rejects_record_outside_site_packages(self):
        (self.program / 'requirements.txt').write_text('requests==2.34.2\n', encoding='utf-8')
        write_dist(self.root, 'requests', '2.34.2', 'requests')
        record = self.root / release_runtime.SITE / 'requests-2.34.2.dist-info/RECORD'
        record.write_text(record.read_text(encoding='utf-8') + '../../../../程序/requirements.txt,,\n',
                          encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'RECORD 越出运行时根目录'):
            release_runtime.inventory(self.root)


if __name__ == '__main__':
    unittest.main()

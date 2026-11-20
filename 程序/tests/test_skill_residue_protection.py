"""残留包管理通道不得列出或回收程序自己按路径读取的资源目录。"""
import tempfile
import unittest
from pathlib import Path

from contract.script_brief import RHYTHM_TEMPLATE_PATH
from contract.service_contract import UserError
from orchestrator import skill_project_layer, skill_templates
from orchestrator.skill_project_layer import PRODUCT_RESOURCE_DIRECTORIES
from orchestrator.skill_registry import Registry


class ResidueProtectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.program = Path(self.temp.name)
        self.root = self.program / 'skills'
        self.package = self.root / 'AIGC创作全流程'
        self.package.mkdir(parents=True)
        (self.package / 'README.md').write_text('总包说明', encoding='utf-8')
        self.templates = self.root / 'templates'
        self.templates.mkdir()
        (self.templates / 'script_process_template.yaml').write_text('name: x', encoding='utf-8')

    def scan(self):
        rows = skill_project_layer.scan_residue(self.program, package_source=Registry._package_source)
        return [row['name'] for row in rows]

    def dispose(self, names):
        return skill_project_layer.dispose_residue(
            self.program, names, package_source=Registry._package_source)

    def test_templates_directory_is_not_listed(self):
        self.assertEqual(self.scan(), ['AIGC创作全流程'])

    def test_templates_directory_cannot_be_disposed(self):
        self.assertIsInstance(self.dispose('templates'), UserError)
        self.assertTrue((self.templates / 'script_process_template.yaml').is_file())
        self.assertEqual(list(self.program.rglob('恢复位置.json')), [])

    def test_batch_containing_templates_is_rejected_whole(self):
        self.assertIsInstance(self.dispose(['AIGC创作全流程', 'templates']), UserError)
        self.assertTrue(self.package.is_dir())
        self.assertTrue(self.templates.is_dir())

    def test_name_case_does_not_bypass_protection(self):
        self.templates.rename(self.root / 'Templates')
        self.assertEqual(self.scan(), ['AIGC创作全流程'])
        self.assertIsInstance(self.dispose('Templates'), UserError)
        self.assertTrue((self.root / 'Templates').is_dir())

    def test_other_packages_remain_disposable(self):
        result = self.dispose('AIGC创作全流程')
        self.assertTrue(result.ok, result.reason)
        self.assertFalse(self.package.exists())
        self.assertTrue(self.templates.is_dir())


class ProductResourceDirectoryTests(unittest.TestCase):
    def test_protected_set_covers_every_directory_read_by_path(self):
        self.assertIn(skill_templates.template_root().name.casefold(), PRODUCT_RESOURCE_DIRECTORIES)
        parts = Path(RHYTHM_TEMPLATE_PATH).parts
        self.assertEqual(parts[0], 'skills')
        self.assertIn(parts[1].casefold(), PRODUCT_RESOURCE_DIRECTORIES)

    def test_bundled_templates_are_not_listed_in_real_program(self):
        root = skill_templates.template_root()
        self.assertTrue(root.is_dir(), '随程序分发的阶段模板目录缺失：%s' % root)
        rows = skill_project_layer.scan_residue(root.parents[1], package_source=Registry._package_source)
        self.assertNotIn(root.name, [row['name'] for row in rows])


if __name__ == '__main__':
    unittest.main()

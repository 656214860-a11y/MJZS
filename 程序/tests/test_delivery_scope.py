"""REQ-S13-01/04/11/24/26/28/32/50/51/53：质检与交付阶段的依赖、范围、声明与登记事实。"""
import unittest
from pathlib import Path

import pet_bus
import script_contract
import skill_tools
import stage_completion_service
import stage_flow
import stage_layout
import stage_parallel
import workflow_settings
from delivery_import_service import ALLOWED_SUFFIXES

ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / 'skills' / '13质检交付SKILL'
SKILLS = ('pipeline-delivery', 'qa-overall-check', 'qa-style-consistency',
          'qa-compliance-check', 'delivery-report-generate', 'delivery-archive')


class DeliveryScopeTests(unittest.TestCase):
    def test_req_s13_01_delivery_depends_on_edit(self):
        self.assertEqual(stage_flow.DEPENDS['delivery'], ('edit',))
        self.assertEqual(pet_bus.STAGE_NAMES['delivery'], '质检与交付')

    def test_req_s13_04_delivery_collects_no_locks(self):
        self.assertNotIn('delivery', script_contract.STAGE_LOCK_REQUIREMENTS)

    def test_req_s13_11_import_accepts_only_mp4_and_mov(self):
        self.assertEqual(ALLOWED_SUFFIXES, frozenset({'.mp4', '.mov'}))

    def test_req_s13_24_declared_outputs_are_not_checked_by_completion(self):
        row = next(item for item in stage_layout.STAGES if item[1] == 'delivery')
        self.assertEqual(row[0], '13质检交付')
        self.assertEqual(row[4], ('edits.json',))
        self.assertEqual(row[5], ('qc_report.json', 'delivery.json'))
        source = (ROOT / 'stage_completion_service.py').read_text(encoding='utf-8')
        for name in ('qc_report', 'delivery.json', 'delivery_manifest'):
            with self.subTest(name=name):
                self.assertNotIn(name, source)

    def test_req_s13_26_import_and_completion_suffixes_differ(self):
        _folders, suffixes = stage_completion_service.media_output_folders(ROOT, 'delivery')
        self.assertEqual(suffixes, {'.mp4', '.mov', '.mkv'})
        self.assertTrue(set(ALLOWED_SUFFIXES) < suffixes)

    def test_req_s13_28_commercial_status_has_no_reader(self):
        for path in ROOT.glob('*.py'):
            if path.name == 'stage_completion_service.py':
                continue
            with self.subTest(module=path.name):
                self.assertNotIn('commercial_status', path.read_text(encoding='utf-8', errors='replace'))

    def test_req_s13_32_commercial_categories_are_the_seven_kinds(self):
        self.assertEqual(stage_completion_service.COMMERCIAL_CATEGORIES,
                         ('script', 'reference', 'image', 'video', 'music', 'font', 'voice'))

    def test_req_s13_50_six_skills_exist_and_pipeline_is_default(self):
        for name in SKILLS:
            with self.subTest(skill=name):
                self.assertTrue((SKILL_DIR / (name + '.skill.md')).is_file())
        preset = workflow_settings.BUILTIN_WORKFLOW_PRESETS['AIGC全流程']
        self.assertEqual(preset['stage_skills']['delivery'], ['pipeline-delivery'])

    def test_req_s13_51_parallel_config_runs_independent_checks(self):
        config = stage_parallel.CONFIG['delivery']
        self.assertEqual((config['min'], config['max'], config['serial']), (2, 4, False))
        self.assertEqual(config['retry']['attempts'], 2)
        self.assertEqual(config['retry']['on_exhaust'], stage_parallel.ON_REPORT)

    def test_req_s13_53_tool_registration_split(self):
        for tool in ('qa.visualCheck', 'qa.audioCheck', 'qa.subtitleCheck',
                     'delivery.generateReport', 'delivery.exportManifest'):
            with self.subTest(tool=tool):
                self.assertIn(tool, skill_tools.READY)
        for tool in ('qa.styleCheck', 'qa.complianceCheck', 'delivery.archive',
                     'delivery.validate', 'delivery.package'):
            with self.subTest(tool=tool):
                self.assertIn(tool, skill_tools.PAGES)
                self.assertNotIn(tool, skill_tools.READY)


if __name__ == '__main__':
    unittest.main()

"""REQ-S13-01/04/11/24/25/26/28/32/50/51/52/53：质检与交付阶段的依赖、范围、声明与登记事实。"""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pet_bus
import script_contract
import skill_tools
import stage_completion_service
import stage_config
import stage_flow
import stage_layout
import stage_parallel
import workflow_settings
from agent.core import file_hash, read, save
from tests.architecture._scan import entity_file
from domain.delivery_import_service import ALLOWED_SUFFIXES

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

    def test_req_s13_11_import_accepts_mp4_mov_and_mkv(self):
        self.assertEqual(ALLOWED_SUFFIXES, frozenset({'.mp4', '.mov', '.mkv'}))

    def test_req_s13_24_declared_outputs_are_written_by_completion(self):
        row = next(item for item in stage_layout.STAGES if item[1] == 'delivery')
        self.assertEqual(row[0], '13质检交付')
        self.assertEqual(row[4], ('edits.json',))
        self.assertEqual(row[5], ('qc_report.json', 'delivery.json'))
        source = Path(stage_completion_service.__file__).read_text(encoding='utf-8')
        for name in ('qc_report', 'delivery.json', 'delivery_manifest'):
            with self.subTest(name=name):
                self.assertIn(name, source)

    def test_req_s13_26_import_and_completion_suffixes_are_one_set(self):
        _folders, suffixes = stage_completion_service.media_output_folders(ROOT, 'delivery')
        self.assertEqual(suffixes, {'.mp4', '.mov', '.mkv'})
        self.assertEqual(set(ALLOWED_SUFFIXES), suffixes)

    def test_req_s13_28_commercial_status_is_shown_on_delivery_page(self):
        source = entity_file('desktop_media_pages').read_text(encoding='utf-8')
        self.assertIn('commercial_status', source)

    def test_req_s13_32_commercial_categories_are_the_seven_kinds(self):
        self.assertEqual(stage_completion_service.COMMERCIAL_CATEGORIES,
                         ('script', 'reference', 'image', 'video', 'music', 'font', 'voice'))

    def test_req_s13_50_six_skills_exist_and_pipeline_is_default(self):
        for name in SKILLS:
            with self.subTest(skill=name):
                self.assertTrue((SKILL_DIR / (name + '.skill.md')).is_file())
        self.assertIn('pipeline-delivery', stage_config.default_entry('delivery')['skills'])

    def test_req_s13_51_parallel_config_runs_independent_checks(self):
        config = stage_parallel.CONFIG['delivery']
        self.assertEqual((config['min'], config['max'], config['serial']), (2, 4, False))
        self.assertEqual(config['retry']['attempts'], 2)
        self.assertEqual(config['retry']['on_exhaust'], stage_parallel.ON_REPORT)

    def test_req_s13_53_tool_registration_split(self):
        for tool in ('qa.visualCheck', 'qa.audioCheck', 'qa.subtitleCheck',
                     'delivery.generateReport', 'delivery.exportManifest',
                     'delivery.validate', 'delivery.package'):
            with self.subTest(tool=tool):
                self.assertIn(tool, skill_tools.READY)
        for tool in ('qa.styleCheck', 'qa.complianceCheck', 'delivery.archive'):
            with self.subTest(tool=tool):
                self.assertIn(tool, skill_tools.PAGES)
                self.assertNotIn(tool, skill_tools.READY)


class DeliveryQcTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        source = self.root / 'storyboard' / 'episode.json'
        save(source, {'id': 'EP01', 'shots': [{'id': 'S01'}]})
        save(self.root / 'ui_settings.json', {'frame_json': str(source), 'adopted_storyboards': [str(source)]})
        save(self.root / 'config.json', {'ffprobe': 'test-probe'})

    def master(self, bundle=None, streams=None):
        folder = stage_completion_service.media_output_folders(self.root, 'delivery')[0][0]
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / 'MASTER.mp4'
        path.write_bytes(b'fixture-media')
        if bundle is not None:
            data = {'master': path.name, 'master_sha256': file_hash(path)}
            data.update(bundle)
            save(folder / 'edit_bundle.json', data)
        self.streams = streams or [{'codec_type': 'video', 'width': 1280, 'height': 720},
                                   {'codec_type': 'audio'}]
        return path

    def prepare(self, path):
        result = {'format': {'duration': '2.5'}, 'streams': self.streams}
        with patch('agent.media.probe', return_value=result):
            return stage_completion_service.prepare_media_completion(self.root, 'delivery', [path])

    def test_req_s13_25_qc_passes_clean_bundle_and_warns_on_soft_gaps(self):
        prepared = self.prepare(self.master({'qc': {'errors': []}, 'coverage': {'skipped': ['S02']}},
                                            [{'codec_type': 'video', 'width': 1280, 'height': 720}]))
        qc = prepared['qc']
        self.assertTrue(qc['passed'])
        self.assertTrue(any('没有音轨' in item for item in qc['warnings']))
        self.assertTrue(any('跳过' in item for item in qc['warnings']))
        self.assertEqual(qc['bound'], [prepared['outputs'][0]['sha256']])

    def test_req_s13_25_external_master_without_bundle_is_warning_not_error(self):
        qc = self.prepare(self.master())['qc']
        self.assertTrue(qc['passed'])
        self.assertTrue(any('外部导入' in item for item in qc['warnings']))

    def test_req_s13_25_failed_edit_qc_blocks_confirmation(self):
        prepared = self.prepare(self.master({'qc': {'errors': ['画面尺寸与规格不符']}}))
        self.assertFalse(prepared['qc']['passed'])
        with self.assertRaisesRegex(ValueError, '质检未通过'):
            stage_completion_service.confirm_media_completion(self.root, 'delivery', prepared)
        self.assertFalse(stage_completion_service.completion_evidence(self.root, 'delivery')[0])

    def test_req_s13_25_bundle_not_matching_master_is_qc_error(self):
        path = self.master({'master_sha256': 'deadbeef'})
        self.assertFalse(self.prepare(path)['qc']['passed'])

    def test_req_s13_24_confirmation_writes_declared_artifacts(self):
        prepared = self.prepare(self.master({'qc': {'errors': []}}))
        stage_completion_service.confirm_media_completion(self.root, 'delivery', prepared)
        from contract.stage_path_service import write_dir
        folder = write_dir(self.root, 'delivery')
        for name in ('qc_report.json', 'delivery.json', 'delivery_manifest.json'):
            with self.subTest(name=name):
                self.assertTrue((folder / name).is_file())
        manifest = read(folder / 'delivery_manifest.json')
        for row in manifest['files']:
            self.assertEqual(file_hash(self.root / row['path']), row['sha256'])
        self.assertTrue(read(folder / 'delivery.json')['qc_passed'])
        report = stage_completion_service.publish_delivery_report(self.root)
        self.assertIn('质检：通过', report.read_text(encoding='utf-8'))
        self.assertEqual(len(stage_completion_service.package_delivery(self.root)), 4)

    def test_req_s13_53_validate_and_package_tools_need_confirmed_delivery(self):
        context = {'project': str(self.root)}
        self.assertFalse(skill_tools.call('delivery.validate', context)['ok'])
        self.assertFalse(skill_tools.call('delivery.package', context)['ok'])
        prepared = self.prepare(self.master({'qc': {'errors': []}}))
        stage_completion_service.confirm_media_completion(self.root, 'delivery', prepared)
        self.assertTrue(skill_tools.call('delivery.validate', context)['ok'])
        self.assertTrue(skill_tools.call('delivery.package', context)['ok'])

    def test_req_s13_28_commercial_status_states(self):
        self.assertEqual(stage_completion_service.commercial_status(self.root)[0], 'none')
        prepared = self.prepare(self.master({'qc': {'errors': []}}))
        stage_completion_service.confirm_media_completion(self.root, 'delivery', prepared)
        self.assertEqual(stage_completion_service.commercial_status(self.root)[0], 'pending')

    def test_req_s13_52_legacy_confirmation_without_qc_needs_reconfirmation(self):
        prepared = self.prepare(self.master({'qc': {'errors': []}}))
        target = stage_completion_service.confirm_media_completion(self.root, 'delivery', prepared)
        data = read(target)
        data.pop('qc')
        save(target, data)
        self.assertFalse(stage_completion_service.completion_evidence(self.root, 'delivery')[0])


if __name__ == '__main__':
    unittest.main()

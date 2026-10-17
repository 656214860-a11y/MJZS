"""REQ-S12-01/02/03/20/23/25/26/30/31/32：后期剪辑阶段的依赖、采用版本、产物位置、完成证据与 SKILL 工具边界。"""
import tempfile
import unittest
from pathlib import Path

import engine
import pet_bus
import project_stages
import skill_tools
import stage_completion_service
import stage_flow
import stage_layout
import stage_parallel
import workflow_settings

ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / 'skills' / '12后期剪辑SKILL'


def version(number, **extra):
    row = {'version': number, 'state': 'downloaded', 'qc_pass': True, 'review': 'pass'}
    row.update(extra)
    return row


class EditingScopeTests(unittest.TestCase):
    def test_req_s12_01_edit_is_stage_12_between_video_and_delivery(self):
        self.assertEqual(pet_bus.STAGES.index('edit') + 1, 12)
        self.assertEqual(pet_bus.STAGE_NAMES['edit'], '后期剪辑')
        self.assertEqual(stage_flow.DEPENDS['edit'], ('video',))
        self.assertEqual(stage_flow.DEPENDS['delivery'], ('edit',))

    def test_req_s12_02_pinned_approved_version_wins_otherwise_last_approved(self):
        pinned = [version(1, pinned=True), version(2)]
        self.assertEqual(engine.adopted_edit_version(pinned)[0]['version'], 1)
        plain = [version(1), version(2), version(3, review='pending')]
        self.assertEqual(engine.adopted_edit_version(plain)[0]['version'], 2)

    def test_req_s12_02_unapproved_only_shot_has_no_adopted_version(self):
        chosen, reason = engine.adopted_edit_version([version(1, review='pending'), version(2, qc_pass=False)])
        self.assertIsNone(chosen)
        self.assertEqual(reason, engine.ADOPT_UNAPPROVED)

    def test_req_s12_02_missing_file_is_reported_not_replaced_by_another_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            chosen, reason = engine.adopted_edit_version([version(1, file='gone.mp4', sha256='x')], tmp)
        self.assertIsNone(chosen)
        self.assertEqual(reason, engine.ADOPT_MISSING)

    def test_req_s12_03_automatic_release_is_approved_but_not_content_reviewed(self):
        auto = version(1, review_by='auto')
        human = version(2, review_by='user')
        self.assertEqual(len(engine.approved_versions([auto, human])), 2)
        self.assertFalse(engine.content_reviewed(auto))
        self.assertTrue(engine.content_reviewed(human))

    def test_req_s12_20_master_goes_to_delivery_exports_not_editing_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            editing = project_stages.editing(tmp)
            exports = project_stages.exports(tmp)
        self.assertEqual(editing.name, '12后期剪辑')
        self.assertEqual(exports.name, '导出成片')
        self.assertEqual(exports.parent.name, '13质检交付')

    def test_req_s12_23_completion_evidence_reads_editing_and_export_folders(self):
        with tempfile.TemporaryDirectory() as tmp:
            folders, suffixes = stage_completion_service.media_output_folders(tmp, 'edit')
            names = {folder.name for folder in folders}
        self.assertIn('12后期剪辑', names)
        self.assertIn('导出成片', names)
        self.assertEqual(suffixes, {'.mp4', '.mov', '.mkv'})

    def test_req_s12_25_layout_declares_edits_json_that_no_module_writes(self):
        row = next(item for item in stage_layout.STAGES if item[1] == 'edit')
        self.assertEqual(row[0], '12后期剪辑')
        self.assertIn('edits.json', row[5])
        writers = [path.name for path in ROOT.glob('*.py')
                   if path.name != 'stage_layout.py' and 'edits.json' in path.read_text(encoding='utf-8')]
        self.assertEqual(writers, [])

    def test_req_s12_26_edit_runs_single_agent_and_blocks_after_two_retries(self):
        config = stage_parallel.CONFIG['edit']
        self.assertEqual((config['min'], config['max'], config['limit']), (1, 1, 1))
        self.assertFalse(config['serial'])
        self.assertEqual(config['retry']['attempts'], 2)
        self.assertEqual(config['retry']['on_exhaust'], stage_parallel.ON_BLOCK)

    def test_req_s12_30_default_skill_and_seven_skill_files(self):
        preset = workflow_settings.BUILTIN_WORKFLOW_PRESETS['AIGC全流程']
        self.assertEqual(preset['stage_skills']['edit'], ['pipeline-editing'])
        files = sorted(path.name for path in SKILL_DIR.glob('*.skill.md'))
        self.assertEqual(len(files), 7)
        self.assertIn('pipeline-editing.skill.md', files)

    def test_req_s12_31_only_compose_is_executable_other_edit_tools_are_page_steps(self):
        self.assertEqual(skill_tools.status_of('edit.compose'), 'ready')
        for tool in ('edit.assemble', 'edit.validate', 'edit.addTransition', 'edit.addSFX', 'edit.addBGM'):
            with self.subTest(tool=tool):
                self.assertEqual(skill_tools.status_of(tool), 'page')

    def test_req_s12_32_platform_export_tool_returns_spec_only(self):
        self.assertEqual(skill_tools.status_of('edit.exportDouyin'), 'ready')
        result = skill_tools.call('edit.exportDouyin', {'platform': 'douyin'})
        self.assertTrue(result['ok'])
        self.assertIn('spec', result)
        self.assertNotIn('path', result)


if __name__ == '__main__':
    unittest.main()

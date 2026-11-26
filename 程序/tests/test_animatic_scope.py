"""REQ-S04-01/03/04/21/22/50/51/60：分镜预演阶段的位置、依赖、锁、门禁、并行、输入索引与 SKILL。"""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import pet_bus
import script_contract
import stage_flow
from orchestrator import stage_handler_registry
import stage_layout
import stage_parallel
from desktop import Desktop
from ui.pet_ui_stages import stage_run_action

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / 'skills' / '04 分镜预演SKILL' / 'pipeline-animatic.skill.md'


def _host(**attrs):
    host = Mock(**attrs)
    host.present_stage = Desktop.present_stage.__get__(host)
    return host


class AnimaticScopeTests(unittest.TestCase):
    def test_req_s04_01_stage_is_fourth_between_storyboard_and_assets(self):
        self.assertEqual(pet_bus.STAGES.index('animatic'), 3)
        row = next(item for item in stage_layout.STAGES if item[1] == 'animatic')
        self.assertEqual(row[0], '04分镜预演')
        self.assertEqual(stage_flow.DEPENDS['animatic'], ('storyboard',))
        self.assertEqual(stage_flow.DEPENDS['assets'], ('storyboard',))

    def test_req_s04_03_start_only_opens_the_page_and_never_generates(self):
        with tempfile.TemporaryDirectory() as folder:
            manual = _host(root=Path(folder), pet=None)
            self.assertEqual(stage_handler_registry.start(
                manual, 'animatic', 'manual', run_action=stage_run_action), '')
            auto = _host(root=Path(folder))
            reply = stage_handler_registry.start(auto, 'animatic', 'auto', run_action=stage_run_action)
        manual.show.assert_called_once_with(pet_bus.STAGES.index('animatic'))
        auto.show.assert_called_once_with(pet_bus.STAGES.index('animatic'))
        self.assertIn('确认节奏、时长和对白同步', reply)
        auto.pet._emit.assert_called_once_with('stage.failed', stage='animatic', error=reply)

    def test_req_s04_03_page_rejection_or_exception_prevents_waiting_event(self):
        host = _host(show=Mock(return_value=False))
        with patch.object(stage_flow, 'unchecked', return_value=False):
            self.assertIs(stage_handler_registry.start(
                host, 'animatic', run_action=stage_run_action), False)
            host.show.assert_called_once_with(pet_bus.STAGES.index('animatic'))
            host.show.side_effect = RuntimeError('page failed')
            with self.assertRaisesRegex(RuntimeError, 'page failed'):
                stage_handler_registry.start(host, 'animatic', run_action=stage_run_action)
        self.assertEqual(host.show.call_count, 2)
        host.pet._emit.assert_not_called()

    def test_req_s04_03_unchecked_auto_stage_skips_without_opening_page(self):
        host, skip = Mock(), Mock(return_value='skipped')
        with patch.object(stage_flow, 'unchecked', return_value=True):
            self.assertEqual(stage_handler_registry.start(
                host, 'animatic', run_action=stage_run_action, skip_action=skip), 'skipped')
        skip.assert_called_once_with(host, 'animatic')
        host.show.assert_not_called()
        host.pet._emit.assert_not_called()

    def test_req_s04_04_no_lock_is_required(self):
        self.assertNotIn('animatic', script_contract.STAGE_LOCK_REQUIREMENTS)

    def test_req_s04_05_and_42_gates_sg_a_and_sg_b_are_registered(self):
        gates = {row['id']: row for row in stage_parallel.GATES}
        self.assertEqual((gates['SG-A']['from'], gates['SG-A']['to'], gates['SG-A']['check']),
                         ('storyboard', 'animatic', 'animatic_input_ready'))
        self.assertEqual((gates['SG-B']['from'], gates['SG-B']['to'], gates['SG-B']['check']),
                         ('animatic', 'assets', 'animatic_ready'))

    def test_req_s04_05_empty_project_blocks_sg_a(self):
        with tempfile.TemporaryDirectory() as folder:
            result = stage_parallel.animatic_input_ready(folder)
        self.assertFalse(result['ok'])

    def test_req_s04_21_22_parallel_config(self):
        config = stage_parallel.CONFIG['animatic']
        self.assertEqual((config['unit'], config['limit'], config['serial']), (stage_parallel.BATCH, 3, True))
        self.assertEqual(config['retry']['attempts'], 2)
        self.assertEqual(config['retry']['on_exhaust'], stage_parallel.ON_MANUAL)

    def test_req_s04_41_unconfirmed_empty_project_is_not_complete(self):
        from domain import animatic_service
        with tempfile.TemporaryDirectory() as folder:
            ok, _reason = animatic_service.evidence(folder)
        self.assertFalse(ok)

    def test_req_s04_50_51_single_free_skill_with_local_only_constraints(self):
        text = SKILL.read_text(encoding='utf-8')
        self.assertIn('paid: false', text)
        self.assertIn('dependsOn: [pipeline-storyboard-draft]', text)
        self.assertIn('tools: [animatic.generate, animatic.validate]', text)
        self.assertIn('不替代正式资产或首帧或正式视频', text)
        self.assertEqual(len(list(SKILL.parent.glob('*.skill.md'))), 1)

    def test_req_s04_60_sga_reads_storyboard_draft_index_for_readiness(self):
        """REQ-S04-60：采用分镜时写下的 storyboard_draft.json 是预演输入就绪判定的落盘索引。"""
        import storyboard_selection
        from agent.core import read, save
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            source = root / '03初步分镜' / '分镜拆分' / 'ep1.json'
            save(source, {'episode_id': 'EP001', 'shots': [
                {'id': 'SH001', 'location': 'LOC_001', 'characters': ['CHAR_001'],
                 'image_prompt': '门边的人', 'duration': 1}]})
            save(root / 'ui_settings.json', {'adopted_storyboards': ['03初步分镜/分镜拆分/ep1.json']})
            index = storyboard_selection.sync_draft_outputs(root) / 'storyboard_draft.json'
            self.assertTrue(index.is_file())
            self.assertTrue(stage_parallel.animatic_input_ready(root)['ok'])
            draft = read(index)
            draft['sources'] = []
            save(index, draft)
            result = stage_parallel.animatic_input_ready(root)
        self.assertFalse(result['ok'])
        self.assertIn('storyboard_draft.json', result['detail'])

    def test_req_s04_60_animatic_docs_no_longer_declare_notes_file(self):
        """REQ-S04-60：确认记录以 animatic_manifest.json 的 confirmed 为准，预演不再登记 animatic_notes.md。"""
        row = next(item for item in stage_layout.STAGES if item[1] == 'animatic')
        names = [name for folder, name, _text in stage_layout.docs_rows() if folder == row[0]]
        self.assertNotIn('animatic_notes.md', names)
        self.assertNotIn('animatic_notes.md', stage_layout.readme_text(row))

    def test_req_s04_61_without_batch_id_defaults_to_one_default_batch(self):
        """REQ-S04-61：03 不写 batch_id，预演缺省只有 default 一批；批间并行只是保留能力。"""
        from domain import animatic_service
        shots = animatic_service.shots_of({'shots': [
            {'id': 'SH001', 'image_prompt': '提示一', 'duration': 1},
            {'id': 'SH002', 'image_prompt': '提示二', 'duration': 1},
        ]})
        self.assertEqual([row['batch'] for row in shots], ['default', 'default'])

    def test_req_s04_62_animatic_products_stay_upstream_only(self):
        """REQ-S04-62：预演成果只在本阶段保留，下游不读、不做下游消费。"""
        by_stage = {row[1]: row for row in stage_layout.STAGES}
        animatic_products = {'animatic_manifest.json', 'animatic.mp4', 'temporary_audio'}
        self.assertIn('animatic_manifest.json', by_stage['animatic'][5])
        for stage in ('assets', 'continuity', 'final', 'keyframe', 'previs', 'video'):
            with self.subTest(stage=stage):
                self.assertFalse(animatic_products & set(by_stage[stage][4]))
        from_animatic = [gate for gate in stage_parallel.GATES if gate['from'] == 'animatic']
        self.assertEqual([(gate['id'], gate['to'], gate['check']) for gate in from_animatic],
                         [('SG-B', 'assets', 'animatic_ready')])


if __name__ == '__main__':
    unittest.main(verbosity=2)

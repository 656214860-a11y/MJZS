"""REQ-S12-01/02/03/04/20/23/25/26/30/31/32/33：后期剪辑阶段的依赖、采用版本、产物位置、完成证据与 SKILL 工具边界。"""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

import edit_export
import engine
import pet_bus
from contract import project_stages
import skill_tools
import stage_completion_service
import stage_config
import stage_flow
import stage_layout
import stage_parallel
import workflow_settings
from skip_reasons import MISSING_FFMPEG
from tests.architecture._scan import entity_file

ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / 'skills' / '12后期剪辑SKILL'
FFMPEG = Path('D:/Tools/ffmpeg/bin/ffmpeg.exe')


def version(number, **extra):
    row = {'version': number, 'state': 'downloaded', 'qc_pass': True, 'review': 'pass'}
    row.update(extra)
    return row


class EditingScopeTests(unittest.TestCase):
    def test_req_s12_01_edit_is_stage_12_between_video_and_delivery(self):
        self.assertEqual(pet_bus.STAGES.index('edit') + 1, 12)
        self.assertEqual(pet_bus.STAGE_NAMES['edit'], '后期剪辑')
        self.assertEqual(stage_flow.DEPENDS['edit'], ('video', 'audio'))
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

    def test_req_s12_25_edits_json_is_written_with_settings_and_bundle(self):
        row = next(item for item in stage_layout.STAGES if item[1] == 'edit')
        self.assertEqual(row[0], '12后期剪辑')
        self.assertIn('edits.json', row[5])
        with tempfile.TemporaryDirectory() as tmp:
            studio = engine.Studio.__new__(engine.Studio)
            studio.root = Path(tmp)
            self.assertEqual(studio.edit_settings()['transition']['kind'], 'none')
            studio.save_edit_settings('fade', 0.8, '', 0.4)
            saved = json.loads((project_stages.editing(tmp) / 'edits.json').read_text(encoding='utf-8'))
            self.assertEqual(saved['transition'], {'kind': 'fade', 'seconds': 0.8})
            self.assertEqual(studio.edit_settings()['music']['volume'], 0.4)
            studio.save_edit_settings('bogus', 99, '', 5)
            self.assertEqual(studio.edit_settings(), edit_export.normalize_edits({}))

    def test_req_s12_04_edit_inputs_records_audio_and_subtitle_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            studio = engine.Studio.__new__(engine.Studio)
            studio.root = Path(tmp)
            project_stages.audio(tmp).mkdir(parents=True)
            project_stages.subtitles(tmp).mkdir(parents=True)
            (project_stages.audio(tmp) / 'S01.wav').write_bytes(b'a')
            (project_stages.audio(tmp) / 'note.txt').write_bytes(b'x')
            (project_stages.subtitles(tmp) / 'ep.srt').write_bytes(b's')
            rows = studio.edit_inputs()
        self.assertEqual([item['path'].rsplit('/', 1)[-1] for item in rows['audio']], ['S01.wav'])
        self.assertEqual([item['path'].rsplit('/', 1)[-1] for item in rows['subtitles']], ['ep.srt'])

    def test_req_s12_33_transition_and_music_filters(self):
        self.assertIsNone(edit_export.transition_filter([3, 3], 'none', 0.5))
        self.assertIsNone(edit_export.transition_filter([3], 'fade', 0.5))
        plan = edit_export.transition_filter([3, 4, 5], 'fade', 0.5)
        self.assertIn('xfade=transition=fade:duration=0.5:offset=2.5', plan)
        self.assertIn('xfade=transition=fade:duration=0.5:offset=6.0', plan)
        self.assertEqual(plan.count('acrossfade'), 2)
        self.assertTrue(plan.endswith('[a]'))
        self.assertEqual(edit_export.transition_seconds([1, 4], 'fade', 2), 0.5)
        self.assertIn('volume=0.3', edit_export.music_filter(0.3))
        self.assertEqual(edit_export.normalize_edits({'transition': {'kind': 'x'}})['transition']['kind'], 'none')

    @unittest.skipUnless(FFMPEG.is_file(), MISSING_FFMPEG)
    def test_req_s12_33_s12_32_real_transition_music_and_platform_export(self):
        from agent.media import probe
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ('S01.mp4', 'S02.mp4'):
                subprocess.run([str(FFMPEG), '-y', '-v', 'error', '-f', 'lavfi', '-i',
                                'testsrc=size=320x180:rate=24:duration=2', '-f', 'lavfi', '-i',
                                'sine=frequency=440:duration=2', '-shortest', '-pix_fmt', 'yuv420p',
                                str(root / name)], check=True)
            music = root / 'bgm.wav'
            subprocess.run([str(FFMPEG), '-y', '-v', 'error', '-f', 'lavfi', '-i', 'sine=frequency=220:duration=1',
                            str(music)], check=True)
            studio = engine.Studio.__new__(engine.Studio)
            studio.root = root
            studio.cfg = {'ffmpeg': str(FFMPEG), 'ffprobe': str(FFMPEG.with_name('ffprobe.exe'))}
            chosen = [({'id': 'S01', 'duration': 2}, {}, root / 'S01.mp4'), ({'id': 'S02', 'duration': 2}, {}, root / 'S02.mp4')]
            (root / 'concat.txt').write_text("file 'S01.mp4'\nfile 'S02.mp4'\n", encoding='utf-8')
            edits = studio.save_edit_settings('fade', 0.5, str(music), 0.3)
            pending = root / 'MASTER.partial.mp4'
            overlap = studio._join_shots(root, chosen, pending, studio.edit_settings())
            self.assertAlmostEqual(overlap, 0.5)
            facts = probe(pending, studio.cfg)
            self.assertAlmostEqual(float(facts['format']['duration']), 3.5, delta=0.3)
            self.assertTrue(any(s['codec_type'] == 'audio' for s in facts['streams']))
            self.assertEqual(edits['music']['file'], str(music.resolve()) if edits['music']['file'].startswith(str(root)) else edits['music']['file'])
            spec = edit_export.platform_spec('douyin')
            dest = studio.export_platform(pending, spec, 'douyin')
            video = [s for s in probe(dest, studio.cfg)['streams'] if s['codec_type'] == 'video'][0]
            self.assertEqual((video['width'], video['height']), (spec['width'], spec['height']))
            record = json.loads((root / 'edits.json').read_text(encoding='utf-8'))
            self.assertEqual(record['platform_exports'][0]['platform'], 'douyin')

    def test_req_s12_26_edit_runs_single_agent_and_blocks_after_two_retries(self):
        config = stage_parallel.CONFIG['edit']
        self.assertEqual((config['min'], config['max'], config['limit']), (1, 1, 1))
        self.assertFalse(config['serial'])
        self.assertEqual(config['retry']['attempts'], 2)
        self.assertEqual(config['retry']['on_exhaust'], stage_parallel.ON_BLOCK)

    def test_req_s12_30_default_skill_and_seven_skill_files(self):
        self.assertIn('pipeline-editing', stage_config.default_entry('edit')['skills'])
        files = sorted(path.name for path in SKILL_DIR.glob('*.skill.md'))
        self.assertEqual(len(files), 7)
        self.assertIn('pipeline-editing.skill.md', files)

    def test_req_s12_31_only_compose_is_executable_other_edit_tools_are_page_steps(self):
        self.assertEqual(skill_tools.status_of('edit.compose'), 'ready')
        for tool in ('edit.assemble', 'edit.validate', 'edit.addTransition', 'edit.addSFX', 'edit.addBGM'):
            with self.subTest(tool=tool):
                self.assertEqual(skill_tools.status_of(tool), 'page')

    def test_req_s12_32_tool_gives_spec_and_page_exports_with_same_table(self):
        self.assertEqual(skill_tools.status_of('edit.exportDouyin'), 'ready')
        result = skill_tools.call('edit.exportDouyin', {'platform': 'douyin'})
        self.assertTrue(result['ok'])
        self.assertEqual(result['spec']['width'], edit_export.PLATFORMS['douyin']['width'])
        self.assertNotIn('path', result)
        self.assertTrue(callable(engine.Studio.export_platform))
        source = entity_file('desktop_media_pages').read_text(encoding='utf-8')
        self.assertIn('export_platform', source)


if __name__ == '__main__':
    unittest.main()

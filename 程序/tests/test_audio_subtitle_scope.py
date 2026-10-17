"""REQ-S11-01/02/03/04/10/11/12/20/21/22/23/24/30/31/40：配音与字幕阶段的依赖、范围、字幕契约与 SKILL 归属。"""
import unittest
from pathlib import Path

import pet_bus
import stage_flow
import stage_layout
import stage_parallel
import subtitle_export_service
import subtitle_timing
import tts_api

ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / 'skills' / '11配音字幕SKILL'
SKILLS = ('pipeline-audio-subtitle', 'voice-tts-synthesis', 'voice-multi-character',
          'voice-emotion-check', 'subtitle-auto-align', 'subtitle-format-export')


def _audio_row():
    return next(row for row in stage_layout.STAGES if row[1] == 'audio')


class AudioSubtitleScopeTests(unittest.TestCase):
    def test_req_s11_01_stage_identity_and_position(self):
        self.assertEqual(pet_bus.STAGE_NAMES['audio'], '配音与字幕')
        self.assertEqual(pet_bus.STAGES.index('audio'), 10)
        self.assertEqual(_audio_row()[0], '11配音与字幕')

    def test_req_s11_02_depends_only_on_final_storyboard(self):
        self.assertEqual(stage_flow.DEPENDS['audio'], ('final',))
        self.assertEqual(_audio_row()[4], ('storyboard_final.json',))

    def test_req_s11_03_audio_is_a_paid_stage(self):
        self.assertIn('audio', stage_flow.PAID_STAGES)

    def test_req_s11_03_parallel_is_per_track_serial_with_two_retries(self):
        config = stage_parallel.CONFIG['audio']
        self.assertTrue(config['serial'])
        self.assertEqual(config['retry']['attempts'], 2)

    def test_req_s11_04_completion_accepts_only_audio_media_suffixes(self):
        import tempfile
        import stage_completion_service
        with tempfile.TemporaryDirectory() as tmp:
            _folders, suffixes = stage_completion_service.media_output_folders(Path(tmp), 'audio')
        self.assertEqual(suffixes, {'.mp3', '.wav', '.m4a', '.aac'})

    def test_req_s11_10_audio_kinds_and_default_to_dialogue(self):
        self.assertEqual(tts_api.AUDIO_KINDS, ('dialogue', 'narration', 'bgm', 'sfx', 'full'))
        self.assertEqual(tts_api.audio_kind('随便.wav'), 'dialogue')
        for kind in ('narration', 'bgm', 'sfx', 'full'):
            with self.subTest(kind=kind):
                name = tts_api.marked_audio_name('x', kind) + '.wav'
                self.assertEqual(tts_api.audio_kind(name), kind)
        self.assertEqual(tts_api.marked_audio_name('x', 'dialogue'), 'x')

    def test_req_s11_11_import_rejects_unknown_stage_or_kind(self):
        import audio_import_service
        with self.assertRaises(ValueError):
            audio_import_service.import_audio('.', 'a.wav', publish=lambda *a: None, stage='video')
        with self.assertRaises(ValueError):
            audio_import_service.import_audio('.', 'a.wav', publish=lambda *a: None, kind='voice')

    def test_req_s11_12_batch_line_identity_fields(self):
        self.assertEqual(tts_api.LINE_IDENTITY_FIELDS,
                         ('shot_id', 'text', 'voice', 'speed', 'model', 'endpoint'))

    def test_req_s11_20_partial_timing_is_rejected_not_fixed(self):
        episode = {'shots': [{'id': 'S1', 'duration': 4, 'dialogue': [
            {'speaker': 'a', 'text': '甲', 'start': 0, 'end': 1}, {'speaker': 'b', 'text': '乙'}]}]}
        with self.assertRaises(ValueError):
            subtitle_timing.timed_entries(episode)
        with self.assertRaises(ValueError):
            subtitle_timing.calibrate_entries(episode)

    def test_req_s11_21_invalid_timeline_raises(self):
        bad = {
            'overlap': [('S1', '', 'a', 0, 2), ('S1', '', 'b', 1, 3)],
            'reversed': [('S1', '', 'a', 2, 1)],
            'negative': [('S1', '', 'a', -1, 1)],
        }
        for name, entries in bad.items():
            with self.subTest(name=name):
                with self.assertRaises(ValueError):
                    subtitle_timing.validate_entries(entries)
        with self.assertRaises(ValueError):
            subtitle_timing.validate_entries([('S1', '', 'a', 0, 5)], total=3)

    def test_req_s11_22_estimate_marks_uncalibrated_and_audio_calibrates(self):
        episode = {'shots': [{'id': 'S1', 'duration': 4, 'dialogue': [
            {'speaker': 'a', 'text': '甲'}, {'speaker': 'b', 'text': '乙乙'}]}]}
        _entries, estimated = subtitle_timing.timed_entries(episode)
        self.assertTrue(estimated)
        self.assertEqual(len(subtitle_export_service.pending_calibration(episode)), 2)
        _entries, report = subtitle_timing.calibrate_entries(episode, audio=[1.0, 2.0])
        self.assertEqual(report['mode'], 'audio')
        self.assertEqual(report['uncalibrated'], [])

    def test_req_s11_23_srt_format(self):
        self.assertEqual(subtitle_timing.stamp(3661.5), '01:01:01,500')
        rows = subtitle_timing.rows_from_entries([('S1', '', '多行\n文本', 0, 1.5)])
        self.assertEqual(rows, ['1\n00:00:00,000 --> 00:00:01,500\n多行 文本\n'])

    def test_req_s11_24_only_srt_exporter_exists_no_ass(self):
        self.assertTrue(callable(subtitle_export_service.export_srt))
        names = [n for n in dir(subtitle_export_service) if 'ass' in n.lower().split('_')]
        self.assertEqual(names, [])

    def test_req_s11_30_six_skills_exist_and_entry_is_paid(self):
        for name in SKILLS:
            with self.subTest(name=name):
                self.assertTrue((SKILL_DIR / (name + '.skill.md')).is_file())
        entry = (SKILL_DIR / 'pipeline-audio-subtitle.skill.md').read_text(encoding='utf-8')
        self.assertIn('paid: true', entry)
        self.assertIn('dependsOn: [pipeline-storyboard-final]', entry)

    def test_req_s11_31_multi_character_skill_is_merged_into_tts(self):
        text = (SKILL_DIR / 'voice-multi-character.skill.md').read_text(encoding='utf-8')
        self.assertIn('已合并到「TTS 配音合成」', text)

    def test_req_s11_40_declared_outputs_have_no_code_producer(self):
        self.assertEqual(_audio_row()[5], ('voice.json', 'subtitles.json'))
        for module in (tts_api, subtitle_export_service):
            source = Path(module.__file__).read_text(encoding='utf-8')
            for name in ('voice.json', 'subtitles.json', 'audio_manifest.json'):
                with self.subTest(module=module.__name__, name=name):
                    self.assertNotIn(name, source)


if __name__ == '__main__':
    unittest.main()

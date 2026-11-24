"""REQ-S04-74/75/76/77：预演三轨临时声音——逐镜 TTS 幂等复用、对白超长告警、整轨优先与 -12dB 音乐混音。"""
import tempfile
import unittest
from pathlib import Path

from domain.animatic_audio import (SUBDIRS, build_audio_mix_command, detect_overlong,
                                   dialogue_text, plan, shot_tts)


def _shot(shot_id, seconds, dialogue=None):
    return {'id': shot_id, 'seconds': seconds, 'dialogue': dialogue}


class DialogueTextTests(unittest.TestCase):
    def test_req_s04_75_multi_line_list_filters_blanks_and_joins(self):
        """多句对白列表滤掉空项，按顺序以「。」连接。"""
        self.assertEqual(dialogue_text(['第一句', '', '第二句']), '第一句。第二句')
        self.assertEqual(dialogue_text(['  ', None]), '')

    def test_req_s04_75_string_dict_and_blank_forms(self):
        self.assertEqual(dialogue_text(' 一句 '), '一句')
        self.assertEqual(dialogue_text({'text': '台词'}), '台词')
        self.assertEqual(dialogue_text({'line': '备用字段'}), '备用字段')
        self.assertEqual(dialogue_text(None), '')
        self.assertEqual(dialogue_text('   '), '')
        self.assertEqual(dialogue_text({'text': ' '}), '')


class PlanTests(unittest.TestCase):
    def test_req_s04_74_three_track_subdirs_are_declared(self):
        self.assertEqual(SUBDIRS, {'dialogue': '声音/对白', 'track': '声音/整轨',
                                   'music': '声音/音乐'})

    def test_req_s04_74_silent_when_no_dialogue_track_or_music(self):
        result = plan([_shot('SH001', 2), _shot('SH002', 3, '  ')])
        self.assertEqual(result['mode'], 'silent')
        self.assertEqual(result['tts_shots'], [])
        self.assertIsNone(result['full_track'])
        self.assertIsNone(result['music'])

    def test_req_s04_76_full_track_wins_over_per_shot_dialogue(self):
        """整轨配音优先：已有对白也一律不排逐镜 TTS。"""
        with tempfile.TemporaryDirectory() as folder:
            track = Path(folder) / '整轨.mp3'
            track.write_bytes(b'audio')
            result = plan([_shot('SH001', 2, '台词'), _shot('SH002', 3, '词')],
                          full_track=track)
        self.assertEqual(result['mode'], 'full_track')
        self.assertEqual(result['tts_shots'], [])
        self.assertEqual(result['full_track'], track)

    def test_req_s04_76_missing_or_empty_full_track_falls_back_to_per_shot(self):
        with tempfile.TemporaryDirectory() as folder:
            empty = Path(folder) / '空.mp3'
            empty.write_bytes(b'')
            missing = Path(folder) / '没有.mp3'
            for candidate in (empty, missing):
                with self.subTest(candidate=candidate.name):
                    result = plan([_shot('SH001', 2, '台词')], full_track=candidate)
                    self.assertEqual(result['mode'], 'per_shot_tts')
                    self.assertIsNone(result['full_track'])

    def test_req_s04_75_tts_shots_carry_text_and_timeline_position(self):
        result = plan([_shot('SH001', 2.0, ['一', '二']), _shot('SH002', 3.5, None),
                       _shot('SH003', 1.5, '三')])
        self.assertEqual(result['mode'], 'per_shot_tts')
        self.assertEqual(result['tts_shots'], [
            {'id': 'SH001', 'text': '一。二', 'start_seconds': 0.0, 'seconds': 2.0},
            {'id': 'SH003', 'text': '三', 'start_seconds': 5.5, 'seconds': 1.5}])

    def test_req_s04_76_music_is_optional_and_passed_through(self):
        with tempfile.TemporaryDirectory() as folder:
            music = Path(folder) / 'bgm.mp3'
            music.write_bytes(b'm')
            result = plan([_shot('SH001', 2)], music=music)
            self.assertEqual(result['mode'], 'silent')
            self.assertEqual(result['music'], music)
            missing = plan([_shot('SH001', 2)], music=Path(folder) / '无.mp3')
            self.assertIsNone(missing['music'])


class ShotTtsTests(unittest.TestCase):
    def _synth(self):
        calls = []

        def synthesize(text, **kwargs):
            calls.append((text, kwargs))
            return b'TTS:' + text.encode('utf-8')

        return calls, synthesize

    def test_req_s04_75_empty_dialogue_returns_none_without_synthesis(self):
        calls, synth = self._synth()
        with tempfile.TemporaryDirectory() as folder:
            result = shot_tts(_shot('SH001', 2, '  '), Path(folder), {},
                              synthesize=synth, signature_fn=lambda text, settings: 'sig',
                              write_temporary=lambda path, raw: path.write_bytes(raw))
        self.assertIsNone(result)
        self.assertEqual(calls, [])

    def test_req_s04_75_existing_nonempty_temp_audio_is_reused(self):
        """幂等：同签名非空临时音频直接复用，不再调用合成器。"""
        calls, synth = self._synth()
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / 'SH001_temp_abc.mp3'
            target.write_bytes(b'cached')
            path = shot_tts(_shot('SH001', 2, '台词'), Path(folder), {'voice': 'v'},
                            synthesize=synth, signature_fn=lambda text, settings: 'abc',
                            write_temporary=lambda path, raw: path.write_bytes(raw),
                            project='proj')
            self.assertEqual(path, target)
            self.assertEqual(target.read_bytes(), b'cached')
        self.assertEqual(calls, [])

    def test_req_s04_75_zero_byte_temp_audio_is_regenerated_with_request_id(self):
        calls, synth = self._synth()
        writes = []
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / 'SH007_temp_xyz.mp3'
            target.write_bytes(b'')
            path = shot_tts(_shot('SH007', 2, '台词'), Path(folder), {'model': 'm'},
                            synthesize=synth, signature_fn=lambda text, settings: 'xyz',
                            write_temporary=lambda path, raw: (writes.append((path, raw)),
                                                               path.write_bytes(raw))[0],
                            project='proj')
            self.assertEqual(path, target)
            self.assertEqual(writes, [(target, 'TTS:台词'.encode('utf-8'))])
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][0], '台词')
        self.assertEqual(calls[0][1].get('request_id'), 'tts-previs:SH007:xyz')
        self.assertEqual(calls[0][1].get('project'), 'proj')
        self.assertEqual(calls[0][1].get('settings'), {'model': 'm'})

    def test_req_s04_75_non_persistent_run_sends_no_request_id(self):
        calls, synth = self._synth()
        with tempfile.TemporaryDirectory() as folder:
            shot_tts(_shot('SH009', 2, '词'), Path(folder), {},
                     synthesize=synth, signature_fn=lambda text, settings: 's',
                     write_temporary=lambda path, raw: path.write_bytes(raw),
                     persistent=False)
        self.assertIsNone(calls[0][1].get('request_id'))


class DetectOverlongTests(unittest.TestCase):
    def test_req_s04_75_overlong_dialogue_is_flagged_not_trimmed(self):
        """对白实测超过镜头时长容差即告警；容差内不误报，且绝不改时长。"""
        shots = [_shot('SH001', 3.0, '词'), _shot('SH002', 3.0, '词')]
        clips = {'SH001': 'a.mp3', 'SH002': 'b.mp3'}
        durations = {'a.mp3': 4.8, 'b.mp3': 3.05}
        warnings = detect_overlong(shots, clips, probe_duration=durations.get)
        self.assertEqual(len(warnings), 1)
        self.assertEqual(warnings[0], {'shot_id': 'SH001', 'audio_seconds': 4.8,
                                       'shot_seconds': 3.0,
                                       'message': '对白超长，请调长本镜时长或回初步分镜拆镜'})
        self.assertEqual(shots[0]['seconds'], 3.0)

    def test_req_s04_75_shots_without_clips_are_skipped(self):
        warnings = detect_overlong([_shot('SH001', 3.0, '词'), _shot('SH002', 3.0)],
                                   {'SH001': 'a.mp3'}, probe_duration=lambda path: 1.0)
        self.assertEqual(warnings, [])


class MixCommandTests(unittest.TestCase):
    def test_req_s04_74_no_tracks_produces_silent_anullsrc_trimmed_to_total(self):
        """全镜无对白且无整轨也无音乐：anullsrc 静音轨截齐总长。"""
        command = build_audio_mix_command('out.wav', 6.0)
        text = ' '.join(command)
        self.assertIn('anullsrc', text)
        index = command.index('-t')
        self.assertEqual(float(command[index + 1]), 6.0)
        self.assertEqual(command[-1], 'out.wav')

    def test_req_s04_76_full_track_fills_alone_without_dialogue_mix(self):
        """整轨优先：命令只用整轨输入，不混入逐镜对白。"""
        command = build_audio_mix_command('out.wav', 4.0, full_track='track.mp3',
            dialogue_clips=[{'path': 'd1.mp3', 'start_ms': 500}])
        text = ' '.join(command)
        self.assertIn('track.mp3', text)
        self.assertNotIn('adelay', text)
        self.assertNotIn('d1.mp3', text)

    def test_req_s04_75_dialogue_clips_are_delayed_and_mixed(self):
        command = build_audio_mix_command('out.wav', 9.0, dialogue_clips=[
            {'path': 's1.mp3', 'start_ms': 0}, {'path': 's2.mp3', 'start_ms': 2500}])
        filters = command[command.index('-filter_complex') + 1]
        self.assertIn('adelay=2500|2500', filters)
        self.assertIn('amix', filters)
        self.assertIn('s2.mp3', command)

    def test_req_s04_76_music_is_ducked_at_minus_12_db_and_trimmed(self):
        command = build_audio_mix_command('out.wav', 7.5,
            dialogue_clips=[{'path': 's1.mp3', 'start_ms': 0}], music='bgm.mp3')
        filters = command[command.index('-filter_complex') + 1]
        self.assertIn('volume=-12dB', filters)
        self.assertIn('amix', filters)
        self.assertIn('apad', filters)
        index = command.index('-t')
        self.assertEqual(command[index + 1], '7.5')

    def test_req_s04_76_full_track_and_music_mix_together(self):
        command = build_audio_mix_command('out.wav', 5.0, full_track='track.mp3',
                                          music='bgm.mp3')
        filters = command[command.index('-filter_complex') + 1]
        self.assertIn('volume=-12dB', filters)
        self.assertIn('amix', filters)


if __name__ == '__main__':
    unittest.main(verbosity=2)

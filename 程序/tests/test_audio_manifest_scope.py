"""REQ-S11-24/40：ASS 字幕与 SRT 同批导出；voice／subtitles／audio_manifest 清单的真实产出。"""
import json
import tempfile
import unittest
from pathlib import Path

import audio_import_service
import stage_execution_service
import stage_path_service
import subtitle_export_service
import subtitle_timing
from project_stages import audio

EPISODE = {'shots': [{'id': 'SH001', 'title': '初见', 'duration': 4, 'dialogue': [
    {'speaker': 'A', 'text': '你好{x}', 'start': 0, 'end': 2.5},
    {'speaker': 'B', 'text': '再见', 'start': 2.5, 'end': 3.75}]}]}


class AssSubtitleTests(unittest.TestCase):
    def test_req_s11_24_ass_stamp_and_text_format(self):
        self.assertEqual(subtitle_timing.ass_stamp(3661.5), '1:01:01.50')
        text = subtitle_timing.ass_text([('S1', '', '多行\n文本{a}', 0, 1.5)])
        self.assertTrue(text.startswith('[Script Info]'))
        self.assertIn('[V4+ Styles]', text)
        self.assertIn('Dialogue: 0,0:00:00.00,0:00:01.50,Default,,0,0,0,,多行 文本｛a｝', text)

    def test_req_s11_24_srt_export_publishes_matching_ass_in_same_batch(self):
        with tempfile.TemporaryDirectory() as folder:
            result = stage_execution_service.export_stage_srt(folder, EPISODE)
            self.assertTrue(result.ok)
            srt = result.data[0]
            ass = srt.with_suffix('.ass')
            self.assertTrue(srt.is_file() and ass.is_file())
            body = ass.read_text(encoding='utf-8-sig')
            self.assertIn('Dialogue: 0,0:00:00.00,0:00:02.50,Default,,0,0,0,,你好｛x｝', body)
            self.assertIn('0:00:03.75', body)

    def test_req_s11_24_ass_failure_keeps_the_published_srt(self):
        published = []

        def publish(target, text, validate, update_index, encoding='utf-8'):
            if Path(target).suffix == '.ass':
                raise OSError('disk')
            published.append(Path(target).suffix)
            return target

        with self.assertLogs('subtitle_export_service', 'WARNING'):
            result = subtitle_export_service.export_srt('project', EPISODE, publish=publish)
        self.assertTrue(result.ok)
        self.assertEqual(published[0], '.srt')


class AudioManifestTests(unittest.TestCase):
    def manifests(self, root):
        folder = stage_path_service.write_dir(root, 'audio') / 'output'
        return {name: json.loads((folder / name).read_text(encoding='utf-8'))
                for name in audio_import_service.MANIFEST_NAMES}

    def test_req_s11_40_manifest_names_cover_the_declared_outputs(self):
        self.assertEqual(audio_import_service.MANIFEST_NAMES, ('voice.json', 'subtitles.json', 'audio_manifest.json'))

    def test_req_s11_40_empty_project_yields_empty_lists(self):
        with tempfile.TemporaryDirectory() as folder:
            payload = audio_import_service.audio_manifests(folder)
            self.assertEqual(payload['voice.json']['tracks'], [])
            self.assertEqual(payload['audio_manifest.json']['subtitle_count'], 0)

    def test_req_s11_40_export_writes_and_refreshes_all_three_manifests(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            audio(root).mkdir(parents=True)
            (audio(root) / '旁白_x.wav').write_bytes(b'abc')
            (audio(root) / 'line.mp3').write_bytes(b'abcd')
            result = stage_execution_service.export_stage_srt(root, EPISODE)
            self.assertTrue(result.ok)
            data = self.manifests(root)
            kinds = {item['file'].rsplit('/', 1)[-1]: item['kind'] for item in data['voice.json']['tracks']}
            self.assertEqual(sorted(kinds.values()), ['dialogue', 'narration'])
            formats = sorted(item['format'] for item in data['subtitles.json']['files'])
            self.assertEqual(formats, ['ass', 'calibration', 'srt'])
            self.assertTrue(all(len(item['sha256']) == 64 for item in data['subtitles.json']['files']))
            self.assertEqual(data['audio_manifest.json']['voice'], data['voice.json'])
            self.assertEqual(data['audio_manifest.json']['subtitle_count'], 3)
            self.assertTrue(all(not Path(item['file']).is_absolute() for item in data['voice.json']['tracks']))


if __name__ == '__main__':
    unittest.main()

"""REQ-S11-24/40：ASS 字幕与 SRT 同批导出；voice／subtitles／audio_manifest 清单的真实产出。"""
import json
import tempfile
import unittest
from pathlib import Path

from domain import audio_import_service
import stage_execution_service
from contract import stage_path_service
from domain import subtitle_export_service
from domain import subtitle_timing
from contract.project_stages import audio

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

    def test_req_s11_40_sentence_dub_batches_listed_as_dialogue(self):
        """逐句配音分句音频按批次进 voice.json，用途一律对白并带所属批次。"""
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            base = audio(root)
            batch_a = base / '配音分句' / '批次A'
            batch_b = base / '配音分句' / '配音批次_20260101'
            batch_a.mkdir(parents=True)
            batch_b.mkdir(parents=True)
            (base / '整轨_x.wav').write_bytes(b'abc')
            (batch_a / '001_SH001_你好_0.0s.mp3').write_bytes(b'abcd')
            (batch_a / '批次.json').write_text('{}', encoding='utf-8')
            (batch_a / '时间轴.json').write_text('[]', encoding='utf-8')
            (batch_b / '002_SH002_再见_1.0s.wav').write_bytes(b'ab')
            payload = audio_import_service.audio_manifests(root)
            tracks = payload['voice.json']['tracks']
            by_file = {item['file']: item for item in tracks}
            rel_top = (base / '整轨_x.wav').relative_to(root).as_posix()
            rel_a = (batch_a / '001_SH001_你好_0.0s.mp3').relative_to(root).as_posix()
            rel_b = (batch_b / '002_SH002_再见_1.0s.wav').relative_to(root).as_posix()
            self.assertEqual(by_file[rel_top], {'file': rel_top, 'kind': 'full', 'bytes': 3})
            self.assertIn(rel_a, by_file)
            self.assertIn(rel_b, by_file)
            self.assertEqual(by_file[rel_a]['kind'], 'dialogue')
            self.assertEqual(by_file[rel_a]['bytes'], 4)
            self.assertEqual(by_file[rel_a]['batch'], '批次A')
            self.assertEqual(by_file[rel_b]['batch'], '配音批次_20260101')
            self.assertNotIn('批次.json', [Path(item['file']).name for item in tracks])
            self.assertEqual(payload['audio_manifest.json']['voice'], payload['voice.json'])
            self.assertEqual(payload['audio_manifest.json']['track_count'], len(tracks))

    def test_req_s11_40_sentence_dub_skips_history_and_recycle_dirs(self):
        """分句批次内的 历史版本/ 与 回收站/ 不进清单；顶层 历史版本/ 同样不列。"""
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            batch = audio(root) / '配音分句' / '批次A'
            (batch / '历史版本').mkdir(parents=True)
            (batch / '回收站').mkdir(parents=True)
            (batch / '历史版本' / 'old.mp3').write_bytes(b'x')
            (batch / '回收站' / 'gone.mp3').write_bytes(b'x')
            (batch / '001_SH001_你好_0.0s.mp3').write_bytes(b'ok')
            history = audio(root) / '历史版本'
            history.mkdir(parents=True)
            (history / 'old2.mp3').write_bytes(b'x')
            payload = audio_import_service.audio_manifests(root)
            files = [item['file'] for item in payload['voice.json']['tracks']]
            self.assertIn((batch / '001_SH001_你好_0.0s.mp3').relative_to(root).as_posix(), files)
            self.assertFalse(any('历史版本' in name or '回收站' in name for name in files))

    def test_req_s11_40_no_sentence_dir_keeps_manifest_identical(self):
        """没有 配音分句/ 目录时清单与旧口径逐字一致：顶层条目不多字段。"""
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            base = audio(root)
            base.mkdir(parents=True)
            (base / 'line.mp3').write_bytes(b'abcd')
            payload = audio_import_service.audio_manifests(root)
            rel = (base / 'line.mp3').relative_to(root).as_posix()
            self.assertEqual(payload['voice.json']['tracks'],
                             [{'file': rel, 'kind': 'dialogue', 'bytes': 4}])


if __name__ == '__main__':
    unittest.main()

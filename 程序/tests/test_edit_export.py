"""剪辑软件交付出口：纯文本生成，不写文件、不启动剪辑软件。"""
import unittest
import xml.etree.ElementTree as ET

import edit_export as ex

CLIPS = [{'shot': 'S01', 'file': 'S01.mp4', 'duration': 2.5},
         {'shot': 'S02', 'file': 'S02.mp4', 'duration': 4},
         {'shot': 'S&3', 'file': 'S3.mp4', 'duration': 0.04}]
SPEC = {'fps': 24, 'width': 1080, 'height': 1920}


class EditExportTests(unittest.TestCase):
    """REQ-S12-35：EDL（CMX3600）、FCPXML 与分轨素材清单；时间码非丢帧，按帧数累计防漂移。"""

    def test_timecode_and_layout_accumulate_frames_without_drift(self):
        self.assertEqual(ex.timecode(0, 24), '00:00:00:00')
        self.assertEqual(ex.timecode(24 * 3661 + 5, 24), '01:01:01:05')
        rows = ex.layout(CLIPS, 24)
        self.assertEqual([row['frames'] for row in rows], [60, 96, 1])
        self.assertEqual(rows[1]['start'], 60)
        self.assertEqual(rows[-1]['end'], 157)
        with self.assertRaises(ValueError):
            ex.layout([{'shot': 'x', 'file': 'x', 'duration': 'abc'}], 24)

    def test_edl_is_cmx3600_with_clip_names(self):
        text = ex.build_edl('第一集', CLIPS, 24)
        lines = text.splitlines()
        self.assertEqual(lines[0], 'TITLE: 第一集')
        self.assertIn('FCM: NON-DROP FRAME', lines)
        event = [line for line in lines if line.startswith('002 ')][0]
        self.assertTrue(event.endswith('00:00:00:00 00:00:04:00 00:00:02:12 00:00:06:12'))
        self.assertIn('* FROM CLIP NAME: S02.mp4', lines)

    def test_fcpxml_is_well_formed_and_escapes_names(self):
        root = ET.fromstring(ex.build_fcpxml('A "B" <C>', CLIPS, SPEC))
        self.assertEqual(root.tag, 'fcpxml')
        fmt = root.find('./resources/format')
        self.assertEqual((fmt.get('width'), fmt.get('height'), fmt.get('frameDuration')), ('1080', '1920', '1/24s'))
        clips = root.findall('.//spine/asset-clip')
        self.assertEqual([clip.get('name') for clip in clips], ['S01', 'S02', 'S&3'])
        self.assertEqual(clips[1].get('offset'), '60/24s')
        self.assertEqual(root.find('.//sequence').get('duration'), '157/24s')

    def test_tracks_and_export_texts(self):
        texts = ex.export_texts('t', CLIPS, SPEC, {'S01': {'version': 2, 'sha256': 'abc'}})
        self.assertEqual(set(texts), {ex.EDL_NAME, ex.FCPXML_NAME, ex.TRACKS_NAME})
        tracks = texts[ex.TRACKS_NAME]
        self.assertEqual(tracks['clips'][0]['source_sha256'], 'abc')
        self.assertIsNone(tracks['clips'][1]['source_version'])
        self.assertEqual(tracks['total_frames'], 157)
        with self.assertRaises(ValueError):
            ex.export_texts('t', [], SPEC)


class PublishEditListsTests(unittest.TestCase):
    """REQ-S12-22：EDL／FCPXML／分轨清单写失败时不删成片，如实报「剪辑交付包不完整」。"""

    def test_encode_does_not_report_success_when_delivery_lists_fail(self):
        import tempfile
        from pathlib import Path
        from types import SimpleNamespace
        from unittest.mock import Mock, patch
        import engine
        from edit_export import normalize_edits
        studio = SimpleNamespace(cfg={'ffmpeg': 'fake'}, output_spec=lambda: SPEC,
                                 publish_edit_bundle=Mock(),
                                 publish_edit_lists=lambda *args: {'ok': False, 'reason': 'disk full'},
                                 edit_settings=lambda: normalize_edits(None))
        studio._join_shots = lambda *args: engine.Studio._join_shots(studio, *args)
        def encode_command(args, **kwargs):
            if isinstance(args[-1], Path):
                args[-1].write_bytes(b'encoded fixture')
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder)
            with patch('engine.command', side_effect=encode_command), patch('engine.check', return_value={'errors': []}):
                with self.assertRaisesRegex(ValueError, '剪辑交付包不完整'):
                    engine.Studio._encode(studio, [], out)
            self.assertEqual((out / 'MASTER.mp4').read_bytes(), b'encoded fixture')
            studio.publish_edit_bundle.assert_called_once()

    def test_studio_writes_three_files_and_tolerates_bad_data(self):
        import json
        import tempfile
        from pathlib import Path
        import engine
        chosen = [({'id': 'S01', 'duration': 2}, {'version': 1, 'sha256': 'h1'}, Path('S01.mp4'))]
        with tempfile.TemporaryDirectory() as folder:
            self.assertTrue(engine.Studio.publish_edit_lists(None, folder, chosen, SPEC)['ok'])
            names = sorted(path.name for path in Path(folder).iterdir())
            self.assertEqual(names, sorted([ex.EDL_NAME, ex.FCPXML_NAME, ex.TRACKS_NAME]))
            data = json.loads((Path(folder) / ex.TRACKS_NAME).read_text(encoding='utf-8'))
            self.assertEqual(data['clips'][0]['source_sha256'], 'h1')
        with tempfile.TemporaryDirectory() as folder:
            bad = [({'id': 'S01', 'duration': 'x'}, {}, Path('S01.mp4'))]
            result = engine.Studio.publish_edit_lists(None, folder, bad, SPEC)
            self.assertFalse(result['ok'])
            self.assertTrue(result['reason'])
            self.assertEqual(list(Path(folder).iterdir()), [])

    def test_partial_export_write_failure_is_reported_without_removing_master(self):
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        import engine
        chosen = [({'id': 'S01', 'duration': 2}, {'version': 1, 'sha256': 'fixture'}, Path('S01.mp4'))]
        with tempfile.TemporaryDirectory() as folder:
            master = Path(folder) / 'master.mp4'; master.write_bytes(b'test master')
            with patch('engine.save_text', side_effect=OSError('disk full')):
                result = engine.Studio.publish_edit_lists(None, folder, chosen, SPEC)
            self.assertFalse(result['ok'])
            self.assertIn('disk full', result['reason'])
            self.assertEqual(master.read_bytes(), b'test master')


if __name__ == '__main__':
    unittest.main()

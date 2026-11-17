"""REQ-S10-21/31：视频阶段清单 videos.json／video_manifest.json 的真实产出与「100 镜/项目」上限。"""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import engine
from contract import stage_path_service
import video_task_state


def _shot(index, **extra):
    return {'id': 'S%03d' % index, 'duration': 5, 'video_prompt': '推镜', 'frame': 'f.png', **extra}


def _studio(folder, count=2, **extra):
    root = Path(folder)
    (root / 'episode.json').write_text(json.dumps({'shots': [_shot(i + 1, **extra) for i in range(count)]}),
                                       encoding='utf-8')
    (root / 'config.json').write_text(json.dumps({'reserve_seconds': 0, 'budget_seconds': 0}), encoding='utf-8')
    return engine.Studio(root, factory=lambda *a, **k: None, episode_file='episode.json')


class VideoManifestTests(unittest.TestCase):
    def read_manifests(self, root):
        folder = stage_path_service.write_dir(root, 'video') / 'output'
        return [json.loads((folder / name).read_text(encoding='utf-8'))
                for name in video_task_state.MANIFEST_NAMES]

    def test_req_s10_21_manifest_names_are_the_declared_stage_outputs(self):
        import stage_layout
        row = next(item for item in stage_layout.STAGES if item[1] == 'video')
        self.assertEqual(video_task_state.MANIFEST_NAMES, ('videos.json', 'video_manifest.json'))
        self.assertIn('videos.json', row[5])

    def test_req_s10_21_download_review_and_pin_write_both_manifests(self):
        with tempfile.TemporaryDirectory() as folder:
            studio = _studio(folder)
            state = studio.state()
            version = {'version': 1, 'state': 'running', 'created': 0}
            state['shots']['S001'].append(version)
            dest = studio.root / 'data' / 'S001' / 'v001' / 'S001.mp4'
            dest.parent.mkdir(parents=True)
            dest.write_bytes(b'video')
            with patch.object(engine.Studio, 'record_video_usage'):
                studio.publish_downloaded_video(state, 'S001', version, dest, {'errors': []})
            first, second = self.read_manifests(studio.root)
            self.assertEqual(first, second)
            self.assertEqual(first['stage'], 'video')
            self.assertEqual(first['shot_count'], 2)
            self.assertEqual(first['adopted_count'], 0)
            studio.review('S001', 'pass', '')
            first, _second = self.read_manifests(studio.root)
            row = next(item for item in first['shots'] if item['id'] == 'S001')
            self.assertEqual((first['adopted_count'], row['adopted_version']), (1, 1))
            self.assertTrue(row['file'].endswith('S001.mp4'))
            self.assertEqual(len(row['sha256']), 64)
            studio.pin_version('S001', None)
            self.assertEqual(self.read_manifests(studio.root)[0]['adopted_count'], 1)

    def test_req_s10_21_manifest_write_failure_does_not_break_the_download(self):
        with tempfile.TemporaryDirectory() as folder:
            studio = _studio(folder)
            with patch('engine.save', side_effect=OSError('disk')), self.assertLogs('engine', 'WARNING'):
                studio.publish_manifest()

    def test_req_s10_31_limit_is_100_shots_with_a_clear_error(self):
        self.assertEqual(video_task_state.VIDEO_MAX_SHOTS, 100)
        with tempfile.TemporaryDirectory() as folder:
            self.assertEqual(len(_studio(folder, 100).episode['shots']), 100)
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(ValueError, '101.*100'):
                _studio(folder, 101)

    def test_req_s10_31_deleted_shots_do_not_count(self):
        shots = [{'id': 'S%d' % i} for i in range(100)] + [{'id': 'X', 'video_deleted': True}]
        self.assertEqual(video_task_state.shot_count_error(shots), '')
        self.assertTrue(video_task_state.shot_count_error(shots + [{'id': 'Y'}]))


if __name__ == '__main__':
    unittest.main()

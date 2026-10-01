import tempfile
import unittest
from pathlib import Path

from agent.core import save
from storyboard_rows_service import frame_rows, rows_from_sources, shot_stats


class StoryboardRowsServiceTests(unittest.TestCase):
    def test_current_scope_keeps_plain_ids(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / 'EP001_分镜.json'
            episode = {'episode_id': 'EP001', 'shots': [
                {'id': 'EP001_SH001', 'frame': 'frames/a.png'},
                {'id': 'EP001_SH002', 'frame': 'frames/b.png'},
            ]}
            save(source, episode)
            rows = frame_rows(root, source, episode, root)
            self.assertEqual([row[0] for row in rows], ['EP001_SH001', 'EP001_SH002'])
            self.assertEqual([row[2] for row in rows], [source.resolve(), source.resolve()])

    def test_duplicate_ids_receive_source_suffix(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            first = root / 'EP001_分镜.json'
            second = root / 'EP002_分镜.json'
            one = {'episode_id': 'EP001', 'shots': [{'id': 'SH001', 'frame': 'frames/a.png'}]}
            two = {'episode_id': 'EP002', 'shots': [{'id': 'SH001', 'frame': 'frames/b.png'}]}
            rows = rows_from_sources([(first, root, one), (second, root, two)])
            self.assertEqual([row[0] for row in rows], ['SH001@EP001_分镜', 'SH001@EP002_分镜'])

    def test_shot_stats_counts_only_existing_non_deleted_frames(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'frames').mkdir()
            (root / 'frames' / 'a.png').write_bytes(b'png')
            source = root / 'EP001_分镜.json'
            save(source, {'shots': [
                {'id': 'SH001', 'frame': 'frames/a.png'},
                {'id': 'SH002', 'frame': 'frames/missing.png'},
                {'id': 'SH003', 'frame': 'frames/a.png', 'frame_deleted': True},
            ]})
            self.assertEqual(shot_stats([source]), (3, 1))

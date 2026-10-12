# -*- coding: utf-8 -*-
"""采用前影响预览：与同集已采用分镜的新增／删除／改动与将失效首帧／视频（只读）。"""
import json
import tempfile
import unittest
from pathlib import Path

import file_cache
from stage_execution_service import storyboard_adoption_impact


def shot(sid, **extra):
    data = {'id': sid, 'title': sid, 'duration': 5, 'video_prompt': '待填写',
            'characters': [], 'location': None, 'props': [], 'first_frame_assets': [],
            'frame': 'frames/%s.png' % sid, 'dialogue': []}
    data.update(extra)
    return data


def board(root, episode_id, shots, name='episode.json'):
    folder = root / '03初步分镜' / '分镜文档'
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    path.write_text(json.dumps({'episode_id': episode_id, 'title': '测试',
                                'duration': sum(s.get('duration', 0) for s in shots),
                                'shots': shots}, ensure_ascii=False), encoding='utf-8')
    return path


def adopt(project, source):
    (project / 'ui_settings.json').write_text(json.dumps(
        {'adopted_storyboards': [Path(source).resolve().relative_to(project).as_posix()]},
        ensure_ascii=False), encoding='utf-8')


class AdoptionImpactTests(unittest.TestCase):
    def setUp(self):
        file_cache.clear()
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name) / '项目'
        self.root.mkdir(parents=True)
        self.addCleanup(self._tmp.cleanup)

    def impact(self, paths):
        file_cache.clear()
        return storyboard_adoption_impact(self.root, paths)

    def test_reorder_reports_reorder_without_adding_or_removing(self):
        base = board(self.root, 'EP001', [shot('SH001'), shot('SH002'), shot('SH003')])
        adopt(self.root, base)
        candidate = board(self.root, 'EP001', [shot('SH002'), shot('SH001'), shot('SH003')],
                          name='episode_2.json')
        before = candidate.read_bytes()
        result = self.impact([candidate])
        row = result['episodes'][0]
        self.assertEqual(row['added'], [])
        self.assertEqual(row['removed'], [])
        self.assertEqual(row['changed'], [])
        self.assertEqual(row['reordered'], ['SH002', 'SH001'])
        self.assertIn('重排', result['summary'])
        self.assertEqual(candidate.read_bytes(), before, '预览不得改写镜头编号或文件')

    def test_removed_shot_orphans_first_frame_and_video(self):
        base = board(self.root, 'EP001', [shot('SH001'), shot('SH002')])
        frame = self.root / '03初步分镜' / 'frames' / 'SH001.png'
        frame.parent.mkdir(parents=True, exist_ok=True)
        frame.write_bytes(b'PNG')
        (self.root / 'data').mkdir()
        (self.root / 'data' / 'state.json').write_text(json.dumps(
            {'schema': 1, 'shots': {'SH001': [{'version': 1}], 'SH002': []}}), encoding='utf-8')
        adopt(self.root, base)
        candidate = board(self.root, 'EP001', [shot('SH002')], name='episode_2.json')
        result = self.impact([candidate])
        self.assertEqual(result['episodes'][0]['removed'], ['SH001'])
        self.assertEqual(result['frames'], [str(frame.resolve())])
        self.assertEqual(result['videos'], ['SH001'])
        self.assertIn('首帧将失效', result['summary'])
        self.assertIn('视频将失效', result['summary'])

    def test_dialogue_only_change_is_reported_and_keeps_media(self):
        lines = [{'speaker': '甲', 'text': '走', 'start': 0, 'end': 1}]
        base = board(self.root, 'EP001', [shot('SH001', dialogue=lines)])
        adopt(self.root, base)
        candidate = board(self.root, 'EP001',
                          [shot('SH001', dialogue=[{'speaker': '甲', 'text': '别走', 'start': 0, 'end': 1}])],
                          name='episode_2.json')
        result = self.impact([candidate])
        row = result['episodes'][0]
        self.assertEqual(row['changed'], [{'id': 'SH001', 'fields': ['dialogue']}])
        self.assertEqual(result['frames'], [])
        self.assertEqual(result['videos'], [])

    def test_asset_replace_is_reported_and_invalidates_frame(self):
        base = board(self.root, 'EP001', [shot('SH001', characters=['CHAR_001'])])
        frame = self.root / '03初步分镜' / 'frames' / 'SH001.png'
        frame.parent.mkdir(parents=True, exist_ok=True)
        frame.write_bytes(b'PNG')
        adopt(self.root, base)
        candidate = board(self.root, 'EP001', [shot('SH001', characters=['CHAR_002'])],
                          name='episode_2.json')
        result = self.impact([candidate])
        row = result['episodes'][0]
        self.assertEqual(row['changed'][0]['id'], 'SH001')
        self.assertIn('assets', row['changed'][0]['fields'])
        self.assertEqual(result['frames'], [str(frame.resolve())])

    def test_fresh_adopt_without_baseline_is_all_added(self):
        candidate = board(self.root, 'EP001', [shot('SH001'), shot('SH002')])
        result = self.impact([candidate])
        row = result['episodes'][0]
        self.assertEqual(row['base'], '')
        self.assertEqual(row['added'], ['SH001', 'SH002'])
        self.assertIn('+2 镜', result['summary'])

    def test_preview_is_read_only_for_prefs_and_files(self):
        base = board(self.root, 'EP001', [shot('SH001')])
        adopt(self.root, base)
        candidate = board(self.root, 'EP001', [shot('SH001')], name='episode_2.json')
        prefs = self.root / 'ui_settings.json'
        before_prefs = prefs.read_bytes()
        before_candidate = candidate.read_bytes()
        self.impact([candidate])
        self.assertEqual(prefs.read_bytes(), before_prefs, '取消采用前预览不得改正式采用清单')
        self.assertEqual(candidate.read_bytes(), before_candidate)

    def test_duration_change_is_reported_and_invalidates_existing_frame(self):
        base = board(self.root, 'EP001', [shot('SH001', duration=5)])
        frame = self.root / '03初步分镜' / 'frames' / 'SH001.png'
        frame.parent.mkdir(parents=True, exist_ok=True)
        frame.write_bytes(b'PNG')
        adopt(self.root, base)
        candidate = board(self.root, 'EP001', [shot('SH001', duration=8)], name='episode_2.json')
        result = self.impact([candidate])
        self.assertEqual(result['episodes'][0]['changed'][0]['fields'], ['duration'])
        self.assertEqual(result['frames'], [str(frame.resolve())])


if __name__ == '__main__':
    unittest.main()

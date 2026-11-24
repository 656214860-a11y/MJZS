# -*- coding: utf-8 -*-
"""视频持久过期标记：版本记录签名 vs 同一口径现算指纹（只读，不落盘第二份真源）。"""
import json
import tempfile
import unittest
from pathlib import Path

import video_staleness


class VideoStalenessTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.source = self.root / 'episode.json'
        self.source.write_text(json.dumps({'episode_id': 'EP001', 'shots': [
            {'id': 'SH001', 'duration': 5, 'video_prompt': '雨夜街头'},
            {'id': 'SH002', 'duration': 6, 'video_prompt': '咖啡馆对话'},
        ]}), encoding='utf-8')

    def shot(self, sid, prompt):
        return {'id': sid, 'duration': 5 if sid == 'SH001' else 6, 'video_prompt': prompt}

    def version(self, signature):
        return {'version': 1, 'state': 'downloaded', 'review': 'pass', 'signature': signature}

    def test_current_signature_is_stable_across_reads(self):
        first = video_staleness.current_signature(self.source, self.shot('SH001', '雨夜街头'))
        second = video_staleness.current_signature(self.source, self.shot('SH001', '雨夜街头'))
        self.assertTrue(first)
        self.assertEqual(first, second)

    def test_version_not_stale_when_signature_matches_current(self):
        current = video_staleness.current_signature(self.source, self.shot('SH001', '雨夜街头'))
        self.assertFalse(video_staleness.version_is_stale(self.version(current), current))
        self.assertTrue(video_staleness.version_is_stale(self.version('旧指纹'), current))

    def test_stale_shots_flags_only_mismatched_generated_shots(self):
        generated = {
            'SH001': [self.version(video_staleness.current_signature(self.source, self.shot('SH001', '雨夜街头')))],
            'SH002': [self.version('旧指纹')],
        }
        self.assertEqual(video_staleness.stale_shots(self.source, set(generated), generated), ['SH002'])

    def test_stale_shots_empty_when_no_generated_versions(self):
        generated = {'SH001': [{'version': 1, 'state': 'failed'}]}
        self.assertEqual(video_staleness.stale_shots(self.source, set(generated), generated), [])

    def test_stale_shots_empty_when_all_match(self):
        generated = {'SH001': [self.version(video_staleness.current_signature(self.source, self.shot('SH001', '雨夜街头')))]}
        self.assertEqual(video_staleness.stale_shots(self.source, set(generated), generated), [])


if __name__ == '__main__':
    unittest.main()

# -*- coding: utf-8 -*-
"""当前阶段目录辅助函数的回归测试。"""
import tempfile
import unittest
from pathlib import Path

from contract import project_stages as stages


class ProjectStagePathTests(unittest.TestCase):
    def test_audio_editing_and_delivery_outputs_stay_in_numbered_stages(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.assertEqual(stages.audio(root), root / '11配音与字幕' / '音频')
            self.assertEqual(stages.subtitles(root), root / '11配音与字幕' / '字幕')
            self.assertEqual(stages.editing(root), root / '12后期剪辑')
            self.assertEqual(stages.delivery(root), root / '13质检交付')
            self.assertEqual(stages.exports(root), root / '13质检交付' / '导出成片')
            self.assertFalse((root / 'audio').exists())
            self.assertFalse((root / 'editing').exists())
            self.assertFalse((root / 'exports').exists())

# -*- coding: utf-8 -*-
"""视频/音频卡片（R3136）：试听/播放、确认采用、重新生成、导出 SRT。

运行：python tests/test_video_audio_card.py（真 Tk；运行器会切隐藏桌面）
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from skip_reasons import PLATFORM_TKINTER
from ui import ui_media_player


class MediaPlayerCardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import tkinter as tk
            cls.tk = tk
        except Exception:
            cls.tk = None

    def setUp(self):
        if self.tk is None:
            self.skipTest(PLATFORM_TKINTER)
        self.win = self.tk.Tk()
        self.win.withdraw()
        self.addCleanup(self.win.destroy)

    @staticmethod
    def _buttons(frame):
        return {child.cget('text'): child for child in frame.winfo_children()[-1].winfo_children()
                if child.winfo_class() == 'TButton'}

    def test_audio_card_play_confirm_regenerate_export(self):
        seen = []
        frame = ui_media_player.build_audio_card(
            self.win, 'vo.mp3',
            hooks={'play': lambda path: seen.append(('play', path)),
                   'confirm': lambda path: seen.append(('confirm', path)),
                   'regenerate': lambda path: seen.append(('regen', path)),
                   'export': lambda path: seen.append(('export', path))})
        buttons = self._buttons(frame)
        self.assertEqual(set(buttons), {'试听', '导出 SRT', '确认采用', '重新生成'})
        buttons['试听'].invoke()
        buttons['导出 SRT'].invoke()
        buttons['确认采用'].invoke()
        buttons['重新生成'].invoke()
        self.assertEqual(seen, [('play', 'vo.mp3'), ('export', 'vo.mp3'),
                                ('confirm', 'vo.mp3'), ('regen', 'vo.mp3')])

    def test_video_card_play_confirm_regenerate(self):
        seen = []
        frame = ui_media_player.build_video_card(
            self.win, 'clip.mp4',
            on_play=lambda path: seen.append(('play', path)),
            on_confirm=lambda path: seen.append(('confirm', path)),
            on_regenerate=lambda path: seen.append(('regen', path)))
        buttons = self._buttons(frame)
        self.assertEqual(set(buttons), {'播放', '确认采用', '重新生成'})
        buttons['播放'].invoke()
        self.assertEqual(seen, [('play', 'clip.mp4')])


if __name__ == '__main__':
    unittest.main()

# -*- coding: utf-8 -*-
"""多模态参考上传（R3136）：图片/音频参考 → FILE part，不支持的类型拒绝。

运行：python tests/test_multimodal_upload.py
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ui import ui_multimodal


class MultimodalUploadTests(unittest.TestCase):
    def test_reference_part_classifies_image_and_audio(self):
        image = ui_multimodal.reference_part('ref.png')
        self.assertEqual(image['type'], 'file')
        self.assertEqual(image['payload']['kind'], 'image')
        self.assertEqual(image['payload']['name'], 'ref.png')
        self.assertEqual(ui_multimodal.reference_part('ref.mp3')['payload']['kind'], 'audio')
        self.assertIsNone(ui_multimodal.reference_part('notes.txt'))

    def test_attach_references_rejects_unsupported(self):
        parts, rejected = ui_multimodal.attach_references(['a.png', 'b.mp3', 'c.txt'])
        self.assertEqual(len(parts), 2)
        self.assertEqual(rejected, ['c.txt'])


if __name__ == '__main__':
    unittest.main()

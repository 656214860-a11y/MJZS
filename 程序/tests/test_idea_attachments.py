# -*- coding: utf-8 -*-
"""剧本准备文本附档服务的无 Tk 回归。"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

HERE = str(Path(__file__).resolve().parents[1])
sys.path.insert(0, HERE)
os.chdir(HERE)

import idea_attachments


class IdeaAttachmentsTests(unittest.TestCase):
    def test_attachment_service_reads_only_bounded_text_files(self):
        with tempfile.TemporaryDirectory() as td:
            source = Path(td) / '资料.txt'
            source.write_text('人物：林默', encoding='utf-8')
            prepared = idea_attachments.prepare((source,))
            self.assertEqual(prepared['names'], ('资料.txt',))
            self.assertIn('<attachment_text>\n人物：林默', prepared['context'])
            binary = Path(td) / '图片.png'
            binary.write_bytes(b'not an image')
            with self.assertRaisesRegex(ValueError, '仅支持文本附档'):
                idea_attachments.prepare((binary,))

    def test_upload_is_archived_as_markdown_and_recent_files_are_referenced(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            first = root / 'first.txt'; first.write_text('第一份创意', encoding='utf-8')
            second = root / 'second.md'; second.write_text('第二份创意', encoding='utf-8')
            from stage_execution_service import archive_idea_attachments
            archived = archive_idea_attachments(root, (first, second))
            self.assertEqual(len(archived), 2)
            self.assertTrue(all(path.parent.name == '输入' and path.suffix == '.md' for path in archived))
            self.assertEqual(archived[0].read_text(encoding='utf-8').strip(), '第一份创意')
            prepared = idea_attachments.referenced(root, '请使用上传的文件')
            self.assertEqual(set(prepared['names']), {path.name for path in archived})
            self.assertIn('第一份创意', prepared['context'])

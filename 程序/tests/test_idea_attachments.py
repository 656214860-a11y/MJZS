# -*- coding: utf-8 -*-
"""剧本准备文本附档服务的无 Tk 回归。"""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

HERE = str(Path(__file__).resolve().parents[1])
sys.path.insert(0, HERE)
os.chdir(HERE)

import idea_attachments
from service_contract import SystemError, UserError
from stage_execution_service import project_context


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
            prepared = idea_attachments.referenced(project_context(root), '请使用上传的文件')
            self.assertEqual(set(prepared['names']), {path.name for path in archived})
            self.assertIn('第一份创意', prepared['context'])

    def test_store_returns_paths_in_result(self):
        from agent.core import save_text
        def publish(target, text):
            save_text(target, text)
            return target
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / 'input.txt'
            source.write_text('创意', encoding='utf-8')
            result = idea_attachments.store(project_context(root), [source], publish=publish)
            self.assertTrue(result.ok)
            self.assertIsInstance(result.data, tuple)
            self.assertEqual(result.data[0].read_text(encoding='utf-8'), '创意\n')

    def test_invalid_attachment_returns_user_error_before_publish(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            empty = root / 'empty.txt'; empty.touch()
            damaged = root / 'bad.docx'; damaged.write_bytes(b'not a docx')
            publisher = Mock()
            cases = ([root / 'missing.txt'], [empty], [damaged],
                     [root / ('%d.txt' % index) for index in range(6)])
            for paths in cases:
                with self.subTest(paths=paths):
                    result = idea_attachments.store(project_context(root), paths, publish=publisher)
                    self.assertIsInstance(result, UserError)
                    self.assertFalse(result.ok)
            publisher.assert_not_called()

    def test_read_and_publish_io_failure_returns_system_error(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / 'input.txt'; source.write_text('创意', encoding='utf-8')
            for point in ('read_source', 'publish'):
                with self.subTest(point=point), self.assertLogs('idea_attachments', level='ERROR'):
                    publisher = Mock(side_effect=OSError('private-location'))
                    if point == 'read_source':
                        with patch('idea_attachments.read_source', side_effect=OSError('private-location')):
                            result = idea_attachments.store(project_context(root), [source], publish=publisher)
                        publisher.assert_not_called()
                    else:
                        result = idea_attachments.store(project_context(root), [source], publish=publisher)
                    self.assertIsInstance(result, SystemError)
                    self.assertIsNone(result.data)
                    self.assertNotIn('private-location', result.reason)

    def test_docx_io_cause_is_system_error_not_input_error(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / 'input.docx'; source.write_bytes(b'docx')
            with patch('idea_attachments.zipfile.ZipFile', side_effect=OSError('private-location')):
                with self.assertLogs('idea_attachments', level='ERROR'):
                    result = idea_attachments.store(project_context(root), [source], publish=Mock())
            self.assertIsInstance(result, SystemError)

    def test_publisher_programming_error_is_not_masked(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / 'input.txt'; source.write_text('创意', encoding='utf-8')
            for failure in (TypeError('broken'), KeyError('broken'), ValueError('publisher bug')):
                with self.subTest(failure=type(failure).__name__), self.assertRaises(type(failure)):
                    idea_attachments.store(project_context(root), [source], publish=Mock(side_effect=failure))
            with self.assertRaises(TypeError):
                idea_attachments.store(project_context(root), [source])

    def test_l3_checks_failed_store_result(self):
        from stage_execution_service import archive_idea_attachments
        with patch('idea_attachments.store', return_value=SystemError('失败')):
            with self.assertRaisesRegex(ValueError, '失败'):
                archive_idea_attachments('.', [])

"""引用附档的转换正文只供简报提取，不能进入本地 Agent 投递文本。"""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from domain import idea_attachments
import idea_chat
from orchestrator.idea_chat_controller import IdeaChatController
from stage_execution_service import (archive_idea_attachments, idea_chat_gateway,
    project_context, stage_idea_attachment_reference, stage_idea_brief_defaults)


@patch('stage_execution_service.idea_attachment_local_mode', return_value=True)
class AttachmentBriefTests(unittest.TestCase):
    def test_local_converted_body_fills_brief_but_never_submission_or_raw(self, _mode):
        body = '故事梗概：旧照片显影未来。\n故事角色：摄影师阿青\n故事题材：悬疑\n故事集数：12集\n交付形态：markdown'
        with tempfile.TemporaryDirectory() as td:
            source = Path(td) / '创意.txt'
            source.write_text(body, encoding='utf-8')
            archived = archive_idea_attachments(td, (source,))
            controller = IdeaChatController()
            controller.replace_attachments(archived)
            prepared = controller.prepare_submission(td, '', is_example=False)
            reference = prepared['attachments']
            context = project_context(td)
            result = idea_chat.receive_brief(context, prepared['submission'],
                gateway=idea_chat_gateway(), attachment_reference=reference)
            self.assertEqual(result['missing'], ())
            self.assertEqual(result['fields']['story_summary'], '旧照片显影未来。')
            self.assertEqual(result['fields']['main_characters'], '摄影师阿青')
            values = idea_chat.brief_creation_values(context, attachment_reference=reference)
            self.assertEqual(values['故事梗概'], '旧照片显影未来。')
            self.assertIn(archived[0].relative_to(td).as_posix(), prepared['submission'])
            self.assertIn('请先读取', prepared['submission'])
            for text in (prepared['submission'], prepared['visible_value'],
                         result['raw_path'].read_text(encoding='utf-8')):
                self.assertNotIn('旧照片显影未来', text)
                self.assertNotIn('<attachment_text>', text)

    def test_explicit_reference_is_reused_without_a_second_scan(self, _mode):
        with tempfile.TemporaryDirectory() as td:
            paths = []
            for index in range(2):
                source = Path(td) / ('创意%d.txt' % index)
                source.write_text('故事梗概：第%d份素材。' % index, encoding='utf-8')
                paths.extend(archive_idea_attachments(td, (source,)))
            with patch('domain.idea_attachments.uploaded', wraps=idea_attachments.uploaded) as scan:
                reference = stage_idea_attachment_reference(td, '@' + paths[0].name)
                with patch('stage_execution_service.stage_idea_attachment_reference',
                           side_effect=AssertionError('must reuse reference')):
                    defaults = stage_idea_brief_defaults(td, reference=reference)
                self.assertEqual(scan.call_count, 1)
            self.assertEqual(defaults['values']['故事梗概'], '第0份素材。')
            self.assertNotIn('第1份', ''.join(reference['brief_texts']))

    def test_unreadable_original_remains_missing_with_explicit_notice(self, _mode):
        with tempfile.TemporaryDirectory() as td:
            source = Path(td) / '原件.pdf'
            source.write_bytes(b'%PDF-unparsed')
            archive_idea_attachments(td, (source,))
            reference = stage_idea_attachment_reference(td)
            result = idea_chat.receive_brief(project_context(td), reference['context'],
                gateway=idea_chat_gateway(), attachment_reference=reference)
            self.assertTrue(result['missing'])
            self.assertIsNone(result['complete_path'])
            self.assertIn('引用附档无本地可读转换稿,请补充填写或改用 .md/.txt 重新上传',
                          result['attachment_notice'])
            self.assertEqual(reference['brief_texts'], ())

    def test_header_only_xlsx_conversion_cannot_complete_brief(self, _mode):
        from tests.test_idea_attachments import IdeaAttachmentsTests
        with tempfile.TemporaryDirectory() as td:
            source = Path(td) / '表头.xlsx'
            labels = ('故事梗概', '故事角色', '故事题材', '故事集数', '单集时间')
            rows = ''.join('<row><c t="inlineStr"><is><t>%s</t></is></c>'
                           '<c t="inlineStr"><is><t>%s</t></is></c></row>' % (label, label)
                           for label in labels)
            IdeaAttachmentsTests().make_xlsx(source, {'xl/worksheets/sheet1.xml':
                '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                '<sheetData>' + rows + '</sheetData></worksheet>'})
            archive_idea_attachments(td, (source,))
            reference = stage_idea_attachment_reference(td)
            result = idea_chat.receive_brief(project_context(td), reference['context'],
                gateway=idea_chat_gateway(), attachment_reference=reference)
            for field in ('story_summary', 'main_characters', 'genre', 'length'):
                self.assertIn(field, result['missing'])
            self.assertIsNone(result['complete_path'])


if __name__ == '__main__':
    unittest.main()

"""Office 附档资源预算；全部使用临时文件与合成内容。"""
import io
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import Mock, patch
import zipfile

import idea_attachments
from service_contract import UserError
from stage_execution_service import project_context
from tests import test_idea_attachments as fixtures


class OfficeBudgetTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def docx(self, text):
        path = self.root / '创意.docx'
        raw = ('<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
               '<w:body><w:p><w:r><w:t>' + text + '</w:t></w:r></w:p></w:body></w:document>').encode()
        with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('word/document.xml', raw)
        return path, raw

    def xlsx(self, overrides=None):
        path = self.root / '创意.xlsx'
        fixtures.IdeaAttachmentsTests().make_xlsx(path, overrides)
        return path

    def test_normal_chinese_docx_keeps_text(self):
        path, _ = self.docx('角色：林默；故事：雨夜重逢')
        self.assertEqual(idea_attachments.read_source(path), '角色：林默；故事：雨夜重逢')

    def test_compressed_docx_declared_size_rejected_before_open(self):
        path, _ = self.docx('x' * 300_000)
        self.assertLess(path.stat().st_size, idea_attachments.MAX_FILE_BYTES)
        with patch.object(idea_attachments, 'MAX_XML_MEMBER_BYTES', 1024, create=True):
            with patch.object(zipfile.ZipFile, 'open', side_effect=AssertionError('must reject before opening')):
                with self.assertRaisesRegex(ValueError, '解压.*上限') as caught:
                    idea_attachments.read_source(path)
        self.assertNotIn(str(self.root), str(caught.exception))

    def test_actual_read_is_bounded_even_if_declared_size_is_small(self):
        path, raw = self.docx('x' * 1000)
        stream = io.BytesIO(raw)
        read = Mock(wraps=stream.read)
        stream.read = read
        archive = Mock()
        archive.__enter__ = Mock(return_value=archive)
        archive.__exit__ = Mock(return_value=False)
        archive.getinfo.return_value = SimpleNamespace(file_size=1)
        archive.open.return_value = stream
        archive.read.return_value = raw
        with patch.object(idea_attachments, 'MAX_XML_MEMBER_BYTES', 256, create=True):
            with patch('idea_attachments.zipfile.ZipFile', return_value=archive):
                with self.assertRaisesRegex(ValueError, '解压.*上限'):
                    idea_attachments.read_source(path)
        read.assert_called_once_with(257)
        archive.read.assert_not_called()

    def test_xlsx_cumulative_xml_budget(self):
        path = self.xlsx()
        with zipfile.ZipFile(path) as archive:
            sizes = [archive.getinfo(name).file_size for name in (
                'xl/workbook.xml', 'xl/_rels/workbook.xml.rels',
                'xl/sharedStrings.xml', 'xl/worksheets/sheet1.xml')]
        with patch.object(idea_attachments, 'MAX_XML_MEMBER_BYTES', max(sizes) + 1, create=True):
            with patch.object(idea_attachments, 'MAX_XML_TOTAL_BYTES', sum(sizes) - 1, create=True):
                with self.assertRaisesRegex(ValueError, '解压.*上限'):
                    idea_attachments.read_source(path)

    def test_each_xlsx_xml_kind_has_member_budget(self):
        path = self.xlsx()
        with zipfile.ZipFile(path) as archive:
            originals = {name: archive.read(name).decode() for name in (
                'xl/workbook.xml', 'xl/_rels/workbook.xml.rels',
                'xl/sharedStrings.xml', 'xl/worksheets/sheet1.xml')}
        for member, raw in originals.items():
            with self.subTest(member=member):
                path = self.xlsx({member: raw + ' ' * 2200})
                with patch.object(idea_attachments, 'MAX_XML_MEMBER_BYTES', 2000, create=True):
                    with self.assertRaisesRegex(ValueError, '解压.*上限'):
                        idea_attachments.read_source(path)

    def test_shared_string_repetition_has_converted_text_budget(self):
        ns = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
        path = self.xlsx({
            'xl/sharedStrings.xml': f'<sst xmlns="{ns}"><si><t>' + '字' * 60 + '</t></si></sst>',
            'xl/worksheets/sheet1.xml': f'<worksheet xmlns="{ns}"><sheetData><row>'
                '<c t="s"><v>0</v></c><c t="s"><v>0</v></c></row></sheetData></worksheet>',
        })
        with patch.object(idea_attachments, 'MAX_CONVERTED_CHARS', 100, create=True):
            with self.assertRaisesRegex(ValueError, '转换.*上限'):
                idea_attachments.read_source(path)

    def test_docx_converted_text_budget(self):
        path, _ = self.docx('中文' * 100)
        with patch.object(idea_attachments, 'MAX_CONVERTED_CHARS', 100, create=True):
            with self.assertRaisesRegex(ValueError, '转换.*上限'):
                idea_attachments.read_source(path)

    def test_local_keeps_raw_but_api_rejects_over_budget_conversion(self):
        path, _ = self.docx('x' * 1000)
        publish = Mock(side_effect=lambda target, content: target)
        with patch.object(idea_attachments, 'MAX_XML_MEMBER_BYTES', 256, create=True):
            result = idea_attachments.store(project_context(self.root), (path,), publish=publish)
            self.assertIsInstance(result, UserError)
            publish.assert_not_called()
            result = idea_attachments.store(project_context(self.root), (path,), publish=publish, local_mode=True)
        self.assertTrue(result.ok)
        publish.assert_called_once()
        self.assertEqual(publish.call_args.args[1], path.read_bytes())

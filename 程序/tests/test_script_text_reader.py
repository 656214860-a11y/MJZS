"""剧本文本读取：docx 正文 XML 有解压体积上限，恶意压缩包不能拖垮应用。"""
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

import script_text_reader

_BODY = ('<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
         '<w:body><w:p><w:r><w:t>{}</w:t></w:r></w:p></w:body></w:document>')


def _docx(folder, text):
    path = Path(folder) / 'script.docx'
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('word/document.xml', _BODY.format(text))
    return path


class DocxBudgetTests(unittest.TestCase):
    def test_normal_docx_is_read(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertEqual(script_text_reader.script_text(_docx(folder, '你好')), '你好')

    def test_oversized_document_xml_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path = _docx(folder, 'a' * 5000)
            with mock.patch.object(script_text_reader, 'MAX_DOCX_XML_BYTES', 100):
                with self.assertRaisesRegex(ValueError, '过大'):
                    script_text_reader.script_text(path)


if __name__ == '__main__':
    unittest.main()

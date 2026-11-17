"""Read user-provided Markdown, text, or Word screenplay documents."""
from pathlib import Path
from infra.file_cache import read_bytes

# Word 正文 XML 解压后的上限：正常剧本远小于此，恶意压缩包（解压炸弹）会被拦在读取阶段。
MAX_DOCX_XML_BYTES = 20_000_000


def script_text(path):
    path = Path(path)
    if path.suffix.lower() == '.docx':
        import xml.etree.ElementTree as ET
        import zipfile
        try:
            with zipfile.ZipFile(path) as archive:
                with archive.open('word/document.xml') as member:
                    raw_xml = member.read(MAX_DOCX_XML_BYTES + 1)
            if len(raw_xml) > MAX_DOCX_XML_BYTES:
                raise ValueError('Word 剧本正文过大（解压后超过 20 MB），请拆分后再导入')
            document = ET.fromstring(raw_xml)
        except (zipfile.BadZipFile, KeyError, ET.ParseError):
            raise ValueError('Word 剧本文件损坏或不是有效的 .docx，请另存后重试') from None
        ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
        text = '\n'.join(''.join(row.itertext()) for row in document.findall('.//w:p', ns))
    elif path.suffix.lower() in ('.txt', '.md'):
        raw = read_bytes(path)
        try:
            text = raw.decode('utf-8-sig')
        except UnicodeDecodeError:
            try:
                text = raw.decode('utf-16') if raw[:2] in (b'\xff\xfe', b'\xfe\xff') else raw.decode('gb18030')
            except UnicodeDecodeError:
                raise ValueError('无法识别剧本文件编码，请另存为 UTF-8 文本') from None
    else:
        raise ValueError('请选择 Markdown、TXT 或 Word 剧本')
    if not text.strip():
        raise ValueError('当前剧本没有可读取的正文，请先填写剧本')
    return text.strip()

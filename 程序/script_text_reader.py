"""Read user-provided Markdown, text, or Word screenplay documents."""
from pathlib import Path
from file_cache import read_bytes


def script_text(path):
    path = Path(path)
    if path.suffix.lower() == '.docx':
        import xml.etree.ElementTree as ET
        import zipfile
        try:
            with zipfile.ZipFile(path) as archive:
                document = ET.fromstring(archive.read('word/document.xml'))
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

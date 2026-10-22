"""idea_attachments._read_xlsx 压平：旧实现原样内嵌，与新实现在各类工作簿上逐例对照（含预算计费顺序）。"""
import io
import tempfile
import unittest
import zipfile
from pathlib import Path

import idea_attachments

LEGACY_SRC = r'''def _legacy_read_xlsx(path):
    """按工作簿顺序提取单元格文本；不执行公式、宏或嵌入对象。"""
    if path.stat().st_size > MAX_FILE_BYTES:
        raise ValueError('附档过大（单个文件最多 1 MB）：' + path.name)
    ns = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
    rel_ns = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'
    package_ns = '{http://schemas.openxmlformats.org/package/2006/relationships}'
    try:
        with zipfile.ZipFile(path) as archive:
            budget = _OfficeBudget(archive, path)
            workbook = ET.fromstring(budget.read('xl/workbook.xml'))
            relations = ET.fromstring(budget.read('xl/_rels/workbook.xml.rels'))
            targets = {rel.attrib['Id']: rel.attrib['Target']
                       for rel in relations.findall(package_ns + 'Relationship')
                       if rel.get('TargetMode') != 'External'}
            strings = []
            if 'xl/sharedStrings.xml' in archive.namelist():
                shared = ET.fromstring(budget.read('xl/sharedStrings.xml'))
                strings = [''.join(node.text or '' for node in item.iter(ns + 't'))
                           for item in shared.findall(ns + 'si')]
            lines = []
            for sheet in workbook.findall(ns + 'sheets/' + ns + 'sheet'):
                target = targets[sheet.attrib[rel_ns + 'id']]
                member = posixpath.normpath(target.lstrip('/') if target.startswith('/')
                                           else posixpath.join('xl', target))
                if not member.startswith('xl/worksheets/'):
                    raise KeyError('worksheet target')
                root = ET.fromstring(budget.read(member))
                if lines:
                    budget.text('\n')
                lines.append(budget.text('【工作表：%s】' % sheet.attrib['name']))
                for row in root.findall(ns + 'sheetData/' + ns + 'row'):
                    budget.text('\n')
                    cells = []
                    for cell in row.findall(ns + 'c'):
                        value = cell.findtext(ns + 'v', '')
                        if cell.find(ns + 'f') is not None:
                            pass  # 公式只读取缓存值；没有缓存时保持空白。
                        elif cell.get('t') == 's':
                            if not value.isascii() or not value.isdecimal() or int(value) >= len(strings):
                                raise KeyError('shared string index')
                            value = strings[int(value)]
                        elif cell.get('t') == 'inlineStr':
                            inline = cell.find(ns + 'is')
                            value = (''.join(node.text or '' for node in inline.iter(ns + 't'))
                                     if inline is not None else '')
                        # 数值原样输出，不进行日期序列号换算。
                        if cells:
                            budget.text('\t')
                        cells.append(budget.text(value))
                    lines.append('\t'.join(cells))
        return '\n'.join(lines).strip()
    except (OSError, KeyError, zipfile.BadZipFile, ET.ParseError) as exc:
        raise ValueError('XLSX 无法读取：' + path.name) from exc
'''

NS = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
RNS = 'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"'
PNS = 'xmlns="http://schemas.openxmlformats.org/package/2006/relationships"'


def _workbook(sheets):
    items = ''.join('<sheet name="%s" sheetId="%d" r:id="rId%d"/>' % (name, i + 1, i + 1)
                    for i, (name, _) in enumerate(sheets))
    return '<workbook %s %s><sheets>%s</sheets></workbook>' % (NS, RNS, items)


def _rels(targets, external=()):
    items = ''.join('<Relationship Id="rId%d" Type="t" Target="%s"/>' % (i + 1, t) for i, t in enumerate(targets))
    items += ''.join('<Relationship Id="%s" Type="t" Target="http://x" TargetMode="External"/>' % i for i in external)
    return '<Relationships %s>%s</Relationships>' % (PNS, items)


def _sheet(rows):
    body = ''.join('<row>%s</row>' % ''.join(rows_cells) for rows_cells in rows)
    return '<worksheet %s><sheetData>%s</sheetData></worksheet>' % (NS, body)


def _shared(strings):
    return '<sst %s>%s</sst>' % (NS, ''.join('<si><t>%s</t></si>' % t for t in strings))


def _zip(members):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w') as archive:
        for name, text in members.items():
            archive.writestr(name, text)
    return buffer.getvalue()


def _cells():
    return {
        's0': '<c t="s"><v>0</v></c>', 's1': '<c t="s"><v>1</v></c>', 'num': '<c><v>3.5</v></c>',
        'inline': '<c t="inlineStr"><is><t>行内</t></is></c>', 'inline_empty': '<c t="inlineStr"></c>',
        'formula': '<c><f>A1+1</f><v>9</v></c>', 'formula_nov': '<c t="s"><f>X</f></c>',
        'empty': '<c/>', 'bad_str': '<c t="s"><v>x</v></c>', 'far_str': '<c t="s"><v>99</v></c>',
        'unicode_digit': '<c t="s"><v>\u0661</v></c>', 'neg': '<c t="s"><v>-1</v></c>',
    }


def _base(rows1, rows2=None, shared=('甲', '乙'), targets=None, extra=None, sheets=None):
    sheets = sheets or [('一', None)] + ([('二', None)] if rows2 is not None else [])
    members = {
        'xl/workbook.xml': _workbook(sheets),
        'xl/_rels/workbook.xml.rels': _rels(targets or ['worksheets/sheet1.xml', 'worksheets/sheet2.xml'][:len(sheets)]),
        'xl/worksheets/sheet1.xml': _sheet(rows1),
    }
    if rows2 is not None:
        members['xl/worksheets/sheet2.xml'] = _sheet(rows2)
    if shared is not None:
        members['xl/sharedStrings.xml'] = _shared(shared)
    members.update(extra or {})
    return _zip(members)


def _cases():
    c = _cells()
    yield 'normal', _base([[c['s0'], c['num'], c['s1']], [c['inline'], c['formula']]], [[c['s1']]])
    yield 'empty_cells', _base([[c['empty'], c['inline_empty'], c['formula_nov']], []], [])
    yield 'abs_target', _base([[c['s0']]], targets=['/xl/worksheets/sheet1.xml'])
    yield 'outside_target', _base([[c['s0']]], targets=['../evil.xml'], extra={'evil.xml': _sheet([[c['s0']]])})
    yield 'no_shared_strings', _base([[c['s0']]], shared=None)
    yield 'no_shared_but_num', _base([[c['num']]], shared=None)
    for key in ('bad_str', 'far_str', 'unicode_digit', 'neg'):
        yield key, _base([[c[key]]])
    yield 'external_rel', _zip({
        'xl/workbook.xml': _workbook([('一', None)]),
        'xl/_rels/workbook.xml.rels': _rels([], external=['rId1']),
        'xl/worksheets/sheet1.xml': _sheet([[c['num']]])})
    yield 'missing_sheet_part', _base([[c['num']]], targets=['worksheets/nope.xml'])
    yield 'not_a_zip', b'not a zip'
    yield 'bad_xml', _zip({'xl/workbook.xml': '<a', 'xl/_rels/workbook.xml.rels': '<a/>'})
    yield 'no_sheets', _base([[c['num']]], sheets=[])


def _run(function, data):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / 'book.xlsx'
        path.write_bytes(data)
        try:
            return ('ok', function(path))
        except Exception as exc:
            return (type(exc).__name__, str(exc), type(exc.__cause__).__name__)


class ReadXlsxEquivalence(unittest.TestCase):
    def setUp(self):
        namespace = dict(vars(idea_attachments))
        exec(compile(LEGACY_SRC, 'legacy_read_xlsx', 'exec'), namespace)
        self.namespace = namespace   # 旧实现读自己的全局副本，改上限时两边都要改
        self.legacy = namespace['_legacy_read_xlsx']

    def test_workbooks(self):
        n = 0
        for name, data in _cases():
            self.assertEqual(_run(idea_attachments._read_xlsx, data), _run(self.legacy, data), name)
            n += 1
        self.assertEqual(n, 15)

    def test_budgets_trip_at_the_same_point(self):
        c = _cells()
        data = _base([[c['s0'], c['s1'], c['num']] for _ in range(6)])
        for limit in range(1, 80, 3):
            saved = idea_attachments.MAX_CONVERTED_CHARS
            idea_attachments.MAX_CONVERTED_CHARS = limit
            try:
                self.assertEqual(_run(idea_attachments._read_xlsx, data), _run(self.legacy, data), limit)
            finally:
                idea_attachments.MAX_CONVERTED_CHARS = saved
        for member_limit in (50, 200, 400):
            saved = idea_attachments.MAX_XML_MEMBER_BYTES
            idea_attachments.MAX_XML_MEMBER_BYTES = member_limit
            try:
                self.assertEqual(_run(idea_attachments._read_xlsx, data), _run(self.legacy, data), member_limit)
            finally:
                idea_attachments.MAX_XML_MEMBER_BYTES = saved
        saved = idea_attachments.MAX_FILE_BYTES
        idea_attachments.MAX_FILE_BYTES = self.namespace['MAX_FILE_BYTES'] = 10
        try:
            self.assertEqual(_run(idea_attachments._read_xlsx, data), _run(self.legacy, data))
        finally:
            idea_attachments.MAX_FILE_BYTES = self.namespace['MAX_FILE_BYTES'] = saved


if __name__ == '__main__':
    unittest.main()

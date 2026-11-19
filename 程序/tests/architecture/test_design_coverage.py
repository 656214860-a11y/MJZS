"""设计规格覆盖门禁：SRS 的每个高优先级条目都必须有设计落点（对应 ADR-0004 唯一权威）。

规则来由：用户把「设计覆盖 SRS 全部高优先级需求」定为设计规格的退出条件。
空口说「覆盖了」不可核，因此把 `docs/specs/README.md` 的覆盖映射表变成机器可验的事实：

* PRD 里每个 P0-*／P1-*／P2-* 与 US** 条目，必须在覆盖映射表里出现一行；
* 该行必须指向 `docs/specs/` 下真实存在的分册文件；
* 分册文件必须真的包含被引用的章节号（防止「表格里写了、正文里没有」）。

不做的事：不校验需求描述的文字内容是否准确（那是评审的事），只校验结构性可达。
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

from tests.architecture._scan import ROOT

PROGRAM = ROOT
SPECS = PROGRAM / 'docs' / 'specs'
INDEX = SPECS / 'README.md'
PRD = PROGRAM / '说明' / '产品需求规格.md'

# PRD 里必须被设计规格覆盖的条目。
PRIORITY_ROW = re.compile(r'^\|\s*(P[012]-\d+)\s', re.M)
STORY_ROW = re.compile(r'^\|\s*(US\d{2})\s', re.M)
# 覆盖映射表的表格行：| PRD 条目 | 覆盖册 | 覆盖方式 |
COVERAGE_ROW = re.compile(r'^\|\s*((?:P[012]-\d+)|(?:US\d{2}))[^|]*\|\s*([^|]+)\|\s*([^|]*)\|', re.M)
# 「01 §6」这类引用：册号 + 章节号。
SECTION_REF = re.compile(r'^(\d{2})\s*§\s*([0-9]+(?:\.[0-9]+)*)')


def prd_items() -> tuple[set[str], set[str]]:
    """返回 (优先级条目集合, 用户故事集合)。"""
    text = PRD.read_text(encoding='utf-8')
    return set(PRIORITY_ROW.findall(text)), set(STORY_ROW.findall(text))


def coverage_rows() -> dict[str, str]:
    """覆盖映射表：条目 → 「覆盖册」单元格原文。同一 ID 多行时合并。"""
    text = INDEX.read_text(encoding='utf-8')
    rows: dict[str, str] = {}
    for item, volume, how in COVERAGE_ROW.findall(text):
        rows[item.strip()] = (volume.strip(), how.strip())
    return rows


def spec_files() -> dict[str, Path]:
    files = {path.name[:2]: path for path in sorted(SPECS.glob('[0-9][0-9]_*.md'))}
    # 索引本身也承载设计条款（文档层级、规模基线），登记为 00 册。
    files['00'] = INDEX
    return files


def section_numbers(path: Path) -> set[str]:
    """某分册里出现的章节号（## N. / ### N.M 标题）。"""
    text = path.read_text(encoding='utf-8')
    return {m.group(1) for m in re.finditer(r'^#{2,4}\s+(\d+(?:\.\d+)*)[.\s]', text, re.M)}


def unresolved(rows: dict[str, str], files: dict[str, Path]) -> list[str]:
    """覆盖映射表里指向不存在的册、或不存在的章节的条目。"""
    missing: list[str] = []
    for item, (volume, _how) in sorted(rows.items()):
        refs = SECTION_REF.findall(volume)
        if not refs:
            missing.append(f'{item} → 「{volume}」没有 册号 §章节号 形式的设计落点')
            continue
        for number, section in refs:
            path = files.get(number)
            if path is None:
                missing.append(f'{item} → 引用了不存在的分册 {number}_*.md')
                continue
            sections = section_numbers(path)
            # 允许引用父章节：§3 覆盖 3.1／3.2。
            if not any(s == section or s.startswith(section + '.') for s in sections):
                missing.append(f'{item} → {path.name} 里没有章节 {section}')
    return missing


class DesignCoverageTests(unittest.TestCase):
    def setUp(self):
        self.priorities, self.stories = prd_items()
        self.rows = coverage_rows()
        self.files = spec_files()

    def test_spec_index_exists(self):
        self.assertTrue(INDEX.is_file(), 'docs/specs/README.md 不存在')
        self.assertGreaterEqual(len(self.files), 7,
                                'docs/specs/ 应有 7 个分册（01–07），实际 %d' % len(self.files))

    def test_every_priority_requirement_has_a_landing_place(self):
        missing = sorted(self.priorities - set(self.rows))
        self.assertEqual(missing, [],
                         'PRD 的优先级条目在设计规格里没有落点：%s\n'
                         '请在 docs/specs/README.md §4 的覆盖映射表补行' % '、'.join(missing))

    def test_every_user_story_has_a_landing_place(self):
        missing = sorted(self.stories - set(self.rows))
        self.assertEqual(missing, [],
                         'PRD 的用户故事在设计规格里没有落点：%s\n'
                         '请在 docs/specs/README.md §4 的覆盖映射表补行' % '、'.join(missing))

    def test_coverage_rows_point_at_real_sections(self):
        problems = unresolved(self.rows, self.files)
        self.assertEqual(problems, [],
                         '覆盖映射表指向不存在的位置：\n' + '\n'.join(problems))

    def test_no_stale_coverage_rows(self):
        """覆盖表里出现 PRD 已经没有的条目＝表过期，同样要红。"""
        known = self.priorities | self.stories
        stale = sorted(set(self.rows) - known)
        self.assertEqual(stale, [],
                         '覆盖映射表列了 PRD 里不存在的条目（表已过期）：%s' % '、'.join(stale))

    def test_unresolved_detects_negative_samples(self):
        """负向自测：错册号、错章节、非 § 形式都必须被检出，断言不恒真。"""
        files = {'01': SPECS / '01_架构与技术选型.md'}
        bad = {
            'P0-9': ('99 §1', ''),
            'P0-8': ('01 §999', ''),
            'P0-7': ('01 全文', ''),
        }
        problems = unresolved(bad, files)
        self.assertEqual(len(problems), 3, '三个坏样本应各报一条，实际 %r' % (problems,))

    def test_positive_sample_resolves(self):
        """正样本：真实存在的册与章节必须放行，否则门禁会误报。"""
        files = {'01': SPECS / '01_架构与技术选型.md'}
        self.assertEqual(unresolved({'P0-x': ('01 §1', '')}, files), [])


if __name__ == '__main__':
    unittest.main()

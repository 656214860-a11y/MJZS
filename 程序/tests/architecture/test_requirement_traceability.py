"""文档先行的需求锚定棘轮（AGENTS §2.7 第 4 条）。

REQUIREMENTS.md 里标 ✅ 的需求必须有测试锚定（测试名 ``test_req_s10_03_*`` 或 docstring/注释写
``REQ-S10-03``，支持 ``REQ-S10-01/02/03`` 斜杠简写）。历史上补写文档时已有一批 ✅ 没有锚点，
登记在 ``维护记录/需求锚定基线.json``：

- 新增的 ✅ 需求没有测试锚定即失败（补测试，或降为 🟡）；
- 基线里的编号一旦有了锚点、或不再是 ✅，必须从基线删除（只许减少）；
- 测试里引用了 REQUIREMENTS.md 不存在的编号即失败（编号删除后不复用）。
"""
import json
import re
import unittest
from pathlib import Path

from tests.architecture._scan import ROOT

REQUIREMENTS = ROOT / 'docs' / 'REQUIREMENTS.md'
BASELINE = ROOT / '维护记录' / '需求锚定基线.json'
ROW = re.compile(r'^- \*\*(REQ-S\d+-\d+)\*\*\s*(\S+)', re.M)
DOC_ANCHOR = re.compile(r'(?i)req-s(\d+)-(\d+(?:/\d+)*)')
NAME_ANCHOR = re.compile(r'(?i)req_s(\d+)_(\d+)')


def requirement_status():
    text = REQUIREMENTS.read_text(encoding='utf-8')
    return {m.group(1): m.group(2) for m in ROW.finditer(text)}


def anchored_requirements():
    found = set()
    for path in (ROOT / 'tests').rglob('*.py'):
        if path.name == Path(__file__).name:
            continue
        text = path.read_text(encoding='utf-8', errors='ignore')
        for m in DOC_ANCHOR.finditer(text):
            for number in m.group(2).split('/'):
                found.add(f'REQ-S{m.group(1)}-{number}')
        for m in NAME_ANCHOR.finditer(text):
            found.add(f'REQ-S{m.group(1)}-{m.group(2)}')
    return found


def untested_done_requirements():
    status = requirement_status()
    anchored = anchored_requirements()
    return {rid for rid, mark in status.items() if mark == '✅' and rid not in anchored}


class RequirementTraceabilityTests(unittest.TestCase):
    def test_requirement_ids_are_unique(self):
        ids = ROW.findall(REQUIREMENTS.read_text(encoding='utf-8'))
        seen = [rid for rid, _ in ids]
        self.assertEqual(len(seen), len(set(seen)), '需求编号重复；删除的编号不得复用')

    def test_tests_do_not_reference_unknown_requirements(self):
        unknown = sorted(anchored_requirements() - set(requirement_status()))
        self.assertEqual(unknown, [], '测试引用了 REQUIREMENTS.md 不存在的编号')

    def test_new_done_requirement_needs_a_test_anchor(self):
        baseline = set(json.loads(BASELINE.read_text(encoding='utf-8'))['untested_done'])
        new = sorted(untested_done_requirements() - baseline)
        self.assertEqual(new, [],
                         '以下 ✅ 需求没有测试锚定：补测试（docstring 写 REQ-xx），或降为 🟡')

    def test_baseline_only_shrinks(self):
        baseline = set(json.loads(BASELINE.read_text(encoding='utf-8'))['untested_done'])
        stale = sorted(baseline - untested_done_requirements())
        self.assertEqual(stale, [],
                         '以下编号已有测试锚定或不再是 ✅，请从 维护记录/需求锚定基线.json 删除')


if __name__ == '__main__':
    unittest.main()

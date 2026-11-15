"""规则文件体积预算：模型只加载文件前 16 KB，超出的规则等于不存在（对应 C1）。

``程序/AGENTS.md`` 曾长到 31 KB，§5 自检与 §8 执行协议落在加载上限之后而无人察觉。
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

from tests.architecture._scan import ROOT

REPO = ROOT.parent
BUDGETS = {
    ROOT / 'AGENTS.md': 16000,
    REPO / 'AGENTS.md': 2000,
    REPO / 'CLAUDE.md': 4000,
}
LINK = re.compile(r'\[[^\]]*\]\(([^)#\s]+)(?:#[^)]*)?\)')
MUST_FIT = ('## 5. 自检规则', '## 8. 任务执行协议', '## 2.6 Git 提交门禁')
LIMIT = 16384


def oversize(size, budget):
    return max(0, size - budget)


def broken_links(path: Path):
    text = path.read_text(encoding='utf-8')
    return [target for target in LINK.findall(text)
            if '://' not in target and not (path.parent / target).exists()]


class AgentDocBudgetTests(unittest.TestCase):
    def test_overflow_arithmetic(self):
        self.assertEqual(oversize(100, 100), 0)
        self.assertEqual(oversize(130, 100), 30)

    def test_entry_files_stay_within_budget(self):
        for path, budget in BUDGETS.items():
            size = len(path.read_bytes())
            self.assertEqual(oversize(size, budget), 0,
                             '%s 为 %d 字节，超过预算 %d：先删旧规则，细则写进 runbook.md' % (path.name, size, budget))

    def test_critical_sections_begin_inside_the_loaded_prefix(self):
        data = (ROOT / 'AGENTS.md').read_bytes()
        for heading in MUST_FIT:
            position = data.find(heading.encode('utf-8'))
            self.assertGreaterEqual(position, 0, '缺少 %s' % heading)
            self.assertLess(position, LIMIT, '%s 落在加载上限 %d 字节之后' % (heading, LIMIT))

    def test_relative_links_point_at_existing_files(self):
        for path in BUDGETS:
            self.assertEqual(broken_links(path), [], '%s 有失效链接' % path.name)

    def test_link_checker_flags_a_missing_target(self):
        import tempfile
        with tempfile.TemporaryDirectory() as temporary:
            sample = Path(temporary) / 'x.md'
            sample.write_text('[好](x.md) [坏](missing.md) [外](https://a.b/c)', encoding='utf-8')
            self.assertEqual(broken_links(sample), ['missing.md'])


if __name__ == '__main__':
    unittest.main()

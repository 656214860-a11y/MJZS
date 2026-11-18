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
    # 工程文档体系任务书轮5（R3503）：agent 会整读的工程文档同样受 16 KB 加载窗口约束。
    ROOT / '文档导航.md': 16000,
    ROOT / '说明' / '工程文档登记表.md': 16000,
    ROOT / '说明' / '产品需求规格.md': 16000,
    ROOT / '说明' / '已知坑与不可破坏契约.md': 16000,
    ROOT / '维护记录' / 'README.md': 16000,
    ROOT / 'docs' / 'adr' / 'README.md': 16000,
}
# D10 总量预算：程序/ 根 .md 与 维护记录/ 顶层文件只减不增的上限。
ROOT_MD_BUDGET = 18
MAINTENANCE_FILE_BUDGET = 60
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

    def test_budget_guard_rejects_oversize_sample(self):
        """负向自测：构造超预算样本，证明体积断言确实会红而非恒真。"""
        import tempfile
        with tempfile.TemporaryDirectory() as temporary:
            sample = Path(temporary) / 'big.md'
            sample.write_text('x' * 20000, encoding='utf-8')
            size = len(sample.read_bytes())
            self.assertGreater(oversize(size, 16000), 0,
                               '超预算样本未被 oversize() 检出，预算断言形同虚设')

    def test_program_root_markdown_count_within_budget(self):
        count = len([p for p in ROOT.iterdir() if p.is_file() and p.suffix == '.md'])
        self.assertLessEqual(count, ROOT_MD_BUDGET,
                             '程序/ 根 .md 共 %d 份，超过 D10 预算 %d：新文档进子目录或说明/' % (count, ROOT_MD_BUDGET))

    def test_maintenance_record_top_level_count_within_budget(self):
        directory = ROOT / '维护记录'
        count = len([p for p in directory.iterdir() if p.is_file()])
        self.assertLessEqual(count, MAINTENANCE_FILE_BUDGET,
                             '维护记录/ 顶层文件共 %d 个，超过 D10 预算 %d：历史件移入归档子目录' % (count, MAINTENANCE_FILE_BUDGET))


if __name__ == '__main__':
    unittest.main()

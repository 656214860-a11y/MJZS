"""规则文件体积预算：整读型规则文件超出加载窗口等于不存在（对应 C1）。

``程序/AGENTS.md`` 曾长到 31 KB，§5 自检与 §8 执行协议落在加载上限之后而无人察觉。

两类文档分开管（R3504）：

* ``BUDGETS`` 整读型 —— agent 开工时必须从头读完的规则文件，仍按 16 KB 加载窗口卡。
* ``REFERENCE_BUDGETS`` 按节查询型 —— 权威参考文档（如产品需求规格）。它们不可能在
  16 KB 内讲完一个产品的全部需求，切碎成子文档反而破坏权威性与可检索性；因此改为
  放宽体积上限，并要求开头有章节索引，使 agent 能先定位节再读，而不是整读或盲扫。
"""
from __future__ import annotations

import re
import subprocess
import unittest
from pathlib import Path

from tests.architecture._scan import ROOT

REPO = ROOT.parent
# 整读型：开工必读、正文即规则，超出 16 KB 的尾部对模型等于不存在。
BUDGETS = {
    ROOT / 'AGENTS.md': 16000,
    REPO / 'AGENTS.md': 2000,
    REPO / 'CLAUDE.md': 4000,
    # 工程文档体系任务书轮5（R3503）：agent 会整读的工程文档同样受 16 KB 加载窗口约束。
    ROOT / '文档导航.md': 16000,
    ROOT / '说明' / '工程文档登记表.md': 16000,
    ROOT / '说明' / '已知坑与不可破坏契约.md': 16000,
    ROOT / '维护记录' / 'README.md': 16000,
    ROOT / 'docs' / 'adr' / 'README.md': 16000,
}
# 按节查询型：权威参考文档。上限不按加载窗口卡，而按「单文件仍可检索」的体量卡；
# 必须带章节索引（INDEX_HEADING），且索引要出现在 INDEX_WINDOW 字节内。
REFERENCE_BUDGETS = {
    ROOT / '说明' / '产品需求规格.md': 96000,
}
INDEX_WINDOW = 8192
# 章节索引标题：`## 0. 章节索引` / `## 目录` / `## 索引` 等。
INDEX_HEADING = re.compile(
    r'^#{1,3}\s*(?:第?[0-9一二三四五六七八九十]+[.、]?\s*)?(?:章节索引|内容索引|目录|索引)\s*$',
    re.M)
# D10 总量预算：程序/ 根 .md 与 维护记录/ 顶层文件只减不增的上限。
ROOT_MD_BUDGET = 18
MAINTENANCE_FILE_BUDGET = 60
LINK = re.compile(r'\[[^\]]*\]\(([^)#\s]+)(?:#[^)]*)?\)')
MUST_FIT = ('## 5. 自检规则', '## 8. 任务执行协议', '## 2.6 Git 提交门禁')
LIMIT = 16384


def tracked_files():
    """git ls-files 口径的跟踪文件集（相对 ROOT）；git 不可用时退回文件系统枚举。

    运行时落盘的 gitignored 状态文件（如 维护记录/基准历史.json）不计入 D10 预算——
    预算约束的是入库文件的膨胀，不是工作区里的运行时产物。"""
    try:
        out = subprocess.run(['git', 'ls-files', '-z'], cwd=ROOT,
                             capture_output=True, timeout=30)
        if out.returncode == 0:
            return [p for p in out.stdout.decode('utf-8').split('\0') if p]
    except (OSError, subprocess.SubprocessError):
        pass
    return [str(p.relative_to(ROOT)).replace('\\', '/')
            for p in ROOT.rglob('*') if p.is_file()]


def oversize(size, budget):
    return max(0, size - budget)


def broken_links(path: Path):
    text = path.read_text(encoding='utf-8')
    return [target for target in LINK.findall(text)
            if '://' not in target and not (path.parent / target).exists()]


def missing_index(text, window=INDEX_WINDOW):
    """按节查询型文档必须在窗口内给出章节索引；返回 True 表示缺失。

    索引落在窗口之后等于没有：模型先读到的是正文而非导航。"""
    return INDEX_HEADING.search(text[:window]) is None


class AgentDocBudgetTests(unittest.TestCase):
    def test_overflow_arithmetic(self):
        self.assertEqual(oversize(100, 100), 0)
        self.assertEqual(oversize(130, 100), 30)

    def test_entry_files_stay_within_budget(self):
        for path, budget in BUDGETS.items():
            size = len(path.read_bytes())
            self.assertEqual(oversize(size, budget), 0,
                             '%s 为 %d 字节，超过预算 %d：先删旧规则，细则写进 runbook.md' % (path.name, size, budget))

    def test_reference_documents_stay_within_budget(self):
        for path, budget in REFERENCE_BUDGETS.items():
            size = len(path.read_bytes())
            self.assertEqual(oversize(size, budget), 0,
                             '%s 为 %d 字节，超过参考文档预算 %d：拆分为同目录子文档并在索引登记，'
                             '或删去已失效的历史段落' % (path.name, size, budget))

    def test_reference_documents_declare_section_index(self):
        for path in REFERENCE_BUDGETS:
            text = path.read_text(encoding='utf-8')
            self.assertFalse(missing_index(text),
                             '%s 缺少章节索引：按节查询型文档必须在正文前 %d 字节内给出'
                             '「## 0. 章节索引」或等价的目录标题，否则模型只能整读或盲扫' % (path.name, INDEX_WINDOW))

    def test_missing_index_detects_both_samples(self):
        """负向自测：索引缺失／落在窗口之后都要被检出，断言不恒真。"""
        index = '## 0. 章节索引\n\n| 节 | 标题 |\n|---|---|\n'
        self.assertFalse(missing_index(index + '正文' * 100))
        self.assertTrue(missing_index('正文' * 4000))
        self.assertTrue(missing_index('正文' * 4000 + index))

    def test_critical_sections_begin_inside_the_loaded_prefix(self):
        data = (ROOT / 'AGENTS.md').read_bytes()
        for heading in MUST_FIT:
            position = data.find(heading.encode('utf-8'))
            self.assertGreaterEqual(position, 0, '缺少 %s' % heading)
            self.assertLess(position, LIMIT, '%s 落在加载上限 %d 字节之后' % (heading, LIMIT))

    def test_relative_links_point_at_existing_files(self):
        for path in list(BUDGETS) + list(REFERENCE_BUDGETS):
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
            self.assertEqual(oversize(1000, 96000), 0, '参考文档档不应把 1 KB 文档判为超预算')

    def test_program_root_markdown_count_within_budget(self):
        count = len([p for p in tracked_files()
                     if '/' not in p and p.endswith('.md')])
        self.assertLessEqual(count, ROOT_MD_BUDGET,
                             '程序/ 根 .md 共 %d 份，超过 D10 预算 %d：新文档进子目录或说明/' % (count, ROOT_MD_BUDGET))

    def test_maintenance_record_top_level_count_within_budget(self):
        count = len([p for p in tracked_files()
                     if p.startswith('维护记录/') and p.count('/') == 1])
        self.assertLessEqual(count, MAINTENANCE_FILE_BUDGET,
                             '维护记录/ 顶层跟踪文件共 %d 个，超过 D10 预算 %d：历史件移入归档子目录' % (count, MAINTENANCE_FILE_BUDGET))


if __name__ == '__main__':
    unittest.main()
